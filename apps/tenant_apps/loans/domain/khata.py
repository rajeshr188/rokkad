"""KHATA-1: simple interest on agreed limits, independent of pawn economics.

Inputs are approved/effective terms supplied by the caller. This module neither
posts charges nor decides whether an operation is authorized or collateral held.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from fractions import Fraction


CONTRACT_VERSION = "KHATA-1"
MAX_MONEY = Decimal("9999999999999999.99")


class KhataCalculationError(ValueError):
    pass


def amount(value, *, positive=False):
    """Reject lossy money input, including floats, NaN and sub-paise amounts."""
    if isinstance(value, (float, bool)):
        raise KhataCalculationError("Use exact decimal money values.")
    try:
        result = Decimal(value)
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise KhataCalculationError("Invalid money amount.") from exc
    if not result.is_finite() or result < 0 or result > MAX_MONEY:
        raise KhataCalculationError("Money amount is outside supported bounds.")
    if result != result.quantize(Decimal("0.01")) or (positive and result == 0):
        raise KhataCalculationError("Money must be in paise and positive where required.")
    return result


def decimal_rate(value, *, ltv=False):
    if isinstance(value, (float, bool)):
        raise KhataCalculationError("Use exact decimal rates.")
    try:
        result = Decimal(value)
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise KhataCalculationError("Invalid rate.") from exc
    if not result.is_finite() or result < 0 or result > Decimal("9999.999999"):
        raise KhataCalculationError("Rate is outside supported bounds.")
    if result != result.quantize(Decimal("0.000001")):
        raise KhataCalculationError("Rates support at most six decimal places.")
    if ltv and not 0 < result <= 1:
        raise KhataCalculationError("LTV must be greater than zero and at most one.")
    return result


def _day(value):
    if type(value) is not date:
        raise KhataCalculationError("Use business dates, not timestamps.")
    return value


def anniversary(opened_on: date, months: int) -> date:
    _day(opened_on)
    if type(months) is not int or months < 0:
        raise KhataCalculationError("Month index must be a nonnegative integer.")
    year, month0 = divmod(opened_on.year * 12 + opened_on.month - 1 + months, 12)
    if not 1 <= year <= 9999:
        raise KhataCalculationError("Anniversary exceeds the supported date range.")
    return date(year, month0 + 1, min(opened_on.day, monthrange(year, month0 + 1)[1]))


def _paise(value: Fraction, *, floor=False) -> Decimal:
    scaled = value * 100
    whole, remainder = divmod(scaled.numerator, scaled.denominator)
    if not floor and remainder * 2 >= scaled.denominator:
        whole += 1
    return Decimal(whole) / 100


@dataclass(frozen=True)
class Terms:
    effective_on: date
    limit: Decimal
    monthly_rate: Decimal
    revision: int = 1

    def __post_init__(self):
        _day(self.effective_on)
        object.__setattr__(self, "limit", amount(self.limit, positive=True))
        object.__setattr__(self, "monthly_rate", decimal_rate(self.monthly_rate))
        if type(self.revision) is not int or self.revision < 1:
            raise KhataCalculationError("Revision must be a positive integer.")


@dataclass(frozen=True)
class InterestSegment:
    start: date
    end: date
    terms: Terms
    period_days: int
    exact_charge: Fraction


@dataclass(frozen=True)
class InterestPeriod:
    index: int
    start: date
    end: date
    charged_through: date
    due_on: date
    segments: tuple[InterestSegment, ...]
    actual_charge: Decimal
    minimum_adjustment: Decimal
    charge: Decimal


def calculate_interest(*, opened_on, through, terms, frequency="MONTHLY"):
    """Return monthly evidence for [opened_on, through), including opening floor.

    This is a settlement/calculation quote, not a due balance. The opening floor
    is included even for same-day closure, but retains the scheduled due date.
    Same-day activations require ascending unique revision numbers; the last
    supplies that day's terms, while the first preserves the opening floor.
    Annual Feb-29 anniversaries clamp to Feb-28 and restore in leap years.
    """
    _day(opened_on)
    _day(through)
    terms = tuple(terms)
    if frequency not in {"MONTHLY", "ANNUAL"}:
        raise KhataCalculationError("Choose monthly or annual collection.")
    if through < opened_on or not terms or any(not isinstance(t, Terms) for t in terms):
        raise KhataCalculationError("Invalid calculation interval or agreement terms.")
    if terms[0].effective_on != opened_on:
        raise KhataCalculationError("Opening terms must start on the opening date.")
    for before, after in zip(terms, terms[1:]):
        if after.effective_on < before.effective_on or after.revision <= before.revision:
            raise KhataCalculationError("Terms must follow effective date and revision order.")
    floor = Fraction(terms[0].limit) * Fraction(terms[0].monthly_rate) / 100
    result = []
    index = 0
    position = 0
    while index == 0 or anniversary(opened_on, index) < through:
        start, end = anniversary(opened_on, index), anniversary(opened_on, index + 1)
        stop = min(end, through)
        while position + 1 < len(terms) and terms[position + 1].effective_on <= start:
            position += 1
        cursor = start
        segments = []
        while cursor < stop:
            next_change = terms[position + 1].effective_on if position + 1 < len(terms) else stop
            segment_end = min(stop, next_change)
            current = terms[position]
            exact = (Fraction(current.limit) * Fraction(current.monthly_rate) / 100
                     * Fraction((segment_end - cursor).days, (end - start).days))
            if segment_end > cursor:
                segments.append(InterestSegment(cursor, segment_end, current, (end - start).days, exact))
            cursor = segment_end
            while position + 1 < len(terms) and terms[position + 1].effective_on <= cursor:
                position += 1
        actual = sum((s.exact_charge for s in segments), Fraction())
        charged = max(floor, actual) if index == 0 else actual
        due_index = index + 1 if frequency == "MONTHLY" else (index // 12 + 1) * 12
        rounded, actual_rounded = _paise(charged), _paise(actual)
        result.append(InterestPeriod(index, start, end, stop, anniversary(opened_on, due_index),
                                     tuple(segments), actual_rounded, rounded - actual_rounded, rounded))
        index += 1
    return tuple(result)


@dataclass(frozen=True)
class DrawPosition:
    limit: Decimal
    principal: Decimal
    unused: Decimal

    def __post_init__(self):
        for name in ("limit", "principal", "unused"):
            object.__setattr__(self, name, amount(getattr(self, name), positive=name == "limit"))
        if self.principal + self.unused > self.limit:
            raise KhataCalculationError("Principal plus unused entitlement exceeds the agreed limit.")


def available_draw(position: DrawPosition, *, collateral_value, ltv):
    backing = _paise(Fraction(amount(collateral_value)) * Fraction(decimal_rate(ltv, ltv=True)), floor=True)
    return min(position.unused, max(Decimal(0), backing - position.principal))


def withdraw(position: DrawPosition, *, value, collateral_value, ltv):
    value = amount(value, positive=True)
    if value > available_draw(position, collateral_value=collateral_value, ltv=ltv):
        raise KhataCalculationError("Withdrawal exceeds unused entitlement or collateral backing.")
    return DrawPosition(position.limit, position.principal + value, position.unused - value)


def revise_limit(position: DrawPosition, *, new_limit, principal_repayment=Decimal(0)):
    new_limit, repayment = amount(new_limit, positive=True), amount(principal_repayment)
    if repayment > position.principal:
        raise KhataCalculationError("Repayment exceeds principal outstanding.")
    if repayment and new_limit >= position.limit:
        raise KhataCalculationError("Principal repayment requires a formal limit reduction.")
    principal = position.principal - repayment
    if principal > new_limit:
        raise KhataCalculationError("Repay principal above the reduced limit.")
    return DrawPosition(new_limit, principal, max(Decimal(0), position.unused + new_limit - position.limit))
