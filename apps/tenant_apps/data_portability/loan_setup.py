"""HTTP preparation step for the Loans-owned history setup checks."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans.models import LoanLicenseRevision, LoanSeries, LoanProductVersion
from apps.tenant_apps.loans.services.history_setup import (
    HistorySetupError, preview_history_setup, require_history_setup_access,
)


class RevisionChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.license_number} ? revision {obj.revision_number} ({obj.issued_on} to {obj.expires_on})"


class ProductChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.product.name} ? version {obj.version} ({obj.status})"


class HistorySetupForm(forms.Form):
    source_namespace = forms.UUIDField(help_text="Stable UUID identifying the source register or exporting Workspace; reuse it for every import from that source.")
    source_loan_id = forms.CharField(max_length=120, strip=False, label="Stable source loan ID")
    source_loan_number = forms.CharField(max_length=120, strip=False, label="Original loan number")
    source_license_number = forms.CharField(max_length=100, strip=False, label="Original licence number")
    disbursed_on = forms.DateField(label="Original disbursal date", widget=forms.DateInput(attrs={"type": "date"}))
    tenure_months = forms.IntegerField(min_value=1, label="Original tenure in months")
    calculation_contract_version = forms.CharField(max_length=40, strip=False, label="Source calculation contract version")
    operational_grace_days = forms.IntegerField(min_value=0, max_value=30, label="Source operational grace days")
    revision_id = RevisionChoice(queryset=LoanLicenseRevision.objects.none(), label="Destination licence revision")
    series_id = forms.ModelChoiceField(queryset=LoanSeries.objects.none(), label="Destination series")
    product_version_id = ProductChoice(queryset=LoanProductVersion.objects.none(), label="Destination product version")
    source_release_id = forms.CharField(max_length=120, strip=False, required=False, label="Source full-release ID (if released)")
    source_release_number = forms.CharField(max_length=120, strip=False, required=False, label="Original release number (if released)")

    def __init__(self, *args, workspace_id, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["revision_id"].queryset = LoanLicenseRevision.objects.filter(workspace_id=workspace_id).order_by("license_number", "revision_number")
        self.fields["series_id"].queryset = LoanSeries.objects.filter(workspace_id=workspace_id).select_related("license").order_by("license_id", "code")
        self.fields["product_version_id"].queryset = LoanProductVersion.objects.filter(workspace_id=workspace_id,
            repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", status__in=["ACTIVE", "RETIRED"]).select_related("product").order_by("product_id", "version")

    def preview_arguments(self):
        values = self.cleaned_data.copy()
        for field in ("revision_id", "series_id", "product_version_id"):
            values[field] = values[field].pk
        return values


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def prepare(request):
    args = {"workspace_id": request.workspace.pk, "actor": request.user}
    require_history_setup_access(**args)
    form = HistorySetupForm(request.POST if request.method == "POST" else None, workspace_id=request.workspace.pk)
    preview = None
    if request.method == "POST" and form.is_valid():
        try:
            preview = preview_history_setup(**args, **form.preview_arguments())
        except HistorySetupError as exc:
            form.add_error(None, str(exc))
    return render(request, "data_portability/loan_setup.html", {"form": form, "preview": preview})
