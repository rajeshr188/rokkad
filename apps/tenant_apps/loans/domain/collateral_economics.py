"""Database-free collateral-tranche and net-disbursal economics."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from .policies import ValuationMethod
from .vocabulary import CollateralMetal, StringEnum


ZERO = Decimal("0")


class FeeCalculationType(StringEnum):
    FIXED = "FIXED"
    PERCENTAGE = "PERCENTAGE"


class CollateralEconomicsError(ValueError):
    """Economic validation failure with optional form-addressable context."""

    def __init__(self, message, *, reference=None, field=None):
        super().__init__(message)
        self.reference = str(reference) if reference is not None else None
        self.field = field


@dataclass(frozen=True)
class CollateralTrancheInput:
    reference: str
    metal: CollateralMetal
    net_weight: Decimal
    purity_percentage: Decimal
    allocated_principal: Decimal
    monthly_interest_rate: Decimal
    metal_rate_per_unit: Decimal | None
    latest_appraised_value: Decimal | None


@dataclass(frozen=True)
class CollateralTrancheResult:
    reference: str
    metal: CollateralMetal
    allocated_principal: Decimal
    monthly_interest_rate: Decimal
    calculated_metal_value: Decimal | None
    latest_appraised_value: Decimal | None
    selected_value: Decimal
    maximum_principal: Decimal
    monthly_interest: Decimal
    advance_interest: Decimal


@dataclass(frozen=True)
class DisbursalFeeInput:
    code: str
    name: str
    calculation_type: FeeCalculationType
    value: Decimal
    deducted_at_disbursal: bool = True


@dataclass(frozen=True)
class DisbursalFeeResult:
    code: str
    name: str
    amount: Decimal
    deducted_at_disbursal: bool


@dataclass(frozen=True)
class PawnDisbursalEconomics:
    tranches: tuple[CollateralTrancheResult, ...]
    fees: tuple[DisbursalFeeResult, ...]
    gross_principal: Decimal
    effective_monthly_rate: Decimal
    monthly_interest: Decimal
    advance_interest_periods: int
    advance_interest: Decimal
    deducted_fees: Decimal
    net_disbursed: Decimal


def calculate_pawn_disbursal_economics(
    tranches,
    *,
    valuation_method,
    maximum_ltv_ratio,
    advance_interest_periods=1,
    fees=(),
    currency_quantum=Decimal("0.01"),
):
    """Validate item LTV and derive exact gross, deduction, and net totals."""

    try:
        method = ValuationMethod(valuation_method)
        ltv = Decimal(str(maximum_ltv_ratio))
        quantum = Decimal(str(currency_quantum)).normalize()
        periods = int(advance_interest_periods)
    except (TypeError, ValueError) as exc:
        raise CollateralEconomicsError("Collateral economic policy is invalid.") from exc
    if not ZERO < ltv <= Decimal("1"):
        raise CollateralEconomicsError("Maximum LTV must be above zero and at most one.")
    if not 0 <= periods <= 12:
        raise CollateralEconomicsError(
            "Advance-interest periods must be between zero and twelve."
        )
    if quantum <= ZERO:
        raise CollateralEconomicsError("Currency quantum must be positive.")

    results = tuple(
        _calculate_tranche(
            item,
            method=method,
            maximum_ltv_ratio=ltv,
            advance_interest_periods=periods,
            quantum=quantum,
        )
        for item in tranches
    )
    if not results:
        raise CollateralEconomicsError("At least one collateral tranche is required.")
    gross = sum((item.allocated_principal for item in results), ZERO).quantize(
        quantum
    )
    if gross <= ZERO:
        raise CollateralEconomicsError("Gross principal must be positive.")
    monthly_interest = sum(
        (item.monthly_interest for item in results), ZERO
    ).quantize(quantum)
    advance_interest = sum(
        (item.advance_interest for item in results), ZERO
    ).quantize(quantum)
    fee_results = tuple(_calculate_fee(item, gross, quantum) for item in fees)
    deducted_fees = sum(
        (item.amount for item in fee_results if item.deducted_at_disbursal), ZERO
    ).quantize(quantum)
    net = (gross - advance_interest - deducted_fees).quantize(quantum)
    if net <= ZERO:
        raise CollateralEconomicsError(
            "Advance interest and deducted fees must leave a positive net disbursal."
        )
    effective_rate = (
        monthly_interest / gross * Decimal("100")
    ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return PawnDisbursalEconomics(
        tranches=results,
        fees=fee_results,
        gross_principal=gross,
        effective_monthly_rate=effective_rate,
        monthly_interest=monthly_interest,
        advance_interest_periods=periods,
        advance_interest=advance_interest,
        deducted_fees=deducted_fees,
        net_disbursed=net,
    )


def _calculate_tranche(item, *, method, maximum_ltv_ratio, advance_interest_periods, quantum):
    try:
        metal = CollateralMetal(item.metal)
        net_weight = Decimal(str(item.net_weight))
        purity = Decimal(str(item.purity_percentage))
        principal = Decimal(str(item.allocated_principal)).quantize(quantum)
        rate = Decimal(str(item.monthly_interest_rate))
        metal_rate = (
            Decimal(str(item.metal_rate_per_unit))
            if item.metal_rate_per_unit is not None
            else None
        )
        appraisal = (
            Decimal(str(item.latest_appraised_value)).quantize(quantum)
            if item.latest_appraised_value is not None
            else None
        )
    except (TypeError, ValueError) as exc:
        raise CollateralEconomicsError(
            f"Collateral {item.reference} has invalid economic values."
        ) from exc
    if net_weight <= ZERO or not ZERO < purity <= Decimal("100"):
        raise CollateralEconomicsError(
            f"Collateral {item.reference} has invalid weight or purity."
        )
    if principal <= ZERO or rate < ZERO:
        raise CollateralEconomicsError(
            f"Collateral {item.reference} requires positive principal and a non-negative rate."
        )
    calculated = None
    if metal_rate is not None:
        if metal_rate <= ZERO:
            raise CollateralEconomicsError(
                f"Collateral {item.reference} metal value rate must be positive."
            )
        calculated = (
            metal_rate * net_weight * purity / Decimal("100")
        ).quantize(quantum, rounding=ROUND_DOWN)
    selected = _selected_value(
        item.reference,
        method=method,
        calculated=calculated,
        appraisal=appraisal,
    )
    maximum = (selected * maximum_ltv_ratio).quantize(
        quantum, rounding=ROUND_DOWN
    )
    if principal > maximum:
        raise CollateralEconomicsError(
            f"Collateral {item.reference} allocation {principal} exceeds its maximum {maximum} at the configured LTV.",
            reference=item.reference,
            field="allocated_principal",
        )
    monthly = (principal * rate / Decimal("100")).quantize(
        quantum, rounding=ROUND_HALF_UP
    )
    advance = (monthly * advance_interest_periods).quantize(
        quantum, rounding=ROUND_HALF_UP
    )
    return CollateralTrancheResult(
        reference=str(item.reference),
        metal=metal,
        allocated_principal=principal,
        monthly_interest_rate=rate,
        calculated_metal_value=calculated,
        latest_appraised_value=appraisal,
        selected_value=selected,
        maximum_principal=maximum,
        monthly_interest=monthly,
        advance_interest=advance,
    )


def _selected_value(reference, *, method, calculated, appraisal):
    if method == ValuationMethod.CALCULATED_METAL_VALUE:
        value = calculated
        missing = "a current metal valuation rate"
    elif method == ValuationMethod.LATEST_APPRAISAL:
        value = appraisal
        missing = "a staff appraisal"
    else:
        value = min(calculated, appraisal) if calculated is not None and appraisal is not None else None
        missing = "both a current metal valuation rate and a staff appraisal"
    if value is None or value <= ZERO:
        raise CollateralEconomicsError(
            f"Collateral {reference} requires {missing} for the configured valuation method."
        )
    return value


def _calculate_fee(item, gross, quantum):
    try:
        kind = FeeCalculationType(item.calculation_type)
        value = Decimal(str(item.value))
    except (TypeError, ValueError) as exc:
        raise CollateralEconomicsError(f"Fee {item.code} is invalid.") from exc
    if not str(item.code or "").strip() or not str(item.name or "").strip() or value < ZERO:
        raise CollateralEconomicsError("Fee code, name, and non-negative value are required.")
    amount = value if kind == FeeCalculationType.FIXED else gross * value / Decimal("100")
    return DisbursalFeeResult(
        code=str(item.code),
        name=str(item.name),
        amount=amount.quantize(quantum, rounding=ROUND_HALF_UP),
        deducted_at_disbursal=bool(item.deducted_at_disbursal),
    )


__all__ = [
    "CollateralEconomicsError",
    "CollateralTrancheInput",
    "CollateralTrancheResult",
    "DisbursalFeeInput",
    "DisbursalFeeResult",
    "FeeCalculationType",
    "PawnDisbursalEconomics",
    "calculate_pawn_disbursal_economics",
]
