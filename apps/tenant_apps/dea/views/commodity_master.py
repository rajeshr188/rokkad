from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.dea.forms_commodity import CommodityCreateForm, CommodityUpdateForm
from apps.tenant_apps.dea.models import Commodity
from apps.tenant_apps.dea.services.commodity_account_setup import (
    setup_standard_commodity_accounts,
)

from .access import dea_accountant_required


@dea_accountant_required
def commodity_list(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "active").strip().lower()

    commodities = Commodity.objects.annotate(
        account_count=Count("commodity_accounts", distinct=True)
    ).order_by("code")

    if query:
        commodities = commodities.filter(
            Q(code__icontains=query) | Q(name__icontains=query)
        )

    if status == "inactive":
        commodities = commodities.filter(is_active=False)
    elif status != "all":
        status = "active"
        commodities = commodities.filter(is_active=True)

    context = {
        "title": "Commodity Master",
        "commodities": commodities,
        "query": query,
        "status": status,
        "counts": {
            "all": Commodity.objects.count(),
            "active": Commodity.objects.filter(is_active=True).count(),
            "inactive": Commodity.objects.filter(is_active=False).count(),
        },
    }
    return TemplateResponse(request, "dea/commodity_master/list.html", context)


@dea_accountant_required
def commodity_detail(request, commodity_id):
    commodity = get_object_or_404(
        Commodity.objects.prefetch_related("commodity_accounts__party"),
        pk=commodity_id,
    )
    context = {
        "title": f"Commodity {commodity.code}",
        "commodity": commodity,
        "active_accounts": commodity.commodity_accounts.filter(is_active=True).order_by(
            "code"
        ),
        "inactive_accounts": commodity.commodity_accounts.filter(
            is_active=False
        ).order_by("code"),
    }
    return TemplateResponse(request, "dea/commodity_master/detail.html", context)


@dea_accountant_required
@require_http_methods(["POST"])
def commodity_quick_setup_accounts(request, commodity_id):
    commodity = get_object_or_404(Commodity, pk=commodity_id)
    result = setup_standard_commodity_accounts(commodity)

    if result.created_codes:
        messages.success(
            request,
            f"Created commodity accounts: {', '.join(result.created_codes)}.",
        )
    if result.existing_codes:
        messages.info(
            request,
            f"Already present: {', '.join(result.existing_codes)}.",
        )
    for note in result.skipped_notes:
        messages.info(request, note)

    return redirect("dea_commodity_detail", commodity_id=commodity.pk)


@dea_accountant_required
@require_http_methods(["GET", "POST"])
def commodity_create(request):
    if request.method == "POST":
        form = CommodityCreateForm(request.POST)
        if form.is_valid():
            commodity = form.save()
            messages.success(
                request,
                f"Commodity {commodity.code} created successfully.",
            )
            return redirect("dea_commodity_detail", commodity_id=commodity.pk)
    else:
        form = CommodityCreateForm()

    context = {
        "title": "Create Commodity",
        "form": form,
        "commodity": None,
        "is_create": True,
    }
    return TemplateResponse(request, "dea/commodity_master/form.html", context)


@dea_accountant_required
@require_http_methods(["GET", "POST"])
def commodity_update(request, commodity_id):
    commodity = get_object_or_404(Commodity, pk=commodity_id)
    if request.method == "POST":
        form = CommodityUpdateForm(request.POST, instance=commodity)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Commodity {commodity.code} updated successfully.",
            )
            return redirect("dea_commodity_detail", commodity_id=commodity.pk)
    else:
        form = CommodityUpdateForm(instance=commodity)

    context = {
        "title": f"Edit Commodity {commodity.code}",
        "form": form,
        "commodity": commodity,
        "is_create": False,
    }
    return TemplateResponse(request, "dea/commodity_master/form.html", context)


@dea_accountant_required
@require_http_methods(["POST"])
def commodity_deactivate(request, commodity_id):
    commodity = get_object_or_404(Commodity, pk=commodity_id)

    if not commodity.is_active:
        messages.info(request, f"Commodity {commodity.code} is already inactive.")
        return redirect("dea_commodity_detail", commodity_id=commodity.pk)

    active_accounts = commodity.commodity_accounts.filter(is_active=True).count()
    if active_accounts:
        messages.error(
            request,
            (
                f"Cannot deactivate {commodity.code} while {active_accounts} active "
                "commodity account(s) still exist."
            ),
        )
        return redirect("dea_commodity_detail", commodity_id=commodity.pk)

    commodity.is_active = False
    commodity.save()
    messages.success(request, f"Commodity {commodity.code} deactivated.")
    return redirect("dea_commodity_list")
