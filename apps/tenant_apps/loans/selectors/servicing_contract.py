"""Read-only selection of frozen servicing semantics; never recognizes interest."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans.models import current_tenant_workspace_id
from .balances import PawnLoanBalance
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
    checkpoint_period_number: int | None = None
    checkpoint_item_bases: tuple[tuple[int, Decimal], ...] = ()
    checkpoint_current_recognized_interest: Decimal | None = None
    checkpoint_current_unpaid_interest: Decimal | None = None
    checkpoint_advance_coverage: tuple[tuple[int, Decimal], ...] = ()
    checkpoint_next_increase_on: date | None = None


@dataclass(frozen=True)
class ServicingPosition:
    contract: ServicingContract
    balance: PawnLoanBalance
    balance_basis: str
    transaction_coverage: TransactionCompleteness | None
    continuation: object | None = None


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
    if policy and policy.policy_version not in (1, 2):
        raise ServicingContractError("This loan has an unsupported frozen interest policy version.")
    common = dict(original_date=loan.loan_date, policy_snapshot_id=loan.policy_snapshot_id,
                  interest_method=getattr(policy, "interest_method", None),
                  partial_month_method=getattr(policy, "partial_month_method", None))
    if openings:
        from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
        from apps.tenant_apps.loans.services.opening_validation import COLLECTION_PROFILES, POLICY_COLLECTION_PROFILES
        origin = openings[0]
        opening = read_opening_evidence(loan, origin)
        review = opening["review"]
        if as_of_date < origin.effective_date:
            raise ServicingContractError("Servicing history before the migration cutover is unavailable.")
        if opening["profile"] == "loan-terminal-evidence/1":
            if len(events) != 1 or policy is None or policy.basis != "RECORDED_CONTRACT" or policy.policy_version != 2:
                raise ServicingContractError("Terminal position requires its sole checkpoint and frozen recorded agreement.")
            return ServicingContract(**common, origin_event_id=origin.pk, origin_kind=origin.event_kind,
                profile="loan-terminal-position/1", financial_history_from=origin.effective_date,
                currency_quantum=policy.currency_quantum, rounding_scope="PER_ITEM_PER_ANNIVERSARY",
                rounding_mode="HALF_UP", anniversary_rule="DAY_AFTER_ORIGINAL_ANNIVERSARY",
                principal_reduction_rule="EARLIER_TRANSACTIONS_UNAVAILABLE")
        if review["profile"] not in COLLECTION_PROFILES:
            raise ServicingContractError("This opening has no supported collection continuation checkpoint.")
        if policy and policy.basis == "RECORDED_CONTRACT":
            raise ServicingContractError("Opening and recorded-disbursal contract evidence conflict.")
        terms = review["terms"]
        if review["profile"] in POLICY_COLLECTION_PROFILES and (
            policy is None or policy.policy_version != 2 or policy.interest_method != "SIMPLE"
            or policy.partial_month_method != "FULL_MONTH"
            or policy.currency_quantum.normalize() != Decimal(terms["interest_quantum"])):
            raise ServicingContractError("The reviewed opening must match its captured shared monthly policy.")
        checkpoint = {}
        if review["profile"] in ("loan-opening-review/4", "loan-opening-review/5"):
            carry = review["continuation"]
            checkpoint = dict(checkpoint_period_number=carry["period_number"],
                checkpoint_item_bases=tuple((opening["item_mapping"][row["item_id"]], Decimal(row["principal_base"])) for row in carry["bases"]),
                checkpoint_current_recognized_interest=Decimal(carry["current_period_recognized_interest"]),
                checkpoint_current_unpaid_interest=Decimal(carry["current_period_unpaid_interest"]),
                checkpoint_advance_coverage=tuple((row["period_number"], Decimal(row["interest"])) for row in carry["advance_coverage"]),
                checkpoint_next_increase_on=date.fromisoformat(carry["next_increase_on"]))
        return ServicingContract(**common, **checkpoint, origin_event_id=origin.pk, origin_kind=origin.event_kind,
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
        if profile is None and policy.policy_version == 1 and origin:
            # Early recorded snapshots support the existing event fold, without
            # implying an anniversary agreement or granting paper continuation.
            return ServicingContract(**common, origin_event_id=origin.pk, origin_kind=origin.event_kind,
                profile="recorded-event-fold/1", financial_history_from=loan.loan_date,
                currency_quantum=policy.currency_quantum, rounding_scope=policy.rounding_method,
                rounding_mode="HALF_UP", anniversary_rule="FROZEN_RECORDED_PERIODS",
                principal_reduction_rule="FROZEN_RECORDED_CONTRACT")
        if profile == "recorded-anniversary/3" and (policy.policy_version != 2 or policy.currency_quantum.normalize() not in (Decimal("0.01"), Decimal("1"))):
            raise ServicingContractError("The shared monthly contract requires its captured supported economic policy.")
        if profile not in {"recorded-anniversary/1", "recorded-anniversary/2", "recorded-anniversary/3"}:
            raise ServicingContractError("This recorded contract has no supported collection profile.")
        return ServicingContract(**common, origin_event_id=origin.pk, origin_kind=origin.event_kind,
            profile=profile, financial_history_from=loan.loan_date, currency_quantum=policy.currency_quantum.normalize() if profile.endswith("/3") else Decimal("0.01"),
            rounding_scope="PER_ITEM_PER_ANNIVERSARY" if profile.endswith(("/2", "/3")) else "PER_ANNIVERSARY",
            rounding_mode="HALF_UP", anniversary_rule="DAY_AFTER_ORIGINAL_ANNIVERSARY" if profile.endswith("/3") else "ON_ORIGINAL_ANNIVERSARY",
            principal_reduction_rule="NEXT_ANNIVERSARY_COLLECTION_BOUNDARY" if profile.endswith("/3") else "FOLLOWING_ANNIVERSARY_EXCLUDING_SAME_DAY_PAYMENT")
    if origin and origin.payload.get("recording", {}).get("collection_profile"):
        raise ServicingContractError("Recorded collection evidence requires its frozen recorded policy.")
    return ServicingContract(**common, origin_event_id=origin.pk if origin else None,
        origin_kind=origin.event_kind if origin else None, profile="native-monthly-policy/2" if policy and policy.policy_version == 2 else "native-event-fold/1",
        financial_history_from=loan.loan_date, currency_quantum=getattr(policy, "currency_quantum", None),
        rounding_scope=getattr(policy, "rounding_method", None), rounding_mode="HALF_UP",
        anniversary_rule="DAY_AFTER_ORIGINAL_ANNIVERSARY" if policy and policy.policy_version == 2 else "FROZEN_NATIVE_PERIODS", principal_reduction_rule="FROZEN_NATIVE_CONTRACT")


def get_servicing_position(loan, *, as_of_date, operation="REPAYMENT", include_coverage=False):
    """Return supported collection debt, including eligible monthly charges.

    Closed opening reminders use only the recorded fold, as before. Active opening
    quotes retain dedicated after-cutover/chronology/schedule validation. Coverage
    is optional metadata so ordinary amount reads do not perform a new book review.
    """
    if operation not in {"REPAYMENT", "NOTICE"}:
        raise ServicingContractError("Unsupported servicing position operation.")
    from .continuation import resolve_loan_continuation
    continuation = resolve_loan_continuation(loan, as_of_date=as_of_date)
    contract = continuation.contract
    basis = "RECORDED_DEBT"
    if contract.profile == "loan-terminal-position/1":
        return ServicingPosition(contract, continuation.recorded_balance, "VERIFIED_TERMINAL_POSITION",
            transaction_completeness(loan, as_of_date) if include_coverage else None, continuation)
    if (contract.checkpoint_period_number is not None and as_of_date == contract.financial_history_from):
        # The verified checkpoint itself has no post-cutover catch-up. This is
        # a read, not authorization to insert an action on the cutover day.
        balance = continuation.recorded_balance
    elif contract.origin_kind == "MIGRATION_OPENING" and (operation == "REPAYMENT" or loan.state == "ACTIVE"):
        from apps.tenant_apps.loans.services.opening_servicing import opening_release_context
        opening_release_context(loan, as_of_date=as_of_date)
        balance = continuation.collection_balance
        basis = "COLLECTION_WITH_UNPOSTED_INTEREST"
    elif contract.origin_kind == "MIGRATION_OPENING":
        balance = continuation.recorded_balance
    elif contract.profile in {"recorded-anniversary/1", "recorded-anniversary/2", "recorded-anniversary/3"}:
        balance = continuation.collection_balance
        basis = "COLLECTION_WITH_UNPOSTED_INTEREST"
    else:
        balance = continuation.collection_balance
        if continuation.recognition.collection_eligible:
            basis = "COLLECTION_WITH_UNPOSTED_INTEREST"
    coverage = transaction_completeness(loan, as_of_date) if include_coverage else None
    return ServicingPosition(contract, balance, basis, coverage, continuation)
