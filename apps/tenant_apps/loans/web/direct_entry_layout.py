"""Read-only standing-policy guidance for the direct New loan editor."""
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.tenant_apps.loans.services.economic_policies import (
    resolve_pawn_loan_economic_policy, resolve_pawn_metal_interest_rate_policy,
)


def direct_entry_layout_context(request, form):
    if not request.loan_entry_presentation.get("direct_new_entry"):
        return {}
    result = dict(direct_standing_tenure=None, direct_valuation_method="",
                  direct_product_compact=False, direct_tenure_open=True,
                  direct_date_open=True)
    try:
        series = form.fields["series"].clean(form["series"].value())
        day = form.fields["loan_date"].clean(form["loan_date"].value())
    except ValidationError:
        return result
    result["direct_date_open"] = bool(form["loan_date"].errors) or day != timezone.localdate()
    products = list(form.fields["product_version"].queryset.filter(
        Q(available_from__isnull=True) | Q(available_from__lte=day),
    ).filter(Q(available_until__isnull=True) | Q(available_until__gte=day))[:2])
    if len(products) == 1 and str(form["product_version"].value()) == str(products[0].pk):
        result.update(direct_product_compact=True, direct_selected_product=products[0])
    values = dict(workspace_id=request.loans_workspace.pk, license_id=series.license_id,
                  series_id=series.pk, as_of_date=day)
    try:
        policy = resolve_pawn_loan_economic_policy(**values)
    except ValueError:
        return result
    result.update(direct_standing_tenure=policy.default_tenure_months,
                  direct_valuation_method=policy.valuation_method)
    result["direct_tenure_open"] = bool(form["tenure_months"].errors) or not policy.default_tenure_months or (
        str(form["tenure_months"].value()) != str(policy.default_tenure_months))
    for metal in ("GOLD", "SILVER"):
        try:
            rate = resolve_pawn_metal_interest_rate_policy(**values, metal=metal)
        except ValueError:
            continue
        result["direct_" + metal.lower() + "_rate"] = rate.monthly_interest_rate
    return result
