"""Owner-confirmed collection arithmetic for unchanged legacy loans; no posting.

The first month is paid at disbursal. Collection increases the day after each
original-date anniversary, clamping only the individual short month.
"""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, localcontext

RULE = "original-anniversary-upfront-inclusive/1"
AGGREGATE_RULE = "original-anniversary-upfront-inclusive/2"


def round_rupees(amount):
    """Confirmed rounding of ONE amount; does not choose aggregation timing."""
    if not isinstance(amount, Decimal) or not amount.is_finite() or not 0 <= amount < Decimal("1e16"):
        raise ValueError("Require a finite nonnegative Decimal below 1e16.")
    with localcontext() as context:
        context.prec = 32
        return amount.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)


def collection_calendar(original, as_of):
    if type(original) is not date or type(as_of) is not date or as_of < original:
        raise ValueError("Require business dates with comparison on or after origination.")
    months = (as_of.year - original.year) * 12 + as_of.month - original.month
    if months > 1200:
        raise ValueError("Legacy collection review supports at most 100 years.")

    def anniversary(offset):
        year, month = divmod(original.year * 12 + original.month - 1 + offset, 12)
        return date(year, month + 1, min(original.day, monthrange(year, month + 1)[1]))

    additional = max(0, months - (as_of <= anniversary(months)))
    try:
        next_increase = anniversary(additional + 1) + timedelta(days=1)
    except (ValueError, OverflowError) as exc:
        raise ValueError("Next collection boundary is outside supported dates.") from exc
    return {"rule": RULE, "original_date": original.isoformat(), "as_of": as_of.isoformat(),
            "additional_months": additional, "next_increase_on": next_increase.isoformat()}


def collection_interest(original, as_of, monthly_charge):
    """Whole-rupee monthly charge only: aggregation timing cannot affect this case.

    Caller must establish unchanged principal, first-month payment and no later
    payments. This is collection arithmetic, not accrued revenue or an opening.
    """
    rounded = round_rupees(monthly_charge)
    if monthly_charge != rounded:
        raise ValueError("Fractional monthly charges require a confirmed aggregation rule.")
    result = collection_calendar(original, as_of)
    with localcontext() as context:
        context.prec = 32
        result["additional_interest"] = str(rounded * result["additional_months"])
    return result


def aggregate_collection_interest(original, as_of, monthly_charge):
    """Rehearsal baseline: sum item monthly charges, multiply, then round once.

    Negotiated collections are separate evidence. This estimate does not infer
    receipts, interest concessions or permission to settle a live loan.
    """
    round_rupees(monthly_charge)  # Validate the same bounded Decimal input.
    result = collection_calendar(original, as_of)
    with localcontext() as context:
        context.prec = 64
        unrounded = monthly_charge * result["additional_months"]
        rounded = round_rupees(unrounded)
        result.update(rule=AGGREGATE_RULE, monthly_interest_unrounded=str(monthly_charge),
                      additional_interest_unrounded=str(unrounded), additional_interest=str(rounded),
                      rounding_adjustment=str(rounded - unrounded),
                      rounding_basis="SUM_ITEMS_THEN_MONTHS_HALF_EVEN_WHOLE_RUPEE")
    return result
