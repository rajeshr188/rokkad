"""
Payment Voucher Views

Views for managing PaymentVoucher creation, listing, and detail display.
Handles the payment-centric accounting architecture.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse_lazy
from django.db import transaction
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods

from ..models import PaymentVoucher, CashFlowDirection, PaymentMethod
from ..forms import PaymentVoucherForm
from ..posting.engine import DjangoPostingEngine
from ..services.post_doc import create_and_post_voucher_for_doc


class PaymentVoucherListView(LoginRequiredMixin, ListView):
    """List all payment vouchers with filtering by direction, loan, date."""

    model = PaymentVoucher
    template_name = "dea/paymentvoucher_list.html"
    context_object_name = "payments"
    paginate_by = 50

    def get_queryset(self):
        qs = PaymentVoucher.objects.select_related(
            "source_content_type", "created_by", "updated_by"
        ).order_by("-payment_date")

        # Filter by direction if provided
        direction = self.request.GET.get("direction")
        if direction in ["RECEIPT", "PAYMENT"]:
            qs = qs.filter(direction=direction)

        # Filter by loan if loan_id provided
        loan_id = self.request.GET.get("loan_id")
        if loan_id:
            qs = qs.filter(source_object_id=loan_id)

        # Filter by payment method
        method = self.request.GET.get("method")
        if method:
            qs = qs.filter(payment_method=method)

        # Filter by date range
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        if date_from:
            qs = qs.filter(payment_date__gte=date_from)
        if date_to:
            qs = qs.filter(payment_date__lte=date_to)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["directions"] = CashFlowDirection.choices
        context["methods"] = PaymentMethod.choices
        context["current_direction"] = self.request.GET.get("direction", "")
        context["current_method"] = self.request.GET.get("method", "")
        return context


class PaymentVoucherDetailView(LoginRequiredMixin, DetailView):
    """Display details of a single payment voucher."""

    model = PaymentVoucher
    template_name = "dea/paymentvoucher_detail.html"
    context_object_name = "payment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.object

        # Get source document information
        if payment.source_document:
            context["source_doc"] = payment.source_document
            context["source_doc_url"] = payment.source_document.get_absolute_url()

        # Get journal entry if posted
        if payment.posted:
            from .models import JournalEntry

            context["journal_entries"] = JournalEntry.objects.filter(
                vouchers__paymentvouchers=payment.id
            )

        return context


class PaymentVoucherCreateView(LoginRequiredMixin, CreateView):
    """Create a new payment voucher for a source document."""

    model = PaymentVoucher
    form_class = PaymentVoucherForm
    template_name = "dea/paymentvoucher_form.html"

    def get_initial(self):
        initial = super().get_initial()

        # Pre-fill source document if provided via query parameter
        source_model = self.request.GET.get("source_model")
        source_id = self.request.GET.get("source_id")

        if source_model and source_id:
            try:
                ct = ContentType.objects.get(model=source_model.lower())
                initial["source_content_type"] = ct
                initial["source_object_id"] = source_id
            except ContentType.DoesNotExist:
                pass

        return initial

    def form_valid(self, form):
        """Save form and trigger posting to accounting."""
        response = super().form_valid(form)
        payment = self.object
        payment.created_by = self.request.user
        payment.updated_by = self.request.user
        payment.save()

        try:
            # Auto-post to accounting
            with transaction.atomic():
                voucher, je = create_and_post_voucher_for_doc(
                    doc=payment,
                    user=self.request.user,
                    voucher_type_input=payment.get_voucher_type(),
                    engine=DjangoPostingEngine(),
                )
                payment.posted = True
                payment.save()

                messages.success(
                    self.request,
                    f"Payment {payment.payment_id} created and posted to accounting. "
                    f"Voucher: {voucher.voucher_no}",
                )
        except Exception as e:
            messages.error(
                self.request, f"Payment created but posting failed: {str(e)}"
            )

        return response

    def get_success_url(self):
        return reverse_lazy("dea:paymentvoucher_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Create Payment Voucher"
        return context


class PaymentVoucherUpdateView(LoginRequiredMixin, UpdateView):
    """Update a payment voucher (before posting only)."""

    model = PaymentVoucher
    form_class = PaymentVoucherForm
    template_name = "dea/paymentvoucher_form.html"

    def form_valid(self, form):
        payment = self.object

        # Prevent editing if already posted
        if payment.posted:
            messages.error(
                self.request, "Cannot edit a payment that has been posted to accounting"
            )
            return self.form_invalid(form)

        payment.updated_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("dea:paymentvoucher_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Edit Payment {self.object.payment_id}"
        context["is_posted"] = self.object.posted
        return context


class PaymentVoucherDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a payment voucher (before posting only)."""

    model = PaymentVoucher
    template_name = "dea/paymentvoucher_confirm_delete.html"
    success_url = reverse_lazy("dea:paymentvoucher_list")

    def delete(self, request, *args, **kwargs):
        payment = self.get_object()

        # Prevent deletion if already posted
        if payment.posted:
            messages.error(
                request, "Cannot delete a payment that has been posted to accounting"
            )
            return redirect(payment.get_absolute_url())

        return super().delete(request, *args, **kwargs)


# Import models and utilities
from django.utils import timezone
