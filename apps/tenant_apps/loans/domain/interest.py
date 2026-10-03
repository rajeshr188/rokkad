from decimal import Decimal, ROUND_HALF_UP

from .policies import PartialMonthMethod


class InterestCalculationError(ValueError):
    pass


def partial_period_fraction(*, method, elapsed_days, period_days,
                            minimum_first_month=False, period_number=1,
                            cutoff_days=15, lower_fraction=Decimal("0.5")):
    """Inclusive elapsed days; weekly/day fractions use this actual monthly period."""
    method = PartialMonthMethod(method)
    if not 1 <= elapsed_days <= period_days or period_number < 1:
        raise InterestCalculationError("Invalid monthly period boundaries.")
    if elapsed_days == period_days or (minimum_first_month and period_number == 1):
        return Decimal("1")
    if method == PartialMonthMethod.FULL_MONTH:
        return Decimal("1")
    if method == PartialMonthMethod.SLAB:
        return Decimal(str(lower_fraction)) if elapsed_days <= cutoff_days else Decimal("1")
    chargeable_days = ((elapsed_days + 6) // 7) * 7 if method == PartialMonthMethod.STARTED_WEEKS else elapsed_days
    return Decimal(min(chargeable_days, period_days)) / Decimal(period_days)


def calculate_period_interest(
    *, calculation_base, monthly_interest_rate, period_fraction, currency_quantum
):
    base = Decimal(str(calculation_base))
    rate = Decimal(str(monthly_interest_rate))
    fraction = Decimal(str(period_fraction))
    quantum = Decimal(str(currency_quantum))
    if base < 0 or rate < 0 or not Decimal("0") < fraction <= Decimal("1"):
        raise InterestCalculationError("Interest calculation inputs are outside policy bounds.")
    unrounded = base * rate / Decimal("100") * fraction
    return unrounded, unrounded.quantize(quantum, rounding=ROUND_HALF_UP)
