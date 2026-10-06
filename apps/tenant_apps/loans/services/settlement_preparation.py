"""Common settlement facts; action commands still own authority and posting."""
from dataclasses import dataclass, replace
from decimal import Decimal

from apps.tenant_apps.loans.selectors.continuation import LoanContinuation, resolve_loan_continuation

from .pawn_disbursal import assert_pawn_loan_financial_actions_allowed
from .pawn_interest import preview_pawn_loan_accruals, started_month_charge_allowed
from .servicing_eligibility import servicing_eligibility

ZERO = Decimal("0")
OPERATIONS = {"FULL_RELEASE": "releasing the loan", "RENEWAL": "renewal", "AUCTION": "auction completion"}


@dataclass(frozen=True)
class SettlementPreparation:
    continuation: LoanContinuation
    completed_period_accruals: tuple
    catch_up_accrual: object | None
    opening_obligations: object | None

    @property
    def recorded_collection(self):
        return self.continuation.recognition.adapter == "RECORDED_CUMULATIVE"

    @property
    def balance_before_catch_up(self):
        """Recorded cumulative deltas or completed native periods, no paired charge."""
        balance = self.continuation.recorded_balance
        extra = (self.continuation.recognition.additional_interest if self.recorded_collection else
            sum((row.recognized_interest for row in self.completed_period_accruals), ZERO))
        overdue = self.continuation.as_of_date > balance.due_date
        return replace(balance, interest_outstanding=balance.interest_outstanding + extra,
            current_interest_outstanding=balance.current_interest_outstanding + (ZERO if overdue else extra),
            overdue_interest_outstanding=balance.overdue_interest_outstanding + (extra if overdue else ZERO),
            total_due=balance.total_due + extra)


def prepare_loan_settlement(loan, *, operation, effective_date, lock=False, occurred_at=None):
    """Read current facts, retaining opening bounds and legacy period prerequisites.

    This does not certify collateral, authorize an action, or execute a supplied
    recognition plan. A writer must revalidate inside its own atomic aggregate lock.
    """
    if operation not in OPERATIONS:
        raise ValueError("Unsupported loan settlement operation.")
    servicing_eligibility(loan, operation=operation, purpose="CURRENT", effective_date=effective_date, occurred_at=occurred_at).require()
    return _settlement_facts(loan, operation=operation, effective_date=effective_date, lock=lock)


def _settlement_facts(loan, *, operation, effective_date, lock):
    """Recompute under the same command after derived recognition, without rechecking its book prefix."""
    continuation = resolve_loan_continuation(loan, as_of_date=effective_date)
    if continuation.contract.origin_kind == "MIGRATION_OPENING":
        from .opening_servicing import opening_release_context, _opening_accrual_from_collection
        collection, obligations = opening_release_context(loan, as_of_date=effective_date)
        partial = _opening_accrual_from_collection(loan, collection=collection, as_of_date=effective_date)
        return SettlementPreparation(continuation, (), partial, obligations)
    assert_pawn_loan_financial_actions_allowed(loan.pk, lock=lock)
    if continuation.recognition.adapter == "RECORDED_CUMULATIVE":
        return SettlementPreparation(continuation, (), None, None)
    periods = (continuation.recognition.calculation if continuation.recognition.adapter == "NATIVE_PERIODS" else
        preview_pawn_loan_accruals(loan.pk, as_of_date=effective_date))
    completed = tuple(row for row in periods if not row.is_partial)
    if completed and not started_month_charge_allowed(loan.policy_snapshot):
        raise ValueError("Finalize every completed interest period before " + OPERATIONS[operation] + ".")
    partial = periods[-1] if periods and periods[-1].is_partial else None
    return SettlementPreparation(continuation, completed, partial, None)


def _recognize_settlement_interest(loan, *, operation, effective_date, actor, request_key, occurred_at=None):
    """Internal: authorized atomic caller holds the loan lock; recompute, never execute a read plan.

    Completed monthly charges remain independently owed after a terminal action
    reversal. The action-specific writer owns its paired partial/opening catch-up.
    Recorded cumulative recognition retains its own event identity and correction
    guards. Opening recognition stays exclusively with the bounded opening writer.
    """
    preparation = prepare_loan_settlement(loan, operation=operation, effective_date=effective_date, lock=True, occurred_at=occurred_at)
    recognition = None
    if preparation.recorded_collection:
        from .recorded_collections import recognize_collection_interest
        recognition = recognize_collection_interest(loan, effective_date, actor=actor, request_key=request_key)
    elif preparation.continuation.contract.origin_kind != "MIGRATION_OPENING":
        from .pawn_interest import recognize_due_monthly_interest
        recognize_due_monthly_interest(loan, effective_date, actor=actor, include_partial=False)
    return _settlement_facts(loan, operation=operation, effective_date=effective_date, lock=True), recognition


def settlement_scheduled_interest(loan, *, effective_date, amount, opening_obligations=None):
    """Allocation capacity is the frozen schedule, not the dynamic debt forecast."""
    from .recorded_collections import recording_for, scheduled_interest
    from .servicing_eligibility import shared_monthly_bullet
    if loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
        if opening_obligations is None:
            from .opening_servicing import opening_release_context
            _, opening_obligations = opening_release_context(loan, as_of_date=effective_date)
        return min(amount, opening_obligations.remaining.interest)
    if recording_for(loan) or shared_monthly_bullet(loan):
        return scheduled_interest(loan, effective_date, amount)
    return amount
