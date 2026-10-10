"""Bounded fictional cash examples using the ordinary Loans arithmetic."""
from datetime import timedelta
from decimal import Decimal

from apps.tenant_apps.loans.domain.collateral_economics import DisbursalFeeInput, _calculate_fee
from apps.tenant_apps.loans.domain.interest import calculate_period_interest, partial_period_fraction
from apps.tenant_apps.loans.domain.monthly_contract import anniversary, period_dates, item_monthly_interest


def calculate_setup_example(*, policy, monthly_rate, fees, principal, start, end):
    """No borrower, valuation, number allocation, database writer or saved loan."""
    principal = Decimal(principal)
    if not principal.is_finite() or not Decimal("0.01") <= principal <= Decimal("999999999"):
        raise ValueError("Choose an example principal between INR 0.01 and INR 999,999,999.")
    if not 0 <= (end - start).days <= 730:
        raise ValueError("Choose a closing date on or after the example loan date, within two years.")
    quantum = policy.currency_quantum.normalize()
    monthly = item_monthly_interest(principal, monthly_rate, quantum)
    advance = monthly * policy.advance_interest_periods
    fee_rows = tuple(_calculate_fee(DisbursalFeeInput(
        code=fee.code, name=fee.name, calculation_type=fee.calculation_type,
        value=fee.value, deducted_at_disbursal=fee.deducted_at_disbursal,
    ), principal, Decimal("0.01")) for fee in fees)
    deducted = sum((fee.amount for fee in fee_rows if fee.deducted_at_disbursal), Decimal("0"))
    separate = sum((fee.amount for fee in fee_rows if not fee.deducted_at_disbursal), Decimal("0"))
    payout = principal - advance - deducted
    if payout <= 0:
        raise ValueError("The saved upfront interest and charges leave no positive payout for this example.")
    result = dict(principal=principal, monthly_interest=monthly, advance=advance,
        deducted_fees=deducted, separate_fees=separate, payout=payout, fees=fee_rows,
        start=start, end=end, settlements=[], interest_method=policy.interest_method)
    # Capitalization is an explicit financial action, not an automatic prediction.
    # Never manufacture a later compound balance from setup alone.
    if policy.interest_method != "SIMPLE":
        result["settlement_unavailable"] = True
        return result

    for closing in dict.fromkeys((end, anniversary(start, 1), anniversary(start, 1) + timedelta(days=1))):
        remaining, total = advance, Decimal("0")
        rows = []
        for number in range(1, 26):
            begin, finish = period_dates(start, number)
            if begin > closing:
                break
            through = min(finish, closing)
            fraction = partial_period_fraction(method=policy.partial_month_method,
                elapsed_days=(through - begin).days + 1, period_days=(finish - begin).days + 1,
                minimum_first_month=policy.minimum_first_month, period_number=number,
                cutoff_days=policy.partial_month_cutoff_days, lower_fraction=policy.partial_month_lower_fraction)
            _, amount = calculate_period_interest(calculation_base=principal, monthly_interest_rate=monthly_rate,
                period_fraction=fraction, currency_quantum=quantum)
            credit = min(remaining, amount)
            remaining -= credit
            additional = amount - credit
            total += additional
            rows.append(dict(start=begin, end=through, fraction=fraction, interest=amount, credit=credit, additional=additional))
        result["settlements"].append(dict(date=closing, additional_interest=total,
            amount=principal + total, unused_advance=remaining, rows=rows))
    return result
