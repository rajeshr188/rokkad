"""
Journal Entry Voucher Views

CRUD views for managing JournalEntryVoucher with line items formset support.
"""

from django.shortcuts import redirect
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
from django.db.models import Q
from decimal import Decimal

from ..forms_vouchers import (
    JournalEntryPairFormSet,
    JournalEntryVoucherForm,
    build_journal_entry_pair_initial,
    save_journal_entry_pairs,
)
from ..models import JournalEntryVoucher, VoucherType
from ..posting.engine import DjangoPostingEngine
from ..services.post_doc import create_and_post_voucher_for_doc


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
        all_entries = list(self.get_queryset())
        balanced_entries = sum(1 for entry in all_entries if entry.is_balanced)
        total_debit = sum(entry.total_debit.amount for entry in all_entries)

        context["summary"] = {
            "total_entries": len(all_entries),
            "balanced_entries": balanced_entries,
            "unbalanced_entries": len(all_entries) - balanced_entries,
            "total_debit": total_debit,
        }
        context["total_entries"] = context["summary"]["total_entries"]
        context["reviewed_count"] = sum(
            1 for entry in all_entries if entry.reviewed_by_id is not None
        )
        context["pending_count"] = sum(
            1 for entry in all_entries if entry.reviewed_by_id is None
        )

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
        context["je"] = journal_entry

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
        from django.contrib.contenttypes.models import ContentType

        from ..models import Voucher

        try:
            voucher = Voucher.objects.filter(
                doc_content_type=ContentType.objects.get_for_model(journal_entry),
                doc_object_id=journal_entry.pk,
                status="POSTED",
            ).first()
            if voucher:
                context["voucher"] = voucher
                context["journal_entries_posted"] = voucher.journal_entries.all()
        except Exception:
            pass

        return context


class JournalEntryVoucherCreateView(LoginRequiredMixin, CreateView):
    """Create a new journal entry voucher using pair-based posting rows."""

    model = JournalEntryVoucher
    form_class = JournalEntryVoucherForm
    template_name = "dea/journalentryvoucher_form.html"
    success_url = reverse_lazy("dea_journal_entry_voucher_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["pair_formset"] = JournalEntryPairFormSet(
                self.request.POST,
                prefix="pairs",
            )
        else:
            context["pair_formset"] = JournalEntryPairFormSet(prefix="pairs")
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        pair_formset = context["pair_formset"]

        if not pair_formset.is_valid():
            messages.error(self.request, "Please correct the posting pairs below.")
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                form.instance.created_by = self.request.user
                form.instance.updated_by = self.request.user
                form.instance.auto_post_to_accounting = False
                self.object = form.save()

                pair_count = save_journal_entry_pairs(self.object, pair_formset)
                self.object.full_clean()
                self.object.save(update_fields=["total_debit", "total_credit", "updated_by", "updated_at"])

                VoucherType.objects.get_or_create(
                    name=self.object.get_voucher_type(),
                    defaults={
                        "description": f"Manual {self.object.get_entry_type_display()} journal adjustment"
                    },
                )
                create_and_post_voucher_for_doc(
                    doc=self.object,
                    user=self.request.user,
                    voucher_type_input=self.object.get_voucher_type(),
                    engine=DjangoPostingEngine(),
                )
        except Exception as exc:
            messages.error(self.request, f"Could not save the journal adjustment: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Journal adjustment {self.object.je_number} saved using {pair_count} posting pair(s).",
        )
        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


class JournalEntryVoucherUpdateView(LoginRequiredMixin, UpdateView):
    """Update an existing journal entry voucher using pair-based rows."""

    model = JournalEntryVoucher
    form_class = JournalEntryVoucherForm
    template_name = "dea/journalentryvoucher_form.html"
    success_url = reverse_lazy("dea_journal_entry_voucher_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["pair_formset"] = JournalEntryPairFormSet(
                self.request.POST,
                prefix="pairs",
            )
        else:
            context["pair_formset"] = JournalEntryPairFormSet(
                initial=build_journal_entry_pair_initial(self.object),
                prefix="pairs",
            )
        context["is_update"] = True
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        pair_formset = context["pair_formset"]

        if not pair_formset.is_valid():
            messages.error(self.request, "Please correct the posting pairs below.")
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                form.instance.updated_by = self.request.user
                form.instance.auto_post_to_accounting = False
                self.object = form.save()

                pair_count = save_journal_entry_pairs(self.object, pair_formset)
                self.object.full_clean()
                self.object.save(update_fields=["total_debit", "total_credit", "updated_by", "updated_at"])

                VoucherType.objects.get_or_create(
                    name=self.object.get_voucher_type(),
                    defaults={
                        "description": f"Manual {self.object.get_entry_type_display()} journal adjustment"
                    },
                )
                create_and_post_voucher_for_doc(
                    doc=self.object,
                    user=self.request.user,
                    voucher_type_input=self.object.get_voucher_type(),
                    engine=DjangoPostingEngine(),
                )
        except Exception as exc:
            messages.error(self.request, f"Could not update the journal adjustment: {exc}")
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Journal adjustment {self.object.je_number} updated with {pair_count} posting pair(s).",
        )
        return redirect(self.success_url)


class JournalEntryVoucherDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a journal entry voucher"""

    model = JournalEntryVoucher
    template_name = "dea/journalentryvoucher_confirm_delete.html"
    success_url = reverse_lazy("dea_journal_entry_voucher_list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Journal entry deleted successfully!")
        return super().delete(request, *args, **kwargs)
