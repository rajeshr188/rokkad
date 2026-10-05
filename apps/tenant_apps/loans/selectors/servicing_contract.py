"""Read-only selection of frozen servicing semantics; never recognizes interest."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans.models import current_tenant_workspace_id
from .balances import PawnLoanBalance, get_pawn_loan_balance
from .transaction_completeness import TransactionCompleteness, transaction_completeness


class ServicingContractError(ValueError):
    pass


@dataclass(frozen=True)
class ServicingContract:
    origin_event_id: int | None
    origin_kind: str | None
    profile: str
    original_date: date
    financial_history_from: date
    policy_snapshot_id: int | None
    interest_method: str | None
    partial_month_method: str | None
    currency_quantum: Decimal | None
    rounding_scope: str | None
    rounding_mode: str
    anniversary_rule: str
    principal_reduction_rule: str
    recognized_interest_at_cutover: Decimal | None = None
    unpaid_interest_at_cutover: Decimal | None = None


@dataclass(frozen=True)
class ServicingPosition:
    contract: ServicingContract
    balance: PawnLoanBalance
    balance_basis: str
    transaction_coverage: TransactionCompleteness | None


def resolve_servicing_contract(loan, *, as_of_date):
    """Inspect saved facts once, keeping provenance separate from the calculator.

    Native event folds also support older unitemized loans without snapshots.
    Missing policy fields remain unknown; they do not acquire invented terms.
    This read contract does not grant posting eligibility or certify coverage.
    """
    if current_tenant_workspace_id() is None or loan.workspace_id != current_tenant_workspace_id():
        raise ServicingContractError("Servicing requires the loan's active Workspace context.")
    if type(as_of_date) is not date or as_of_date < loan.loan_date:
        raise ServicingContractError("Servicing history before the original loan date is unavailable.")
    events = tuple(loan.loan_events.all())
    openings = [event for event in events if event.event_kind == "MIGRATION_OPENING"]
    originals = [event for event in events if event.event_kind in {"DISBURSAL", "RENEWAL_OPENING"}]
    reversed_ids = {event.reversal_of_id for event in events if event.reversal_of_id}
    active_originals = [event for event in originals if event.pk not in reversed_ids]
    if len(openings) > 1 or (openings and originals) or len(active_originals) > 1:
        raise ServicingContractError("Servicing requires exactly one supported financial origin.")
    policy = loan.policy_snapshot if loan.policy_snapshot_id else None
    common = dict(original_date=loan.loan_date, policy_snapshot_id=loan.policy_snapshot_id,
                  interest_method=getattr(policy, "interest_method", None),
                  partial_month_method=getattr(policy, "partial_month_method", None))
    if openings:
        from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
        from apps.tenant_apps.loans.services.opening_validation import COLLECTION_PROFILE
        origin = openings[0]
        review = read_opening_evidence(loan, origin)["review"]
        if as_of_date < origin.effective_date:
            raise ServicingContractError("Servicing history before the migration cutover is unavailable.")
        if review["profile"] != COLLECTION_PROFILE:
            raise ServicingContractError("This opening has no supported collection continuation checkpoint.")
        if policy and policy.basis == "RECORDED_CONTRACT":
            raise ServicingContractError("Opening and recorded-disbursal contract evidence conflict.")
        terms = review["terms"]
        return ServicingContract(**common, origin_event_id=origin.pk, origin_kind=origin.event_kind,
            profile=terms["rule_id"], financial_history_from=origin.effective_date,
            currency_quantum=Decimal(terms["interest_quantum"]), rounding_scope=terms["rounding_scope"],
            rounding_mode=terms["rounding_mode"], anniversary_rule="DAY_AFTER_ORIGINAL_ANNIVERSARY",
            principal_reduction_rule="NEXT_ANNIVERSARY_COLLECTION_BOUNDARY",
            recognized_interest_at_cutover=Decimal(review["continuation"]["recognized_interest"]),
            unpaid_interest_at_cutover=Decimal(review["balances"]["interest"]))
    origin = active_originals[0] if active_originals else None
    if origin is None and loan.state in {"ACTIVE", "CLOSED"}:
        raise ServicingContractError("This operational loan has no supported financial origin.")
    if policy and policy.basis == "RECORDED_CONTRACT":
        recording = origin.payload.get("recording", {}) if origin else {}
        if not isinstance(recording, dict):
            raise ServicingContractError("This recorded contract has malformed collection evidence.")
        profile = recording.get("collection_profile")
        if profile not in {"recorded-anniversary/1", "recorded-anniversary/2"}:
            raise ServicingContractError("This recorded contract has no supported collection profile.")
        return ServicingContract(**common, origin_event_id=origin.pk, origin_kind=origin.event_kind,
            profile=profile, financial_history_from=loan.loan_date, currency_quantum=Decimal("0.01"),
            rounding_scope="PER_ITEM_PER_ANNIVERSARY" if profile.endswith("/2") else "PER_ANNIVERSARY",
            rounding_mode="HALF_UP", anniversary_rule="ON_ORIGINAL_ANNIVERSARY",
            principal_reduction_rule="FOLLOWING_ANNIVERSARY_EXCLUDING_SAME_DAY_PAYMENT")
    if origin and origin.payload.get("recording", {}).get("collection_profile"):
        raise ServicingContractError("Recorded collection evidence requires its frozen recorded policy.")
    return ServicingContract(**common, origin_event_id=origin.pk if origin else None,
        origin_kind=origin.event_kind if origin else None, profile="native-event-fold/1",
        financial_history_from=loan.loan_date, currency_quantum=getattr(policy, "currency_quantum", None),
        rounding_scope=getattr(policy, "rounding_method", None), rounding_mode="HALF_UP",
        anniversary_rule="FROZEN_NATIVE_PERIODS", principal_reduction_rule="FROZEN_NATIVE_CONTRACT")


def get_servicing_position(loan, *, as_of_date, operation="REPAYMENT", include_coverage=False):
    """Return the existing operation's balance, not a projected exposure.

    Closed opening reminders use only the recorded fold, as before. Active opening
    quotes retain dedicated after-cutover/chronology/schedule validation. Coverage
    is optional metadata so ordinary amount reads do not perform a new book review.
    """
    if operation not in {"REPAYMENT", "NOTICE"}:
        raise ServicingContractError("Unsupported servicing position operation.")
    contract = resolve_servicing_contract(loan, as_of_date=as_of_date)
    basis = "RECORDED_DEBT"
    if contract.origin_kind == "MIGRATION_OPENING" and (operation == "REPAYMENT" or loan.state == "ACTIVE"):
        from apps.tenant_apps.loans.services.opening_servicing import opening_payment_balance
        balance, _ = opening_payment_balance(loan, as_of_date=as_of_date)
        basis = "COLLECTION_WITH_UNPOSTED_INTEREST"
    elif contract.profile in {"recorded-anniversary/1", "recorded-anniversary/2"}:
        from apps.tenant_apps.loans.services.recorded_collections import collection_balance
        balance = collection_balance(loan, as_of_date)
        basis = "COLLECTION_WITH_UNPOSTED_INTEREST"
    else:
        balance = get_pawn_loan_balance(loan, as_of_date=as_of_date)
    coverage = transaction_completeness(loan, as_of_date) if include_coverage else None
    return ServicingPosition(contract, balance, basis, coverage)
