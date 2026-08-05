"""Shared policy, valuation, and LTV resolution for PawnLoan workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from apps.tenant_apps.loans.domain import (
    CollateralTrancheInput,
    DisbursalFeeInput,
    PawnDisbursalEconomics,
    ValuationMethod,
    calculate_pawn_disbursal_economics,
)
from apps.tenant_apps.loans.models import (
    PawnLoanEconomicPolicy,
    PawnMetalInterestRatePolicy,
)
from apps.tenant_apps.loans.services.economic_policies import (
    resolve_pawn_loan_economic_policy,
    resolve_pawn_loan_fee_policies,
    resolve_pawn_metal_interest_rate_policy,
)
from apps.tenant_apps.rates.facade import (
    RATE_FOUND,
    get_latest_commodity_valuation_rate,
)


@dataclass(frozen=True)
class ResolvedPawnDraftEconomics:
    economics: PawnDisbursalEconomics
    economic_policy: PawnLoanEconomicPolicy
    rate_policies: tuple[PawnMetalInterestRatePolicy, ...]


def resolve_pawn_draft_economics(
    *, workspace_id: int, license_id: int, as_of_date: date, collateral
) -> ResolvedPawnDraftEconomics:
    policy = resolve_pawn_loan_economic_policy(
        workspace_id=workspace_id,
        license_id=license_id,
        as_of_date=as_of_date,
    )
    needs_metal_value = policy.valuation_method in {
        ValuationMethod.CALCULATED_METAL_VALUE.value,
        ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value,
    }
    rate_policies = []
    tranches = []
    valuation_rates = {}
    for index, item in enumerate(collateral, start=1):
        rate_policy = resolve_pawn_metal_interest_rate_policy(
            workspace_id=workspace_id,
            license_id=license_id,
            metal=item.metal,
            as_of_date=as_of_date,
        )
        rate_policies.append(rate_policy)
        metal_rate = None
        if needs_metal_value:
            metal_key = str(getattr(item.metal, "value", item.metal)).upper()
            if metal_key not in valuation_rates:
                lookup = get_latest_commodity_valuation_rate(
                    commodity_code=metal_key,
                    as_of=as_of_date,
                )
                valuation_rates[metal_key] = (
                    lookup.rate.buying_rate if lookup.status == RATE_FOUND else None
                )
            metal_rate = valuation_rates[metal_key]
        tranches.append(
            CollateralTrancheInput(
                reference=str(index),
                metal=item.metal,
                net_weight=item.net_weight,
                purity_percentage=item.purity_percentage,
                allocated_principal=item.allocated_principal,
                monthly_interest_rate=rate_policy.monthly_interest_rate,
                metal_rate_per_unit=metal_rate,
                latest_appraised_value=item.latest_appraised_value,
            )
        )
    fee_inputs = tuple(
        DisbursalFeeInput(
            code=fee.code,
            name=fee.name,
            calculation_type=fee.calculation_type,
            value=fee.value,
            deducted_at_disbursal=fee.deducted_at_disbursal,
        )
        for fee in resolve_pawn_loan_fee_policies(
            workspace_id=workspace_id,
            license_id=license_id,
            as_of_date=as_of_date,
        )
    )
    economics = calculate_pawn_disbursal_economics(
        tranches,
        valuation_method=policy.valuation_method,
        maximum_ltv_ratio=policy.maximum_ltv_ratio,
        advance_interest_periods=policy.advance_interest_periods,
        fees=fee_inputs,
    )
    return ResolvedPawnDraftEconomics(
        economics=economics,
        economic_policy=policy,
        rate_policies=tuple(rate_policies),
    )


__all__ = ["ResolvedPawnDraftEconomics", "resolve_pawn_draft_economics"]
