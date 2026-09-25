"""Effective-dated configuration writes and resolution for PawnLoan economics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from .action_access import require_setup_administration
from apps.tenant_apps.loans.domain import (
    CollateralMetal,
    FeeCalculationType,
    InterestMethod,
    PartialMonthMethod,
    RoundingMethod,
    ValuationMethod,
)
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanSeries,
    PawnLoanEconomicPolicy,
    PawnLoanFeePolicy,
    PawnMetalInterestRatePolicy,
    current_tenant_workspace_id,
)


class PawnEconomicPolicyError(ValueError):
    """Raised when configuration is missing or crosses a tenant boundary."""


@dataclass(frozen=True)
class PawnEconomicConfiguration:
    economic_policy: PawnLoanEconomicPolicy
    gold_rate_policy: PawnMetalInterestRatePolicy
    silver_rate_policy: PawnMetalInterestRatePolicy


@transaction.atomic
def create_pawn_economic_configuration(
    *,
    workspace,
    gold_monthly_interest_rate: Decimal,
    silver_monthly_interest_rate: Decimal,
    actor=None,
    **policy_values,
) -> PawnEconomicConfiguration:
    """Append one complete operator configuration as an atomic policy set."""
    require_setup_administration(workspace.pk, actor)

    economic_policy = create_pawn_loan_economic_policy(
        workspace=workspace, actor=actor, **policy_values
    )
    rate_scope = {
        "workspace": workspace,
        "license": policy_values.get("license"),
        "effective_from": policy_values.get("effective_from"),
        "effective_until": policy_values.get("effective_until"),
        "actor": actor,
    }
    gold_rate_policy = create_pawn_metal_interest_rate_policy(
        metal=CollateralMetal.GOLD,
        monthly_interest_rate=gold_monthly_interest_rate,
        **rate_scope,
    )
    silver_rate_policy = create_pawn_metal_interest_rate_policy(
        metal=CollateralMetal.SILVER,
        monthly_interest_rate=silver_monthly_interest_rate,
        **rate_scope,
    )
    from apps.orgs.audit import AuditLog
    AuditLog.log("SETTINGS_UPDATE", user=actor, company=workspace,
        description="Saved a new calculation policy revision and monthly rates.",
        data={"economic_policy_id": economic_policy.pk, "revision": economic_policy.revision,
              "effective_from": str(economic_policy.effective_from), "license_id": economic_policy.license_id,
              "maximum_ltv_ratio": str(economic_policy.maximum_ltv_ratio),
              "gold_rate_policy_id": gold_rate_policy.pk, "silver_rate_policy_id": silver_rate_policy.pk})
    return PawnEconomicConfiguration(
        economic_policy=economic_policy,
        gold_rate_policy=gold_rate_policy,
        silver_rate_policy=silver_rate_policy,
    )


@transaction.atomic
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
    rounding_method: RoundingMethod | str = RoundingMethod.PER_ACCRUAL_PERIOD,
    currency_quantum: Decimal = Decimal("0.01"),
    effective_from: date | None = None,
    effective_until: date | None = None,
    license: LoanLicense | None = None,
    actor=None,
) -> PawnLoanEconomicPolicy:
    _require_scope(workspace.pk, license)
    require_setup_administration(workspace.pk, actor)
    day = effective_from or timezone.localdate()
    revision = _next_revision(PawnLoanEconomicPolicy, workspace, license=license, effective_from=day)
    policy = PawnLoanEconomicPolicy(
        revision=revision,
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
        rounding_method=RoundingMethod(rounding_method).value,
        currency_quantum=currency_quantum,
        effective_from=day,
        effective_until=effective_until,
        created_by=actor,
    )
    policy.full_clean()
    policy.save()
    return policy


@transaction.atomic
def create_pawn_metal_interest_rate_policy(
    *,
    workspace,
    metal: CollateralMetal | str,
    monthly_interest_rate: Decimal,
    effective_from: date | None = None,
    effective_until: date | None = None,
    license: LoanLicense | None = None,
    series: LoanSeries | None = None,
    actor=None,
) -> PawnMetalInterestRatePolicy:
    _require_scope(workspace.pk, license)
    require_setup_administration(workspace.pk, actor)
    day = effective_from or timezone.localdate()
    revision = _next_revision(PawnMetalInterestRatePolicy, workspace, license=license,
                              series=series, metal=CollateralMetal(metal).value, effective_from=day)
    policy = PawnMetalInterestRatePolicy(
        revision=revision,
        workspace=workspace,
        license=license,
        metal=CollateralMetal(metal).value,
        series=series,
        monthly_interest_rate=monthly_interest_rate,
        effective_from=day,
        effective_until=effective_until,
        created_by=actor,
    )
    policy.full_clean()
    policy.save()
    return policy


@transaction.atomic
def create_pawn_series_interest_rates(*, workspace, series, gold_monthly_interest_rate,
                                     silver_monthly_interest_rate, effective_from, actor):
    """Append both metal overrides together, retaining earlier dated evidence."""
    require_setup_administration(workspace.pk, actor)
    _lock_policy_workspace(workspace)
    series = LoanSeries.objects.select_for_update().select_related("license").get(
        pk=series.pk, workspace=workspace)
    policies = tuple(create_pawn_metal_interest_rate_policy(workspace=workspace,
        license=series.license, series=series, metal=metal, monthly_interest_rate=rate,
        effective_from=effective_from, actor=actor)
        for metal, rate in ((CollateralMetal.GOLD, gold_monthly_interest_rate),
                            (CollateralMetal.SILVER, silver_monthly_interest_rate)))
    from apps.orgs.audit import AuditLog
    AuditLog.log("UPDATE", user=actor, company=workspace,
        description="Added series-specific monthly interest rates.",
        data={"series_id": series.pk, "policy_ids": [p.pk for p in policies],
              "effective_from": str(effective_from), "gold": str(gold_monthly_interest_rate),
              "silver": str(silver_monthly_interest_rate)})
    return policies


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
    require_setup_administration(workspace.pk, actor)
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
        policy = current.filter(license_id=license_id).order_by("-effective_from", "-revision", "-id").first()
    if policy is None:
        policy = current.filter(license__isnull=True).order_by("-effective_from", "-revision", "-id").first()
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
    series_id: int | None = None,
) -> PawnMetalInterestRatePolicy:
    _require_scope_ids(workspace_id, license_id)
    metal_value = CollateralMetal(metal).value
    current = _current_rows(
        PawnMetalInterestRatePolicy, workspace_id, as_of_date
    ).filter(metal=metal_value)
    policy = None
    if series_id is not None:
        if not LoanSeries.objects.filter(pk=series_id, workspace_id=workspace_id, license_id=license_id).exists():
            raise PawnEconomicPolicyError("Series must belong to the policy workspace and license.")
        policy = current.filter(series_id=series_id).order_by("-effective_from", "-revision", "-id").first()
    current = current.filter(series__isnull=True)
    if policy is None and license_id is not None:
        policy = current.filter(license_id=license_id).order_by("-effective_from", "-revision", "-id").first()
    if policy is None:
        policy = current.filter(license__isnull=True).order_by("-effective_from", "-revision", "-id").first()
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


def _lock_policy_workspace(workspace):
    # Match origination/monitoring lock order; an empty policy scope cannot lock.
    from apps.orgs.models import Company
    Company.all_objects.select_for_update().get(pk=workspace.pk)


def _next_revision(model, workspace, **scope):
    _lock_policy_workspace(workspace)
    return (model.objects.filter(workspace=workspace, **scope).aggregate(value=Max("revision"))["value"] or 0) + 1


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
    "PawnEconomicConfiguration",
    "PawnEconomicPolicyError",
    "create_pawn_economic_configuration",
    "create_pawn_loan_economic_policy",
    "create_pawn_loan_fee_policy",
    "create_pawn_metal_interest_rate_policy",
    "resolve_pawn_loan_economic_policy",
    "resolve_pawn_loan_fee_policies",
    "resolve_pawn_metal_interest_rate_policy",
]
