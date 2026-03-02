from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    UpdateView,
    ListView,
)
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..forms import LicenseForm, LicenseDocumentForm
from ..models import License, LicenseDocument, Series


@login_required
@for_htmx(use_block="content")
def license_list(request):
    """List all licenses with filtering options"""
    licenses = License.objects.all()

    # Apply filters
    license_type = request.GET.get("type")
    status = request.GET.get("status")
    business_type = request.GET.get("business_type")

    if license_type:
        licenses = licenses.filter(type=license_type)
    if status:
        licenses = licenses.filter(status=status)
    if business_type:
        licenses = licenses.filter(business_type=business_type)

    # Auto-update status for expired licenses
    for license_obj in licenses:
        license_obj.auto_update_status()

    context = {
        "object_list": licenses,
        "license_types": License.LICENSE_TYPE_CHOICES,
        "statuses": License.STATUS_CHOICES,
        "business_types": License.BUSINESS_TYPE_CHOICES,
    }

    return TemplateResponse(request, "girvi/license/license_list.html", context=context)


class LicenseCreateView(LoginRequiredMixin, CreateView):
    """Create a new license"""

    model = License
    form_class = LicenseForm
    template_name = "girvi/license/license_form.html"


class LicenseDetailView(LoginRequiredMixin, DetailView):
    """Display license details with documents and linked licenses"""

    model = License
    template_name = "girvi/license/license_detail.html"
    context_object_name = "license"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        license_obj = self.object

        # Auto-update status
        license_obj.auto_update_status()

        # Get linked licenses
        context["linked_licenses"] = license_obj.get_linked_licenses()

        # Get documents
        context["documents"] = license_obj.get_documents()
        context["document_count"] = license_obj.get_document_count()

        # Expiry info
        context["days_until_expiry"] = license_obj.days_until_expiry()
        context["is_expiring_soon"] = license_obj.is_expiring_soon(days=30)
        context["is_expired"] = license_obj.is_expired()
        context["status_color"] = license_obj.get_status_display_color()

        return context


class LicenseUpdateView(LoginRequiredMixin, UpdateView):
    """Update license details"""

    model = License
    form_class = LicenseForm
    template_name = "girvi/license/license_form.html"


class LicenseDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a license"""

    model = License
    success_url = reverse_lazy("girvi:girvi_license_list")
    template_name = "girvi/license/license_confirm_delete.html"


class LicenseExpiryReportView(LoginRequiredMixin, ListView):
    """View licenses expiring soon"""

    model = License
    template_name = "girvi/license/license_expiry_report.html"
    context_object_name = "expiring_licenses"

    def get_queryset(self):
        licenses = License.objects.all()

        # Get licenses expiring within 90 days
        expiring = [l for l in licenses if l.is_expiring_soon(days=90)]
        return sorted(
            expiring,
            key=lambda x: x.days_until_expiry()
            if x.days_until_expiry()
            else float("inf"),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = timezone.now().date()
        return context


class LicenseDocumentUploadView(LoginRequiredMixin, CreateView):
    """Upload a document for a license"""

    model = LicenseDocument
    form_class = LicenseDocumentForm
    template_name = "girvi/license/document_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        license_id = self.kwargs.get("license_id")
        context["license"] = get_object_or_404(License, pk=license_id)
        return context

    def form_valid(self, form):
        license_id = self.kwargs.get("license_id")
        form.instance.license = get_object_or_404(License, pk=license_id)
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, "Document uploaded successfully!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("girvi:girvi_license_detail", args=[self.object.license.pk])


class LicenseDocumentDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a license document"""

    model = LicenseDocument
    template_name = "girvi/license/document_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("girvi:girvi_license_detail", args=[self.object.license.pk])

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Document deleted successfully!")
        return super().delete(request, *args, **kwargs)


class LicenseRenewalView(LoginRequiredMixin, UpdateView):
    """Handle license renewal"""

    model = License
    form_class = LicenseForm
    template_name = "girvi/license/license_renewal_form.html"

    def form_valid(self, form):
        license_obj = form.instance
        old_expiry = license_obj.date_expires

        # Update renewal info
        license_obj.status = "RENEWED"
        license_obj.renewal_date = timezone.now().date()

        response = super().form_valid(form)

        messages.success(
            self.request,
            f"License renewed successfully! New expiry date: {license_obj.date_expires}",
        )
        return response

    def get_success_url(self):
        return reverse_lazy("girvi:girvi_license_detail", args=[self.object.pk])


def activate_series(request, pk):
    """Activate/deactivate a series"""
    s = get_object_or_404(Series, pk=pk)
    s.activate()
    return redirect("girvi:girvi_loan_list")
