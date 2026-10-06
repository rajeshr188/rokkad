"""Shared policy, valuation, and LTV resolution for PawnLoan workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

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
from .origination_settings import maximum_quote_age_days


@dataclass(frozen=True)
class ResolvedPawnDraftEconomics:
    economics: PawnDisbursalEconomics
    economic_policy: PawnLoanEconomicPolicy
    rate_policies: tuple[PawnMetalInterestRatePolicy, ...]
    fee_policies: tuple[PawnLoanFeePolicy, ...]
    valuation_quotes: dict
    evaluated_at: datetime
    maximum_quote_age_days: int | None = None


def resolve_pawn_draft_economics(
    *, workspace_id: int, license_id: int, as_of_date: date, collateral,
    require_fresh_rates=False,
    series_id: int | None = None,
    historical_context=None,
) -> ResolvedPawnDraftEconomics:
    collateral = tuple(collateral)
    if historical_context is not None:
        from .historical_origination import historical_policies
        policy, historical_rates, historical_fees = historical_policies(
            historical_context, collateral, license_id=license_id, series_id=series_id)
    else:
        policy = resolve_pawn_loan_economic_policy(
            series_id=series_id,
            workspace_id=workspace_id,
            license_id=license_id,
            as_of_date=as_of_date,
        )
    needs_metal_value = policy.valuation_method in {
        ValuationMethod.CALCULATED_METAL_VALUE.value,
        ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL.value,
    }
    evaluated_at = timezone.now()
    quote_age = maximum_quote_age_days(workspace_id) if historical_context is None and needs_metal_value else None
    if require_fresh_rates and needs_metal_value and historical_context is None:
        # Reject the date before looking up quotes at that date. Today's newly
        # entered quote cannot repair a review that still selects yesterday.
        require_current_origination_date(as_of_date, at=evaluated_at)
    quote_rows = get_origination_quote_rows(workspace_id=workspace_id, loan_date=as_of_date,
        metals=tuple(str(getattr(item.metal, "value", item.metal)).upper() for item in collateral),
        at=evaluated_at, maximum_age_days=quote_age) if needs_metal_value and historical_context is None else []
    if require_fresh_rates and historical_context is None:
        require_fresh_quotes(quote_rows)
    valuation_rates = {row["metal"]: row["rate"].buying_rate if row["usable"] else None for row in quote_rows}
    valuation_quotes = {row["metal"]: row["evidence"] for row in quote_rows}
    if historical_context is not None:
        from .historical_origination import historical_quotes
        valuation_quotes = historical_quotes(historical_context, method=policy.valuation_method,
            metals=tuple(str(getattr(item.metal, "value", item.metal)).upper() for item in collateral))
        valuation_rates = {metal: Decimal(row["buying_rate"]) for metal, row in valuation_quotes.items()}
    rate_policies = []
    tranches = []
    for index, item in enumerate(collateral, start=1):
        rate_policy = historical_rates[index - 1] if historical_context is not None else resolve_pawn_metal_interest_rate_policy(
            series_id=series_id,
            workspace_id=workspace_id,
            license_id=license_id,
            metal=item.metal,
            as_of_date=as_of_date,
        )
        rate_policies.append(rate_policy)
        override = getattr(item, "interest_rate_override", None)
        if override is not None and not getattr(item, "interest_override_reason", "").strip():
            raise ValueError("An interest override requires a reason.")
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
                monthly_interest_rate=rate_policy.monthly_interest_rate if override is None else override,
                metal_rate_per_unit=metal_rate,
                latest_appraised_value=item.latest_appraised_value,
            )
        )
    fee_policies = historical_fees if historical_context is not None else tuple(
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
        currency_quantum=policy.currency_quantum,
        interest_policy_version=2,
    )
    return ResolvedPawnDraftEconomics(
        economics=economics,
        economic_policy=policy,
        rate_policies=tuple(rate_policies),
        fee_policies=fee_policies,
        valuation_quotes=valuation_quotes,
        evaluated_at=evaluated_at,
        maximum_quote_age_days=quote_age,
    )


__all__ = ["ResolvedPawnDraftEconomics", "resolve_pawn_draft_economics"]
