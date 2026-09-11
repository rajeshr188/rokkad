"""Rates public facade for cross-app read access."""

from dataclasses import dataclass
from datetime import date, datetime
from apps.tenancy.context import current_workspace_id


@dataclass(frozen=True)
class CommodityRateLookupResult:
    status: str
    rate: object | None = None
    commodity_code: str = ""
    metal: str = ""
    currency: str = ""
    purity: str = ""


COMMODITY_TO_RATE_METAL = {
    "GOLD": "Gold",
    "SILVER": "Silver",
}

RATE_FOUND = "FOUND"
RATE_MISSING = "MISSING_RATE"
RATE_UNSUPPORTED_COMMODITY = "UNSUPPORTED_COMMODITY"
RATE_UNSUPPORTED_CURRENCY = "UNSUPPORTED_CURRENCY"
RATE_UNSUPPORTED_PURITY = "UNSUPPORTED_PURITY"


def get_workspace_rate_dashboard_summary():
    from apps.tenant_apps.rates.models import RateSource

    return {
        "gold_rate": get_latest_commodity_valuation_rate(commodity_code="GOLD").rate,
        "silver_rate": get_latest_commodity_valuation_rate(commodity_code="SILVER").rate,
        "has_rate_sources": RateSource.objects.filter(workspace_id=current_workspace_id()).exists(),
    }


def get_latest_commodity_valuation_rate(
    *,
    commodity_code: str,
    as_of: date | datetime | None = None,
    currency: str = "INR",
    purity: str = "24k",
) -> CommodityRateLookupResult:
    from apps.tenant_apps.rates.models import Rate
    from django.utils import timezone

    normalized_code = (commodity_code or "").strip().upper()
    normalized_currency = (currency or "").strip().upper()
    normalized_purity = (purity or "").strip()
    metal = COMMODITY_TO_RATE_METAL.get(normalized_code)

    if not metal:
        return CommodityRateLookupResult(
            status=RATE_UNSUPPORTED_COMMODITY,
            commodity_code=normalized_code,
            currency=normalized_currency,
            purity=normalized_purity,
        )

    if normalized_currency not in {choice[0] for choice in Rate.Currency.choices}:
        return CommodityRateLookupResult(
            status=RATE_UNSUPPORTED_CURRENCY,
            commodity_code=normalized_code,
            metal=metal,
            currency=normalized_currency,
            purity=normalized_purity,
        )

    if normalized_purity not in {choice[0] for choice in Rate.Purity.choices}:
        return CommodityRateLookupResult(
            status=RATE_UNSUPPORTED_PURITY,
            commodity_code=normalized_code,
            metal=metal,
            currency=normalized_currency,
            purity=normalized_purity,
        )

    rates = Rate.objects.filter(
        workspace_id=current_workspace_id(),
        metal=metal,
        currency=normalized_currency,
        purity=normalized_purity,
        successor__isnull=True,
        is_withdrawal=False,
    )
    as_of = as_of if as_of is not None else timezone.now()
    if isinstance(as_of, datetime):
        rates = rates.filter(effective_at__lte=as_of)
    else:
        rates = rates.filter(effective_at__date__lte=as_of)

    rate = rates.order_by("-effective_at", "-timestamp", "-pk").first()
    if not rate:
        return CommodityRateLookupResult(
            status=RATE_MISSING,
            commodity_code=normalized_code,
            metal=metal,
            currency=normalized_currency,
            purity=normalized_purity,
        )

    return CommodityRateLookupResult(
        status=RATE_FOUND,
        rate=rate,
        commodity_code=normalized_code,
        metal=metal,
        currency=normalized_currency,
        purity=normalized_purity,
    )
