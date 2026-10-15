"""Read-only collection amounts and explicitly defined monthly report metrics."""
from dataclasses import dataclass
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Q

from apps.tenant_apps.loans.domain.vocabulary import CollateralMetal
from .balances import PawnLoanBalance, get_pawn_loan_balance
from .continuation import RECORDED_PROFILES
from .servicing_contract import get_servicing_position

ZERO = Decimal("0")
MONTHS_BASIS = "Oldest monthly charges covered first; a partly unpaid month counts as one."


def collateral_preview(items, *, provisional=False):
    """Small recorded-item preview shared by the directory and Party lists."""
    items = tuple(items)
    preview = []
    for item in items[:2]:
        custody = ""
        if not provisional:
            if hasattr(item, "get_custody_state_display"):
                custody = "Handover unconfirmed" if item.custody_state == "PAPER_CLOSED" else item.get_custody_state_display()
            elif hasattr(item, "preview_returned"):
                custody = "Returned" if item.preview_returned else "Held"
        preview.append(dict(description=item.description, quantity=item.quantity,
            metal=item.get_metal_display(), net_weight=item.net_weight, custody=custody))
    return {"items": tuple(preview), "more_count": max(0, len(items) - 2)}


def get_loan_collateral_summary(loan):
    """Recorded descriptions and current holdings, not original/historical stock.

    Each item's weights already describe its entire quantity. Never multiply
    weights by piece count, or infer missing gross from net.
    """
    items = tuple(loan.collateral_items.all())
    descriptions = []
    weights = {metal.value: [ZERO, ZERO] for metal in CollateralMetal}
    uncertain_metals = set()
    for item in items:
        quantity = "not recorded" if item.quantity is None else str(item.quantity)
        descriptions.append(f"{item.description}; {item.get_metal_display()}; "
            f"qty {quantity}; {item.get_custody_state_display()}")
        if item.custody_state == "PAPER_CLOSED":
            uncertain_metals.add(item.metal)
        if item.custody_state not in {"IN_VAULT", "WITH_FUNDING_LENDER"}:
            continue
        group = weights[item.metal]
        group[0] = None if group[0] is None or item.gross_weight is None else group[0] + item.gross_weight
        group[1] += item.net_weight
    for metal in uncertain_metals:
        weights[metal] = [None, None]
    # No items is incomplete evidence, not proof of empty holdings. Drafts and
    # approvals have provisional item rows but do not establish disbursed custody.
    values = tuple(value for metal in CollateralMetal for value in weights[metal.value])
    if not items or loan.state in {"DRAFT", "APPROVED", "CANCELLED"}:
        values = (None,) * len(values)
    return ("\n".join(descriptions) or "Not recorded", *values)


@dataclass(frozen=True)
class LoanSummary:
    balance: PawnLoanBalance | None
    age_months: int | None
    unpaid_interest_months: int | None
    months_basis: str
    balance_basis: str


def completed_months(original, on):
    if original is None or original > on:
        return None
    months = (on.year - original.year) * 12 + on.month - original.month
    anniversary = date(on.year, on.month, min(original.day, monthrange(on.year, on.month)[1]))
    return months - (on < anniversary)


def unpaid_month_count(charges, outstanding):
    """Reporting convention only, never an allocation or a new debt calculation."""
    charges = tuple(Decimal(value) for value in charges)
    if outstanding < ZERO or any(value < ZERO for value in charges) or sum(charges, ZERO) < outstanding:
        return None
    remaining, count = outstanding, 0
    for charge in reversed(charges):
        if remaining <= ZERO:
            break
        if charge > ZERO:
            count += 1
            remaining -= charge
    return count


def get_loan_summary(loan, *, as_of_date):
    age = completed_months(loan.loan_date, as_of_date)
    if loan.state in {"DRAFT", "APPROVED"}:
        return LoanSummary(None, age, None, "Not yet disbursed", "Not yet disbursed")
    try:
        if loan.state != "ACTIVE":
            balance = get_pawn_loan_balance(loan, as_of_date=as_of_date)
            return LoanSummary(balance, age, 0 if balance.interest_outstanding == ZERO else None,
                "Completed record; monthly attribution unavailable", "Recorded debt")
        position = get_servicing_position(loan, as_of_date=as_of_date)
        if position.contract.origin_event_id is None:
            raise ValueError("Active loan requires its financial origin")
    except ValueError:
        return LoanSummary(None, age, None, "Unavailable: review financial evidence", "Unavailable")

    balance, continuation = position.balance, position.continuation
    count, basis = None, "Unavailable: monthly history is not established"
    if balance.interest_outstanding == ZERO:
        count, basis = 0, "No unpaid interest"
    elif continuation is not None and position.contract.supports_completed_monthly_servicing:
        plan = continuation.recognition
        if position.contract.profile in RECORDED_PROFILES:
            # The existing calculator retains varying principal/rates and advance
            # coverage. Do not divide debt by today's monthly interest amount.
            charges = [Decimal(row["interest"]) for row in plan.calculation["months"]]
            count = unpaid_month_count(charges, balance.interest_outstanding)
        elif plan.adapter == "NATIVE_PERIODS":
            finalized = loan.interest_accruals.filter(loan_event__effective_date__lte=as_of_date).filter(
                Q(loan_event__reversed_by_event__isnull=True)
                | Q(loan_event__reversed_by_event__effective_date__gt=as_of_date)
            ).order_by("period_number")
            charges = [row.recognized_interest for row in finalized]
            # A complete reconciliation is required; unrelated aggregate accruals
            # must not acquire invented monthly attribution.
            if sum(charges, ZERO) == continuation.recorded_balance.interest_accrued:
                charges += [row.recognized_interest for row in plan.calculation]
                count = unpaid_month_count(charges, balance.interest_outstanding)
        if count is not None:
            basis = MONTHS_BASIS
    balance_basis = {
        "RECORDED_DEBT": "Recorded debt",
        "COLLECTION_WITH_UNPOSTED_INTEREST": "Collection amount including eligible unposted interest",
        "VERIFIED_TERMINAL_POSITION": "Verified closed position",
    }[position.balance_basis]
    return LoanSummary(balance, age, count, basis, balance_basis)
