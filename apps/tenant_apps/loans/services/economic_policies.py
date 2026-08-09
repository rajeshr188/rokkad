"""Effective-dated configuration writes and resolution for PawnLoan economics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    CollateralMetal,
    FeeCalculationType,
    InterestMethod,
    PartialMonthMethod,
    RoundingMethod,
    ValuationMethod,
)
from apps.tenant_apps.loans.models import (
    LoanLicense,
    PawnLoanEconomicPolicy,
    PawnLoanFeePolicy,
    PawnMetalInterestRatePolicy,
    current_tenant_workspace_id,
)


class PawnEconomicPolicyError(ValueError):
    """Raised when configuration is missing or crosses a tenant boundary."""


def create_pawn_loan_economic_policy(
    *,
    workspace,
    valuation_method: ValuationMethod | str,
    maximum_ltv_ratio: Decimal,
    advance_interest_periods: int = 1,
    interest_method: InterestMethod | str = InterestMethod.SIMPLE,
    partial_month_method: PartialMonthMethod | str = PartialMonthMethod.FULL_MONTH,
    partial_month_cutoff_days: int = 15,
    partial_month_lower_fraction: Decimal = Decimal("0.5"),
    capitalization_interval_periods: int = 12,
    accounting_recognition: AccountingRecognition | str = AccountingRecognition.CASH,
    rounding_method: RoundingMethod | str = RoundingMethod.PER_ACCRUAL_PERIOD,
    currency_quantum: Decimal = Decimal("0.01"),
    effective_from: date | None = None,
    effective_until: date | None = None,
    license: LoanLicense | None = None,
    actor=None,
) -> PawnLoanEconomicPolicy:
    _require_scope(workspace.pk, license)
    policy = PawnLoanEconomicPolicy(
        workspace=workspace,
        license=license,
        valuation_method=ValuationMethod(valuation_method).value,
        maximum_ltv_ratio=maximum_ltv_ratio,
        advance_interest_periods=advance_interest_periods,
        interest_method=InterestMethod(interest_method).value,
        partial_month_method=PartialMonthMethod(partial_month_method).value,
        partial_month_cutoff_days=partial_month_cutoff_days,
        partial_month_lower_fraction=partial_month_lower_fraction,
        capitalization_interval_periods=capitalization_interval_periods,
        accounting_recognition=AccountingRecognition(accounting_recognition).value,
        rounding_method=RoundingMethod(rounding_method).value,
        currency_quantum=currency_quantum,
        effective_from=effective_from or timezone.localdate(),
        effective_until=effective_until,
        created_by=actor,
    )
    policy.full_clean()
    policy.save()
    return policy


def create_pawn_metal_interest_rate_policy(
    *,
    workspace,
    metal: CollateralMetal | str,
    monthly_interest_rate: Decimal,
    effective_from: date | None = None,
    effective_until: date | None = None,
    license: LoanLicense | None = None,
    actor=None,
) -> PawnMetalInterestRatePolicy:
    _require_scope(workspace.pk, license)
    policy = PawnMetalInterestRatePolicy(
        workspace=workspace,
        license=license,
        metal=CollateralMetal(metal).value,
        monthly_interest_rate=monthly_interest_rate,
        effective_from=effective_from or timezone.localdate(),
        effective_until=effective_until,
        created_by=actor,
    )
    policy.full_clean()
    policy.save()
    return policy


def create_pawn_loan_fee_policy(
    *,
    workspace,
    code: str,
    name: str,
    calculation_type: FeeCalculationType | str,
    value: Decimal,
    deducted_at_disbursal: bool = True,
    effective_from: date | None = None,
    effective_until: date | None = None,
    license: LoanLicense | None = None,
    actor=None,
) -> PawnLoanFeePolicy:
    _require_scope(workspace.pk, license)
    policy = PawnLoanFeePolicy(
        workspace=workspace,
        license=license,
        code=code.strip().upper(),
        name=name.strip(),
        calculation_type=FeeCalculationType(calculation_type).value,
        value=value,
        deducted_at_disbursal=deducted_at_disbursal,
        effective_from=effective_from or timezone.localdate(),
        effective_until=effective_until,
        created_by=actor,
    )
    policy.full_clean()
    policy.save()
    return policy


def resolve_pawn_loan_economic_policy(
    *, workspace_id: int, license_id: int | None, as_of_date: date
) -> PawnLoanEconomicPolicy:
    _require_scope_ids(workspace_id, license_id)
    current = _current_rows(PawnLoanEconomicPolicy, workspace_id, as_of_date)
    policy = None
    if license_id is not None:
        policy = current.filter(license_id=license_id).order_by("-effective_from", "-id").first()
    if policy is None:
        policy = current.filter(license__isnull=True).order_by("-effective_from", "-id").first()
    if policy is None:
        raise PawnEconomicPolicyError(
            "No active PawnLoan economic policy applies on the requested date."
        )
    return policy


def resolve_pawn_metal_interest_rate_policy(
    *,
    workspace_id: int,
    license_id: int | None,
    metal: CollateralMetal | str,
    as_of_date: date,
) -> PawnMetalInterestRatePolicy:
    _require_scope_ids(workspace_id, license_id)
    metal_value = CollateralMetal(metal).value
    current = _current_rows(
        PawnMetalInterestRatePolicy, workspace_id, as_of_date
    ).filter(metal=metal_value)
    policy = None
    if license_id is not None:
        policy = current.filter(license_id=license_id).order_by("-effective_from", "-id").first()
    if policy is None:
        policy = current.filter(license__isnull=True).order_by("-effective_from", "-id").first()
    if policy is None:
        raise PawnEconomicPolicyError(
            f"No active {metal_value} PawnLoan interest-rate policy applies on the requested date."
        )
    return policy


def resolve_pawn_loan_fee_policies(
    *, workspace_id: int, license_id: int | None, as_of_date: date
) -> tuple[PawnLoanFeePolicy, ...]:
    _require_scope_ids(workspace_id, license_id)
    current = _current_rows(PawnLoanFeePolicy, workspace_id, as_of_date)
    resolved = _latest_by_code(current.filter(license__isnull=True))
    if license_id is not None:
        resolved.update(_latest_by_code(current.filter(license_id=license_id)))
    return tuple(resolved[code] for code in sorted(resolved))


def _current_rows(model, workspace_id, as_of_date):
    return model.objects.filter(
        workspace_id=workspace_id,
        is_active=True,
        effective_from__lte=as_of_date,
    ).filter(Q(effective_until__isnull=True) | Q(effective_until__gte=as_of_date))


def _latest_by_code(queryset):
    resolved = {}
    for policy in queryset.order_by("code", "-effective_from", "-id"):
        resolved.setdefault(policy.code, policy)
    return resolved


def _require_scope(workspace_id, license):
    _require_scope_ids(workspace_id, license.pk if license else None)
    if license and license.workspace_id != workspace_id:
        raise PawnEconomicPolicyError("The license must belong to the policy workspace.")


def _require_scope_ids(workspace_id, license_id):
    active_workspace_id = current_tenant_workspace_id()
    if active_workspace_id is None:
        raise PawnEconomicPolicyError("PawnLoan policy operations require an active tenant schema.")
    if workspace_id != active_workspace_id:
        raise PawnEconomicPolicyError("The policy must belong to the active workspace.")
    if license_id is not None and not LoanLicense.objects.filter(
        pk=license_id, workspace_id=workspace_id
    ).exists():
        raise PawnEconomicPolicyError("The license must belong to the policy workspace.")


__all__ = [
    "PawnEconomicPolicyError",
    "create_pawn_loan_economic_policy",
    "create_pawn_loan_fee_policy",
    "create_pawn_metal_interest_rate_policy",
    "resolve_pawn_loan_economic_policy",
    "resolve_pawn_loan_fee_policies",
    "resolve_pawn_metal_interest_rate_policy",
]
