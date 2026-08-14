import csv
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper

from django.contrib import messages
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

from django.apps import apps as django_apps
from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..access import ProductActionRequiredMixin, product_action_required
from ..forms import (
    InventoryListFilterForm,
    StockOpeningBalanceImportForm,
    StockInForm,
    StockOutForm,
    StockStatementForm,
    UniqueForm,
)
from ..inventory.services import InventoryMovementService
from ..models import ProductVariant, Stock, StockItem, StockStatement, StockTransaction
from ..tables import InventoryTable


@product_action_required("edit")
@for_htmx(use_block="content")
def split_lot(request, pk):
    stock = get_object_or_404(Stock, pk=pk)

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


@product_action_required("edit")
def merge_lot(request, pk):
    node = Stock.objects.get(id=pk)
    print(f"to merge node{node}")
    node.merge()
    return reverse_lazy("product_stock_list")


@product_action_required("view")
@for_htmx(use_block="content")
def stock_list(request):
    form = InventoryListFilterForm(request.GET)
    form.is_valid()  # all fields are required=False; always succeeds, populates cleaned_data

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


@product_action_required("delete")
@require_http_methods(["DELETE"])
def stock_delete(request, pk):
    stock = get_object_or_404(Stock, pk=pk)
    stock.delete()
    messages.error(request, messages.DEBUG, f"Deleted customer {stock.variant}")
    return HttpResponse("")


class StockDetailView(ProductActionRequiredMixin, DetailView):
    template_name = "product/stock/stock_detail.html"
    model = Stock
    required_action = "view"


class StockTransactionListView(ProductActionRequiredMixin, ListView):
    template_name = "product/stock/stocktransaction_list.html"
    model = StockTransaction
    required_action = "view"


class StockStatementListView(ProductActionRequiredMixin, ListView):
    template_name = "product/stock/stockstatement_list.html"
    model = StockStatement
    required_action = "view"

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


class StockStatementView(ProductActionRequiredMixin, TemplateView):
    template_name = "product/stock/add_stockstatement.html"
    required_action = "edit"

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


@product_action_required("edit")
def audit_stock(request):
    stocks = Stock.objects.all()
    for i in stocks:
        i.audit()
    return HttpResponseRedirect(reverse("product_stock_list"))

@product_action_required("view")
def stock_select(request, q=None):
    q = q or request.GET.get("q", "")
    objects = Stock.objects.filter(
        Q(variant__name__icontains=q)
        | Q(lot_no__icontains=q)
        | Q(serial_no__icontains=q)
        | Q(huid__icontains=q)
    )
    return render(
        request, "product/stock/stock_select.html", context={"result": objects}
    )


@product_action_required("create")
def stock_in_direct(request):
    # Check if journal_entry_id is provided in the request
    journal_entry_id = request.GET.get("journal_entry_id", None)
    # Initialize the form with the journal_entry_id
    form = StockInForm(request.POST or None)
    if request.method == "POST":
        journal_entry = None
        if journal_entry_id:
            # Attach to an existing JournalEntry (e.g. from a purchase voucher flow)
            journal_entry = get_object_or_404(django_apps.get_model("dea", "JournalEntry"), id=journal_entry_id)
        # When no journal_entry_id is given, journal_entry stays None.
        # StockTransaction.journal_entry is nullable so this is valid for
        # direct / non-accounting stock-in operations.
        if form.is_valid():
            stock_transaction = form.save(commit=False)
            stock_transaction.journal_entry = journal_entry
            stock_transaction.save()
            return redirect("product_stock_list")

    return render(
        request,
        "product/stock/stock_journalentry.html",
        context={
            "form": form,
            "page_title": "Direct Stock In",
        },
    )


@product_action_required("import")
def stock_opening_balance_import(request):
    form = StockOpeningBalanceImportForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        csv_file = form.cleaned_data["csv_file"]
        rows_created = 0
        errors = []

        try:
            reader = csv.DictReader(TextIOWrapper(csv_file, encoding="utf-8-sig"))
            required_columns = {"variant_id", "quantity", "weight"}
            headers = set(reader.fieldnames or [])
            missing_columns = required_columns - headers
            if missing_columns:
                messages.error(
                    request,
                    f"Missing required CSV columns: {', '.join(sorted(missing_columns))}",
                )
                return render(
                    request,
                    "product/stock/stock_opening_balance_import.html",
                    {"form": form, "page_title": "Import Opening Balances"},
                )

            for idx, row in enumerate(reader, start=2):
                if not any((value or "").strip() for value in row.values()):
                    continue

                try:
                    variant_id = int((row.get("variant_id") or "").strip())
                    quantity = int((row.get("quantity") or "").strip())
                    weight = Decimal((row.get("weight") or "").strip())
                    touch_raw = (row.get("touch") or "").strip()
                    rate_raw = (row.get("rate") or "").strip()
                    lot_no = (row.get("lot_no") or "").strip() or None
                    description = (
                        (row.get("description") or "").strip()
                        or "Opening balance import"
                    )

                    variant = get_object_or_404(ProductVariant, pk=variant_id)
                    stock = Stock.objects.create(
                        variant=variant,
                        quantity=quantity,
                        weight=weight,
                        lot_no=lot_no,
                        purchase_touch=Decimal(touch_raw) if touch_raw else None,
                        purchase_rate=Decimal(rate_raw) if rate_raw else None,
                        is_unique=False,
                    )
                    InventoryMovementService.record_movement(
                        subject=stock,
                        movement_type_id="OB",
                        quantity=quantity,
                        weight=weight,
                        description=description,
                    )
                    rows_created += 1
                except (ValueError, InvalidOperation) as exc:
                    errors.append(f"Row {idx}: {exc}")
                except Exception as exc:  # keep import resilient and continue
                    errors.append(f"Row {idx}: {exc}")

        except UnicodeDecodeError:
            messages.error(request, "CSV must be UTF-8 encoded.")
            return render(
                request,
                "product/stock/stock_opening_balance_import.html",
                {"form": form, "page_title": "Import Opening Balances"},
            )

        if rows_created:
            messages.success(request, f"Imported {rows_created} opening balance rows.")
        if errors:
            preview = " | ".join(errors[:5])
            suffix = "" if len(errors) <= 5 else f" (+{len(errors) - 5} more)"
            messages.warning(request, f"Some rows failed: {preview}{suffix}")

        return redirect("product_stock_list")

    return render(
        request,
        "product/stock/stock_opening_balance_import.html",
        {"form": form, "page_title": "Import Opening Balances"},
    )


@product_action_required("import")
def stock_opening_balance_template_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        'attachment; filename="opening_balance_template.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "variant_id",
        "quantity",
        "weight",
        "touch",
        "rate",
        "lot_no",
        "description",
    ])
    writer.writerow(["101", "1", "10.500", "91.600", "7200.000", "OB-001", "Opening balance lot"]) 

    return response


@product_action_required("create")
def stockin_journalentry(request):
    """Backward-compatible alias for deprecated view name."""
    return stock_in_direct(request)


@product_action_required("create")
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
