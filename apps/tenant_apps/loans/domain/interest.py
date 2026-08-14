from decimal import Decimal, ROUND_HALF_UP


class InterestCalculationError(ValueError):
    pass


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
