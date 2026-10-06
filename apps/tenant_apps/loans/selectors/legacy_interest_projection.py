"""Compatibility forecast for published pre-shared-policy contracts.

This is the former exposure calculation, unchanged; never collectible interest.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from apps.tenant_apps.loans.domain.interest import calculate_period_interest
from .balances import get_pawn_loan_balance


def project_legacy_interest(loan, as_of_date):
    if loan.policy_snapshot is None:
        raise ValueError("Loan is missing its frozen disbursal policy.")
    # Import lazily to avoid selectors <-> services package initialization cycles.
    from apps.tenant_apps.loans.services.pawn_tranches import (
        get_pawn_principal_tranche_balances,
    )

    last = loan.interest_accruals.exclude(
        release_catch_up__reversal__isnull=False
    ).order_by("-period_number").first()
    period_start = last.period_end + timedelta(days=1) if last else loan.loan_date
    quantum = loan.policy_snapshot.currency_quantum
    if loan.policy_snapshot.basis == "RECORDED_CONTRACT":
        quantum = quantum.normalize()
    periods = []
    while period_start <= as_of_date:
        full_end = _add_months(period_start, 1) - timedelta(days=1)
        period_end = min(full_end, as_of_date)
        full_days = Decimal((full_end - period_start).days + 1)
        event_dates = tuple(
            loan.loan_events.filter(
                effective_date__gt=period_start,
                effective_date__lte=period_end,
            ).values_list("effective_date", flat=True).distinct().order_by("effective_date")
        )
        boundaries = (period_start, *event_dates, period_end + timedelta(days=1))
        raw_period = Decimal("0")
        for segment_start, next_start in zip(boundaries, boundaries[1:]):
            segment_days = Decimal((next_start - segment_start).days)
            if segment_days <= 0:
                continue
            tranches = get_pawn_principal_tranche_balances(
                loan, as_of_date=segment_start
            )
            if tranches:
                for tranche in tranches:
                    raw, _ = calculate_period_interest(
                        calculation_base=tranche.principal_outstanding,
                        monthly_interest_rate=tranche.monthly_interest_rate,
                        period_fraction=segment_days / full_days,
                        currency_quantum=quantum,
                    )
                    raw_period += raw
            else:
                balance = get_pawn_loan_balance(loan, as_of_date=segment_start)
                raw, _ = calculate_period_interest(
                    calculation_base=balance.principal_outstanding,
                    monthly_interest_rate=loan.monthly_interest_rate,
                    period_fraction=segment_days / full_days,
                    currency_quantum=quantum,
                )
                raw_period += raw
        projected = raw_period.quantize(
            Decimal(str(quantum)), rounding=ROUND_HALF_UP
        )
        periods.append((period_start, period_end, projected))
        period_start = full_end + timedelta(days=1)
    return tuple(periods)


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))
