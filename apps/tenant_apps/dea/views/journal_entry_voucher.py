"""
Journal Entry Voucher Views

CRUD views for managing JournalEntryVoucher with line items formset support.
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

from ..models import JournalEntryVoucher, JournalEntryLineItem
from ..forms_vouchers import JournalEntryVoucherForm, JournalEntryLineItemFormSet


class JournalEntryVoucherListView(LoginRequiredMixin, ListView):
    """List all journal entry vouchers with filtering"""

    model = JournalEntryVoucher
    template_name = "dea/journalentryvoucher_list.html"
    context_object_name = "journal_entries"
    paginate_by = 50

    def get_queryset(self):
        qs = (
            JournalEntryVoucher.objects.select_related(
                "created_by", "updated_by", "reviewed_by"
            )
            .prefetch_related("line_items")
            .order_by("-je_date", "-created_at")
        )

        # Filter by entry type
        entry_type = self.request.GET.get("entry_type")
        if entry_type:
            qs = qs.filter(entry_type=entry_type)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        if date_from:
            qs = qs.filter(je_date__gte=date_from)
        if date_to:
            qs = qs.filter(je_date__lte=date_to)

        # Search by description
        search = self.request.GET.get("search")
        if search:
            qs = qs.filter(
                Q(description__icontains=search)
                | Q(je_number__icontains=search)
                | Q(memo__icontains=search)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Summary statistics
        all_entries = self.get_queryset()
        context["total_entries"] = all_entries.count()
        context["reviewed_count"] = all_entries.filter(
            reviewed_by__isnull=False
        ).count()
        context["pending_count"] = all_entries.filter(reviewed_by__isnull=True).count()

        # Filters
        context["entry_types"] = JournalEntryVoucher._meta.get_field(
            "entry_type"
        ).choices
        context["current_entry_type"] = self.request.GET.get("entry_type", "")
        context["search_query"] = self.request.GET.get("search", "")

        return context


class JournalEntryVoucherDetailView(LoginRequiredMixin, DetailView):
    """Display details of a single journal entry voucher"""

    model = JournalEntryVoucher
    template_name = "dea/journalentryvoucher_detail.html"
    context_object_name = "journal_entry"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journal_entry = self.object

        # Get line items grouped by DR/CR
        all_lines = journal_entry.line_items.all()
        context["debit_lines"] = all_lines.filter(side="DR")
        context["credit_lines"] = all_lines.filter(side="CR")

        # Calculate totals
        debit_total = sum(line.amount.amount for line in context["debit_lines"])
        credit_total = sum(line.amount.amount for line in context["credit_lines"])

        context["debit_total"] = debit_total
        context["credit_total"] = credit_total
        context["is_balanced"] = abs(debit_total - credit_total) <= Decimal("0.01")
        context["difference"] = debit_total - credit_total

        # Get related journal entries if posted
        from ..models import JournalEntry, Voucher

        try:
            voucher = Voucher.objects.filter(
                business_doc=journal_entry, status="POSTED"
            ).first()
            if voucher:
                context["voucher"] = voucher
                context["journal_entries_posted"] = voucher.journal_entries.all()
        except:
            pass

        return context


class JournalEntryVoucherCreateView(LoginRequiredMixin, CreateView):
    """Create a new journal entry voucher with line items"""

    model = JournalEntryVoucher
    form_class = JournalEntryVoucherForm
    template_name = "dea/journalentryvoucher_form.html"
    success_url = reverse_lazy("dea_journal_entry_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["line_items_formset"] = JournalEntryLineItemFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["line_items_formset"] = JournalEntryLineItemFormSet(
                instance=self.object
            )
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
                messages.error(self.request, "Please check the line items for errors.")
                return self.form_invalid(form)

            # Save journal entry voucher
            self.object = form.save()

            # Save line items
            line_items_formset.instance = self.object
            line_items = line_items_formset.save()

            # Calculate totals from line items
            debit_total = Decimal("0")
            credit_total = Decimal("0")

            for item in self.object.line_items.all():
                if item.side == "DR":
                    debit_total += item.amount.amount
                else:
                    credit_total += item.amount.amount

            # Update journal entry totals
            self.object.total_debit = debit_total
            self.object.total_credit = credit_total
            self.object.save()

            # Check if balanced
            if not self.object.is_balanced:
                messages.warning(
                    self.request,
                    f"Journal entry {self.object.je_number} is not balanced! "
                    f"DR: {debit_total}, CR: {credit_total}, Difference: {self.object.balance_difference}",
                )
            else:
                messages.success(
                    self.request,
                    f"Journal entry {self.object.je_number} created successfully and is balanced!",
                )

        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class JournalEntryVoucherUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing journal entry voucher"""

    model = JournalEntryVoucher
    form_class = JournalEntryVoucherForm
    template_name = "dea/journalentryvoucher_form.html"
    success_url = reverse_lazy("dea_journal_entry_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["line_items_formset"] = JournalEntryLineItemFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["line_items_formset"] = JournalEntryLineItemFormSet(
                instance=self.object
            )
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
                messages.error(self.request, "Please check the line items for errors.")
                return self.form_invalid(form)

            # Save journal entry voucher
            self.object = form.save()

            # Save line items
            line_items_formset.instance = self.object
            line_items_formset.save()

            # Recalculate totals
            debit_total = Decimal("0")
            credit_total = Decimal("0")

            for item in self.object.line_items.all():
                if item.side == "DR":
                    debit_total += item.amount.amount
                else:
                    credit_total += item.amount.amount

            # Update journal entry totals
            self.object.total_debit = debit_total
            self.object.total_credit = credit_total
            self.object.save()

            # Check if balanced
            if not self.object.is_balanced:
                messages.warning(
                    self.request,
                    f"Journal entry {self.object.je_number} is not balanced! "
                    f"DR: {debit_total}, CR: {credit_total}, Difference: {self.object.balance_difference}",
                )
            else:
                messages.success(
                    self.request,
                    f"Journal entry {self.object.je_number} updated successfully and is balanced!",
                )

        return redirect(self.success_url)


class JournalEntryVoucherDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a journal entry voucher"""

    model = JournalEntryVoucher
    template_name = "dea/journalentryvoucher_confirm_delete.html"
    success_url = reverse_lazy("dea_journal_entry_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, f"Journal entry deleted successfully!")
        return super().delete(request, *args, **kwargs)
