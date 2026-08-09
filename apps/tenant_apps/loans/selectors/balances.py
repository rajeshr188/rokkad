"""Canonical PawnLoan balance, settlement, and posting-readiness selectors."""

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
    LoanOutboxStatus,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations.accounting_policy import (
    is_dea_integration_enabled,
)
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id


ZERO = Decimal("0")
DEFAULT_QUANTUM = Decimal("0.01")


class PawnLoanBalanceSelectorError(ValueError):
    pass


@dataclass(frozen=True)
class PostingBlocker:
    event_id: int
    event_kind: str
    status: str
    message: str


@dataclass(frozen=True)
class PawnLoanBalance:
    loan_id: int
    as_of_date: date
    due_date: date
    principal_disbursed: Decimal
    principal_capitalized: Decimal
    principal_paid: Decimal
    original_principal_paid: Decimal
    capitalized_interest_principal_paid: Decimal
    principal_outstanding: Decimal
    original_principal_outstanding: Decimal
    capitalized_interest_principal_outstanding: Decimal
    interest_accrued: Decimal
    interest_capitalized: Decimal
    interest_paid: Decimal
    interest_outstanding: Decimal
    overdue_interest_outstanding: Decimal
    current_interest_outstanding: Decimal
    fees_assessed: Decimal
    fees_paid: Decimal
    fees_outstanding: Decimal
    total_due: Decimal
    interest_method: str | None
    accounting_recognition: str | None
    is_overdue: bool
    financially_settled: bool
    collateral_partially_returned: bool
    collateral_return_complete: bool
    closure_ready: bool
    posting_ready: bool
    posting_blockers: tuple[PostingBlocker, ...]


def get_pawn_loan_balance(loan_or_id, *, as_of_date: date) -> PawnLoanBalance:
    """Load tenant-scoped source events once and derive every financial status."""
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanBalanceSelectorError("PawnLoan balances require an active tenant schema.")
    loan_id = getattr(loan_or_id, "pk", loan_or_id)
    try:
        loan = (
            PawnLoan.objects.select_related("policy_snapshot", "workspace")
            .prefetch_related("collateral_items", "accounting_events__outbox")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnLoanBalanceSelectorError(
            "PawnLoan was not found in the active workspace."
        ) from exc
    return calculate_pawn_loan_balance(
        loan,
        events=tuple(loan.accounting_events.all()),
        collateral_items=tuple(loan.collateral_items.all()),
        policy_snapshot=_optional_policy_snapshot(loan),
        as_of_date=as_of_date,
        pending_delivery_blocks=is_dea_integration_enabled(loan.workspace),
    )


def calculate_pawn_loan_balance(
    loan,
    *,
    events,
    collateral_items,
    policy_snapshot,
    as_of_date: date,
    pending_delivery_blocks: bool = True,
) -> PawnLoanBalance:
    """Pure event-fold used by repayment, release, reporting, and tests."""
    totals = {
        "principal_disbursed": ZERO,
        "principal_capitalized": ZERO,
        "principal_paid": ZERO,
        "original_principal_paid": ZERO,
        "capitalized_interest_principal_paid": ZERO,
        "interest_accrued": ZERO,
        "interest_capitalized": ZERO,
        "interest_paid": ZERO,
        "fees_assessed": ZERO,
        "fees_paid": ZERO,
    }
    posting_blockers = []
    for event in sorted(events, key=lambda item: (item.effective_date, item.pk or 0)):
        if event.effective_date > as_of_date:
            continue
        _apply_event(totals, event)
        blocker = _posting_blocker(event)
        if blocker and not (
            blocker.status == LoanOutboxStatus.PENDING.value
            and not pending_delivery_blocks
        ):
            posting_blockers.append(blocker)

    quantum = Decimal(str(getattr(policy_snapshot, "currency_quantum", DEFAULT_QUANTUM)))
    _validate_nonnegative_totals(totals)
    principal_outstanding = (
        totals["principal_disbursed"]
        + totals["principal_capitalized"]
        - totals["principal_paid"]
    )
    original_principal_outstanding = (
        totals["principal_disbursed"] - totals["original_principal_paid"]
    )
    capitalized_interest_principal_outstanding = (
        totals["principal_capitalized"]
        - totals["capitalized_interest_principal_paid"]
    )
    interest_outstanding = (
        totals["interest_accrued"]
        - totals["interest_capitalized"]
        - totals["interest_paid"]
    )
    fees_outstanding = totals["fees_assessed"] - totals["fees_paid"]
    for label, value in (
        ("principal", principal_outstanding),
        ("interest", interest_outstanding),
        ("fees", fees_outstanding),
    ):
        if value < ZERO:
            raise PawnLoanBalanceSelectorError(
                f"PawnLoan event history over-settles {label}."
            )
    total_due = principal_outstanding + interest_outstanding + fees_outstanding
    has_disbursal = totals["principal_disbursed"] > ZERO
    financially_settled = has_disbursal and total_due == ZERO
    collateral_items = tuple(collateral_items)
    resolved_custody_states = {
        CollateralCustodyState.WITH_CUSTOMER.value,
        CollateralCustodyState.AUCTION_DISPOSED.value,
        CollateralCustodyState.RENEWAL_TRANSFERRED.value,
    }
    returned_item_count = sum(
        item.custody_state in resolved_custody_states for item in collateral_items
    )
    collateral_partially_returned = (
        0 < returned_item_count < len(collateral_items)
    )
    collateral_return_complete = bool(collateral_items) and all(
        item.custody_state in resolved_custody_states
        for item in collateral_items
    )
    due_date = _add_months(loan.loan_date, loan.tenure_months)
    overdue_interest = interest_outstanding if as_of_date > due_date else ZERO
    current_interest = interest_outstanding - overdue_interest
    return PawnLoanBalance(
        loan_id=loan.pk,
        as_of_date=as_of_date,
        due_date=due_date,
        principal_disbursed=_money(totals["principal_disbursed"], quantum),
        principal_capitalized=_money(totals["principal_capitalized"], quantum),
        principal_paid=_money(totals["principal_paid"], quantum),
        original_principal_paid=_money(totals["original_principal_paid"], quantum),
        capitalized_interest_principal_paid=_money(
            totals["capitalized_interest_principal_paid"], quantum
        ),
        principal_outstanding=_money(principal_outstanding, quantum),
        original_principal_outstanding=_money(
            original_principal_outstanding, quantum
        ),
        capitalized_interest_principal_outstanding=_money(
            capitalized_interest_principal_outstanding, quantum
        ),
        interest_accrued=_money(totals["interest_accrued"], quantum),
        interest_capitalized=_money(totals["interest_capitalized"], quantum),
        interest_paid=_money(totals["interest_paid"], quantum),
        interest_outstanding=_money(interest_outstanding, quantum),
        overdue_interest_outstanding=_money(overdue_interest, quantum),
        current_interest_outstanding=_money(current_interest, quantum),
        fees_assessed=_money(totals["fees_assessed"], quantum),
        fees_paid=_money(totals["fees_paid"], quantum),
        fees_outstanding=_money(fees_outstanding, quantum),
        total_due=_money(total_due, quantum),
        interest_method=getattr(policy_snapshot, "interest_method", None),
        accounting_recognition=getattr(policy_snapshot, "accounting_recognition", None),
        is_overdue=as_of_date > due_date and total_due > ZERO,
        financially_settled=financially_settled,
        collateral_partially_returned=collateral_partially_returned,
        collateral_return_complete=collateral_return_complete,
        closure_ready=financially_settled and collateral_return_complete,
        posting_ready=not posting_blockers,
        posting_blockers=tuple(posting_blockers),
    )


def _apply_event(totals, event):
    kind = TransactionKind(event.event_kind)
    values = event.payload.get("values", {})
    multiplier = Decimal("1")
    if kind == TransactionKind.REVERSAL:
        reversal = event.payload.get("reversal") or {}
        try:
            kind = TransactionKind(reversal["original_event_kind"])
        except (KeyError, ValueError) as exc:
            raise PawnLoanBalanceSelectorError(
                f"Reversal event {event.pk} is missing its original event kind."
            ) from exc
        multiplier = Decimal("-1")

    principal = _amount(values, "principal") * multiplier
    interest = _amount(values, "interest") * multiplier
    fees = _amount(values, "fees") * multiplier
    fees_assessed = _amount(values, "fees_assessed") * multiplier
    if kind == TransactionKind.DISBURSAL:
        totals["principal_disbursed"] += principal
        totals["fees_assessed"] += fees_assessed
    elif kind == TransactionKind.RENEWAL_OPENING:
        capitalized_component = _amount(
            values, "capitalized_interest_principal"
        ) * multiplier
        if multiplier > 0 and capitalized_component > principal:
            raise PawnLoanBalanceSelectorError(
                "Renewal opening capitalized principal exceeds total principal."
            )
        totals["principal_disbursed"] += principal - capitalized_component
        totals["principal_capitalized"] += capitalized_component
        totals["fees_assessed"] += fees_assessed
    elif kind in (
        TransactionKind.REPAYMENT,
        TransactionKind.RELEASE_RECEIPT,
        TransactionKind.AUCTION_RECOVERY,
        TransactionKind.RENEWAL_SETTLEMENT,
    ):
        capitalized_component = (
            _amount(values, "capitalized_interest_principal") * multiplier
        )
        if "capitalized_interest_principal" not in values:
            if multiplier < 0:
                capitalized_component = ZERO
            else:
                available_capitalized = (
                    totals["principal_capitalized"]
                    - totals["capitalized_interest_principal_paid"]
                )
                capitalized_component = min(principal, available_capitalized)
        if multiplier > 0 and capitalized_component > principal:
            raise PawnLoanBalanceSelectorError(
                "Principal payment capitalized-interest split exceeds principal."
            )
        totals["principal_paid"] += principal
        totals["capitalized_interest_principal_paid"] += capitalized_component
        totals["original_principal_paid"] += principal - capitalized_component
        totals["interest_paid"] += interest
        totals["fees_paid"] += fees
    elif kind == TransactionKind.INTEREST_ACCRUAL:
        totals["interest_accrued"] += interest
        totals["fees_assessed"] += fees_assessed
    elif kind == TransactionKind.INTEREST_CAPITALIZATION:
        totals["principal_capitalized"] += interest
        totals["interest_capitalized"] += interest


def _posting_blocker(event):
    try:
        outbox = event.outbox
    except (ObjectDoesNotExist, AttributeError):
        return PostingBlocker(
            event.pk,
            event.event_kind,
            "MISSING",
            "Accounting outbox record is missing.",
        )
    if outbox.status == LoanOutboxStatus.POSTED.value:
        return None
    return PostingBlocker(
        event.pk,
        event.event_kind,
        outbox.status,
        outbox.last_error or f"Accounting delivery is {outbox.status.lower()}.",
    )


def _amount(values, key):
    try:
        amount = Decimal(str(values.get(key, "0")))
    except (TypeError, ValueError) as exc:
        raise PawnLoanBalanceSelectorError(f"Invalid {key} economic value.") from exc
    if amount < ZERO:
        raise PawnLoanBalanceSelectorError(f"{key} economic value cannot be negative.")
    return amount


def _validate_nonnegative_totals(totals):
    for label, value in totals.items():
        if value < ZERO:
            raise PawnLoanBalanceSelectorError(
                f"PawnLoan event history makes {label} negative."
            )
    if totals["original_principal_paid"] > totals["principal_disbursed"]:
        raise PawnLoanBalanceSelectorError(
            "PawnLoan event history over-settles principal (original component)."
        )
    if (
        totals["capitalized_interest_principal_paid"]
        > totals["principal_capitalized"]
    ):
        raise PawnLoanBalanceSelectorError(
            "PawnLoan event history over-settles principal "
            "(capitalized-interest component)."
        )


def _optional_policy_snapshot(loan):
    try:
        return loan.policy_snapshot
    except ObjectDoesNotExist:
        return None


def _money(value, quantum):
    return Decimal(value).quantize(quantum)


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
