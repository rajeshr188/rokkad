from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods  # new
from django.views.generic import DetailView, ListView
from django.views.generic.base import TemplateView
from django_tables2.config import RequestConfig
from types import SimpleNamespace
from datetime import timedelta
from django.utils import timezone

from apps.tenant_apps.dea.models import JournalEntry  # , JournalTypes
from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..forms import (
    InventoryListFilterForm,
    StockInForm,
    StockOutForm,
    StockStatementForm,
    UniqueForm,
)
from ..inventory.services import InventoryMovementService
from ..models import Stock, StockItem, StockStatement, StockTransaction
from ..tables import InventoryTable


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
                print(e)
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
    form = InventoryListFilterForm(request.GET or None)
    if not form.is_valid():
        form = InventoryListFilterForm()

    mode = form.cleaned_data.get("mode") or "lots"
    query = (form.cleaned_data.get("query") or "").strip()
    variant = form.cleaned_data.get("variant")
    non_zero_only = bool(form.cleaned_data.get("non_zero_only"))
    audit_age_days = form.cleaned_data.get("audit_age_days")

    lots_qs = Stock.objects.select_related("variant")
    items_qs = StockItem.objects.select_related("variant")

    if variant:
        lots_qs = lots_qs.filter(variant=variant)
        items_qs = items_qs.filter(variant=variant)

    if query:
        lots_qs = lots_qs.filter(
            Q(huid__icontains=query)
            | Q(lot_no__icontains=query)
            | Q(serial_no__icontains=query)
            | Q(variant__sku__icontains=query)
            | Q(variant__name__icontains=query)
        )
        items_qs = items_qs.filter(
            Q(huid__icontains=query)
            | Q(serial_no__icontains=query)
            | Q(variant__sku__icontains=query)
            | Q(variant__name__icontains=query)
        )

    def build_row(subject, subject_type):
        balance = subject.current_balance()
        if isinstance(subject, Stock):
            last_stmt = subject.stockstatement_set.order_by("-created").first()
            lot_no = subject.lot_no
        else:
            last_stmt = subject.statements.order_by("-created").first()
            lot_no = ""

        last_audit_at = last_stmt.created if last_stmt else None
        if last_audit_at:
            audit_age = (timezone.now() - last_audit_at).days
        else:
            audit_age = None

        return {
            "subject_type": subject_type,
            "subject_id": subject.pk,
            "created": subject.created,
            "variant": subject.variant,
            "lot_no": lot_no,
            "serial_no": subject.serial_no,
            "huid": getattr(subject, "huid", None),
            "quantity": balance["qty"],
            "weight": balance["wt"],
            "status": subject.status,
            "last_audit_at": last_audit_at,
            "audit_age_days": audit_age,
        }

    rows = []
    if mode in ("lots", "unified"):
        rows.extend(build_row(stock, "LOT") for stock in lots_qs)
    if mode in ("items", "unified"):
        rows.extend(build_row(item, "ITEM") for item in items_qs)

    if non_zero_only:
        rows = [
            row
            for row in rows
            if row["quantity"] > 0 or row["weight"] > 0
        ]

    if audit_age_days is not None:
        cutoff = timezone.now() - timedelta(days=audit_age_days)
        rows = [
            row
            for row in rows
            if row["last_audit_at"] is None or row["last_audit_at"] <= cutoff
        ]

    rows.sort(key=lambda row: row["created"], reverse=True)

    table = InventoryTable(rows)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    context = {
        "filter": SimpleNamespace(form=form),
        "table": table,
        "inventory_mode": mode,
    }
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

    def get_queryset(self):
        return (
            StockStatement.objects.select_related(
                "stock",
                "stock__variant",
                "stock_item",
                "stock_item__variant",
            )
            .order_by("-created")
        )


class StockStatementView(TemplateView):
    template_name = "product/stock/add_stockstatement.html"

    def get(self, *args, **kwargs):
        form = StockStatementForm()
        return self.render_to_response({"form": form})

    def post(self, *args, **kwargs):
        form = StockStatementForm(data=self.request.POST)
        if form.is_valid():
            subject = form.cleaned_data["stock"] or form.cleaned_data["stock_item"]
            statement, adjustments = InventoryMovementService.perform_physical_audit(
                subject=subject,
                physical_qty=form.cleaned_data["physical_qty"],
                physical_wt=form.cleaned_data["physical_wt"],
                reconcile=form.cleaned_data["reconcile_now"],
            )
            if adjustments:
                messages.success(self.request, f"Physical audit recorded and reconciled for statement #{statement.pk}.")
            elif statement.has_variance:
                messages.warning(self.request, f"Physical audit recorded with discrepancy for statement #{statement.pk}.")
            else:
                messages.success(self.request, f"Physical audit recorded for statement #{statement.pk}.")
            return redirect(reverse_lazy("product_stockstatement_list"))

        return self.render_to_response({"form": form})


@login_required
def audit_stock(request):
    stocks = Stock.objects.all()
    for i in stocks:
        i.audit()
    return HttpResponseRedirect(reverse("product_stock_list"))

def stock_select(request, q):
    objects = Stock.objects.filter(
        Q(variant__name__icontains=q) | Q(barcode__icontains=q) | Q(huid__contains=q)
    )
    return render(
        request, "product/stock/stock_select.html", context={"result": objects}
    )


def stockin_journalentry(request):
    # Check if journal_entry_id is provided in the request
    journal_entry_id = request.GET.get("journal_entry_id", None)
    # Initialize the form with the journal_entry_id
    form = StockInForm(request.POST or None)
    if request.method == "POST":
        if journal_entry_id:
            # Fetch the existing JournalEntry
            journal_entry = get_object_or_404(JournalEntry, id=journal_entry_id)
        else:
            # Create a new JournalEntry
            journal_entry = JournalEntry.objects.create(desc="Stock In Entry")
            journal_entry_id = journal_entry.id
        if form.is_valid():
            stock_transaction = form.save(commit=False)
            stock_transaction.journal_entry = journal_entry
            stock_transaction.save()
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
