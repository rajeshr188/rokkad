"""Print-profile setup views; publication and assignment rules remain in services."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.web.document_forms import (
    LoanDocumentPrintProfileAssignmentForm,
    LoanDocumentPrintProfileCreateForm,
    LoanDocumentPrintProfileDefinitionForm,
)
from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer,
    DocumentLayoutValidator,
    PawnLoanDocumentProjectionBuilder,
    PrintProfileValidator,
)
from apps.tenant_apps.loans.models import (
    LoanDocumentLayoutRevision,
    LoanDocumentPrintProfile,
    LoanDocumentPrintProfileRevision,
    PawnLoan,
)
from apps.tenant_apps.loans.services.print_profiles import (
    LoanDocumentPrintProfileService,
    PrintProfileServiceError,
)
from apps.tenant_apps.loans.web.document_assets import _revision_assets


@loans_setup_required
def document_print_profile_list(request):
    profiles = LoanDocumentPrintProfile.objects.filter(
        workspace=request.loans_workspace, document_type="loan_ticket",
    ).prefetch_related("revisions", "revisions__assignments__series")
    return render(
        request, "loans/setup/print_profiles/list.html", {"profiles": profiles}
    )


@loans_setup_required
def document_print_profile_create(request):
    form = LoanDocumentPrintProfileCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            revision = LoanDocumentPrintProfileService.create_profile(
                workspace=request.loans_workspace,
                document_type="loan_ticket",
                name=form.cleaned_data["name"],
                definition=form.definition(name=form.cleaned_data["name"]),
                actor=request.user,
                request=request,
            )
        except (PrintProfileServiceError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Print profile created as a validated draft.")
            return redirect('workspace_loans:document_print_profile_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
    return render(
        request, "loans/setup/print_profiles/create.html", {"form": form}
    )


def _print_profile_revision(request, revision_pk):
    return get_object_or_404(
        LoanDocumentPrintProfileRevision.objects.select_related(
            "profile", "profile__workspace"
        ).prefetch_related("assignments__series__license"),
        pk=revision_pk,
        profile__workspace=request.loans_workspace,
        profile__document_type="loan_ticket",
    )


@loans_setup_required
def document_print_profile_detail(request, revision_pk):
    revision = _print_profile_revision(request, revision_pk)
    profile = PrintProfileValidator.load(revision.definition)
    layouts = LoanDocumentLayoutRevision.objects.filter(
        layout__workspace=request.loans_workspace,
        layout__document_type="loan_ticket",
        state=LoanDocumentLayoutRevision.State.PUBLISHED,
    ).select_related("layout").order_by("layout__name", "version")
    sample_loans = PawnLoan.objects.filter(
        workspace=request.loans_workspace, approval_snapshots__isnull=False,
    ).distinct().order_by("-pk")[:20]
    return render(request, "loans/setup/print_profiles/detail.html", {
        "revision": revision,
        "profile": profile,
        "definition_form": LoanDocumentPrintProfileDefinitionForm(initial={
            "composition": profile.composition,
            "scaling_policy": profile.scaling_policy,
            "flip_edge_guidance": profile.flip_edge_guidance,
            "printer_guidance": profile.printer_guidance,
        }),
        "assignment_form": LoanDocumentPrintProfileAssignmentForm(
            workspace=request.loans_workspace
        ),
        "layout_revisions": layouts,
        "sample_loans": sample_loans,
    })


@loans_setup_required
@require_POST
def document_print_profile_update(request, revision_pk):
    revision = _print_profile_revision(request, revision_pk)
    form = LoanDocumentPrintProfileDefinitionForm(request.POST)
    if form.is_valid():
        try:
            LoanDocumentPrintProfileService.update_draft(
                revision=revision,
                definition=form.definition(name=revision.profile.name),
                actor=request.user,
                request=request,
            )
        except (PrintProfileServiceError, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Print-profile draft updated and validated.")
    else:
        messages.error(request, "Print-profile settings are invalid.")
    return redirect('workspace_loans:document_print_profile_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_print_profile_clone(request, revision_pk):
    revision = _print_profile_revision(request, revision_pk)
    clone = LoanDocumentPrintProfileService.clone_revision(
        revision=revision, actor=request.user, request=request
    )
    messages.success(request, f"Created print-profile draft revision {clone.version}.")
    return redirect('workspace_loans:document_print_profile_detail', revision_pk=clone.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_print_profile_publish(request, revision_pk):
    revision = _print_profile_revision(request, revision_pk)
    try:
        LoanDocumentPrintProfileService.publish(
            revision=revision, actor=request.user, request=request
        )
    except (PrintProfileServiceError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Print-profile revision published and frozen.")
    return redirect('workspace_loans:document_print_profile_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_print_profile_assign(request, revision_pk):
    revision = _print_profile_revision(request, revision_pk)
    form = LoanDocumentPrintProfileAssignmentForm(
        request.POST, workspace=request.loans_workspace
    )
    if form.is_valid():
        try:
            LoanDocumentPrintProfileService.assign(
                revision=revision,
                workspace=request.loans_workspace,
                series=form.cleaned_data["series"],
                actor=request.user,
                request=request,
            )
        except (PrintProfileServiceError, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Published print profile assigned.")
    else:
        messages.error(request, "Print-profile assignment scope is invalid.")
    return redirect('workspace_loans:document_print_profile_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_print_profile_retire(request, revision_pk):
    revision = _print_profile_revision(request, revision_pk)
    try:
        LoanDocumentPrintProfileService.retire(
            revision=revision, actor=request.user, request=request
        )
    except (PrintProfileServiceError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Print-profile revision retired; active assignments were disabled.",
        )
    return redirect('workspace_loans:document_print_profile_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
def document_print_profile_preview(request, revision_pk):
    revision = _print_profile_revision(request, revision_pk)
    layout_revision = get_object_or_404(
        LoanDocumentLayoutRevision.objects.select_related("layout").prefetch_related(
            "assets"
        ),
        pk=request.GET.get("layout"),
        layout__workspace=request.loans_workspace,
        layout__document_type="loan_ticket",
        state=LoanDocumentLayoutRevision.State.PUBLISHED,
    )
    loan = get_object_or_404(
        PawnLoan.objects.filter(
            workspace=request.loans_workspace,
            approval_snapshots__isnull=False,
        ).distinct(),
        pk=request.GET.get("loan"),
    )
    try:
        payload = PawnLoanDocumentProjectionBuilder.loan_ticket(loan)
        result = ConfigurableDocumentRenderer.render_with_print_profile(
            payload,
            DocumentLayoutValidator.load(layout_revision.definition),
            PrintProfileValidator.load(revision.definition),
            preview=True,
            assets=_revision_assets(layout_revision),
        )
    except (ValueError, ValidationError) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    response = HttpResponse(result.pdf, content_type="application/pdf")
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    response["Content-Disposition"] = (
        f'{disposition}; filename="profile-preview-{payload.file_name}"'
    )
    response["X-Rokkad-Preview"] = "true"
    response["X-Rokkad-Print-Profile"] = revision.profile.name
    response["X-Rokkad-Print-Profile-Hash"] = revision.content_hash
    response["X-Rokkad-Layout-Revision"] = str(layout_revision.pk)
    return response
