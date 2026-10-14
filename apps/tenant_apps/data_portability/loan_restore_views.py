"""Workspace-scoped destination mapping and review of published loan files."""
import json

from django import forms
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import Http404
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_GET
from django_select2.views import AutoResponseView

from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget
from apps.tenant_apps.loans.models import LoanLicenseRevision, LoanSeries, LoanProductVersion, PawnLoan
from apps.tenant_apps.loans.services.history_setup import require_history_preparation_access
from apps.tenant_apps.loans.services.history_contract import HistoryError
from . import loan_restore
from .loan_setup import RevisionChoice, ProductChoice
from .children import parent_for


class RestoreBorrowerWidget(PartyAutocompleteWidget):
    active_only = False

    def get_queryset(self):
        return super().get_queryset().exclude(status=Party.PartyStatus.ARCHIVED)


class DestinationForm(forms.Form):
    borrower_id = forms.ModelChoiceField(queryset=Party.objects.none(), label="Destination customer")
    series_id = forms.ModelChoiceField(queryset=LoanSeries.objects.none(), label="Destination series")
    revision_id = RevisionChoice(queryset=LoanLicenseRevision.objects.none(), label="Original licence revision")
    product_version_id = ProductChoice(queryset=LoanProductVersion.objects.none(), label="Servicing product")

    def __init__(self, *args, workspace, closed_position=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["borrower_id"].queryset = Party.objects.filter(workspace_id=workspace.pk).exclude(status=Party.PartyStatus.ARCHIVED)
        self.fields["borrower_id"].widget = RestoreBorrowerWidget(
            data_url=reverse("workspace_portability:restore_borrowers", kwargs={"workspace_slug": workspace.slug}),
            attrs={"data-placeholder": "Search customer name, code or phone", "data-minimum-input-length": 1})
        self.fields["series_id"].queryset = LoanSeries.objects.filter(workspace_id=workspace.pk).select_related("license").order_by("license_id", "code")
        if closed_position:
            del self.fields["revision_id"], self.fields["product_version_id"]
        else:
            self.fields["revision_id"].queryset = LoanLicenseRevision.objects.filter(workspace_id=workspace.pk).order_by("license_number", "revision_number")
            self.fields["product_version_id"].queryset = LoanProductVersion.objects.filter(workspace_id=workspace.pk,
                status__in=["ACTIVE", "RETIRED"], repayment_structure__in=["FLEXIBLE_PARTIAL_PAYMENT", "SINGLE_PAYMENT_BULLET"],
                amortisation_method="NONE").select_related("product").order_by("product_id", "version")

    def mapping(self):
        return {key: obj.pk for key, obj in self.cleaned_data.items()}


@login_required
@never_cache
@require_GET
def borrowers(request):
    require_history_preparation_access(request.workspace.pk, request.user, read_only=True)

    class BorrowerResponse(AutoResponseView):
        def get_widget_or_404(self):
            try:
                url = signing.loads(request.GET.get("field_id", ""), salt=PartyAutocompleteWidget.token_salt,
                    max_age=PartyAutocompleteWidget.token_max_age)
            except signing.BadSignature as exc:
                raise Http404("Customer search is invalid or expired.") from exc
            if url != request.path:
                raise Http404("Customer search belongs to another Workspace URL.")
            widget = RestoreBorrowerWidget(data_url=request.path)
            self.queryset = widget.get_queryset().filter(workspace_id=request.workspace.pk)
            return widget

    return BorrowerResponse.as_view()(request)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def review(request, batch_id):
    args = dict(workspace_id=request.workspace.pk, actor=request.user, batch_id=batch_id)
    batch = loan_restore.get_batch(**args)
    action = request.POST.get("action") if request.method == "POST" else None
    forms_rows = []
    for row in batch.document.get("loans", []):
        initial = batch.mapping.get(row["key"], {}).copy()
        reference = row["borrower"]
        party = parent_for(dict(party_source_system=reference["system"], party_external_id=reference["id"]), request.workspace.pk)
        if party is not None:
            initial.setdefault("borrower_id", party.party_id)
        forms_rows.append(dict(source=row, form=DestinationForm(request.POST if action in {"preview", "prepare"} else None,
            initial=initial, prefix="loan-" + row["key"], workspace=request.workspace,
            closed_position=batch.profile.startswith("loan-closed-position"))))
    approval, error = None, None
    try:
        if action in {"preview", "prepare"}:
            valid = [row["form"].is_valid() for row in forms_rows]
            if valid and all(valid):
                values = {row["source"]["key"]: row["form"].mapping() for row in forms_rows}
                if action == "prepare":
                    loan_restore.prepare(**args, values=values)
                else:
                    approval = loan_restore.preview(**args, values=values)
        elif action == "commit":
            loan_restore.commit(**args, approval=request.POST.get("approval", ""), confirmed=request.POST.get("confirmed") == "yes")
            return redirect("workspace_portability:restore_batch", workspace_slug=request.workspace.slug, batch_id=batch_id)
        elif action == "cancel":
            loan_restore.cancel(**args, confirmed=request.POST.get("confirmed") == "yes")
            return redirect("workspace_portability:loan_upload", workspace_slug=request.workspace.slug)
        elif action is not None:
            raise HistoryError("Choose a supported import action.")
    except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
        error = str(exc)
    batch.refresh_from_db()
    return render(request, "data_portability/loan_restore_review.html", dict(batch=batch, forms_rows=forms_rows,
        approval=approval, error=error, owner_review=request.workspace.owner_id == request.user.pk or request.user.is_superuser,
        unfinished=batch.state in {"STAGED", "READY"},
        summary=json.dumps(batch.preview.get("summary", {}), indent=2, ensure_ascii=False),
        imported_loans=PawnLoan.objects.filter(workspace_id=request.workspace.pk, pk__in=batch.results).order_by("pk")))
