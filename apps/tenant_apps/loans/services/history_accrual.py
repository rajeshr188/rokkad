"""Exact portable accrual evidence, reconciled with fixed-precision projections."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from apps.tenant_apps.loans.domain.interest import calculate_period_interest
from .history_contract import HistoryError, decimal
from .pawn_interest import (
    AccrualLinePreview, AccrualPeriodPreview, _add_months, _partial_fraction,
    build_pawn_accrual_detail,
)


def portable_accrual(period, policy, item_ids, *, release_catch_up=False):
    days = (_add_months(period.period_start, 1) - period.period_start).days
    elapsed = (period.period_end - period.period_start).days + 1
    chargeable = None
    if policy.minimum_first_month and period.period_number == 1:
        chargeable = days
    elif policy.partial_month_method == "STARTED_WEEKS":
        chargeable = min(((elapsed + 6) // 7) * 7, days)
    elif policy.partial_month_method == "ACTUAL_DAYS":
        chargeable = elapsed
    return dict(period=period.period_number, start=period.period_start.isoformat(),
        end=period.period_end.isoformat(), fraction=decimal(period.period_fraction),
        base=decimal(period.calculation_base), unrounded=decimal(period.unrounded_interest),
        recognized=decimal(period.recognized_interest), calculated=decimal(period.calculated_interest),
        advance_applied=decimal(period.advance_interest_applied), release_catch_up=release_catch_up, period_days=days,
        elapsed_days=elapsed, chargeable_days=chargeable,
        lines=[dict(item=item_ids[line.collateral_item_id], base=decimal(line.principal_base),
            rate=decimal(line.monthly_interest_rate), fraction=decimal(line.period_fraction),
            unrounded=decimal(line.unrounded_interest), calculated=decimal(line.calculated_interest),
            advance_applied=decimal(line.advance_interest_applied), recognized=decimal(line.recognized_interest))
            for line in period.lines])


def stored_accrual(accrual, policy, item_ids):
    """Reconstruct exact arithmetic from saved inputs; never trust rounded fractions."""
    fraction = _partial_fraction(policy, accrual.period_start, accrual.period_end,
                                 period_number=accrual.period_number)
    quantum = policy.currency_quantum.normalize() if policy.minimum_first_month else policy.currency_quantum
    lines = []
    for line in accrual.lines.order_by("collateral_item_id"):
        unrounded, calculated = calculate_period_interest(calculation_base=line.principal_base,
            monthly_interest_rate=line.monthly_interest_rate, period_fraction=fraction,
            currency_quantum=quantum)
        if (line.period_fraction != fraction.quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)
                or line.unrounded_interest != unrounded.quantize(Decimal(".000000000001"), rounding=ROUND_HALF_UP)
                or line.calculated_interest != calculated
                or line.advance_interest_applied > calculated
                or line.recognized_interest != calculated - line.advance_interest_applied):
            raise HistoryError("Saved item accrual does not reconcile with its frozen calculation inputs.")
        lines.append(AccrualLinePreview(line.collateral_item_id, line.principal_base,
            line.monthly_interest_rate, fraction, unrounded, calculated,
            line.advance_interest_applied, line.recognized_interest))
    if not lines or {line.collateral_item_id for line in lines} != set(item_ids):
        raise HistoryError("Complete item accrual evidence is required.")
    total = lambda field: sum((getattr(line, field) for line in lines), Decimal(0))
    preview = AccrualPeriodPreview(accrual.period_number, accrual.period_start, accrual.period_end,
        fraction, total("principal_base"), total("unrounded_interest"), total("recognized_interest"),
        accrual.period_end < _add_months(accrual.period_start, 1) - timedelta(days=1),
        total("calculated_interest"), total("advance_interest_applied"), tuple(lines))
    if (accrual.period_fraction != fraction.quantize(Decimal(".0001"), rounding=ROUND_HALF_UP)
            or accrual.calculation_base != preview.calculation_base
            or accrual.unrounded_interest != preview.unrounded_interest.quantize(Decimal(".000000000001"), rounding=ROUND_HALF_UP)
            or accrual.recognized_interest != preview.recognized_interest):
        raise HistoryError("Saved accrual totals do not reconcile with their item evidence.")
    if accrual.loan_event_id:
        # Immutable event evidence is exact; numeric spelling may differ.
        expected = build_pawn_accrual_detail(preview, policy)
        if hasattr(accrual, "release_catch_up"):
            expected["release_catch_up"] = True
        actual = accrual.loan_event.payload.get("accrual")
        def numbers(value):
            if isinstance(value, dict): return {k: numbers(v) for k, v in value.items()}
            if isinstance(value, list): return [numbers(v) for v in value]
            if isinstance(value, str):
                try: return Decimal(value)
                except InvalidOperation: return value
            return value
        if numbers(actual) != numbers(expected):
            raise HistoryError("Exact accrual event evidence differs from the saved calculation inputs.")
    elif preview.recognized_interest:
        raise HistoryError("A positive accrual is missing its financial event.")
    return portable_accrual(preview, policy, item_ids, release_catch_up=hasattr(accrual, "release_catch_up"))
