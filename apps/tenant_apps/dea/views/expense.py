"""
Expense Voucher Views

CRUD views for managing ExpenseVoucher with line items formset support.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import transaction
from django.contrib import messages
from django.db.models import Sum, Q, Count
from decimal import Decimal

from ..models import ExpenseVoucher, ExpenseLineItem
from ..forms_vouchers import ExpenseVoucherForm, ExpenseLineItemFormSet


class ExpenseVoucherListView(LoginRequiredMixin, ListView):
    """List all expense vouchers with filtering"""

    model = ExpenseVoucher
    template_name = "dea/expensevoucher_list.html"
    context_object_name = "expenses"
    paginate_by = 50

    def get_queryset(self):
        qs = (
            ExpenseVoucher.objects.select_related("created_by", "updated_by")
            .prefetch_related("line_items")
            .order_by("-expense_date", "-created_at")
        )

        # Filter by source type
        source_type = self.request.GET.get("source_type")
        if source_type:
            qs = qs.filter(source_type=source_type)

        # Filter by payment status
        is_paid = self.request.GET.get("is_paid")
        if is_paid == "true":
            qs = qs.filter(is_paid=True)
        elif is_paid == "false":
            qs = qs.filter(is_paid=False)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        if date_from:
            qs = qs.filter(expense_date__gte=date_from)
        if date_to:
            qs = qs.filter(expense_date__lte=date_to)

        # Search by party name
        search = self.request.GET.get("search")
        if search:
            qs = qs.filter(
                Q(party_name__icontains=search)
                | Q(description__icontains=search)
                | Q(expense_number__icontains=search)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Summary statistics
        all_expenses = self.get_queryset()
        context["total_expenses"] = all_expenses.count()
        context["paid_count"] = all_expenses.filter(is_paid=True).count()
        context["pending_count"] = all_expenses.filter(is_paid=False).count()

        # Total amounts
        totals = all_expenses.aggregate(
            total_amount=Sum("net_payable_currency"),
            paid_amount=Sum("paid_amount_currency"),
        )
        context["total_amount"] = totals["total_amount"] or Decimal("0")
        context["total_paid"] = totals["paid_amount"] or Decimal("0")

        # Filters
        context["source_types"] = ExpenseVoucher._meta.get_field("source_type").choices
        context["current_source_type"] = self.request.GET.get("source_type", "")
        context["current_is_paid"] = self.request.GET.get("is_paid", "")
        context["search_query"] = self.request.GET.get("search", "")

        return context


class ExpenseVoucherDetailView(LoginRequiredMixin, DetailView):
    """Display details of a single expense voucher"""

    model = ExpenseVoucher
    template_name = "dea/expensevoucher_detail.html"
    context_object_name = "expense"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expense = self.object

        # Get line items
        context["line_items"] = expense.line_items.all()

        # Calculate totals
        line_items = context["line_items"]
        context["subtotal"] = sum(item.amount.amount for item in line_items)
        context["total_tax"] = sum(item.tax_amount.amount for item in line_items)
        context["total_tds"] = sum(item.tds_amount.amount for item in line_items)

        # Get related journal entries if posted
        from ..models import JournalEntry, Voucher

        try:
            voucher = Voucher.objects.filter(
                business_doc=expense, status="POSTED"
            ).first()
            if voucher:
                context["voucher"] = voucher
                context["journal_entries"] = voucher.journal_entries.all()
        except:
            pass

        return context


class ExpenseVoucherCreateView(LoginRequiredMixin, CreateView):
    """Create a new expense voucher with line items"""

    model = ExpenseVoucher
    form_class = ExpenseVoucherForm
    template_name = "dea/expensevoucher_form.html"
    success_url = reverse_lazy("dea_expense_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["line_items_formset"] = ExpenseLineItemFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["line_items_formset"] = ExpenseLineItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        line_items_formset = context["line_items_formset"]

        with transaction.atomic():
            # Set created_by and updated_by
            form.instance.created_by = self.request.user
            form.instance.updated_by = self.request.user

            # Validate formset
            if not line_items_formset.is_valid():
                return self.form_invalid(form)

            # Save expense voucher
            self.object = form.save()

            # Save line items
            line_items_formset.instance = self.object
            line_items = line_items_formset.save()

            # Calculate totals from line items
            gross_total = Decimal("0")
            tax_total = Decimal("0")
            tds_total = Decimal("0")
            taxable_total = Decimal("0")

            for item in self.object.line_items.all():
                gross_total += item.amount.amount
                tax_total += item.tax_amount.amount
                tds_total += item.tds_amount.amount
                if item.is_taxable:
                    taxable_total += item.amount.amount

            # Update expense voucher totals
            self.object.gross_amount = gross_total
            self.object.tax_amount = tax_total
            self.object.tds_amount = tds_total
            self.object.taxable_amount = taxable_total
            self.object.save()

            messages.success(
                self.request,
                f"Expense voucher {self.object.expense_number} created successfully!",
            )

        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class ExpenseVoucherUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing expense voucher"""

    model = ExpenseVoucher
    form_class = ExpenseVoucherForm
    template_name = "dea/expensevoucher_form.html"
    success_url = reverse_lazy("dea_expense_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["line_items_formset"] = ExpenseLineItemFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["line_items_formset"] = ExpenseLineItemFormSet(instance=self.object)
        context["is_update"] = True
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        line_items_formset = context["line_items_formset"]

        with transaction.atomic():
            # Set updated_by
            form.instance.updated_by = self.request.user

            # Validate formset
            if not line_items_formset.is_valid():
                return self.form_invalid(form)

            # Save expense voucher
            self.object = form.save()

            # Save line items
            line_items_formset.instance = self.object
            line_items_formset.save()

            # Recalculate totals
            gross_total = Decimal("0")
            tax_total = Decimal("0")
            tds_total = Decimal("0")
            taxable_total = Decimal("0")

            for item in self.object.line_items.all():
                gross_total += item.amount.amount
                tax_total += item.tax_amount.amount
                tds_total += item.tds_amount.amount
                if item.is_taxable:
                    taxable_total += item.amount.amount

            # Update expense voucher totals
            self.object.gross_amount = gross_total
            self.object.tax_amount = tax_total
            self.object.tds_amount = tds_total
            self.object.taxable_amount = taxable_total
            self.object.save()

            messages.success(
                self.request,
                f"Expense voucher {self.object.expense_number} updated successfully!",
            )

        return redirect(self.success_url)


class ExpenseVoucherDeleteView(LoginRequiredMixin, DeleteView):
    """Delete an expense voucher"""

    model = ExpenseVoucher
    template_name = "dea/expensevoucher_confirm_delete.html"
    success_url = reverse_lazy("dea_expense_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, f"Expense voucher deleted successfully!")
        return super().delete(request, *args, **kwargs)
