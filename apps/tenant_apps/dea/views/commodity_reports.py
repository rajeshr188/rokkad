from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse

from apps.tenant_apps.dea.models import Commodity, CommodityMovement, ExposureLine
from apps.tenant_apps.dea.services.exposure_report import (
    ACTIVE_EXPOSURE_STATUSES,
    build_exposure_report,
)
from apps.tenant_apps.dea.services.metal_balance_report import build_metal_balance_report
from apps.tenant_apps.dea.services.valuation_report import build_valuation_report
from apps.tenant_apps.party.models import Party


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _selected_commodity(request):
    commodity_id = request.GET.get("commodity")
    if not commodity_id:
        return None
    return Commodity.objects.filter(pk=commodity_id).first()


def _selected_party(request):
    party_id = request.GET.get("party")
    if not party_id:
        return None
    return Party.objects.filter(pk=party_id).first()


def _commodity_filter_context(request):
    return {
        "commodities": Commodity.objects.filter(is_active=True).order_by("code"),
        "parties": Party.objects.order_by("display_name"),
        "selected_commodity": request.GET.get("commodity", ""),
        "selected_party": request.GET.get("party", ""),
        "selected_as_of": request.GET.get("as_of", ""),
    }


@login_required
def metal_balance_report(request):
    commodity = _selected_commodity(request)
    party = _selected_party(request)
    as_of = _parse_date(request.GET.get("as_of"))
    fixed_status = request.GET.get("fixed_status") or None

    report = build_metal_balance_report(
        as_of=as_of,
        commodity=commodity,
        party=party,
        fixed_status=fixed_status,
    )
    context = {
        "title": "Metal Balance",
        "report": report,
        "fixed_statuses": CommodityMovement.FixedStatus.choices,
        "selected_fixed_status": fixed_status or "",
        **_commodity_filter_context(request),
    }
    return TemplateResponse(request, "dea/commodity_reports/metal_balance.html", context)


@login_required
def exposure_report(request):
    commodity = _selected_commodity(request)
    party = _selected_party(request)
    as_of = _parse_date(request.GET.get("as_of"))
    side = request.GET.get("side") or None
    status = request.GET.get("status") or None
    statuses = (status,) if status else ACTIVE_EXPOSURE_STATUSES

    report = build_exposure_report(
        as_of=as_of,
        commodity=commodity,
        party=party,
        side=side,
        statuses=statuses,
        include_valuation=request.GET.get("include_valuation") == "1",
    )
    context = {
        "title": "Commodity Exposure",
        "report": report,
        "sides": ExposureLine.Side.choices,
        "statuses": ExposureLine.Status.choices,
        "selected_side": side or "",
        "selected_status": status or "",
        "include_valuation": report.include_valuation,
        **_commodity_filter_context(request),
    }
    return TemplateResponse(request, "dea/commodity_reports/exposure.html", context)


@login_required
def valuation_report(request):
    commodity = _selected_commodity(request)
    party = _selected_party(request)
    as_of = _parse_date(request.GET.get("as_of"))
    currency = request.GET.get("currency") or "INR"
    purity = request.GET.get("purity") or "24k"

    report = build_valuation_report(
        as_of=as_of,
        commodity=commodity,
        party=party,
        valuation_currency=currency,
        valuation_purity=purity,
    )
    context = {
        "title": "Commodity Valuation",
        "report": report,
        "selected_currency": report.valuation_currency,
        "selected_purity": report.valuation_purity,
        **_commodity_filter_context(request),
    }
    return TemplateResponse(request, "dea/commodity_reports/valuation.html", context)
