"""Read the effective operator agreement view without another policy resolver."""

from django.db.models import Q
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import LoanProductVersion
from apps.tenant_apps.loans.services.economic_policies import (
    resolve_pawn_loan_economic_policy,
    resolve_pawn_metal_interest_rate_policy,
    resolve_pawn_loan_fee_policies,
    PawnEconomicPolicyError,
)
from apps.tenant_apps.loans.services.entry_purpose import (
    new_loan_entry_purpose as default_entry_purpose,
)
from apps.tenant_apps.loans.services.origination_summary import (
    calculation_terms,
    policy_source,
)


def effective_lending_terms(*, workspace, license=None, series=None, day):
    if current_workspace_id() != workspace.pk:
        raise ValueError("Select the matching Workspace.")
    if series:
        if series.workspace_id != workspace.pk or (
            license and series.license_id != license.pk
        ):
            raise ValueError("Choose a register in this scope.")
        license = series.license
    if license and license.workspace_id != workspace.pk:
        raise ValueError("Choose a licence in this Workspace.")
    args = dict(
        workspace_id=workspace.pk,
        license_id=license.pk if license else None,
        series_id=series.pk if series else None,
        as_of_date=day,
    )
    result = dict(
        day=day,
        scope=(
            f"{license.license_number} / {series.pawn_display_name}"
            if series
            else license.license_number if license else "Business default"
        ),
        rates=[],
        errors=[],
    )
    try:
        policy = resolve_pawn_loan_economic_policy(**args)
        result.update(
            policy=policy,
            maximum_ltv_percent=policy.maximum_ltv_ratio * 100,
            source=policy_source(policy),
            terms=calculation_terms(
                {
                    key: getattr(policy, key)
                    for key in (
                        "interest_method",
                        "partial_month_method",
                        "partial_month_cutoff_days",
                        "partial_month_lower_fraction",
                        "advance_interest_periods",
                        "currency_quantum",
                        "rounding_method",
                        "minimum_first_month",
                        "capitalization_interval_periods",
                    )
                }
            ),
        )
    except PawnEconomicPolicyError as exc:
        result["errors"].append(str(exc))
    for metal in ("GOLD", "SILVER", "BRONZE"):
        try:
            rate = resolve_pawn_metal_interest_rate_policy(**args, metal=metal)
            result["rates"].append(
                dict(
                    metal=metal.title(),
                    value=rate.monthly_interest_rate,
                    source=policy_source(rate),
                )
            )
        except PawnEconomicPolicyError:
            pass
    result["fees"] = resolve_pawn_loan_fee_policies(
        workspace_id=workspace.pk,
        license_id=license.pk if license else None,
        as_of_date=day,
    )
    result["entry"] = default_entry_purpose(
        workspace=workspace,
        license_id=license.pk if license else None,
        series_id=series.pk if series else None,
    )
    result["products"] = list(
        LoanProductVersion.objects.filter(
            workspace=workspace, status="ACTIVE", product__is_active=True
        )
        .filter(Q(available_from__isnull=True) | Q(available_from__lte=day))
        .filter(Q(available_until__isnull=True) | Q(available_until__gte=day))
        .select_related("product")
        .order_by("product__name")[:25]
    )
    return result
