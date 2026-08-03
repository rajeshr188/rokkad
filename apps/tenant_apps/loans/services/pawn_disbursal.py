"""Atomic PawnLoan disbursal source-event workflow."""

from dataclasses import dataclass
from datetime import date

from django.db import transaction

from apps.tenant_apps.loans.domain import (
    LoanOutboxStatus,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
    resolve_policy,
)
from apps.tenant_apps.loans.integrations import disbursal_payload
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanPolicySnapshot,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.accounting_outbox import (
    DeliveryHandler,
    record_loan_accounting_event,
)
from apps.tenant_apps.loans.services.accounting_readiness import (
    require_pawn_loan_accounting_readiness,
)
from apps.tenant_apps.loans.services.license_series import assert_series_can_issue


class PawnDisbursalError(ValueError):
    """Raised when a PawnLoan cannot be safely disbursed."""


@dataclass(frozen=True)
class PawnDisbursalResult:
    loan: PawnLoan
    policy_snapshot: LoanPolicySnapshot
    accounting_event: PawnLoanAccountingEvent
    outbox: PawnLoanAccountingOutbox
    already_disbursed: bool = False


@transaction.atomic
def disburse_pawn_loan(
    loan_id: int,
    *,
    effective_date: date,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnDisbursalResult:
    """Activate an approved loan and enqueue its once-only disbursal intent.

    The outer transaction makes the state change, immutable policy snapshot,
    source accounting event, outbox row, and audit row all-or-nothing.  Actual
    voucher/journal creation remains in DEA and is attempted after commit by
    the outbox delivery seam.
    """
    loan = _locked_loan(loan_id)
    if loan.state == PawnLoanState.ACTIVE.value:
        return _existing_disbursal_result(loan)
    if loan.state != PawnLoanState.APPROVED.value:
        raise PawnDisbursalError("Only an approved PawnLoan can be disbursed.")

    try:
        assert_series_can_issue(loan.series, as_of_date=effective_date)
        require_pawn_loan_accounting_readiness(loan, effective_date=effective_date)
    except Exception as exc:
        if isinstance(exc, PawnDisbursalError):
            raise
        raise PawnDisbursalError(str(exc)) from exc

    policy_snapshot = _persist_policy_snapshot(loan)
    payload = disbursal_payload(
        loan,
        effective_date=effective_date,
        principal_amount=loan.principal_amount,
    ).to_dict()
    event, outbox = record_loan_accounting_event(
        loan.pk,
        event_kind=TransactionKind.DISBURSAL,
        effective_date=effective_date,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    previous_state = loan.state
    loan.state = PawnLoanState.ACTIVE.value
    loan.updated_by = actor
    loan.save(update_fields=["state", "updated_by", "updated_at"])
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.DISBURSED.value,
        from_state=previous_state,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "effective_date": effective_date.isoformat(),
            "policy_snapshot_id": policy_snapshot.pk,
            "accounting_event_id": event.pk,
            "outbox_id": outbox.pk,
            "idempotency_key": outbox.idempotency_key,
        },
    )
    return PawnDisbursalResult(loan, policy_snapshot, event, outbox)


def assert_pawn_loan_financial_actions_allowed(loan_id: int) -> PawnLoan:
    """Block later repayment/release actions while any loan posting is unresolved."""
    loan = _locked_loan(loan_id)
    if loan.accounting_events.filter(
        outbox__status__in=(
            LoanOutboxStatus.PENDING.value,
            LoanOutboxStatus.PROCESSING.value,
            LoanOutboxStatus.FAILED.value,
        )
    ).exists():
        raise PawnDisbursalError(
            "PawnLoan financial actions are blocked until its accounting delivery succeeds."
        )
    return loan


def _locked_loan(loan_id: int) -> PawnLoan:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnDisbursalError("PawnLoan disbursal requires an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_for_update()
            .select_related("license", "series", "series__license", "borrower")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnDisbursalError("PawnLoan was not found in the active workspace.") from exc


def _persist_policy_snapshot(loan: PawnLoan) -> LoanPolicySnapshot:
    policy = resolve_policy().to_disbursal_snapshot()
    values = {
        "policy_version": policy.policy_version,
        "interest_method": policy.interest_method.value,
        "partial_month_method": policy.partial_month_method.value,
        "partial_month_cutoff_days": policy.partial_month_cutoff_days,
        "partial_month_lower_fraction": policy.partial_month_lower_fraction,
        "capitalization_interval_periods": policy.capitalization_interval_periods,
        "accounting_recognition": policy.accounting_recognition.value,
        "valuation_method": policy.valuation_method.value,
        "maximum_ltv_ratio": policy.maximum_ltv_ratio,
        "rounding_method": policy.rounding_method.value,
        "currency_quantum": policy.currency_quantum,
    }
    snapshot, created = LoanPolicySnapshot.objects.get_or_create(
        loan=loan,
        defaults=values,
    )
    if not created:
        raise PawnDisbursalError("PawnLoan already has a disbursal policy snapshot.")
    return snapshot


def _existing_disbursal_result(loan: PawnLoan) -> PawnDisbursalResult:
    try:
        event = loan.accounting_events.get(event_kind=TransactionKind.DISBURSAL.value)
        snapshot = loan.policy_snapshot
        return PawnDisbursalResult(
            loan=loan,
            policy_snapshot=snapshot,
            accounting_event=event,
            outbox=event.outbox,
            already_disbursed=True,
        )
    except (
        PawnLoanAccountingEvent.DoesNotExist,
        PawnLoanAccountingOutbox.DoesNotExist,
        LoanPolicySnapshot.DoesNotExist,
    ) as exc:
        raise PawnDisbursalError(
            "Active PawnLoan is missing its required disbursal accounting records."
        ) from exc
