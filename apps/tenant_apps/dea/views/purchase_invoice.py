"""
Purchase Invoice Voucher Views

CRUD views for managing PurchaseInvoiceVoucher with line items formset support.
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Sum, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from ..forms_vouchers import PurchaseInvoiceForm, PurchaseInvoiceLineItemFormSet
from ..models import PurchaseInvoiceVoucher


class PurchaseInvoiceListView(LoginRequiredMixin, ListView):
    """List all purchase invoices with filtering"""

    model = PurchaseInvoiceVoucher
    template_name = "dea/purchaseinvoicevoucher_list.html"
    context_object_name = "invoices"
    paginate_by = 50

    def get_queryset(self):
        qs = (
            PurchaseInvoiceVoucher.objects.select_related(
                "vendor", "created_by", "updated_by"
            )
            .prefetch_related("line_items")
            .order_by("-invoice_date", "-created_at")
        )

        # Filter by purchase type
        purchase_type = self.request.GET.get("purchase_type")
        if purchase_type:
            qs = qs.filter(purchase_type=purchase_type)

        # Filter by payment status
        is_paid = self.request.GET.get("is_paid")
        if is_paid == "true":
            qs = qs.filter(is_fully_paid=True)
        elif is_paid == "false":
            qs = qs.filter(is_fully_paid=False)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)

        # Search by vendor or invoice number
        search = self.request.GET.get("search")
        if search:
            qs = qs.filter(
                Q(internal_number__icontains=search)
                | Q(invoice_number__icontains=search)
                | Q(reference__icontains=search)
                | Q(description__icontains=search)
                | Q(vendor__firstname__icontains=search)
                | Q(vendor__lastname__icontains=search)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_invoices = self.get_queryset()

        context["total_invoices"] = all_invoices.count()
        context["paid_count"] = all_invoices.filter(is_fully_paid=True).count()
        context["pending_count"] = all_invoices.filter(is_fully_paid=False).count()

        totals = all_invoices.aggregate(
            total_amount=Sum("net_payable_currency"),
            paid_amount=Sum("paid_amount_currency"),
        )
        context["total_amount"] = totals["total_amount"] or Decimal("0")
        context["total_paid"] = totals["paid_amount"] or Decimal("0")

        context["purchase_types"] = PurchaseInvoiceVoucher._meta.get_field(
            "purchase_type"
        ).choices
        context["current_purchase_type"] = self.request.GET.get("purchase_type", "")
        context["current_is_paid"] = self.request.GET.get("is_paid", "")
        context["search_query"] = self.request.GET.get("search", "")

        return context


class PurchaseInvoiceDetailView(LoginRequiredMixin, DetailView):
    """Display details of a single purchase invoice"""

    model = PurchaseInvoiceVoucher
    template_name = "dea/purchaseinvoicevoucher_detail.html"
    context_object_name = "invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.object

        context["line_items"] = invoice.line_items.all()

        # Totals for display
        context["subtotal"] = sum(
            item.line_total.amount for item in context["line_items"]
        )
        context["total_taxable"] = context["subtotal"]

        # Get related journal entries if posted
        from ..models import Voucher

        try:
            voucher = Voucher.objects.filter(
                business_doc=invoice, status="POSTED"
            ).first()
            if voucher:
                context["voucher"] = voucher
                context["journal_entries"] = voucher.journal_entries.all()
        except Exception:
            pass

        return context


class PurchaseInvoiceCreateView(LoginRequiredMixin, CreateView):
    """Create a new purchase invoice with line items"""

    model = PurchaseInvoiceVoucher
    form_class = PurchaseInvoiceForm
    template_name = "dea/purchaseinvoicevoucher_form.html"
    success_url = reverse_lazy("dea_purchase_invoice_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["line_items_formset"] = PurchaseInvoiceLineItemFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["line_items_formset"] = PurchaseInvoiceLineItemFormSet(
                instance=self.object
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        line_items_formset = context["line_items_formset"]

        with transaction.atomic():
            form.instance.created_by = self.request.user
            form.instance.updated_by = self.request.user

            if not line_items_formset.is_valid():
                return self.form_invalid(form)

            self.object = form.save()
            line_items_formset.instance = self.object
            line_items_formset.save()

            self._recalculate_totals(self.object)

            messages.success(
                self.request,
                f"Purchase invoice {self.object.internal_number} created successfully!",
            )

        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def _recalculate_totals(self, invoice):
        items = invoice.line_items.all()
        subtotal = sum(item.line_total.amount for item in items)
        taxable = subtotal

        cgst = Decimal("0")
        sgst = Decimal("0")
        igst = Decimal("0")

        for item in items:
            line_taxable = item.line_total.amount
            cgst += line_taxable * item.cgst_rate / Decimal("100")
            sgst += line_taxable * item.sgst_rate / Decimal("100")
            igst += line_taxable * item.igst_rate / Decimal("100")

        total = taxable + cgst + sgst + igst
        tds = invoice.tds_amount.amount if invoice.tds_amount else Decimal("0")
        net_payable = total - tds

        invoice.subtotal = subtotal
        invoice.taxable_amount = taxable
        invoice.cgst_amount = cgst
        invoice.sgst_amount = sgst
        invoice.igst_amount = igst
        invoice.total_amount = total
        invoice.net_payable = net_payable
        invoice.save()


class PurchaseInvoiceUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing purchase invoice"""

    model = PurchaseInvoiceVoucher
    form_class = PurchaseInvoiceForm
    template_name = "dea/purchaseinvoicevoucher_form.html"
    success_url = reverse_lazy("dea_purchase_invoice_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["line_items_formset"] = PurchaseInvoiceLineItemFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["line_items_formset"] = PurchaseInvoiceLineItemFormSet(
                instance=self.object
            )
        context["is_update"] = True
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        line_items_formset = context["line_items_formset"]

        with transaction.atomic():
            form.instance.updated_by = self.request.user

            if not line_items_formset.is_valid():
                return self.form_invalid(form)

            self.object = form.save()
            line_items_formset.instance = self.object
            line_items_formset.save()

            self._recalculate_totals(self.object)

            messages.success(
                self.request,
                f"Purchase invoice {self.object.internal_number} updated successfully!",
            )

        return redirect(self.success_url)

    def _recalculate_totals(self, invoice):
        items = invoice.line_items.all()
        subtotal = sum(item.line_total.amount for item in items)
        taxable = subtotal

        cgst = Decimal("0")
        sgst = Decimal("0")
        igst = Decimal("0")

        for item in items:
            line_taxable = item.line_total.amount
            cgst += line_taxable * item.cgst_rate / Decimal("100")
            sgst += line_taxable * item.sgst_rate / Decimal("100")
            igst += line_taxable * item.igst_rate / Decimal("100")

        total = taxable + cgst + sgst + igst
        tds = invoice.tds_amount.amount if invoice.tds_amount else Decimal("0")
        net_payable = total - tds

        invoice.subtotal = subtotal
        invoice.taxable_amount = taxable
        invoice.cgst_amount = cgst
        invoice.sgst_amount = sgst
        invoice.igst_amount = igst
        invoice.total_amount = total
        invoice.net_payable = net_payable
        invoice.save()


class PurchaseInvoiceDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a purchase invoice"""

    model = PurchaseInvoiceVoucher
    template_name = "dea/purchaseinvoicevoucher_confirm_delete.html"
    success_url = reverse_lazy("dea_purchase_invoice_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Purchase invoice deleted successfully!")
        return super().delete(request, *args, **kwargs)
