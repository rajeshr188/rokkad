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
from apps.tenant_apps.loans.services.pawn_economics import (
    resolve_pawn_draft_economics,
)


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
        if not item.photos.exists():
            raise PawnLifecycleError(
                f"Collateral {item.description} requires at least one photograph before approval."
            )
    resolved_economics = _validate_collateral_economics(loan, collateral)

    payload = _approval_payload(loan, collateral, resolved_economics)
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
        "license_revision_id": loan.license_revision_id,
        "series_id": loan.series_id,
        "loan_number": loan.loan_number,
    }
    loan.license = license
    loan.license_revision = license.revisions.order_by("-revision_number").first()
    loan.series = series
    loan.loan_number = allocation.value
    loan.updated_by = actor
    loan.full_clean()
    loan.save(
        update_fields=[
            "license",
            "license_revision",
            "series",
            "loan_number",
            "updated_by",
            "updated_at",
        ]
    )
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.LICENSE_TRANSFERRED.value,
        from_state=PawnLoanState.DRAFT.value,
        to_state=PawnLoanState.DRAFT.value,
        reason=reason.strip(),
        actor=actor,
        metadata={
            "before": old,
            "after": {
                "license_id": license.pk,
                "license_revision_id": loan.license_revision_id,
                "series_id": series.pk,
                "loan_number": allocation.value,
            },
        },
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


def _validate_collateral_economics(loan, collateral):
    allocations = [item.allocated_principal for item in collateral]
    if not any(value is not None for value in allocations):
        return None
    if any(value is None for value in allocations):
        raise PawnLifecycleError(
            "Every collateral item requires an allocated principal before approval."
        )
    resolved = resolve_pawn_draft_economics(
        workspace_id=loan.workspace_id,
        license_id=loan.license_id,
        as_of_date=loan.loan_date,
        collateral=collateral,
    )
    if resolved.economics.gross_principal != loan.principal_amount:
        raise PawnLifecycleError(
            "Collateral allocations no longer reconcile to the loan principal; resave the draft."
        )
    if resolved.economics.effective_monthly_rate != loan.monthly_interest_rate:
        raise PawnLifecycleError(
            "Resolved collateral rates changed; resave the draft before approval."
        )
    for item, tranche, rate_policy in zip(
        collateral,
        resolved.economics.tranches,
        resolved.rate_policies,
        strict=True,
    ):
        if (
            item.monthly_interest_rate != tranche.monthly_interest_rate
            or item.interest_rate_policy_id != rate_policy.pk
        ):
            raise PawnLifecycleError(
                "Resolved collateral rates changed; resave the draft before approval."
            )
    return resolved


def _approval_payload(loan, collateral, resolved_economics=None):
    payload = {
        "loan_id": loan.pk,
        "loan_number": loan.loan_number,
        "workspace_id": loan.workspace_id,
        "borrower_id": loan.borrower_id,
        "license_id": loan.license_id,
        "license_revision_id": loan.license_revision_id,
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
                "allocated_principal": (
                    str(item.allocated_principal)
                    if item.allocated_principal is not None
                    else None
                ),
                "monthly_interest_rate": (
                    str(item.monthly_interest_rate)
                    if item.monthly_interest_rate is not None
                    else None
                ),
                "interest_rate_policy_id": item.interest_rate_policy_id,
                "photo_evidence": [
                    {
                        "photo_id": photo.pk,
                        "sha256": photo.sha256,
                        "workflow_source": photo.workflow_source,
                        "captured_at": photo.captured_at.isoformat(),
                    }
                    for photo in item.photos.all()
                ],
            }
            for item in collateral
        ],
    }
    if resolved_economics is not None:
        economics = resolved_economics.economics
        payload["collateral_economics"] = {
            "economic_policy_id": resolved_economics.economic_policy.pk,
            "valuation_method": resolved_economics.economic_policy.valuation_method,
            "maximum_ltv_ratio": str(
                resolved_economics.economic_policy.maximum_ltv_ratio
            ),
            "advance_interest_periods": (
                resolved_economics.economic_policy.advance_interest_periods
            ),
            "monthly_interest": str(economics.monthly_interest),
            "advance_interest": str(economics.advance_interest),
            "deducted_fees": str(economics.deducted_fees),
            "net_disbursed": str(economics.net_disbursed),
            "tranches": [
                {
                    "collateral_item_id": item.pk,
                    "interest_rate_policy_id": rate_policy.pk,
                    "metal": tranche.metal.value,
                    "allocated_principal": str(tranche.allocated_principal),
                    "monthly_interest_rate": str(tranche.monthly_interest_rate),
                    "calculated_metal_value": (
                        str(tranche.calculated_metal_value)
                        if tranche.calculated_metal_value is not None
                        else None
                    ),
                    "latest_appraised_value": (
                        str(tranche.latest_appraised_value)
                        if tranche.latest_appraised_value is not None
                        else None
                    ),
                    "selected_value": str(tranche.selected_value),
                    "maximum_principal": str(tranche.maximum_principal),
                    "monthly_interest": str(tranche.monthly_interest),
                    "advance_interest": str(tranche.advance_interest),
                }
                for item, tranche, rate_policy in zip(
                    collateral,
                    economics.tranches,
                    resolved_economics.rate_policies,
                    strict=True,
                )
            ],
            "fees": [
                {
                    "fee_policy_id": fee_policy.pk,
                    "code": fee.code,
                    "name": fee.name,
                    "calculation_type": fee_policy.calculation_type,
                    "policy_value": str(fee_policy.value),
                    "amount": str(fee.amount),
                    "deducted_at_disbursal": fee.deducted_at_disbursal,
                }
                for fee, fee_policy in zip(
                    economics.fees,
                    resolved_economics.fee_policies,
                    strict=True,
                )
            ],
        }
    return payload
