"""Quote guidance using the same reference lookup as loan valuation."""

from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate


def get_metal_rate_readiness(*, workspace, as_of_date, metals=("GOLD", "SILVER")):
    if current_workspace_id() != workspace.pk:
        raise ValueError("Rate readiness requires the active Workspace.")
    rows = []
    for metal in dict.fromkeys(metals):
        if metal not in {"GOLD", "SILVER"}:
            raise ValueError("Unsupported collateral metal.")
        lookup = get_latest_commodity_valuation_rate(
            commodity_code=metal, as_of=as_of_date, currency="INR", purity="24k",
        )
        rate = lookup.rate
        usable = lookup.status == RATE_FOUND and rate.buying_rate > 0
        rows.append({
            "metal": metal, "label": metal.title(), "usable": usable,
            "rate": rate,
            "age_days": (as_of_date - timezone.localtime(rate.effective_at).date()).days if rate else None,
        })
    return rows
