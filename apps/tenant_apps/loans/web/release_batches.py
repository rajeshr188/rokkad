import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.tenant_apps.loans.access import loans_action_required, loans_workspace_required
from apps.tenant_apps.loans.models import PawnCollateralItem, PawnLoan, PawnReleaseBatch
from apps.tenant_apps.loans.services.release_batches import (
    MAX_BATCH_LOANS, complete_release_batch, decode_quote, preview_release_batch,
)


class SelectionForm(forms.Form):
    loans = forms.MultipleChoiceField(choices=(), label="Search loan numbers, borrowers or phone numbers")


class ConfirmationForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    quote_token = forms.CharField(widget=forms.HiddenInput)
    paid_by = forms.CharField(max_length=255, label="Paid by")
    payment_reference = forms.CharField(max_length=100, required=False, label="Payment reference (optional)")
    payment_confirmed = forms.BooleanField(label="I confirm the exact combined settlement has been collected.")


class CollectorForm(forms.Form):
    loan_id = forms.IntegerField(widget=forms.HiddenInput)
    collector_type = forms.ChoiceField(choices=(("borrower", "The borrower"), ("other", "Another person")), label="Who collects these items?")
    collector_name = forms.CharField(max_length=255, required=False, label="Other collector's name")
    relationship = forms.CharField(max_length=100, required=False, label="Relationship to borrower")
    authorization_note = forms.CharField(max_length=500, required=False, label="How was their authority to collect confirmed?")
    handover_confirmed = forms.BooleanField(label="Collector verified and all items ready for handover.")

    def clean(self):
        data = super().clean()
        if data.get("collector_type") == "other":
            for name in ("collector_name", "relationship", "authorization_note"):
                if not data.get(name):
                    self.add_error(name, "Required when someone other than the borrower collects.")
        data["collector_is_borrower"] = data.get("collector_type") == "borrower"
        return data


def _style(form):
    for field in form.fields.values():
        field.widget.attrs.setdefault("class", "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-select" if isinstance(field.widget, forms.Select) else "form-control")
    return form


@loans_action_required("loan.release")
@require_GET
@never_cache
def search(request):
    query = request.GET.get("q", "").strip()[:100]
    outstanding = PawnCollateralItem.objects.filter(loan_id=OuterRef("pk"), workspace=request.loans_workspace).exclude(custody_state="WITH_CUSTOMER")
    loans = PawnLoan.objects.filter(workspace=request.loans_workspace, state="ACTIVE").filter(
        Exists(outstanding),
    ).select_related("borrower", "license", "series").order_by("loan_number", "pk")
    if query:
        loans = loans.filter(Q(loan_number__icontains=query) | Q(borrower__display_name__icontains=query) | Q(borrower__primary_phone__icontains=query))
    page = Paginator(loans, 20).get_page(request.GET.get("page", 1))
    return JsonResponse({"results": [{"id": loan.pk, "text": f"{loan.loan_number} — {loan.borrower.display_name} — {loan.license.license_number} / {loan.series.code}"} for loan in page], "pagination": {"more": page.has_next()}})


@loans_action_required("loan.release")
@require_http_methods(["GET", "POST"])
@never_cache
def create(request):
    workspace = request.loans_workspace
    context = {"max_loans": MAX_BATCH_LOANS}
    data = request.POST.copy() if request.method == "POST" else None
    confirming = data is not None and data.get("action") == "complete"
    ids = data.getlist("loans") if data is not None else []
    header = _style(ConfirmationForm(data if confirming else None, initial={"request_key": uuid.uuid4()}))
    collector_forms = []
    try:
        if confirming:
            evidence = decode_quote(data.get("quote_token", ""), workspace=workspace)
            ids = [row["loan_id"] for row in evidence["rows"]]
            collector_forms = [_style(CollectorForm(data, prefix=f"collector_{pk}")) for pk in ids]
            valid = header.is_valid()
            for pk, form in zip(ids, collector_forms):
                valid = form.is_valid() and valid
                if form.cleaned_data.get("loan_id") != pk:
                    form.add_error(None, "Collector confirmation does not match the selected loan.")
                    valid = False
            if valid:
                batch = complete_release_batch(
                    workspace=workspace, actor=request.user, collectors=[form.cleaned_data for form in collector_forms],
                    **header.cleaned_data,
                )
                messages.success(request, f"Release batch {batch.pk} completed.")
                return redirect("loans:release_batch_detail", batch_pk=batch.pk)
        if ids:
            context["preview"] = preview_release_batch(workspace=workspace, actor=request.user, loan_ids=ids)
    except (ValueError, ValidationError) as exc:
        context["error"] = str(exc)
        if confirming:
            try:
                context["preview"] = preview_release_batch(workspace=workspace, actor=request.user, loan_ids=ids)
            except (ValueError, ValidationError):
                pass
    preview = context.get("preview")
    if confirming:
        context["form_errors"] = header.errors
    if preview:
        # Every changed selection / failed completion requires fresh payment confirmation.
        header_data = data.copy() if data is not None else {}
        header_data.update({"request_key": data.get("request_key") or str(uuid.uuid4()) if data is not None else str(uuid.uuid4()), "quote_token": preview["quote_token"]})
        header_data.pop("payment_confirmed", None)
        header = _style(ConfirmationForm(initial=header_data))
        if confirming:
            context["confirmation_errors"] = "Review the loan details and confirm payment again."
        for row in preview["rows"]:
            pk = row["loan"].pk
            prefix = f"collector_{pk}"
            bound = data if data is not None and data.get(f"{prefix}-loan_id") else None
            row["collector_form"] = _style(CollectorForm(bound, prefix=prefix, initial={"loan_id": pk, "collector_type": "borrower"}))
        context["confirmation_form"] = header
    selected = preview["rows"] if preview else []
    selection = SelectionForm(initial={"loans": [row["loan"].pk for row in selected]})
    selection.fields["loans"].choices = [(row["loan"].pk, f'{row["loan"].loan_number} — {row["loan"].borrower.display_name}') for row in selected]
    selection.fields["loans"].widget.attrs.update({"id": "batch-loans", "class": "form-select", "data-search-url": reverse("loans:release_batch_search")})
    context["selection_form"] = selection
    template = "loans/batches/_review.html" if request.headers.get("HX-Request") == "true" else "loans/batches/create.html"
    return render(request, template, context)


@loans_workspace_required
@require_GET
@never_cache
def detail(request, batch_pk):
    batch = get_object_or_404(PawnReleaseBatch.objects.select_related("created_by").prefetch_related("lines__release__loan", "lines__release__reversal"), workspace=request.loans_workspace, pk=batch_pk)
    return render(request, "loans/batches/detail.html", {"batch": batch})


@loans_workspace_required
@require_GET
@never_cache
def history(request):
    rows = PawnReleaseBatch.objects.filter(workspace=request.loans_workspace).order_by("-pk")
    return render(request, "loans/batches/history.html", {"page": Paginator(rows, 25).get_page(request.GET.get("page"))})
