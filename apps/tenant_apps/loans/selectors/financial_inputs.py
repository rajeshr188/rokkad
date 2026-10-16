"""Supported, read-only financial inputs for one scoped loan/date calculation.

These are request-local source reads, not a balance cache or posting authority.
The frozen container retains ORM references; callers must not mutate them or
reuse the inputs after source changes. Atomic writers still recheck their sources.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans.models import (
    PawnLoan, RepaymentScheduleVersion, current_tenant_workspace_id,
)
from .balances import PawnLoanBalance, get_pawn_loan_balance
from .continuation import LoanContinuation, resolve_loan_continuation
from .obligation_state import (
    PawnLoanObligationState, calculate_obligation_state_as_of,
    get_active_repayment_schedule_as_of,
)
from .transaction_coverage import RecordedPositionCoverage


class PawnLoanFinancialReadError(ValueError):
    pass


@dataclass(frozen=True)
class PawnLoanObligationInputs:
    loan: PawnLoan
    as_of_date: date
    balance: PawnLoanBalance
    schedule: RepaymentScheduleVersion | None
    obligation_state: PawnLoanObligationState
    operational_grace_days: int

    def require(self, loan_id: int, as_of_date: date):
        workspace_id = current_tenant_workspace_id()
        if (workspace_id is None or self.loan.workspace_id != workspace_id
                or self.loan.pk != loan_id or type(as_of_date) is not date
                or self.as_of_date != as_of_date):
            raise PawnLoanFinancialReadError(
                "Prepared financial inputs must match the loan, date and active Workspace."
            )


@dataclass(frozen=True)
class PawnLoanFinancialInputs(PawnLoanObligationInputs):
    position: LoanContinuation
    transaction_coverage: RecordedPositionCoverage | None = None

    @property
    def is_closed_position(self) -> bool:
        return self.position.contract.profile == "loan-closed-position/1"

    @property
    def principal_history_basis(self) -> str:
        adapter = self.position.recognition.adapter
        if adapter == "VERIFIED_TERMINAL_POSITION":
            return "VERIFIED_TERMINAL_POSITION"
        return "OPENING_CHECKPOINT" if adapter == "OPENING_CHECKPOINT" else "ORIGINAL_PAYOUT"

    @property
    def original_principal(self) -> Decimal | None:
        basis = self.principal_history_basis
        if basis == "VERIFIED_TERMINAL_POSITION":
            return self.loan.principal_amount
        balance = self.position.recorded_balance
        return balance.opening_principal if basis == "OPENING_CHECKPOINT" else balance.principal_disbursed


def _scoped_loan(loan_id: int) -> PawnLoan:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanFinancialReadError("Financial reads require an active Workspace context.")
    try:
        return PawnLoan.objects.select_related(
            "product_version__product", "policy_snapshot"
        ).get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise PawnLoanFinancialReadError("PawnLoan was not found in the active workspace.") from exc


def _obligation_inputs(loan: PawnLoan, as_of_date: date, balance: PawnLoanBalance) -> PawnLoanObligationInputs:
    opening, origin = None, None
    if balance.financial_history_from is not None:
        from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
        origin = loan.loan_events.get(event_kind="MIGRATION_OPENING")
        opening = read_opening_evidence(loan, origin)
    closed_position = opening is not None and opening["profile"] in {
        "loan-closed-position-evidence/1", "loan-closed-position-evidence/2"}
    schedule = None if closed_position else get_active_repayment_schedule_as_of(loan, as_of_date)
    grace_days = 0 if closed_position else loan.product_version.operational_grace_days
    # Decode retained opening evidence here, never in risk/DPD consumers.
    if opening is not None and not closed_position:
        from apps.tenant_apps.loans.services.opening_corrections import opening_schedule_source
        if not balance.financially_settled and (
            schedule is None or schedule.source_event_id != opening_schedule_source(loan, origin)
        ):
            raise PawnLoanFinancialReadError(
                "Opening exposure requires remaining obligations linked to its migration opening."
            )
        grace_days = opening["review"]["terms"]["grace_days"]
    state = calculate_obligation_state_as_of(schedule, as_of_date)
    return PawnLoanObligationInputs(loan, as_of_date, balance, schedule, state, grace_days)


def get_pawn_loan_obligation_inputs(loan_id: int, *, as_of_date: date) -> PawnLoanObligationInputs:
    """Read recorded debt/obligations without requiring an interest projection.

    DPD needs supported recorded obligations, not a supported forecast calculator.
    This narrower capability preserves standalone delinquency's existing scope.
    """
    loan = _scoped_loan(loan_id)
    if type(as_of_date) is not date:
        raise PawnLoanFinancialReadError("Financial reads require a reporting date.")
    try:
        return _obligation_inputs(loan, as_of_date, get_pawn_loan_balance(loan, as_of_date=as_of_date))
    except ValueError as exc:
        raise PawnLoanFinancialReadError(str(exc)) from exc


def get_pawn_loan_financial_inputs(loan_id: int, *, as_of_date: date) -> PawnLoanFinancialInputs:
    """Resolve compatible history, recognition, obligations and grace once.

    Recorded debt and unrecognized exposure remain distinct in ``position``.
    Book coverage is optional metadata, never a prerequisite for calculating debt.
    Earlier-than-checkpoint history remains unavailable. No interest is posted.
    """
    loan = _scoped_loan(loan_id)
    try:
        position = resolve_loan_continuation(loan, as_of_date=as_of_date, include_legacy_projection=True)
        inputs = _obligation_inputs(loan, as_of_date, position.recorded_balance)
    except ValueError as exc:
        raise PawnLoanFinancialReadError(str(exc)) from exc
    return PawnLoanFinancialInputs(loan, as_of_date, inputs.balance, inputs.schedule,
        inputs.obligation_state, inputs.operational_grace_days, position)
