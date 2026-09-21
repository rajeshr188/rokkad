"""Workspace-scoped upload, review, explicit commit and canonical download."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans.services.history_contract import HistoryError, MAX_BYTES, dump, SCHEMA
from apps.tenant_apps.loans.services.opening_export import export_loan_data
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from . import loan_history
from .loan_setup import HistorySetupForm
from .models import LoanHistoryBatch


class UploadForm(forms.Form):
    source = forms.FileField(label="Complete loan history (.jsonl)")

    def clean_source(self):
        value = self.cleaned_data["source"]
        if value.size > MAX_BYTES:
            raise forms.ValidationError("The maximum file size is 5 MiB.")
        return value


class MappingForm(HistorySetupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in tuple(self.fields):
            if name not in {"revision_id", "series_id", "product_version_id"}:
                del self.fields[name]


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def upload(request):
    args = dict(workspace_id=request.workspace.pk, actor=request.user)
    require_history_setup_access(**args)
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            batch = loan_history.stage(**args, content=form.cleaned_data["source"].read(MAX_BYTES + 1))
            return redirect("workspace_portability:loan_batch", workspace_slug=request.workspace.slug, batch_id=batch.public_id)
        except HistoryError as exc:
            form.add_error(None, exc.user_message)
    batches = LoanHistoryBatch.objects.filter(workspace_id=request.workspace.pk, profile="loan-history/1").order_by("-created_at", "-pk")[:20]
    return render(request, "data_portability/loan_history_upload.html", dict(form=form, batches=batches))


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def review(request, batch_id):
    args = dict(workspace_id=request.workspace.pk, actor=request.user, batch_id=batch_id)
    batch = loan_history.get_batch(**args)
    action = request.POST.get("action") if request.method == "POST" else None
    form = MappingForm(request.POST if action == "preview" else None,
        initial=batch.mapping, workspace_id=request.workspace.pk)
    approval, error = None, None
    try:
        if action == "preview" and form.is_valid():
            approval = loan_history.preview(**args, values={k:v.pk for k,v in form.cleaned_data.items()})
        elif action == "commit":
            loan_history.commit(**args, approval=request.POST.get("approval", ""), confirmed=request.POST.get("confirmed") == "yes")
            return redirect("workspace_portability:loan_batch", workspace_slug=request.workspace.slug, batch_id=batch_id)
        elif action == "cancel":
            loan_history.cancel(**args, confirmed=request.POST.get("confirmed") == "yes")
            return redirect("workspace_portability:loan_batch", workspace_slug=request.workspace.slug, batch_id=batch_id)
        elif action not in {None, "preview"}:
            raise HistoryError("Choose a supported import action.")
    except HistoryError as exc:
        error = exc.user_message
    batch.refresh_from_db()
    return render(request, "data_portability/loan_history_review.html", dict(batch=batch, form=form,
        approval=approval, error=error, unfinished=batch.state in {"STAGED", "READY"}))


@login_required
@never_cache
@require_http_methods(["POST"])
def export(request, loan_id):
    try:
        content, filename = export_loan_data(workspace_id=request.workspace.pk, actor=request.user, loan_id=loan_id)
    except ObjectDoesNotExist as exc:
        raise Http404("Loan history is unavailable.") from exc
    except HistoryError as exc:
        return render(request, "data_portability/loan_history_export_error.html", {"error": str(exc)}, status=400)
    response = HttpResponse(content, content_type="application/x-ndjson")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@never_cache
@require_http_methods(["GET"])
def schema(request):
    require_history_setup_access(request.workspace.pk, request.user)
    response = HttpResponse(dump(SCHEMA), content_type="application/schema+json")
    response["Content-Disposition"] = 'attachment; filename="loan-history-v1.schema.json"'
    return response
