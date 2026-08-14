"""FundingLoan vocabulary and collateral-pledge policy."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum

from .vocabulary import CollateralCustodyState, PawnLoanState


class FundingLoanState(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SETTLEMENT_PENDING = "SETTLEMENT_PENDING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

    def __str__(self):
        return self.value


ALLOWED_FUNDING_LOAN_TRANSITIONS = {
    FundingLoanState.DRAFT: frozenset(
        {FundingLoanState.ACTIVE, FundingLoanState.CANCELLED}
    ),
    FundingLoanState.ACTIVE: frozenset({FundingLoanState.SETTLEMENT_PENDING}),
    FundingLoanState.SETTLEMENT_PENDING: frozenset(
        {FundingLoanState.ACTIVE, FundingLoanState.CLOSED}
    ),
    FundingLoanState.CLOSED: frozenset(),
    FundingLoanState.CANCELLED: frozenset(),
}


def can_transition_funding_loan(source, target):
    try:
        source_state = FundingLoanState(source)
        target_state = FundingLoanState(target)
    except ValueError:
        return False
    return target_state in ALLOWED_FUNDING_LOAN_TRANSITIONS[source_state]


class FundingLoanPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class FundingLoanTerms:
    principal_amount: Decimal
    monthly_interest_rate: Decimal
    activated_on: date
    maturity_on: date
    maximum_funding_ltv_ratio: Decimal = Decimal("0.80")
    currency_quantum: Decimal = Decimal("0.01")

    def __post_init__(self):
        principal = _decimal(self.principal_amount, "Funding principal")
        rate = _decimal(self.monthly_interest_rate, "Monthly interest rate")
        maximum_ltv = _decimal(
            self.maximum_funding_ltv_ratio,
            "Maximum funding LTV ratio",
        )
        quantum = _decimal(self.currency_quantum, "Currency quantum")
        if principal <= 0:
            raise FundingLoanPolicyError("Funding principal must be positive.")
        if rate < 0:
            raise FundingLoanPolicyError(
                "Monthly interest rate cannot be negative."
            )
        if self.maturity_on < self.activated_on:
            raise FundingLoanPolicyError(
                "Funding maturity cannot precede activation."
            )
        if maximum_ltv <= 0 or maximum_ltv > 1:
            raise FundingLoanPolicyError(
                "Maximum funding LTV ratio must be greater than zero and at most one."
            )
        if quantum <= 0:
            raise FundingLoanPolicyError("Currency quantum must be positive.")
        object.__setattr__(self, "principal_amount", principal.quantize(quantum))
        object.__setattr__(self, "monthly_interest_rate", rate)
        object.__setattr__(self, "maximum_funding_ltv_ratio", maximum_ltv)
        object.__setattr__(self, "currency_quantum", quantum)


class FundingLoanEventKind(str, Enum):
    ACTIVATION = "ACTIVATION"
    INTEREST_ACCRUAL = "INTEREST_ACCRUAL"
    FEE_ASSESSMENT = "FEE_ASSESSMENT"
    REPAYMENT = "REPAYMENT"
    REVERSAL = "REVERSAL"


@dataclass(frozen=True)
class FundingLoanEvent:
    sequence: int
    kind: FundingLoanEventKind
    principal_amount: Decimal = Decimal("0")
    interest_amount: Decimal = Decimal("0")
    fee_amount: Decimal = Decimal("0")
    reversal_of_sequence: int | None = None


@dataclass(frozen=True)
class FundingLoanBalance:
    principal_outstanding: Decimal
    interest_outstanding: Decimal
    fees_outstanding: Decimal
    total_due: Decimal

    @property
    def financially_settled(self):
        return self.total_due == 0


@dataclass(frozen=True)
class FundingRepaymentAllocation:
    amount_paid: Decimal
    fees: Decimal
    interest: Decimal
    principal: Decimal


@dataclass(frozen=True)
class FundingClosureReadiness:
    financially_settled: bool
    collateral_returned: bool
    ready: bool
    blockers: tuple[str, ...]


def calculate_funding_loan_balance(
    events: tuple[FundingLoanEvent, ...],
    *,
    currency_quantum=Decimal("0.01"),
) -> FundingLoanBalance:
    quantum = _positive_quantum(currency_quantum)
    ordered = _validated_funding_events(events, quantum=quantum)
    totals = {"principal": Decimal("0"), "interest": Decimal("0"), "fees": Decimal("0")}
    originals = {}
    reversed_sequences = set()
    for event in ordered:
        if event.kind == FundingLoanEventKind.REVERSAL:
            original = originals[event.reversal_of_sequence]
            _apply_funding_event(totals, original, direction=-1)
            reversed_sequences.add(original.sequence)
        else:
            _apply_funding_event(totals, event, direction=1)
            originals[event.sequence] = event
        if any(value < 0 for value in totals.values()):
            raise FundingLoanPolicyError(
                "FundingLoan event history over-settles its balance."
            )
    principal = totals["principal"].quantize(quantum)
    interest = totals["interest"].quantize(quantum)
    fees = totals["fees"].quantize(quantum)
    return FundingLoanBalance(
        principal_outstanding=principal,
        interest_outstanding=interest,
        fees_outstanding=fees,
        total_due=principal + interest + fees,
    )


def allocate_funding_repayment(
    balance: FundingLoanBalance,
    amount,
) -> FundingRepaymentAllocation:
    payment = _decimal(amount, "Funding repayment")
    if payment <= 0:
        raise FundingLoanPolicyError("Funding repayment must be positive.")
    remaining = payment
    fees = min(remaining, balance.fees_outstanding)
    remaining -= fees
    interest = min(remaining, balance.interest_outstanding)
    remaining -= interest
    principal = min(remaining, balance.principal_outstanding)
    remaining -= principal
    if remaining:
        raise FundingLoanPolicyError(
            f"Funding repayment exceeds total due by {remaining}."
        )
    return FundingRepaymentAllocation(payment, fees, interest, principal)


def plan_funding_reversal(
    events: tuple[FundingLoanEvent, ...],
    *,
    original_sequence: int,
) -> FundingLoanEvent:
    ordered = _validated_funding_events(events, quantum=Decimal("0.01"))
    active_originals = []
    reversed_sequences = {
        event.reversal_of_sequence
        for event in ordered
        if event.kind == FundingLoanEventKind.REVERSAL
    }
    for event in ordered:
        if (
            event.kind != FundingLoanEventKind.REVERSAL
            and event.sequence not in reversed_sequences
        ):
            active_originals.append(event)
    if not active_originals or active_originals[-1].sequence != original_sequence:
        raise FundingLoanPolicyError(
            "Later FundingLoan events must be reversed first."
        )
    original = active_originals[-1]
    return FundingLoanEvent(
        sequence=ordered[-1].sequence + 1,
        kind=FundingLoanEventKind.REVERSAL,
        principal_amount=original.principal_amount,
        interest_amount=original.interest_amount,
        fee_amount=original.fee_amount,
        reversal_of_sequence=original.sequence,
    )


class FundingPledgePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class FundingCollateralCandidate:
    collateral_item_id: int
    pawn_loan_id: int
    pawn_loan_state: PawnLoanState
    custody_state: CollateralCustodyState
    active_funding_pledge_id: int | None = None
    collateral_value: Decimal | None = None


@dataclass(frozen=True)
class FundingCustodyTransition:
    collateral_item_id: int
    pawn_loan_id: int
    from_state: CollateralCustodyState
    to_state: CollateralCustodyState


@dataclass(frozen=True)
class FundingCustodyEvent:
    sequence: int
    collateral_item_id: int
    from_state: CollateralCustodyState
    to_state: CollateralCustodyState
    reversal_of_sequence: int | None = None


@dataclass(frozen=True)
class FundingPledgePlan:
    collateral_item_ids: tuple[int, ...]
    source_pawn_loan_ids: tuple[int, ...]
    custody_transitions: tuple[FundingCustodyTransition, ...]


def calculate_funding_interest(
    terms: FundingLoanTerms,
    *,
    principal_outstanding,
    periods: int,
) -> Decimal:
    principal = _decimal(principal_outstanding, "Funding principal outstanding")
    if principal < 0:
        raise FundingLoanPolicyError(
            "Funding principal outstanding cannot be negative."
        )
    if not isinstance(periods, int) or isinstance(periods, bool) or periods <= 0:
        raise FundingLoanPolicyError(
            "Funding interest periods must be a positive integer."
        )
    return (
        principal
        * terms.monthly_interest_rate
        / Decimal("100")
        * periods
    ).quantize(terms.currency_quantum)


def plan_funding_pledge(
    candidates: tuple[FundingCollateralCandidate, ...],
    *,
    terms: FundingLoanTerms | None = None,
) -> FundingPledgePlan:
    """Validate collateral selection and describe lender custody movements."""

    candidates = tuple(candidates)
    if not candidates:
        raise FundingPledgePolicyError(
            "A FundingLoan must pledge at least one collateral item."
        )

    item_ids = tuple(candidate.collateral_item_id for candidate in candidates)
    if len(item_ids) != len(set(item_ids)):
        raise FundingPledgePolicyError(
            "A collateral item cannot appear more than once in a funding pledge."
        )

    transitions = []
    for candidate in candidates:
        if candidate.pawn_loan_state != PawnLoanState.ACTIVE:
            raise FundingPledgePolicyError(
                "Funding collateral must belong to an active PawnLoan."
            )
        if candidate.active_funding_pledge_id is not None:
            raise FundingPledgePolicyError(
                "Collateral already assigned to an active FundingLoan cannot be pledged again."
            )
        if candidate.custody_state != CollateralCustodyState.IN_VAULT:
            raise FundingPledgePolicyError(
                "Funding collateral must be in the branch vault before lender handoff."
            )
        transitions.append(
            FundingCustodyTransition(
                collateral_item_id=candidate.collateral_item_id,
                pawn_loan_id=candidate.pawn_loan_id,
                from_state=CollateralCustodyState.IN_VAULT,
                to_state=CollateralCustodyState.WITH_FUNDING_LENDER,
            )
        )

    if terms is not None:
        values = tuple(
            _positive_collateral_value(candidate) for candidate in candidates
        )
        maximum_principal = sum(values, Decimal("0")) * terms.maximum_funding_ltv_ratio
        if terms.principal_amount > maximum_principal:
            raise FundingPledgePolicyError(
                "Funding principal exceeds the configured collateral LTV limit."
            )

    return FundingPledgePlan(
        collateral_item_ids=item_ids,
        source_pawn_loan_ids=tuple(
            dict.fromkeys(candidate.pawn_loan_id for candidate in candidates)
        ),
        custody_transitions=tuple(transitions),
    )


def plan_funding_return(
    candidates: tuple[FundingCollateralCandidate, ...],
    *,
    funding_loan_state: FundingLoanState,
    principal_outstanding=Decimal("0"),
    maximum_funding_ltv_ratio=Decimal("0.80"),
    retained_candidates: tuple[FundingCollateralCandidate, ...] = (),
) -> tuple[FundingCustodyTransition, ...]:
    """Describe return-to-vault movements before FundingLoan closure."""

    candidates = tuple(candidates)
    if funding_loan_state not in {
        FundingLoanState.ACTIVE,
        FundingLoanState.SETTLEMENT_PENDING,
    }:
        raise FundingPledgePolicyError(
            "Collateral can be returned only from an open FundingLoan."
        )
    if not candidates:
        raise FundingPledgePolicyError(
            "A FundingLoan return must include at least one collateral item."
        )
    if any(
        candidate.custody_state
        != CollateralCustodyState.WITH_FUNDING_LENDER
        for candidate in candidates
    ):
        raise FundingPledgePolicyError(
            "Every returned collateral item must currently be with the funding lender."
        )
    principal = _decimal(principal_outstanding, "Funding principal outstanding")
    if principal < 0:
        raise FundingPledgePolicyError(
            "Funding principal outstanding cannot be negative."
        )
    retained_candidates = tuple(retained_candidates)
    if principal > 0 and not retained_candidates:
        raise FundingPledgePolicyError(
            "All collateral can return only after funding principal is settled."
        )
    if retained_candidates:
        maximum_ltv = _decimal(
            maximum_funding_ltv_ratio,
            "Maximum funding LTV ratio",
        )
        retained_value = sum(
            (_positive_collateral_value(candidate) for candidate in retained_candidates),
            Decimal("0"),
        )
        if principal > retained_value * maximum_ltv:
            raise FundingPledgePolicyError(
                "Retained funding collateral would exceed the configured LTV limit."
            )
    return tuple(
        FundingCustodyTransition(
            collateral_item_id=candidate.collateral_item_id,
            pawn_loan_id=candidate.pawn_loan_id,
            from_state=CollateralCustodyState.WITH_FUNDING_LENDER,
            to_state=CollateralCustodyState.IN_VAULT,
        )
        for candidate in candidates
    )


def assess_funding_closure(
    balance: FundingLoanBalance,
    pledged_candidates: tuple[FundingCollateralCandidate, ...],
) -> FundingClosureReadiness:
    financially_settled = balance.financially_settled
    collateral_returned = bool(pledged_candidates) and all(
        candidate.custody_state == CollateralCustodyState.IN_VAULT
        and candidate.active_funding_pledge_id is None
        for candidate in pledged_candidates
    )
    blockers = []
    if not financially_settled:
        blockers.append("Funding balance must be fully settled before closure.")
    if not collateral_returned:
        blockers.append(
            "Every pledged collateral item must return to the branch vault before closure."
        )
    return FundingClosureReadiness(
        financially_settled=financially_settled,
        collateral_returned=collateral_returned,
        ready=not blockers,
        blockers=tuple(blockers),
    )


def plan_funding_custody_reversal(
    events: tuple[FundingCustodyEvent, ...],
    *,
    original_sequence: int,
) -> FundingCustodyEvent:
    ordered = tuple(sorted(events, key=lambda event: event.sequence))
    sequences = [event.sequence for event in ordered]
    if not ordered or len(sequences) != len(set(sequences)) or any(
        sequence <= 0 for sequence in sequences
    ):
        raise FundingPledgePolicyError(
            "Funding custody events require unique positive sequences."
        )
    originals = {}
    reversed_sequences = set()
    for event in ordered:
        if event.from_state == event.to_state:
            raise FundingPledgePolicyError(
                "Funding custody movement must change location."
            )
        if event.reversal_of_sequence is None:
            originals[event.sequence] = event
            continue
        original = originals.get(event.reversal_of_sequence)
        if original is None or original.sequence in reversed_sequences:
            raise FundingPledgePolicyError(
                "Funding custody reversal must reference one unreversed earlier movement."
            )
        if (
            event.collateral_item_id != original.collateral_item_id
            or event.from_state != original.to_state
            or event.to_state != original.from_state
        ):
            raise FundingPledgePolicyError(
                "Funding custody reversal must exactly invert its original movement."
            )
        later_active_for_item = [
            candidate
            for candidate in originals.values()
            if candidate.collateral_item_id == original.collateral_item_id
            and candidate.sequence > original.sequence
            and candidate.sequence not in reversed_sequences
        ]
        if later_active_for_item:
            raise FundingPledgePolicyError(
                "Later collateral custody movements must be reversed first."
            )
        reversed_sequences.add(original.sequence)

    original = originals.get(original_sequence)
    if original is None or original.sequence in reversed_sequences:
        raise FundingPledgePolicyError(
            "Funding custody reversal requires an unreversed original movement."
        )
    later_active_for_item = [
        candidate
        for candidate in originals.values()
        if candidate.collateral_item_id == original.collateral_item_id
        and candidate.sequence > original.sequence
        and candidate.sequence not in reversed_sequences
    ]
    if later_active_for_item:
        raise FundingPledgePolicyError(
            "Later collateral custody movements must be reversed first."
        )
    return FundingCustodyEvent(
        sequence=ordered[-1].sequence + 1,
        collateral_item_id=original.collateral_item_id,
        from_state=original.to_state,
        to_state=original.from_state,
        reversal_of_sequence=original.sequence,
    )


def _validated_funding_events(events, *, quantum):
    ordered = tuple(sorted(events, key=lambda event: event.sequence))
    sequences = [event.sequence for event in ordered]
    if not ordered or len(sequences) != len(set(sequences)) or any(
        sequence <= 0 for sequence in sequences
    ):
        raise FundingLoanPolicyError(
            "FundingLoan events require unique positive sequences."
        )
    originals = {}
    reversed_sequences = set()
    activation_count = 0
    for event in ordered:
        _validate_event_amounts(event, quantum=quantum)
        if event.kind == FundingLoanEventKind.ACTIVATION:
            activation_count += 1
        if event.kind != FundingLoanEventKind.REVERSAL:
            if event.reversal_of_sequence is not None:
                raise FundingLoanPolicyError(
                    "Only reversal events may reference an original event."
                )
            originals[event.sequence] = event
            continue
        original = originals.get(event.reversal_of_sequence)
        if original is None or original.sequence in reversed_sequences:
            raise FundingLoanPolicyError(
                "FundingLoan reversal must reference one unreversed earlier event."
            )
        if any(
            (
                event.principal_amount != original.principal_amount,
                event.interest_amount != original.interest_amount,
                event.fee_amount != original.fee_amount,
            )
        ):
            raise FundingLoanPolicyError(
                "FundingLoan reversal must exactly compensate its original event."
            )
        active_sequences = [
            sequence
            for sequence in originals
            if sequence not in reversed_sequences
        ]
        if not active_sequences or active_sequences[-1] != original.sequence:
            raise FundingLoanPolicyError(
                "Later FundingLoan events must be reversed first."
            )
        reversed_sequences.add(original.sequence)
    if activation_count != 1:
        raise FundingLoanPolicyError(
            "FundingLoan history requires exactly one activation event."
        )
    return ordered


def _validate_event_amounts(event, *, quantum):
    values = (
        _decimal(event.principal_amount, "Event principal"),
        _decimal(event.interest_amount, "Event interest"),
        _decimal(event.fee_amount, "Event fee"),
    )
    if any(value < 0 or value != value.quantize(quantum) for value in values):
        raise FundingLoanPolicyError(
            "FundingLoan event amounts must be nonnegative currency values."
        )
    if event.kind == FundingLoanEventKind.ACTIVATION and (
        values[0] <= 0 or values[1] != 0 or values[2] != 0
    ):
        raise FundingLoanPolicyError(
            "FundingLoan activation must contain positive principal only."
        )
    if event.kind == FundingLoanEventKind.INTEREST_ACCRUAL and (
        values[1] <= 0 or values[0] != 0 or values[2] != 0
    ):
        raise FundingLoanPolicyError(
            "FundingLoan accrual must contain positive interest only."
        )
    if event.kind == FundingLoanEventKind.FEE_ASSESSMENT and (
        values[2] <= 0 or values[0] != 0 or values[1] != 0
    ):
        raise FundingLoanPolicyError(
            "FundingLoan fee assessment must contain a positive fee only."
        )
    if event.kind == FundingLoanEventKind.REPAYMENT and sum(values) <= 0:
        raise FundingLoanPolicyError(
            "FundingLoan repayment must contain a positive allocation."
        )


def _apply_funding_event(totals, event, *, direction):
    event_direction = direction
    if event.kind == FundingLoanEventKind.REPAYMENT:
        event_direction *= -1
    totals["principal"] += event.principal_amount * event_direction
    totals["interest"] += event.interest_amount * event_direction
    totals["fees"] += event.fee_amount * event_direction


def _positive_collateral_value(candidate):
    if candidate.collateral_value is None:
        raise FundingPledgePolicyError(
            "Every funding collateral item requires a positive valuation."
        )
    try:
        value = _decimal(candidate.collateral_value, "Funding collateral value")
    except FundingLoanPolicyError as exc:
        raise FundingPledgePolicyError(str(exc)) from exc
    if value <= 0:
        raise FundingPledgePolicyError(
            "Every funding collateral item requires a positive valuation."
        )
    return value


def _positive_quantum(value):
    quantum = _decimal(value, "Currency quantum")
    if quantum <= 0:
        raise FundingLoanPolicyError("Currency quantum must be positive.")
    return quantum


def _decimal(value, label):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise FundingLoanPolicyError(f"{label} must be a valid number.") from exc
