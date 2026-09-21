"""Reviewable archive acceptance and a separate historical-only browser."""
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.orgs.access import resolve_workspace_access
from apps.tenant_apps.loans.models import HistoricalLoanEvidence
from apps.tenant_apps.loans.services.archive import get_evidence, export_evidence, require_archive_read
from apps.tenant_apps.loans.services.archive_contract import MAX_BYTES, SCHEMA
from apps.tenant_apps.loans.services.history_contract import dump
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from apps.tenant_apps.loans.services.portability_validation import PortabilityValidationError
from . import loan_archive
from .models import LoanArchiveBatch


class ArchiveUploadForm(forms.Form):
    source = forms.FileField(label="Prepared historical evidence (.json)")

    def clean_source(self):
        value = self.cleaned_data["source"]
        if value.size > MAX_BYTES:
            raise forms.ValidationError("The maximum file size is 1 MiB.")
        return value


@login_required
@never_cache
@require_http_methods(["GET"])
def listing(request):
    workspace = require_archive_read(request.workspace.pk, request.user)
    query = request.GET.get("q", "")[:255].strip()
    rows = HistoricalLoanEvidence.objects.filter(workspace_id=workspace.pk).order_by("-accepted_at", "-pk")
    if query:
        rows = rows.filter(Q(source_id__icontains=query) | Q(document__facts__loan_number__icontains=query))
    access = resolve_workspace_access(actor=request.user, workspace=workspace)
    can_import = (access.platform_override or workspace.owner_id == request.user.pk) and all(
        access.can(action) for action in ("data.import", "workspace.settings.manage"))
    return render(request, "data_portability/archive_list.html", {
        "page": Paginator(rows, 25).get_page(request.GET.get("page")), "query": query, "can_import": can_import})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def upload(request):
    args = dict(workspace_id=request.workspace.pk, actor=request.user)
    require_history_setup_access(**args)
    form = ArchiveUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            batch = loan_archive.stage(**args, content=form.cleaned_data["source"].read(MAX_BYTES + 1))
            return redirect("workspace_portability:archive_batch", workspace_slug=request.workspace.slug, batch_id=batch.public_id)
        except PortabilityValidationError as exc:
            form.add_error(None, exc.user_message)
    batches = LoanArchiveBatch.objects.filter(workspace_id=request.workspace.pk).order_by("-created_at", "-pk")[:20]
    return render(request, "data_portability/archive_upload.html", {"form": form, "batches": batches})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def review(request, batch_id):
    args = dict(workspace_id=request.workspace.pk, actor=request.user, batch_id=batch_id)
    batch = loan_archive.get_batch(**args)
    error, report, approval = None, None, None
    try:
        if request.method == "POST":
            if request.POST.get("action") == "accept":
                result = loan_archive.commit(**args, approval=request.POST.get("approval", ""), confirmed=request.POST.get("confirmed") == "yes")
                return redirect("workspace_portability:archive_detail", workspace_slug=request.workspace.slug, evidence_id=result.public_id)
            elif request.POST.get("action") == "cancel":
                loan_archive.cancel(**args, confirmed=request.POST.get("confirmed") == "yes")
            else:
                error = "Choose an archive review action."
        batch.refresh_from_db()
        if batch.state == "STAGED":
            report, approval = loan_archive.preview(**args)
    except PortabilityValidationError as exc:
        error = exc.user_message
    return render(request, "data_portability/archive_review.html", dict(
        batch=batch, document=batch.document, report=report, approval=approval, error=error,
        source_json=dump(batch.document), staged=batch.state == "STAGED"))


@login_required
@never_cache
@require_http_methods(["GET"])
def detail(request, evidence_id):
    evidence = get_evidence(workspace_id=request.workspace.pk, actor=request.user, evidence_id=evidence_id)
    access = resolve_workspace_access(actor=request.user, workspace=request.workspace)
    return render(request, "data_portability/archive_detail.html", dict(
        evidence=evidence, document=evidence.document, report=evidence.review,
        source_json=dump(evidence.document), can_export=access.can("data.export")))


@login_required
@never_cache
@require_http_methods(["POST"])
def export(request, evidence_id):
    content = export_evidence(workspace_id=request.workspace.pk, actor=request.user, evidence_id=evidence_id)
    response = HttpResponse(content, content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="historical-loan-evidence.json"'
    return response


@login_required
@never_cache
@require_http_methods(["GET"])
def schema(request):
    require_history_setup_access(request.workspace.pk, request.user)
    response = HttpResponse(dump({"$schema": "https://json-schema.org/draft/2020-12/schema", **SCHEMA}), content_type="application/schema+json")
    response["Content-Disposition"] = 'attachment; filename="loan-closed-evidence-v1.schema.json"'
    return response
