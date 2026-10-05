"""Shared original-anniversary monthly contract; no database access."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

POLICY_VERSION = 2
RULE = "original-anniversary-policy/1"
RECORDED_PROFILE = "recorded-anniversary/3"


def anniversary(original, offset):
    if type(original) is not date or type(offset) is not int or not 0 <= offset <= 1200:
        raise ValueError("Require an original business date and bounded month offset.")
    year, month = divmod(original.year * 12 + original.month - 1 + offset, 12)
    return date(year, month + 1, min(original.day, monthrange(year, month + 1)[1]))


def period_dates(original, number):
    """Inclusive first anniversary, then contiguous anchored monthly periods."""
    if type(number) is not int or not 1 <= number <= 1200:
        raise ValueError("Require a bounded monthly period number.")
    start = original if number == 1 else anniversary(original, number - 1) + timedelta(days=1)
    return start, anniversary(original, number)


def charge_count(original, on):
    if type(on) is not date or on < original:
        raise ValueError("Require an as-of business date on or after origination.")
    months = (on.year - original.year) * 12 + on.month - original.month
    if months > 1200:
        raise ValueError("Monthly collection supports at most 100 years.")
    return max(0, months - (on <= anniversary(original, months)))


def round_interest(amount, quantum):
    amount, quantum = Decimal(amount), Decimal(quantum).normalize()
    if not amount.is_finite() or amount < 0 or not quantum.is_finite() or quantum not in (Decimal(".01"), Decimal("1")):
        raise ValueError("Require nonnegative interest and a supported policy quantum (paise or rupees).")
    return amount.quantize(quantum, rounding=ROUND_HALF_UP)


def item_monthly_interest(principal, rate, quantum):
    return round_interest(Decimal(principal) * Decimal(rate) / 100, quantum)
