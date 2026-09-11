from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .access import rate_action_required
from .forms import RateForm, RateSourceForm, RateWithdrawalForm
from .models import Rate, RateSource
from .facade import get_workspace_rate_dashboard_summary
from .services import record_quote, withdraw_quote


# Create your views here.
@rate_action_required("view")
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
def rate_list(request):
    rates = Rate.objects.filter(workspace=request.workspace).select_related("rate_source", "successor").order_by("-timestamp", "-pk")
    return render(
        request,
        "rates/rate_list.html",
        {"rates": rates, "has_rate_sources": RateSource.objects.exists()},
    )

@rate_action_required("view")
def rate_detail(request, pk):
    rate = get_object_or_404(Rate, pk=pk)
    return render(request, "rates/rate_detail.html", {"rate": rate})


@rate_action_required("create")
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
def rate_delete(request, pk):
    rate = get_object_or_404(Rate, pk=pk)
    form = RateWithdrawalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            withdrawal = withdraw_quote(workspace=request.workspace, actor=request.user, quote_id=pk, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            return redirect("workspace_rates:rate_detail", workspace_slug=request.workspace.slug, pk=withdrawal.pk)
    return render(request, "rates/rate_confirm_delete.html", {"rate": rate, "form": form})


@rate_action_required("view")
def ratesource_list(request):
    ratesources = RateSource.objects.all()
    return render(request, "rates/ratesource_list.html", {"ratesources": ratesources})


@rate_action_required("view")
def ratesource_detail(request, pk):
    ratesource = get_object_or_404(RateSource, pk=pk)
    return render(request, "rates/ratesource_detail.html", {"ratesource": ratesource})


@rate_action_required("create")
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
