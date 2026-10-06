"""Validated continuation reads; descriptive recognition plans never post debt."""
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from .balances import PawnLoanBalance, get_pawn_loan_balance
from .servicing_contract import ServicingContract, resolve_servicing_contract

ZERO = Decimal("0")
RECORDED_PROFILES = {"recorded-anniversary/1", "recorded-anniversary/2", "recorded-anniversary/3"}


@dataclass(frozen=True)
class InterestRecognitionPlan:
    # Existing writers must recompute under authority and aggregate lock. This
    # evidence retains their different persistence contracts, not a posting API.
    adapter: str
    additional_interest: Decimal
    collection_eligible: bool
    projection_periods: tuple
    calculation: object
    projection_rule: str


@dataclass(frozen=True)
class LoanContinuation:
    contract: ServicingContract
    as_of_date: date
    recorded_balance: PawnLoanBalance
    recognition: InterestRecognitionPlan
    forecast_through: date

    @property
    def collection_balance(self):
        if self.forecast_through != self.as_of_date:
            raise ValueError("A future forecast is not a current collection balance.")
        balance, plan = self.recorded_balance, self.recognition
        if not plan.collection_eligible:
            return balance
        extra = plan.additional_interest
        overdue = self.as_of_date > balance.due_date
        changes = dict(interest_outstanding=balance.interest_outstanding + extra,
            current_interest_outstanding=balance.current_interest_outstanding + (ZERO if overdue else extra),
            overdue_interest_outstanding=balance.overdue_interest_outstanding + (extra if overdue else ZERO),
            total_due=balance.total_due + extra)
        # Preserve the existing adapters' readiness meanings. Custody/release
        # eligibility is checked separately and is never implied by this amount.
        if plan.adapter == "RECORDED_CUMULATIVE":
            changes["financially_settled"] = balance.financially_settled and not extra
        elif plan.adapter == "NATIVE_PERIODS":
            changes["closure_ready"] = balance.closure_ready and extra == 0
        return replace(balance, **changes)


def resolve_loan_continuation(loan, *, as_of_date, include_legacy_projection=False, forecast_through=None):
    """Select frozen semantics once for collection previews and exposure reads.

    Opening calculation starts at the verified checkpoint, not original payout.
    Legacy daily exposure is a forecast only; it does not become collection debt.
    Operation-specific chronology/schedule checks remain with servicing callers.
    Coverage and valuation quality remain independent of supported arithmetic.
    """
    contract = resolve_servicing_contract(loan, as_of_date=as_of_date)
    horizon = as_of_date if forecast_through is None else forecast_through
    if type(horizon) is not date or horizon < as_of_date:
        raise ValueError("Forecast horizon must be on or after the reporting date.")
    balance = get_pawn_loan_balance(loan, as_of_date=as_of_date)
    periods, calculation, extra = (), None, ZERO
    eligible = False
    adapter = "RECORDED_ONLY"
    rule = "actual-outstanding-daily-v1"
    if contract.profile == "loan-terminal-position/1":
        adapter, eligible, rule = "VERIFIED_TERMINAL_POSITION", False, contract.profile
    elif contract.origin_kind == "MIGRATION_OPENING":
        from apps.tenant_apps.loans.services.opening_continuation import preview_opening_collection
        calculation = preview_opening_collection(loan, events=loan.loan_events.all(), as_of_date=horizon,
            known_through=as_of_date)
        extra = calculation.additional_interest
        if horizon > calculation.cutover_date:
            periods = ((calculation.cutover_date + timedelta(days=1), horizon, extra),)
        adapter, eligible, rule = "OPENING_CHECKPOINT", True, calculation.rule
    elif contract.profile in RECORDED_PROFILES:
        from apps.tenant_apps.loans.services.recorded_collections import collection_state
        calculation = collection_state(loan, horizon, known_through=as_of_date)
        extra = Decimal(calculation["additional"])
        periods = ((loan.loan_date, horizon, extra),) if extra else ()
        adapter, eligible, rule = "RECORDED_CUMULATIVE", True, contract.profile
    elif contract.profile == "native-monthly-policy/2":
        from apps.tenant_apps.loans.services.pawn_interest import preview_pawn_loan_accruals, started_month_charge_allowed
        rule = "original-anniversary-policy/1"
        if loan.state == "ACTIVE":
            calculation = preview_pawn_loan_accruals(loan.pk, as_of_date=horizon, known_through=as_of_date)
            periods = tuple((row.period_start, row.period_end, row.recognized_interest) for row in calculation)
            extra = sum((row[2] for row in periods), ZERO)
            adapter, eligible = "NATIVE_PERIODS", started_month_charge_allowed(loan.policy_snapshot)
    elif include_legacy_projection and loan.state == "ACTIVE":
        if horizon != as_of_date:
            raise ValueError("Legacy daily exposure does not support a future knowledge-capped forecast.")
        from .legacy_interest_projection import project_legacy_interest
        periods = project_legacy_interest(loan, as_of_date)
        extra = sum((row[2] for row in periods), ZERO)
        adapter = "LEGACY_EXPOSURE_ONLY"
    return LoanContinuation(contract, as_of_date, balance,
        InterestRecognitionPlan(adapter, extra, eligible, periods, calculation, rule), horizon)
