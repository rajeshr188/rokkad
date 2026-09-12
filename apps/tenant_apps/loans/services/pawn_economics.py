"""Shared policy, valuation, and LTV resolution for PawnLoan workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    CollateralTrancheInput,
    DisbursalFeeInput,
    PawnDisbursalEconomics,
    ValuationMethod,
    calculate_pawn_disbursal_economics,
)
from apps.tenant_apps.loans.models import (
    PawnLoanEconomicPolicy,
    PawnLoanFeePolicy,
    PawnMetalInterestRatePolicy,
)
from apps.tenant_apps.loans.services.economic_policies import (
    resolve_pawn_loan_economic_policy,
    resolve_pawn_loan_fee_policies,
    resolve_pawn_metal_interest_rate_policy,
)
from apps.tenant_apps.loans.selectors.origination_rates import (
    get_origination_quote_rows, require_fresh_quotes, require_current_origination_date,
)


@dataclass(frozen=True)
class ResolvedPawnDraftEconomics:
    economics: PawnDisbursalEconomics
    economic_policy: PawnLoanEconomicPolicy
    rate_policies: tuple[PawnMetalInterestRatePolicy, ...]
    fee_policies: tuple[PawnLoanFeePolicy, ...]
    valuation_quotes: dict
    evaluated_at: datetime


def resolve_pawn_draft_economics(
    *, workspace_id: int, license_id: int, as_of_date: date, collateral,
    require_fresh_rates=False,
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
    collateral = tuple(collateral)
    evaluated_at = timezone.now()
    quote_rows = get_origination_quote_rows(workspace_id=workspace_id, loan_date=as_of_date,
        metals=tuple(str(getattr(item.metal, "value", item.metal)).upper() for item in collateral),
        at=evaluated_at) if needs_metal_value else []
    if require_fresh_rates:
        require_fresh_quotes(quote_rows)
        if needs_metal_value:
            require_current_origination_date(as_of_date, at=evaluated_at)
    valuation_rates = {row["metal"]: row["rate"].buying_rate if row["usable"] else None for row in quote_rows}
    rate_policies = []
    tranches = []
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
    fee_policies = tuple(
        resolve_pawn_loan_fee_policies(
            workspace_id=workspace_id,
            license_id=license_id,
            as_of_date=as_of_date,
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
        for fee in fee_policies
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
        fee_policies=fee_policies,
        valuation_quotes={row["metal"]: row["evidence"] for row in quote_rows},
        evaluated_at=evaluated_at,
    )


__all__ = ["ResolvedPawnDraftEconomics", "resolve_pawn_draft_economics"]
