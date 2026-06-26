"""
Voucher CRUD Views

Handles creation, editing, posting, and reversing of vouchers.
A voucher is an accounting representation of a business document.

Lifecycle:
- DRAFT: Can be created and edited
- POSTED: Creates journal entries, cannot be edited
- REVERSED: Original voucher marked as reversed, new JE created with opposite entries
"""

from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.db import transaction as db_transaction
from django.db.models import Q, Sum, F
from django.core.exceptions import ValidationError
from django.contrib import messages
from django_tables2 import RequestConfig
from django.utils.translation import gettext_lazy as _

from ..posting.commands import PostVoucherCommand
from ..posting.engine import DjangoPostingEngine
from ..posting.types import PostingError
from ..models import (
    Voucher,
    VoucherType,
    VoucherStatus,
    VoucherLine,
    Ledger,
    Account,
)
from ..forms import VoucherForm, LedgerTransactionForm, AccountTransactionForm
from ..forms_vouchers import VoucherLineFormSet
from ..tables import VoucherTable
from ..filters import VoucherFilter
from ..services.reversal import (
    MissingOriginalJournalEntryError,
    ReversalError,
    ReversalPeriodError,
    VoucherNotPostedError,
    reverse_posted_voucher,
)
from .access import DeaAccountantRequiredMixin, dea_accountant_required
from apps.tenant_apps.utils.htmx_utils import for_htmx


class VoucherListView(DeaAccountantRequiredMixin, ListView):
    """
    List all vouchers with filtering and pagination.

    Features:
    - Filter by status, type, date range
    - Pagination
    - Sortable table
    """

    model = Voucher
    template_name = "dea/voucher_list.html"
    context_object_name = "vouchers"
    paginate_by = 25

    def get_queryset(self):
        """Fetch vouchers with related objects"""
        return Voucher.objects.select_related(
            "voucher_type", "created_by", "updated_by", "doc_content_type"
        ).order_by("-created_at")

    def get_context_data(self, **kwargs):
        """Add filter and table to context"""
        context = super().get_context_data(**kwargs)

        # Apply filters
        filter_obj = VoucherFilter(self.request.GET, queryset=self.get_queryset())

        # Create table
        table = VoucherTable(filter_obj.qs)
        RequestConfig(self.request, paginate={"per_page": 25}).configure(table)

        context["filter"] = filter_obj
        context["table"] = table
        context["total_vouchers"] = Voucher.objects.count()
        context["draft_vouchers"] = Voucher.objects.filter(
            status=VoucherStatus.DRAFT
        ).count()
        context["posted_vouchers"] = Voucher.objects.filter(
            status=VoucherStatus.POSTED
        ).count()
        context["reversed_vouchers"] = Voucher.objects.filter(
            status=VoucherStatus.REVERSED
        ).count()

        return context


class VoucherDetailView(DeaAccountantRequiredMixin, DetailView):
    """
    Display voucher details including:
    - Header information
    - Line items (debit/credit entries)
    - Journal entries (if posted)
    - Audit trail (created/posted/reversed by/at)
    """

    model = Voucher
    template_name = "dea/voucher_detail.html"
    context_object_name = "voucher"

    def get_queryset(self):
        """Fetch voucher with all related objects"""
        return Voucher.objects.select_related(
            "voucher_type", "created_by", "updated_by", "doc_content_type"
        ).prefetch_related(
            "journal_entries", "journal_entries__ltxns", "journal_entries__atxns"
        )

    def get_context_data(self, **kwargs):
        """Add related objects to context"""
        context = super().get_context_data(**kwargs)
        voucher = self.get_object()

        if voucher.business_doc:
            context["business_doc_type"] = voucher.business_doc.__class__.__name__

        # Get journal entries for this voucher
        journal_entries = (
            voucher.journal_entries.select_related("period", "posted_by")
            .prefetch_related("ltxns__ledgerno", "ltxns__ledgerno_dr", "atxns__Account")
            .order_by("posted_at")
        )

        context["journal_entries"] = journal_entries

        # Calculate totals from line items
        context["line_items"] = self._get_line_items(voucher)
        context["total_debit"] = sum(
            item["amount"] for item in context["line_items"] if item["side"] == "DEBIT"
        )
        context["total_credit"] = sum(
            item["amount"] for item in context["line_items"] if item["side"] == "CREDIT"
        )
        context["is_balanced"] = context["total_debit"] == context["total_credit"]

        # Check if can be edited/reversed
        context["can_edit"] = voucher.status == VoucherStatus.DRAFT
        context["can_post"] = (
            voucher.status == VoucherStatus.DRAFT and context["is_balanced"]
        )
        context["can_reverse"] = voucher.status == VoucherStatus.POSTED

        # Check if already reversed
        if voucher.status == VoucherStatus.REVERSED:
            reversing_je = journal_entries.filter(is_reversal_of__isnull=False).first()
            if reversing_je:
                original_je = reversing_je.is_reversal_of
                context["reversed_by_je"] = reversing_je
                context["original_je"] = original_je

        return context

    def _get_line_items(self, voucher):
        """Extract line items from journal entries"""
        items = []

        # For DRAFT vouchers, we might not have JEs yet
        # So we need to reconstruct from the vouch data
        # This is a placeholder - customize based on your data structure

        return items


class VoucherCreateView(DeaAccountantRequiredMixin, CreateView):
    """
    Create a new voucher for a specific voucher type with inline VoucherLine formset.

    Steps:
    1. Enter header information (type, date, narration)
    2. Add line items (debit/credit entries) via inline formset
    3. Balance check: Dr = Cr (enforced by JS and form validation)
    4. Save as DRAFT
    """

    model = Voucher
    form_class = VoucherForm
    template_name = "dea/voucher_form.html"

    def get_initial(self):
        """Pre-populate initial data"""
        initial = super().get_initial()
        initial["created_by"] = self.request.user
        initial["status"] = VoucherStatus.DRAFT
        return initial

    def get_context_data(self, **kwargs):
        """Add voucher types and formset to context"""
        context = super().get_context_data(**kwargs)
        context["voucher_types"] = VoucherType.objects.all()
        context["ledgers"] = Ledger.objects.all()
        context["accounts"] = Account.objects.all()
        
        if self.request.POST:
            context["formset"] = VoucherLineFormSet(self.request.POST, instance=self.object)
        else:
            context["formset"] = VoucherLineFormSet(instance=self.object)
        
        return context

    def form_valid(self, form):
        """Save voucher and associated VoucherLine items"""
        context = self.get_context_data()
        formset = context["formset"]
        
        # Validate that formset is valid
        if formset.is_valid():
            # Set created_by and status before saving
            form.instance.created_by = self.request.user
            form.instance.status = VoucherStatus.DRAFT
            
            # Save parent voucher first
            self.object = form.save()
            
            # Save formset with the parent voucher
            formset.instance = self.object
            formset.save()
            
            messages.success(
                self.request, 
                f"Voucher {self.object.voucher_no} created successfully with {formset.forms.__len__()} line items"
            )
            return super().form_valid(form)
        else:
            # Formset has errors, re-render with errors
            return self.form_invalid(form)

    def get_success_url(self):
        """Redirect to voucher detail after creation"""
        return reverse("dea_voucher_detail", args=[self.object.pk])


class VoucherUpdateView(DeaAccountantRequiredMixin, UpdateView):
    """
    Edit an existing DRAFT voucher including line items.

    Constraints:
    - Only DRAFT vouchers can be edited
    - Cannot edit POSTED or REVERSED vouchers
    - Can modify/add/delete VoucherLine items
    """

    model = Voucher
    form_class = VoucherForm
    template_name = "dea/voucher_form.html"

    def get_queryset(self):
        """Only allow editing DRAFT vouchers"""
        return Voucher.objects.filter(status=VoucherStatus.DRAFT)

    def get_context_data(self, **kwargs):
        """Add formset to context for line items"""
        context = super().get_context_data(**kwargs)
        context["ledgers"] = Ledger.objects.all()
        context["accounts"] = Account.objects.all()
        
        if self.request.POST:
            context["formset"] = VoucherLineFormSet(self.request.POST, instance=self.object)
        else:
            context["formset"] = VoucherLineFormSet(instance=self.object)
        
        return context

    def form_valid(self, form):
        """Update voucher and line items"""
        context = self.get_context_data()
        formset = context["formset"]
        
        if formset.is_valid():
            form.instance.updated_by = self.request.user
            
            # Save parent form
            self.object = form.save()
            
            # Save formset
            formset.instance = self.object
            formset.save()
            
            messages.success(
                self.request, 
                f"Voucher {form.instance.voucher_no} updated successfully"
            )
            return super().form_valid(form)
        else:
            # Formset has errors, re-render with errors
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse("dea_voucher_detail", args=[self.object.pk])


class VoucherDeleteView(DeaAccountantRequiredMixin, DeleteView):
    """
    Delete a DRAFT voucher.

    Constraints:
    - Only DRAFT vouchers can be deleted
    - Cannot delete POSTED or REVERSED vouchers (use reversal instead)
    """

    model = Voucher
    template_name = "dea/voucher_confirm_delete.html"
    success_url = reverse_lazy("dea_voucher_list")

    def get_queryset(self):
        """Only allow deleting DRAFT vouchers"""
        return Voucher.objects.filter(status=VoucherStatus.DRAFT)

    def delete(self, request, *args, **kwargs):
        """Delete and show success message"""
        voucher = self.get_object()
        messages.success(request, f"Voucher {voucher.voucher_no} deleted successfully")
        return super().delete(request, *args, **kwargs)


@dea_accountant_required
@db_transaction.atomic
def post_voucher(request, pk):
    """
    Post a voucher - converts DRAFT to POSTED and creates journal entries.

    Steps:
    1. Validate voucher is DRAFT
    2. Validate voucher is balanced (debit total = credit total)
    3. Validate accounting period is OPEN
    4. Create JournalEntry with all transactions
    5. Update ledger and account balances
    6. Mark voucher as POSTED

    Atomicity: All or nothing - if any step fails, entire transaction rolls back
    """
    voucher = get_object_or_404(Voucher, pk=pk)

    # Check authorization and status
    if voucher.status != VoucherStatus.DRAFT:
        messages.error(
            request,
            f"Cannot post {voucher.status} voucher. Only DRAFT vouchers can be posted.",
        )
        return redirect("dea_voucher_detail", pk=pk)

    try:
        journal_entry = PostVoucherCommand(DjangoPostingEngine()).execute(
            voucher,
            request.user,
        )
        messages.success(
            request,
            f"Voucher {voucher.voucher_no} posted successfully. "
            f"Journal Entry #{journal_entry.id} created.",
        )

    except ValidationError as e:
        messages.error(request, f"Validation error: {e.message}")
    except PostingError as e:
        messages.error(request, f"Error posting voucher: {str(e)}")
    except Exception as e:
        messages.error(request, f"Error posting voucher: {str(e)}")

    return redirect("dea_voucher_detail", pk=pk)


@dea_accountant_required
@db_transaction.atomic
def reverse_voucher(request, pk):
    """
    Reverse a posted voucher.

    Steps:
    1. Validate voucher is POSTED (not DRAFT or already REVERSED)
    2. Get original journal entry
    3. Create new journal entry with opposite debit/credit
    4. Link new JE to original via is_reversal_of
    5. Mark original voucher as REVERSED
    6. Balances automatically revert

    Atomicity: All or nothing
    """
    voucher = get_object_or_404(Voucher, pk=pk)

    # Check status
    if voucher.status != VoucherStatus.POSTED:
        messages.error(
            request,
            f"Cannot reverse {voucher.status} voucher. Only POSTED vouchers can be reversed.",
        )
        return redirect("dea_voucher_detail", pk=pk)

    try:
        result = reverse_posted_voucher(
            voucher=voucher,
            actor=request.user,
            reason=request.POST.get("reason")
            or f"Voucher {voucher.voucher_no} reversed from DEA voucher view.",
            source_action="voucher_view_reversal",
        )
        if result.already_reversed:
            messages.success(
                request,
                f"Voucher {voucher.voucher_no} was already reversed.",
            )
        else:
            reversal_je = result.reversal_journal_entry
            messages.success(
                request,
                f"Voucher {voucher.voucher_no} reversed successfully. "
                f"Reversal Journal Entry #{reversal_je.id} created.",
            )

    except ValidationError as e:
        messages.error(request, f"Validation error: {e.message}")
    except (
        VoucherNotPostedError,
        MissingOriginalJournalEntryError,
        ReversalPeriodError,
        ReversalError,
    ) as e:
        messages.error(request, f"Error reversing voucher: {str(e)}")

    return redirect("dea_voucher_detail", pk=pk)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _calculate_totals(voucher):
    """
    Calculate total debits and credits for a voucher.

    Returns:
        (debit_total, credit_total): Tuple of Decimal amounts
    """
    # This is a placeholder - customize based on your data structure
    # You might fetch from LedgerTransactions, AccountTransactions, or stored fields
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")

    # Example: fetch from ledger transactions in journal entry
    # This is complex because DRAFT vouchers don't have JEs yet

    return debit_total, credit_total


# ============================================================================
# HTMX / AJAX VIEWS
# ============================================================================


def voucher_check_balance(request, pk):
    """
    AJAX endpoint to check if voucher is balanced.
    Returns JSON with balance status.
    """
    voucher = get_object_or_404(Voucher, pk=pk)
    debit_total, credit_total = _calculate_totals(voucher)

    return JsonResponse(
        {
            "is_balanced": debit_total == credit_total,
            "debit_total": str(debit_total),
            "credit_total": str(credit_total),
            "difference": str(abs(debit_total - credit_total)),
        }
    )


def voucher_status_badge(request, pk):
    """
    HTMX endpoint to get status badge for voucher.
    Used for live updates.
    """
    voucher = get_object_or_404(Voucher, pk=pk)
    return render(
        request, "dea/partials/voucher_status_badge.html", {"voucher": voucher}
    )
