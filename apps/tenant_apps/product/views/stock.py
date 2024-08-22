from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods  # new
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from django.views.generic.base import TemplateView
from django_tables2.config import RequestConfig

# from dea.models import JournalEntry  # , JournalTypes
from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..filters import StockFilter
from ..forms import StockInForm, StockOutForm, UniqueForm
from ..models import Stock, StockBalance, StockStatement, StockTransaction
from ..tables import StockTable


@login_required
@for_htmx(use_block="content")
def split_lot(request, pk):
    stock = get_object_or_404(Stock, pk=pk)
    if stock.is_unique:
        messages.error(request, "Cannot split unique stock")

    if request.method == "POST":
        form = UniqueForm(request.POST or None)
        if form.is_valid():
            weight = form.cleaned_data["weight"]
            quantity = form.cleaned_data["quantity"]
            is_unique = form.cleaned_data["is_unique"]
            try:
                stock.split(wt=weight, qty=quantity, is_unique=is_unique)
            except Exception as e:
                messages.error(request, f"Error: {e}")
            return HttpResponseRedirect(reverse("product_stock_list"))

    form = UniqueForm(initial={"stock": stock})
    context = {
        "form": form,
    }
    return TemplateResponse(request, "product/stock/split_lot.html", context)


@login_required
def merge_lot(request, pk):
    node = Stock.objects.get(id=pk)
    print(f"to merge node{node}")
    node.merge()
    return reverse_lazy("product_stock_list")


@login_required
@for_htmx(use_block="content")
def stock_list(request):
    filter = StockFilter(
        request.GET,
        queryset=Stock.objects.all().select_related("variant", "stockbalance"),
    )
    table = StockTable(filter.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    context = {"filter": filter, "table": table}
    return TemplateResponse(request, "product/stock/stock_list.html", context)


@require_http_methods(["DELETE"])
def stock_delete(request, pk):
    stock = get_object_or_404(Stock, pk=pk)
    stock.delete()
    messages.error(request, messages.DEBUG, f"Deleted customer {stock.variant}")
    return HttpResponse("")


class StockDetailView(LoginRequiredMixin, DetailView):
    template_name = "product/stock/stock_detail.html"
    model = Stock


class StockTransactionListView(LoginRequiredMixin, ListView):
    template_name = "product/stock/stocktransaction_list.html"
    model = StockTransaction


class StockStatementListView(LoginRequiredMixin, ListView):
    template_name = "product/stock/stockstatement_list.html"
    model = StockStatement


class StockStatementView(TemplateView):
    template_name = "product/stock/add_stockstatement.html"

    def get(self, *args, **kwargs):
        formset = stockstatement_formset(queryset=StockStatement.objects.none())
        return self.render_to_response({"stockstatement_formset": formset})

    def post(self, *args, **kwargs):
        formset = stockstatement_formset(data=self.request.POST)
        if formset.is_valid():
            formset.save()
            return redirect(reverse_lazy("stockstatement_list"))

        return self.render_to_response({"stockstatement_formset": formset})


@login_required
def audit_stock(request):
    stocks = Stock.objects.all()
    for i in stocks:
        i.audit()
    return HttpResponseRedirect(reverse("product_stock_list"))


from django.db.models import Q


def stock_select(request, q):
    objects = Stock.objects.filter(
        Q(variant__name__icontains=q) | Q(barcode__icontains=q) | Q(huid__contains=q)
    )
    return render(
        request, "product/stock/stock_select.html", context={"result": objects}
    )


def stockin_journalentry(request):
    form = StockInForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect("product_stock_list")
    return render(
        request, "product/stock/stock_journalentry.html", context={"form": form}
    )


@for_htmx(use_block="content")
def stockout_journalentry(request, pk=None):
    if request.method == "POST":
        form = StockOutForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("product_stock_list")
    else:  # GET request
        initial_data = {}
        if pk is not None:
            stock = get_object_or_404(Stock, pk=pk)
            initial_data = {"stock": stock}
        form = StockOutForm(initial=initial_data)

    return TemplateResponse(
        request, "product/stock/stock_journalentry.html", context={"form": form}
    )
