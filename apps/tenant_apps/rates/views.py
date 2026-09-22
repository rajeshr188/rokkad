from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_headers

from .access import rate_action_required
from .forms import RateForm, RateSourceForm, RateWithdrawalForm, RateListForm
from .models import Rate, RateSource
from .facade import get_workspace_rate_dashboard_summary
from .services import record_quote, withdraw_quote


# Create your views here.
@rate_action_required("view")
@never_cache
def get_latest_rate(request):
    summary = get_workspace_rate_dashboard_summary()
    latest_rates = [quote for quote in (summary["gold_rate"], summary["silver_rate"]) if quote]

    rates = []
    for rate in latest_rates:
        rates.append(
            f"{rate.metal} {rate.get_purity_display()} {rate.currency} {rate.buying_rate}/g {rate.effective_at}"
        )

    return HttpResponse(" ".join(rates))


@rate_action_required("view")
@never_cache
@vary_on_headers("HX-Request", "HX-Target", "HX-History-Restore-Request", "HX-Boosted")
def rate_list(request):
    rates = Rate.objects.filter(workspace=request.workspace).select_related("rate_source", "successor").order_by("-timestamp", "-pk")
    form = RateListForm(request.GET)
    if form.is_valid():
        if form.cleaned_data["q"]:
            query = form.cleaned_data["q"]
            rates = rates.filter(Q(source_snapshot__name__icontains=query) | Q(reason__icontains=query))
        if form.cleaned_data["metal"]:
            rates = rates.filter(metal=form.cleaned_data["metal"])
    else:
        rates = rates.none()
    page = Paginator(rates, 25).get_page(request.GET.get("page"))
    fragment = (request.headers.get("HX-Request") == "true" and request.headers.get("HX-Target") == "reference-results"
                and request.headers.get("HX-History-Restore-Request") != "true" and request.headers.get("HX-Boosted") != "true")
    response = render(
        request,
        "rates/rate_list.html#results" if fragment else "rates/rate_list.html",
        {"rates": page.object_list, "page_obj": page, "form": form, "has_rate_sources": RateSource.objects.exists()},
    )
    if fragment:
        response["X-Rokkad-Fragment"] = "reference-results"
    return response

@rate_action_required("view")
@never_cache
def rate_detail(request, pk):
    rate = get_object_or_404(Rate, pk=pk)
    return render(request, "rates/rate_detail.html", {"rate": rate})


@rate_action_required("create")
@never_cache
def rate_create(request):
    if request.method == "POST":
        form = RateForm(request.POST)
        if form.is_valid():
            try:
                rate = record_quote(workspace=request.workspace, actor=request.user, values=form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                return redirect("workspace_rates:rate_detail", workspace_slug=request.workspace.slug, pk=rate.pk)
    else:
        form = RateForm()
    return render(
        request,
        "rates/rate_form.html",
        {"form": form, "has_rate_sources": RateSource.objects.exists()},
    )


@rate_action_required("edit")
@never_cache
def rate_update(request, pk):
    rate = get_object_or_404(Rate, pk=pk)
    if request.method == "POST":
        form = RateForm(request.POST, instance=rate)
        if form.is_valid():
            try:
                rate = record_quote(workspace=request.workspace, actor=request.user, values=form.cleaned_data, supersedes_id=pk)
            except ValidationError as exc:
                form.add_error(None, " ".join(exc.messages))
            else:
                return redirect("workspace_rates:rate_detail", workspace_slug=request.workspace.slug, pk=rate.pk)
    else:
        form = RateForm(instance=rate)
    return render(
        request,
        "rates/rate_form.html",
        {"form": form, "has_rate_sources": RateSource.objects.exists()},
    )


@rate_action_required("delete")
@never_cache
def rate_delete(request, pk):
    rate = get_object_or_404(Rate, pk=pk)
    form = RateWithdrawalForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            withdrawal = withdraw_quote(workspace=request.workspace, actor=request.user, quote_id=pk, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            return redirect("workspace_rates:rate_detail", workspace_slug=request.workspace.slug, pk=withdrawal.pk)
    return render(request, "rates/rate_confirm_delete.html", {"rate": rate, "form": form})


@rate_action_required("view")
@never_cache
def ratesource_list(request):
    ratesources = RateSource.objects.all()
    return render(request, "rates/ratesource_list.html", {"ratesources": ratesources})


@rate_action_required("view")
@never_cache
def ratesource_detail(request, pk):
    ratesource = get_object_or_404(RateSource, pk=pk)
    return render(request, "rates/ratesource_detail.html", {"ratesource": ratesource})


@rate_action_required("create")
@never_cache
def ratesource_create(request):
    if request.method == "POST":
        form = RateSourceForm(request.POST)
        if form.is_valid():
            ratesource = form.save()
            return redirect("workspace_rates:ratesource_detail", workspace_slug=request.workspace.slug, pk=ratesource.pk)
    else:
        form = RateSourceForm()
    return render(request, "rates/ratesource_form.html", {"form": form})


@rate_action_required("edit")
@never_cache
def ratesource_update(request, pk):
    ratesource = get_object_or_404(RateSource, pk=pk)
    if request.method == "POST":
        form = RateSourceForm(request.POST, instance=ratesource)
        if form.is_valid():
            ratesource = form.save()
            return redirect("workspace_rates:ratesource_detail", workspace_slug=request.workspace.slug, pk=ratesource.pk)
    else:
        form = RateSourceForm(instance=ratesource)
    return render(request, "rates/ratesource_form.html", {"form": form})


@rate_action_required("delete")
@never_cache
def ratesource_delete(request, pk):
    ratesource = get_object_or_404(RateSource, pk=pk)
    error = ""
    if request.method == "POST":
        try:
            ratesource.delete()
        except ProtectedError:
            error = "This source has recorded quotes and must remain in history. Its quotes cannot be deleted with the source."
        else:
            return redirect("workspace_rates:ratesource_list", workspace_slug=request.workspace.slug)
    return render(
        request, "rates/ratesource_confirm_delete.html", {"ratesource": ratesource, "error": error}
    )
