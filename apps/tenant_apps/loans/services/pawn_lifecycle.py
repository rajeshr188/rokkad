from __future__ import annotations

import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from apps.tenant_apps.loans.domain import PawnLoanEventKind, PawnLoanState, can_transition
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanLicense,
    LoanSeries,
    PawnLoan,
    PawnLoanApprovalSnapshot,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.license_series import assert_series_can_issue
from apps.tenant_apps.loans.services.number_allocation import allocate_pawn_loan_number


class PawnLifecycleError(ValueError):
    """Raised when a PawnLoan lifecycle command is not allowed."""


@transaction.atomic
def approve_pawn_loan(loan_id: int, *, actor=None) -> PawnLoanApprovalSnapshot:
    loan = _locked_loan(loan_id)
    _require_transition(loan, PawnLoanState.APPROVED)
    assert_series_can_issue(loan.series)
    loan.full_clean()
    collateral = tuple(loan.collateral_items.all())
    if not collateral:
        raise PawnLifecycleError("A PawnLoan requires collateral before approval.")
    for item in collateral:
        item.full_clean()

    payload = _approval_payload(loan, collateral)
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    version = (
        PawnLoanApprovalSnapshot.objects.filter(loan=loan).aggregate(Max("version"))[
            "version__max"
        ]
        or 0
    ) + 1
    snapshot = PawnLoanApprovalSnapshot.objects.create(
        loan=loan,
        version=version,
        payload=payload,
        fingerprint=fingerprint,
        approved_by=actor,
    )
    _set_state(loan, PawnLoanState.APPROVED, actor)
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.APPROVED.value,
        from_state=PawnLoanState.DRAFT.value,
        to_state=PawnLoanState.APPROVED.value,
        actor=actor,
        metadata={
            "approval_snapshot_id": snapshot.pk,
            "approval_version": version,
            "fingerprint": fingerprint,
        },
    )
    return snapshot


@transaction.atomic
def reopen_pawn_loan(loan_id: int, *, reason: str, actor=None) -> PawnLoan:
    loan = _locked_loan(loan_id)
    _require_reason(reason)
    _require_transition(loan, PawnLoanState.DRAFT)
    previous = loan.state
    _set_state(loan, PawnLoanState.DRAFT, actor)
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.RETURNED_TO_DRAFT.value,
        from_state=previous,
        to_state=PawnLoanState.DRAFT.value,
        reason=reason.strip(),
        actor=actor,
    )
    return loan


@transaction.atomic
def cancel_pawn_loan(loan_id: int, *, reason: str, actor=None) -> PawnLoan:
    loan = _locked_loan(loan_id)
    _require_reason(reason)
    _require_transition(loan, PawnLoanState.CANCELLED)
    previous = loan.state
    _set_state(loan, PawnLoanState.CANCELLED, actor)
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.CANCELLED.value,
        from_state=previous,
        to_state=PawnLoanState.CANCELLED.value,
        reason=reason.strip(),
        actor=actor,
    )
    return loan


@transaction.atomic
def transfer_expired_draft_setup(
    loan_id: int,
    *,
    license_id: int,
    series_id: int,
    reason: str,
    actor=None,
) -> PawnLoan:
    loan = _locked_loan(loan_id)
    _require_reason(reason)
    if loan.state != PawnLoanState.DRAFT.value:
        raise PawnLifecycleError("Only a reopened draft can transfer license setup.")
    if loan.license.is_active and not loan.license.is_expired():
        raise PawnLifecycleError("License transfer is only allowed after the current license becomes unavailable.")
    try:
        license = LoanLicense.objects.get(pk=license_id, workspace_id=loan.workspace_id)
        series = LoanSeries.objects.select_related("license").get(pk=series_id, license=license)
    except (LoanLicense.DoesNotExist, LoanSeries.DoesNotExist) as exc:
        raise PawnLifecycleError("Replacement license and series must belong to this workspace.") from exc
    assert_series_can_issue(series)
    allocation = allocate_pawn_loan_number(series=series, actor=actor)
    old = {
        "license_id": loan.license_id,
        "series_id": loan.series_id,
        "loan_number": loan.loan_number,
    }
    loan.license = license
    loan.series = series
    loan.loan_number = allocation.value
    loan.updated_by = actor
    loan.full_clean()
    loan.save(update_fields=["license", "series", "loan_number", "updated_by", "updated_at"])
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.LICENSE_TRANSFERRED.value,
        from_state=PawnLoanState.DRAFT.value,
        to_state=PawnLoanState.DRAFT.value,
        reason=reason.strip(),
        actor=actor,
        metadata={"before": old, "after": {"license_id": license.pk, "series_id": series.pk, "loan_number": allocation.value}},
    )
    return loan


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLifecycleError("PawnLoan transitions require an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_for_update()
            .select_related("license", "series", "borrower")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnLifecycleError("PawnLoan was not found in the active workspace.") from exc


def _require_transition(loan, target):
    if not can_transition(loan.state, target):
        raise PawnLifecycleError(f"PawnLoan cannot transition from {loan.state} to {target.value}.")


def _require_reason(reason):
    if not reason or not reason.strip():
        raise PawnLifecycleError("A reason is required for this transition.")


def _set_state(loan, state, actor):
    loan.state = state.value
    loan.updated_by = actor
    loan.save(update_fields=["state", "updated_by", "updated_at"])


def _approval_payload(loan, collateral):
    return {
        "loan_id": loan.pk,
        "loan_number": loan.loan_number,
        "workspace_id": loan.workspace_id,
        "borrower_id": loan.borrower_id,
        "license_id": loan.license_id,
        "series_id": loan.series_id,
        "principal_amount": str(loan.principal_amount),
        "monthly_interest_rate": str(loan.monthly_interest_rate),
        "loan_date": loan.loan_date.isoformat(),
        "tenure_months": loan.tenure_months,
        "collateral": [
            {
                "item_id": item.pk,
                "description": item.description,
                "metal": item.metal,
                "gross_weight": str(item.gross_weight),
                "net_weight": str(item.net_weight),
                "purity_percentage": str(item.purity_percentage),
                "latest_appraised_value": str(item.latest_appraised_value) if item.latest_appraised_value is not None else None,
            }
            for item in collateral
        ],
    }
