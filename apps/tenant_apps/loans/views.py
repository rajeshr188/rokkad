import hashlib
from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace

import fitz
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, HttpResponseGone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import (
    LOANS_ADMIN_ACTION,
    LOANS_OWNER_ACTION,
    assert_loans_owner_access,
    loans_owner_required,
    loans_setup_required,
    loans_workspace_required,
    loans_action_required,
)
from apps.tenant_apps.loans.domain import (
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.filters import (
    LoanDocumentIssueFilter,
    PawnLoanFilter,
    PawnPhysicalVerificationSessionFilter,
    PawnStorageLocationFilter,
)
from apps.tenant_apps.loans.forms import (
    LoanDocumentAssetUploadForm,
    LoanDocumentAssignmentForm,
    LoanDocumentFlowBlockForm,
    LoanDocumentFlowSettingsForm,
    LoanDocumentLayoutCreateForm,
    LoanDocumentLayoutDefinitionForm,
    LoanDocumentLayoutPackImportForm,
    LoanDocumentOverlayBlockForm,
    LoanDocumentOverlayLogicalSettingsForm,
    LoanDocumentOverlaySettingsForm,
    LoanDocumentPrintProfileAssignmentForm,
    LoanDocumentPrintProfileCreateForm,
    LoanDocumentPrintProfileDefinitionForm,
    PawnPhysicalVerificationObservationForm,
    PawnPhysicalVerificationStartForm,
    PawnSetupTransferForm,
)

_OVERLAY_PAGE_DIMENSIONS_MM = {
    "A4": (210, 297), "A5": (148, 210), "LETTER": (216, 279),
}

_PENDING_STORAGE_ITEM_SESSION_KEY = "loans_pending_storage_item"

from apps.tenant_apps.loans.web.communication_actions import pawn_communication_consent
from apps.tenant_apps.loans.web.communication_policy_actions import (
    pawn_communication_policy,
)
from apps.tenant_apps.loans.web.funding import (
    funding_loan_agreement_pdf,
    funding_loan_read_console,
    funding_loan_read_detail,
    funding_loan_repayment_receipt_pdf,
    funding_loan_return_receipt_pdf,
    funding_loan_statement_pdf,
)
from apps.tenant_apps.loans.web.operations import (
    pawn_loan_notice_list,
    pawn_operations_console,
    pawn_operations_runbook,
    pawn_risk_portfolio,
    pawn_risk_whatsapp_pilot,
)
from apps.tenant_apps.loans.web.reports import (
    pawn_loan_report_export,
    pawn_loan_reports,
    pawn_party_statement,
)
from apps.tenant_apps.loans.web.risk_actions import pawn_risk_borrower_notice_create


def _fit_overlay_geometry(definition, target_page_size):
    """Proportionally fit flat absolute-overlay blocks to another page size."""
    source_page_size = definition.get("page_size", "A4")
    if source_page_size == target_page_size:
        return
    source_width, source_height = _OVERLAY_PAGE_DIMENSIONS_MM[source_page_size]
    target_width, target_height = _OVERLAY_PAGE_DIMENSIONS_MM[target_page_size]
    width_ratio = target_width / source_width
    height_ratio = target_height / source_height
    for page_blocks in (definition.get("blocks", []), definition.get("back_blocks", [])):
        for block in page_blocks:
            width = max(5, round(float(block["width_mm"]) * width_ratio))
            # Preserve useful text/table height while fitting its top-left
            # position. Narrower A5 blocks wrap more often and therefore need
            # at least their original vertical allowance.
            height = max(1, round(float(block["height_mm"])))
            block["width_mm"] = min(width, target_width)
            block["height_mm"] = min(height, target_height)
            block["x_mm"] = min(
                max(0, round(float(block["x_mm"]) * width_ratio)),
                target_width - block["width_mm"],
            )
            block["y_mm"] = min(
                max(0, round(float(block["y_mm"]) * height_ratio)),
                target_height - block["height_mm"],
            )
    definition["page_size"] = target_page_size
from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer,
    DocumentAsset,
    DocumentLayoutValidator,
    PawnLoanDocumentProjectionBuilder,
    PrintProfileValidator,
    built_in_print_profile,
    starter_layout,
)
from apps.tenant_apps.loans.documents.integrity import get_document_integrity_findings
from apps.tenant_apps.loans.documents.packs import (
    LayoutPackError,
    export_layout_pack,
    import_layout_pack,
)
from apps.tenant_apps.loans.models import (
    LoanDocumentIssue,
    LoanDocumentLayout,
    LoanDocumentLayoutRevision,
    LoanDocumentPrintProfile,
    LoanDocumentPrintProfileRevision,
    LoanOperationalNotice,
    PawnCollateralItem,
    PawnCollateralPhoto,
    PawnLoan,
    PawnLoanEvent,
    PawnLoanAuction,
    PawnLoanRelease,
    PawnLoanRenewal,
    PawnPhysicalVerificationObservation,
    PawnPhysicalVerificationSession,
    PawnStorageLocation,
)
from apps.tenant_apps.loans.selectors import (
    get_pawn_loan_balance,
    get_pawn_loan_collateral_valuation,
    get_pawn_loan_delinquency,
    get_pawn_loan_exposure,
    get_pawn_loan_notice_rows,
    get_pawn_loan_risk_assessment,
    get_pawn_loan_series_navigation,
    get_physical_verification_detail,
)
from apps.tenant_apps.loans.services import (
    DocumentLayoutServiceError,
    LoanDocumentLayoutService,
    LoanOperationalNoticeError,
    PawnCollateralMediaError,
    PawnLifecycleError,
    PawnLoanDocumentError,
    PawnLoanDocumentService,
    PawnPhysicalVerificationError,
    RiskSnapshotRefreshError,
    assess_pawn_loan_event_reversal,
    retry_operational_notice,
    issue_configurable_document,
    preview_pawn_loan_accruals,
    reassess_pawn_loans_batch,
    record_physical_verification_observation,
    refresh_loan_risk_snapshot,
    render_collateral_label,
    render_storage_location_label,
    start_physical_verification,
    transfer_expired_draft_setup,
)
from apps.tenant_apps.loans.services.print_profiles import (
    LoanDocumentPrintProfileService,
    PrintProfileServiceError,
)


@loans_workspace_required
def pawn_loan_list(request):
    loans = PawnLoan.objects.filter(workspace=request.loans_workspace).select_related(
        "borrower", "license", "series"
    ).order_by("-created_at")
    loan_filter = PawnLoanFilter(
        request.GET,
        queryset=loans,
        workspace=request.loans_workspace,
    )
    page_obj = Paginator(loan_filter.qs, 25).get_page(request.GET.get("page"))
    readiness = get_pawn_draft_readiness(request.loans_workspace)
    return render(
        request,
        "loans/pawn/list.html",
        {
            "loans": page_obj.object_list,
            "loan_filter": loan_filter,
            "page_obj": page_obj,
            "readiness": readiness,
            "can_manage_loan_setup": request.loans_workspace_access.can("workspace.settings.manage"),
        },
    )


@loans_setup_required
def document_layout_list(request):
    layouts = LoanDocumentLayout.objects.filter(workspace=request.loans_workspace).prefetch_related("revisions")
    assignments = {
        assignment.revision_id: assignment
        for layout in layouts
        for revision in layout.revisions.all()
        for assignment in revision.assignments.filter(is_active=True).select_related("license", "series")
    }
    return render(request, "loans/setup/documents/list.html", {
        "layouts": layouts, "assignments": assignments,
        "pack_form": LoanDocumentLayoutPackImportForm(),
    })


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


@loans_setup_required
def document_issue_list(request):
    issues = LoanDocumentIssue.objects.filter(
        workspace=request.loans_workspace
    ).select_related(
        "revision__layout", "print_profile_revision__profile", "issued_by"
    ).order_by("-issued_at", "-pk")
    issue_filter = LoanDocumentIssueFilter(request.GET, queryset=issues)
    page_obj = Paginator(issue_filter.qs, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "loans/setup/documents/issues.html",
        {
            "issue_filter": issue_filter,
            "issues": page_obj.object_list,
            "page_obj": page_obj,
        },
    )


def _document_issue(request, issue_pk):
    return get_object_or_404(
        LoanDocumentIssue.objects.select_related(
            "revision__layout", "print_profile_revision__profile",
            "prior_issue", "issued_by",
        ),
        pk=issue_pk,
        workspace=request.loans_workspace,
    )


@loans_setup_required
def document_issue_detail(request, issue_pk):
    return render(
        request,
        "loans/setup/documents/issue_detail.html",
        {"issue": _document_issue(request, issue_pk)},
    )


@loans_setup_required
@never_cache
def document_issue_artifact(request, issue_pk):
    issue = _document_issue(request, issue_pk)
    issue.artifact.open("rb")
    content = issue.artifact.read()
    issue.artifact.close()
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="loan-document-issue-{issue.pk}.pdf"'
    )
    response["X-Rokkad-Document-Issue"] = str(issue.pk)
    response["X-Rokkad-PDF-Hash"] = issue.pdf_hash
    return response


@loans_setup_required
def document_layout_guide(request):
    return render(request, "loans/setup/documents/guide.html")


@loans_setup_required
def document_layout_create(request):
    form = LoanDocumentLayoutCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            document_type = form.cleaned_data["document_type"]
            revision = LoanDocumentLayoutService.create_layout(
                workspace=request.loans_workspace, document_type=document_type,
                name=form.cleaned_data["name"], definition=starter_layout(
                    document_type, schema_version=3,
                    layout_mode=form.cleaned_data["layout_mode"] or "FLOW",
                ).canonical_dict(),
                actor=request.user, request=request,
            )
        except (DocumentLayoutServiceError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Starter document layout created as a draft.")
            return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
    return render(request, "loans/setup/documents/create.html", {"form": form})


def _document_revision(request, revision_pk):
    return get_object_or_404(
        LoanDocumentLayoutRevision.objects.select_related("layout", "layout__workspace").prefetch_related("assets", "assignments__license", "assignments__series"),
        pk=revision_pk, layout__workspace=request.loans_workspace,
    )


@loans_setup_required
def document_layout_detail(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    return render(request, "loans/setup/documents/detail.html", {
        "revision": revision,
        "definition_form": LoanDocumentLayoutDefinitionForm(initial={"definition": revision.definition}),
        "asset_form": LoanDocumentAssetUploadForm(),
        "assignment_form": LoanDocumentAssignmentForm(workspace=request.loans_workspace),
        "sample_loan": PawnLoan.objects.filter(workspace=request.loans_workspace, approval_snapshots__isnull=False).order_by("-pk").first(),
    })


@loans_setup_required
def document_layout_designer(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    try:
        layout = DocumentLayoutValidator.load(revision.definition)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
    if layout.schema_version < 2 or layout.layout_mode != "FLOW":
        messages.error(request, "The visual editor supports Flow schema-v2+ drafts only.")
        return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
    if request.method == "POST":
        if revision.state != revision.State.DRAFT:
            messages.error(request, "Published revisions are immutable. Clone this revision before editing.")
            return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
        definition = deepcopy(revision.definition)
        operation = request.POST.get("operation")
        try:
            if operation == "save_settings":
                form = LoanDocumentFlowSettingsForm(request.POST)
                if not form.is_valid():
                    raise ValueError("Page or theme settings are invalid.")
                definition["page_size"] = form.cleaned_data["page_size"]
                definition["page"] = {"margin_mm": form.cleaned_data["margin_mm"]}
                definition["theme"] = {
                    key: form.cleaned_data[key] for key in (
                        "primary_color", "border_color", "font_family",
                        "body_font_size_pt", "heading_font_size_pt",
                    )
                }
            elif operation == "add_block":
                form = LoanDocumentFlowBlockForm(request.POST)
                if not form.is_valid():
                    raise ValueError("New block settings are invalid.")
                definition["blocks"].append(form.block_definition())
            elif operation in {"move_up", "move_down", "remove"}:
                index = int(request.POST.get("index", "-1"))
                if not 0 <= index < len(definition["blocks"]):
                    raise ValueError("Selected block no longer exists.")
                if operation == "remove":
                    definition["blocks"].pop(index)
                else:
                    target = index - 1 if operation == "move_up" else index + 1
                    if 0 <= target < len(definition["blocks"]):
                        definition["blocks"][index], definition["blocks"][target] = definition["blocks"][target], definition["blocks"][index]
            else:
                raise ValueError("Unknown visual editor operation.")
            revision = LoanDocumentLayoutService.update_draft(
                revision=revision, definition=definition, actor=request.user, request=request,
            )
        except (DocumentLayoutServiceError, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Flow draft updated and validated.")
        return redirect('workspace_loans:document_layout_designer', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
    settings_form = LoanDocumentFlowSettingsForm(initial={
        "page_size": layout.page_size, "margin_mm": layout.margin_mm,
        "primary_color": layout.primary_color, "border_color": layout.border_color,
        "font_family": layout.font_family, "body_font_size_pt": layout.body_font_size_pt,
        "heading_font_size_pt": layout.heading_font_size_pt,
    })
    return render(request, "loans/setup/documents/designer.html", {
        "revision": revision, "layout": layout, "settings_form": settings_form,
        "block_form": LoanDocumentFlowBlockForm(),
        "sample_loan": PawnLoan.objects.filter(
            workspace=request.loans_workspace, approval_snapshots__isnull=False,
        ).order_by("-pk").first(),
    })


@loans_setup_required
@never_cache
def document_layout_overlay_background(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    layout = DocumentLayoutValidator.load(revision.definition)
    if layout.layout_mode != "ABSOLUTE_OVERLAY":
        return HttpResponseGone("This revision is not an absolute overlay layout.")
    background_key = layout.surface_background("ORIGINAL_FRONT")
    asset = get_object_or_404(revision.assets, key=background_key, kind="BACKGROUND")
    asset.file.open("rb")
    content = asset.file.read()
    asset.file.close()
    if asset.mime_type != "application/pdf":
        return HttpResponse(content, content_type=asset.mime_type)
    document = fitz.open(stream=content, filetype="pdf")
    try:
        pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        preview = pixmap.tobytes("png")
    finally:
        document.close()
    return HttpResponse(preview, content_type="image/png")


@loans_setup_required
def document_layout_overlay_designer(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    try:
        layout = DocumentLayoutValidator.load(revision.definition)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
    if layout.schema_version < 2 or layout.layout_mode != "ABSOLUTE_OVERLAY":
        messages.error(request, "The overlay editor supports absolute-overlay schema-v2+ drafts only.")
        return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
    background_keys = tuple(revision.assets.filter(kind="BACKGROUND").values_list("key", flat=True))
    image_keys = tuple(revision.assets.filter(kind="IMAGE").values_list("key", flat=True))
    if request.method == "POST":
        if revision.state != revision.State.DRAFT:
            messages.error(request, "Published revisions are immutable. Clone this revision before editing.")
            return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
        definition = deepcopy(revision.definition)
        operation = request.POST.get("operation")
        try:
            if operation == "save_settings":
                if layout.schema_version >= 3:
                    form = LoanDocumentOverlayLogicalSettingsForm(
                        request.POST,
                        background_keys=background_keys,
                        loan_ticket=layout.document_type == "loan_ticket",
                    )
                else:
                    form = LoanDocumentOverlaySettingsForm(
                        request.POST, background_keys=background_keys,
                        sheet_composition_enabled=layout.document_type == "loan_ticket",
                    )
                if not form.is_valid():
                    errors = "; ".join(
                        f"{form.fields.get(field).label if field in form.fields else 'Settings'}: {message}"
                        for field, field_errors in form.errors.get_json_data().items()
                        for message in (error["message"] for error in field_errors)
                    )
                    raise ValueError(errors or "Overlay page settings are invalid.")
                if layout.schema_version >= 3:
                    definition["page_size"] = form.cleaned_data["page_size"]
                    definition["background_asset_key"] = form.cleaned_data[
                        "background_asset_key"
                    ]
                    backgrounds = form.surface_backgrounds()
                    definition["surfaces"] = (
                        {"backgrounds": backgrounds} if backgrounds else None
                    )
                    definition.pop("copy_mode", None)
                    definition.pop("sheet", None)
                else:
                    composition = form.cleaned_data.get("sheet_composition")
                    if composition and definition.get("page_size", "A4") != "A5":
                        _fit_overlay_geometry(definition, "A5")
                    else:
                        definition["page_size"] = form.cleaned_data["page_size"]
                    if composition:
                        # Compact A5 ticket fields should reduce type before
                        # rejecting realistic values that wrap by one line.
                        for block in definition.get("blocks", []):
                            if block.get("type") in {"title", "field", "verification", "signature"}:
                                block["overflow_policy"] = "SHRINK"
                    definition["copy_mode"] = form.cleaned_data["copy_mode"]
                    if composition:
                        definition["background_asset_key"] = ""
                        definition["sheet"] = {
                            "composition": composition,
                            "backgrounds": {
                                surface: form.cleaned_data[surface]
                                for surface in ("original_front", "duplicate_front", "original_back", "duplicate_back")
                            },
                        }
                    else:
                        definition["sheet"] = None
                        definition["background_asset_key"] = form.cleaned_data["background_asset_key"]
            elif operation in {"add_block", "save_block"}:
                form = LoanDocumentOverlayBlockForm(request.POST, asset_keys=image_keys)
                if not form.is_valid():
                    raise ValueError("Overlay block settings are invalid.")
                block = form.block_definition()
                if operation == "add_block":
                    definition["blocks"].append(block)
                else:
                    index = int(request.POST.get("index", "-1"))
                    if not 0 <= index < len(definition["blocks"]):
                        raise ValueError("Selected overlay block no longer exists.")
                    existing = definition["blocks"][index]
                    for key in ("value_format", "overflow_policy", "max_characters", "visible_when", "table_columns", "repeat_header", "style_variant"):
                        if key in existing and key not in block:
                            block[key] = existing[key]
                    definition["blocks"][index] = block
            elif operation == "remove":
                index = int(request.POST.get("index", "-1"))
                if not 0 <= index < len(definition["blocks"]):
                    raise ValueError("Selected overlay block no longer exists.")
                definition["blocks"].pop(index)
            else:
                raise ValueError("Unknown overlay editor operation.")
            revision = LoanDocumentLayoutService.update_draft(
                revision=revision, definition=definition, actor=request.user, request=request,
            )
        except (DocumentLayoutServiceError, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Overlay draft updated and validated.")
        return redirect('workspace_loans:document_layout_overlay_designer', revision_pk=revision.pk, workspace_slug=request.workspace.slug)
    page_width_mm, page_height_mm = _OVERLAY_PAGE_DIMENSIONS_MM[layout.page_size]
    if layout.schema_version >= 3:
        settings_form = LoanDocumentOverlayLogicalSettingsForm(
            background_keys=background_keys,
            loan_ticket=layout.document_type == "loan_ticket",
            initial={
                "page_size": layout.page_size,
                "background_asset_key": layout.background_asset_key,
                **({surface: layout.surfaces.background(surface) for surface in (
                    "original_front", "duplicate_front", "original_back", "duplicate_back",
                )} if layout.surfaces else {}),
            },
        )
    else:
        settings_form = LoanDocumentOverlaySettingsForm(
            background_keys=background_keys,
            sheet_composition_enabled=layout.document_type == "loan_ticket",
            initial={"page_size": layout.page_size, "copy_mode": layout.copy_mode,
                     "background_asset_key": layout.background_asset_key,
                     "sheet_composition": layout.sheet.composition if layout.sheet else "",
                     **({surface: layout.sheet.background(surface) for surface in (
                         "original_front", "duplicate_front", "original_back", "duplicate_back",
                     )} if layout.sheet else {})},
        )
    return render(request, "loans/setup/documents/overlay_designer.html", {
        "revision": revision, "layout": layout, "settings_form": settings_form,
        "add_form": LoanDocumentOverlayBlockForm(asset_keys=image_keys),
        "image_keys": image_keys, "page_width_mm": page_width_mm,
        "page_height_mm": page_height_mm,
        "legacy_composition_controls": layout.schema_version <= 2,
        "preview_background_key": layout.surface_background("ORIGINAL_FRONT"),
        "has_background": layout.surface_background("ORIGINAL_FRONT") in background_keys,
        "sample_loan": PawnLoan.objects.filter(
            workspace=request.loans_workspace, approval_snapshots__isnull=False,
        ).order_by("-pk").first(),
    })


@loans_setup_required
@require_POST
def document_layout_update(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    form = LoanDocumentLayoutDefinitionForm(request.POST)
    if form.is_valid():
        try:
            LoanDocumentLayoutService.update_draft(revision=revision, definition=form.cleaned_data["definition"], actor=request.user, request=request)
        except (DocumentLayoutServiceError, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Draft layout validated and saved.")
    else:
        messages.error(request, "Layout JSON is invalid.")
    return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_layout_asset_add(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    form = LoanDocumentAssetUploadForm(request.POST, request.FILES)
    if form.is_valid():
        upload = form.cleaned_data["file"]
        try:
            LoanDocumentLayoutService.add_asset(
                revision=revision, key=form.cleaned_data["key"], kind=form.cleaned_data["kind"],
                content=upload.read(), filename=upload.name, actor=request.user,
            )
        except (DocumentLayoutServiceError, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Validated document asset added.")
    else:
        messages.error(request, "Asset upload is invalid.")
    return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_layout_clone(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    clone = LoanDocumentLayoutService.clone_revision(revision=revision, actor=request.user, request=request)
    messages.success(request, f"Created draft revision {clone.version}.")
    return redirect('workspace_loans:document_layout_detail', revision_pk=clone.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_layout_publish(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    try:
        LoanDocumentLayoutService.publish(revision=revision, actor=request.user, request=request)
    except (DocumentLayoutServiceError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Layout revision published and frozen.")
    return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_layout_assign(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    form = LoanDocumentAssignmentForm(request.POST, workspace=request.loans_workspace)
    if form.is_valid():
        try:
            LoanDocumentLayoutService.assign(
                revision=revision, workspace=request.loans_workspace,
                license=form.cleaned_data["license"], series=form.cleaned_data["series"],
                actor=request.user, request=request,
            )
        except (DocumentLayoutServiceError, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Published layout assigned.")
    else:
        messages.error(request, "Assignment scope is invalid.")
    return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
@require_POST
def document_layout_retire(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    try:
        LoanDocumentLayoutService.retire(revision=revision, actor=request.user, request=request)
    except (DocumentLayoutServiceError, ValidationError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Published revision retired; its active assignments were disabled.")
    return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


def _revision_assets(revision):
    values = []
    for asset in revision.assets.all():
        asset.file.open("rb")
        content = asset.file.read()
        asset.file.close()
        values.append(DocumentAsset(asset.key, asset.kind, asset.mime_type, content, asset.workspace_id, asset.sha256, asset.width, asset.height, asset.page_count))
    return tuple(values)


@loans_setup_required
@never_cache
def document_layout_preview(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    try:
        payload = _preview_document_payload(request, revision)
        if payload is None:
            return HttpResponse("Create an eligible source document before previewing this layout.", status=409, content_type="text/plain")
        layout = DocumentLayoutValidator.load(revision.definition)
        if layout.schema_version >= 3 and payload.document_type == "loan_ticket":
            result = ConfigurableDocumentRenderer.render_with_print_profile(
                payload, layout, built_in_print_profile(), preview=True,
                assets=_revision_assets(revision),
            )
        else:
            result = ConfigurableDocumentRenderer.render(
                payload, layout, preview=True, assets=_revision_assets(revision)
            )
    except (ValueError, ValidationError) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    response = HttpResponse(result.pdf, content_type="application/pdf")
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="preview-{payload.file_name}"'
    response["X-Rokkad-Preview"] = "true"
    return response


@loans_setup_required
def document_layout_export(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    try:
        content = export_layout_pack(revision)
    except (LayoutPackError, OSError, ValueError) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    response = HttpResponse(content, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="loan-layout-{revision.layout_id}-v{revision.version}.zip"'
    return response


@loans_setup_required
@require_POST
def document_layout_import(request):
    form = LoanDocumentLayoutPackImportForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Layout pack upload is invalid.")
        return redirect('workspace_loans:document_layout_list', workspace_slug=request.workspace.slug)
    upload = form.cleaned_data["pack"]
    try:
        revision = import_layout_pack(
            workspace=request.loans_workspace, content=upload.read(),
            actor=request.user, request=request, name=form.cleaned_data["name"] or None,
        )
    except (LayoutPackError, DocumentLayoutServiceError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect('workspace_loans:document_layout_list', workspace_slug=request.workspace.slug)
    messages.success(request, "Layout pack imported as an unpublished draft for review.")
    return redirect('workspace_loans:document_layout_detail', revision_pk=revision.pk, workspace_slug=request.workspace.slug)


@loans_setup_required
def document_layout_diagnostics(request):
    findings = get_document_integrity_findings()
    return render(request, "loans/setup/documents/diagnostics.html", {"findings": findings})


def _preview_document_payload(request, revision):
    workspace = request.loans_workspace
    kind = revision.layout.document_type
    if kind == "loan_ticket":
        source = get_object_or_404(PawnLoan, pk=request.GET.get("loan"), workspace=workspace) if request.GET.get("loan") else PawnLoan.objects.filter(workspace=workspace, approval_snapshots__isnull=False).order_by("-pk").first()
        return PawnLoanDocumentProjectionBuilder.loan_ticket(source) if source else None
    if kind == "repayment_receipt":
        source = PawnLoanEvent.objects.filter(loan__workspace=workspace, event_kind=TransactionKind.REPAYMENT.value).select_related("loan__workspace", "loan__license", "loan__borrower").order_by("-pk").first()
        return PawnLoanDocumentProjectionBuilder.repayment_receipt(source) if source else None
    if kind == "release_memo":
        source = PawnLoanRelease.objects.filter(workspace=workspace).select_related("loan__workspace", "loan__license", "loan__borrower", "loan_event").prefetch_related("items__collateral_item").order_by("-pk").first()
        return PawnLoanDocumentProjectionBuilder.release_memo(source) if source else None
    if kind in {"auction_notice", "auction_recovery"}:
        source = PawnLoanAuction.objects.filter(workspace=workspace).select_related("loan__workspace", "loan__license", "loan__borrower", "loan_event", "notice").prefetch_related("items__collateral_item").order_by("-pk").first()
        if not source: return None
        return PawnLoanDocumentProjectionBuilder.auction_notice(source) if kind == "auction_notice" else PawnLoanDocumentProjectionBuilder.auction_recovery_memo(source)
    source = PawnLoanRenewal.objects.filter(workspace=workspace).select_related("source_loan__workspace", "source_loan__license", "source_loan__borrower", "successor_loan", "settlement_event", "opening_event").order_by("-pk").first()
    return PawnLoanDocumentProjectionBuilder.renewal_memo(source) if source else None


def _configurable_document_response(request, *, payload, loan, source_type, source_id, source_fingerprint):
    use_fixed = request.GET.get("renderer") == "fixed"
    if use_fixed and not _can_administer(request):
        return HttpResponse("Fixed-renderer recovery requires workspace administration access.", status=403, content_type="text/plain")
    use_legacy_profile = request.GET.get("print_profile") == "legacy"
    if use_legacy_profile and not _can_administer(request):
        return HttpResponse(
            "Legacy print-profile recovery requires workspace administration access.",
            status=403,
            content_type="text/plain",
        )
    try:
        result = issue_configurable_document(
            workspace=request.loans_workspace,
            payload=payload,
            loan=loan,
            source_type=source_type,
            source_id=source_id,
            source_fingerprint=source_fingerprint,
            actor=request.user,
            request=request,
            fixed_recovery=use_fixed,
            legacy_profile_recovery=use_legacy_profile,
        )
    except (
        ValueError, ValidationError, DocumentLayoutServiceError,
        PrintProfileServiceError,
    ) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    if result.use_fixed_renderer:
        return None
    return _issued_document_response(result.issue, payload)


def _issued_document_response(issue, payload):
    issue.artifact.open("rb")
    pdf = issue.artifact.read()
    issue.artifact.close()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{payload.file_name}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Rokkad-Verification-ID"] = payload.verification_id
    response["X-Rokkad-Document-Issue"] = str(issue.pk)
    if issue.print_profile_hash:
        response["X-Rokkad-Print-Profile"] = issue.print_profile_name
        response["X-Rokkad-Print-Profile-Hash"] = issue.print_profile_hash
    return response


@loans_workspace_required
def pawn_loan_ticket_pdf(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    try:
        payload = PawnLoanDocumentProjectionBuilder.loan_ticket(loan)
        approval = loan.approval_snapshots.order_by("-version").first()
        response = _configurable_document_response(
            request, payload=payload, loan=loan, source_type="PawnLoan",
            source_id=loan.pk, source_fingerprint=approval.fingerprint,
        )
        if response is not None: return response
        result = PawnLoanDocumentService.render_loan_ticket(loan)
    except (PawnLoanDocumentError, ValueError) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    return PawnLoanDocumentService.build_pdf_response(result)


@loans_workspace_required
def pawn_loan_kfs_schedule_pdf(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    try:
        payload = PawnLoanDocumentProjectionBuilder.loan_kfs_schedule(loan)
        schedule = loan.repayment_schedules.order_by("-version").first()
        existing = LoanDocumentLayoutService.find_official_issue(
            workspace=request.loans_workspace, document_type=payload.document_type,
            source_type="RepaymentScheduleVersion", source_id=schedule.pk,
            source_fingerprint=schedule.fingerprint,
        )
        if existing:
            return _issued_document_response(existing, payload)
        result = PawnLoanDocumentService.render_loan_kfs_schedule(loan)
        render_result = SimpleNamespace(
            pdf=result.pdf, renderer_version="fixed-kfs-v1",
            payload_hash=hashlib.sha256(repr(payload).encode()).hexdigest(),
            layout_hash="", asset_hashes={},
        )
        issue = LoanDocumentLayoutService.issue(
            workspace=request.loans_workspace, document_type=payload.document_type,
            source_type="RepaymentScheduleVersion", source_id=schedule.pk,
            source_fingerprint=schedule.fingerprint,
            payload_schema_version=payload.schema_version, render_result=render_result,
            filename=payload.file_name, actor=request.user,
        )
        return _issued_document_response(issue, payload)
    except (PawnLoanDocumentError, ValueError, ValidationError) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")


@loans_workspace_required
def pawn_repayment_receipt_pdf(request, pk, event_pk):
    event = get_object_or_404(
        PawnLoanEvent.objects.select_related(
            "loan",
            "loan__workspace",
            "loan__license",
            "loan__borrower",
            "reversed_by_event",
        ),
        pk=event_pk,
        loan_id=pk,
        loan__workspace=request.loans_workspace,
        event_kind=TransactionKind.REPAYMENT.value,
    )
    payload = PawnLoanDocumentProjectionBuilder.repayment_receipt(event)
    response = _configurable_document_response(
        request, payload=payload, loan=event.loan,
        source_type="PawnLoanEvent", source_id=event.pk,
        source_fingerprint=event.payload_fingerprint,
    )
    if response is not None:
        return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_repayment_receipt(event))


@loans_workspace_required
def pawn_release_memo_pdf(request, release_pk):
    release = get_object_or_404(
        PawnLoanRelease.objects.select_related(
            "workspace",
            "loan",
            "loan__license",
            "loan__borrower",
            "loan_event",
            "loan_event",
            "reversal",
        ).prefetch_related("items__collateral_item"),
        pk=release_pk,
        workspace=request.loans_workspace,
    )
    payload = PawnLoanDocumentProjectionBuilder.release_memo(release)
    response = _configurable_document_response(
        request, payload=payload, loan=release.loan,
        source_type="PawnLoanRelease", source_id=release.pk,
        source_fingerprint=release.loan_event.payload_fingerprint,
    )
    if response is not None:
        return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_release_memo(release))


@loans_workspace_required
def pawn_loan_detail(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    series_navigation = get_pawn_loan_series_navigation(loan)
    context = {
        "loan": loan,
        "previous_loan": series_navigation.previous,
        "next_loan": series_navigation.next,
        "today": timezone.localdate(),
        "can_administer": _can_administer(request),
        "can_manage_storage": _can_manage_storage(request),
        "notice_rows": get_pawn_loan_notice_rows(loan),
        "auctions": loan.auctions.select_related("loan_event").order_by("-attempt_number"),
        "renewals": PawnLoanRenewal.objects.filter(
            Q(source_loan=loan) | Q(successor_loan=loan)
        ).select_related(
            "source_loan",
            "successor_loan",
            "settlement_event",
            "opening_event",
        ),
    }
    if loan.state in {PawnLoanState.ACTIVE.value, PawnLoanState.CLOSED.value}:
        try:
            context["balance"] = get_pawn_loan_balance(
                loan.pk,
                as_of_date=context["today"],
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["balance_error"] = str(exc)
        try:
            context["exposure"] = get_pawn_loan_exposure(
                loan.pk,
                as_of_date=context["today"],
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["exposure_error"] = str(exc)
        try:
            context["delinquency"] = get_pawn_loan_delinquency(loan.pk, as_of_date=context["today"])
            context["collateral_valuation"] = get_pawn_loan_collateral_valuation(loan.pk, as_of_date=context["today"])
            context["risk_assessment"] = get_pawn_loan_risk_assessment(loan.pk, as_of_date=context["today"])
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["risk_error"] = str(exc)
    if loan.state == PawnLoanState.ACTIVE.value:
        try:
            context["accrual_previews"] = preview_pawn_loan_accruals(
                loan.pk,
                as_of_date=context["today"],
                include_partial=True,
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["accrual_error"] = str(exc)
    context["event_rows"] = _event_rows(
        loan,
        can_administer=context["can_administer"],
    )
    for action in ("repay", "release", "accrue", "capitalize"):
        context["can_" + action] = request.loans_workspace_access.can("loan." + action)
    context["can_renew"] = all(
        request.loans_workspace_access.can(action)
        for action in ("loan.release", "loan.approve", "loan.disburse")
    )
    context["can_send_notice"] = request.loans_workspace_access.can("data.edit")
    context["can_edit_loan"] = request.loans_workspace_access.can("data.edit")
    context["can_split_draft"] = context["can_edit_loan"] and request.loans_workspace_access.can("data.create")
    context["can_delete_draft_photos"] = loan.state == "DRAFT" and request.loans_workspace_access.can("data.edit")
    context["can_approve"] = request.loans_workspace_access.can("loan.approve")
    context["can_disburse"] = request.loans_workspace_access.can("loan.disburse")
    context["simple_owner"] = request.loans_workspace.loan_workflow == "SIMPLE" and request.loans_workspace_access.can("workspace.transfer")
    context["primary_action"] = _primary_action(loan, context)
    return render(request, "loans/pawn/detail.html", context)


@loans_workspace_required
@never_cache
def pawn_collateral_photo_document(request, pk, item_pk, photo_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    photo = get_object_or_404(
        PawnCollateralPhoto,
        pk=photo_pk,
        collateral_item_id=item_pk,
        collateral_item__loan=loan,
    )
    with photo.file.open("rb") as photo_file:
        content = photo_file.read()
    response = HttpResponse(content, content_type=photo.mime_type)
    response["Content-Disposition"] = content_disposition_header(
        request.GET.get("inline") != "1",
        photo.original_filename,
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@loans_workspace_required
def pawn_collateral_label_pdf(request, pk, item_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    item = get_object_or_404(PawnCollateralItem, pk=item_pk, loan=loan)
    action = request.GET.get("action", "PREVIEW").upper()
    scan_url = request.build_absolute_uri(
        reverse("workspace_loans:pawn_collateral_scan", kwargs={"workspace_slug": request.loans_workspace.slug, "public_id": item.public_id})
    )
    try:
        result = render_collateral_label(
            item.pk,
            qr_target=scan_url,
            action=action,
            actor=request.user,
        )
    except (PawnCollateralMediaError, ValidationError, ValueError) as exc:
        return HttpResponse(str(exc), status=409)
    response = HttpResponse(result.content, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        False, f"{loan.loan_number}-{item.public_id}-label.pdf"
    )
    return response


@loans_workspace_required
def pawn_collateral_scan(request, public_id):
    item = get_object_or_404(
        PawnCollateralItem.objects.select_related("loan"),
        public_id=public_id,
        loan__workspace=request.loans_workspace,
    )
    verification = request.GET.get("verification")
    if verification:
        assert_loans_owner_access(request)
        session = get_object_or_404(
            PawnPhysicalVerificationSession,
            public_id=verification,
            workspace=request.loans_workspace,
        )
        return redirect(
            f"{reverse('workspace_loans:pawn_physical_verification_detail', kwargs={'workspace_slug': request.loans_workspace.slug, 'pk': session.pk})}?item={item.pk}"
        )
    if (
        _can_manage_storage(request)
        and item.custody_state == "IN_VAULT"
    ):
        request.session[_PENDING_STORAGE_ITEM_SESSION_KEY] = {
            "workspace_id": request.loans_workspace.pk,
            "item_public_id": str(item.public_id),
        }
    return redirect(
        f"{reverse('workspace_slug_loan_detail', kwargs={'workspace_slug': request.loans_workspace.slug, 'pk': item.loan_id})}#collateral-{item.public_id}"
    )


@loans_owner_required
def pawn_storage_location_list(request):
    locations = PawnStorageLocation.objects.filter(
        workspace=request.loans_workspace
    ).select_related(
        "parent",
        "parent__parent",
        "parent__parent__parent",
        "parent__parent__parent__parent",
    ).annotate(current_item_count=Count("current_collateral_items")).order_by(
        "level",
        "code",
        "pk",
    )
    location_filter = PawnStorageLocationFilter(
        request.GET,
        queryset=locations,
        workspace=request.loans_workspace,
    )
    page_obj = Paginator(location_filter.qs, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "loans/storage/location_list.html",
        {
            "location_filter": location_filter,
            "locations": page_obj.object_list,
            "page_obj": page_obj,
        },
    )


@loans_owner_required
def pawn_storage_location_label(request, pk):
    location = get_object_or_404(
        PawnStorageLocation,
        pk=pk,
        workspace=request.loans_workspace,
    )
    qr_target = request.build_absolute_uri(
        reverse("workspace_loans:pawn_storage_location_scan", kwargs={"workspace_slug": request.loans_workspace.slug, "public_id": location.public_id})
    )
    content = render_storage_location_label(location, qr_target=qr_target)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        False, f"storage-{location.code}.pdf"
    )
    return response


@loans_owner_required
def pawn_storage_location_scan(request, public_id):
    location = get_object_or_404(
        PawnStorageLocation,
        public_id=public_id,
        workspace=request.loans_workspace,
        is_active=True,
    )
    item_public_id = request.GET.get("item")
    verification = request.GET.get("verification")
    if verification:
        session = get_object_or_404(
            PawnPhysicalVerificationSession,
            public_id=verification,
            workspace=request.loans_workspace,
        )
        query = f"?location={location.pk}"
        if item_public_id:
            item = get_object_or_404(
                PawnCollateralItem,
                public_id=item_public_id,
                loan__workspace=request.loans_workspace,
            )
            query += f"&item={item.pk}"
        return redirect(
            f"{reverse('workspace_loans:pawn_physical_verification_detail', kwargs={'workspace_slug': request.loans_workspace.slug, 'pk': session.pk})}{query}"
        )
    if location.level not in {
        PawnStorageLocation.Level.BOX,
        PawnStorageLocation.Level.SLOT,
    }:
        messages.info(request, "Collateral can only be placed in a Box or Slot.")
        return redirect("workspace_loans:pawn_storage_location_list", workspace_slug=request.loans_workspace.slug)
    if item_public_id:
        item = get_object_or_404(
            PawnCollateralItem,
            public_id=item_public_id,
            loan__workspace=request.loans_workspace,
        )
        return redirect(
            f"{reverse('workspace_loans:pawn_collateral_storage_transfer', kwargs={'workspace_slug': request.loans_workspace.slug, 'pk': item.loan_id, 'item_pk': item.pk})}?destination={location.pk}"
        )
    pending = request.session.get(_PENDING_STORAGE_ITEM_SESSION_KEY, {})
    if (
        _can_manage_storage(request)
        and pending.get("workspace_id") == request.loans_workspace.pk
        and pending.get("item_public_id")
    ):
        item = PawnCollateralItem.objects.filter(
            public_id=pending["item_public_id"],
            loan__workspace=request.loans_workspace,
            custody_state="IN_VAULT",
        ).first()
        if item is not None:
            return redirect(
                f"{reverse('workspace_loans:pawn_collateral_storage_transfer', kwargs={'workspace_slug': request.loans_workspace.slug, 'pk': item.loan_id, 'item_pk': item.pk})}?destination={location.pk}"
            )
        request.session.pop(_PENDING_STORAGE_ITEM_SESSION_KEY, None)
    messages.info(request, "Scan an in-vault collateral item before scanning its destination.")
    return redirect("workspace_loans:pawn_storage_location_list", workspace_slug=request.loans_workspace.slug)


@loans_owner_required
def pawn_physical_verification_list(request):
    form = PawnPhysicalVerificationStartForm(
        request.POST or None, workspace=request.loans_workspace
    )
    if request.method == "POST" and form.is_valid():
        try:
            session = start_physical_verification(
                scope_location_id=form.cleaned_data["scope_location"].pk,
                actor=request.user,
            )
        except (PawnPhysicalVerificationError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Physical-verification scope frozen.")
            return redirect("workspace_loans:pawn_physical_verification_detail", workspace_slug=request.loans_workspace.slug, pk=session.pk)
    sessions = PawnPhysicalVerificationSession.objects.filter(
        workspace=request.loans_workspace
    ).select_related(
        "scope_location",
        "scope_location__parent",
        "scope_location__parent__parent",
        "scope_location__parent__parent__parent",
        "scope_location__parent__parent__parent__parent",
        "started_by",
        "completed_by",
    ).annotate(expected_item_count=Count("expectations")).order_by(
        "-started_at",
        "-pk",
    )
    session_filter = PawnPhysicalVerificationSessionFilter(
        request.GET,
        queryset=sessions,
        workspace=request.loans_workspace,
    )
    page_obj = Paginator(session_filter.qs, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "loans/verification/session_list.html",
        {
            "form": form,
            "session_filter": session_filter,
            "sessions": page_obj.object_list,
            "page_obj": page_obj,
        },
    )


@loans_owner_required
def pawn_physical_verification_detail(request, pk):
    session = get_object_or_404(
        PawnPhysicalVerificationSession.objects.select_related("scope_location"),
        pk=pk,
        workspace=request.loans_workspace,
    )
    initial = {}
    if request.method == "GET":
        if request.GET.get("item"):
            initial["collateral_item"] = request.GET["item"]
        if request.GET.get("location"):
            initial["observed_location"] = request.GET["location"]
        if request.GET.get("classification") in dict(
            PawnPhysicalVerificationObservation.Classification.choices
        ):
            initial["classification"] = request.GET["classification"]
    form = PawnPhysicalVerificationObservationForm(
        request.POST or None, workspace=request.loans_workspace, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        try:
            record_physical_verification_observation(
                session.pk,
                collateral_item_id=form.cleaned_data["collateral_item"].pk,
                classification=form.cleaned_data["classification"],
                observed_location_id=(form.cleaned_data["observed_location"].pk if form.cleaned_data.get("observed_location") else None),
                notes=form.cleaned_data.get("notes", ""),
                actor=request.user,
            )
        except (PawnPhysicalVerificationError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Immutable verification observation recorded.")
            return redirect("workspace_loans:pawn_physical_verification_detail", workspace_slug=request.loans_workspace.slug, pk=session.pk)
    detail = get_physical_verification_detail(session)
    return render(
        request,
        "loans/verification/session_detail.html",
        {"session": session, "detail": detail, "form": form},
    )


@loans_workspace_required
def pawn_loan_auction_notice_pdf(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    payload = PawnLoanDocumentProjectionBuilder.auction_notice(auction)
    response = _configurable_document_response(
        request, payload=payload, loan=auction.loan,
        source_type="PawnLoanAuctionNotice", source_id=auction.pk,
        source_fingerprint=hashlib.sha256(payload.verification_id.encode()).hexdigest(),
    )
    if response is not None: return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_auction_notice(auction))


@loans_workspace_required
def pawn_loan_auction_recovery_pdf(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    try:
        payload = PawnLoanDocumentProjectionBuilder.auction_recovery_memo(auction)
        response = _configurable_document_response(
            request, payload=payload, loan=auction.loan,
            source_type="PawnLoanAuction", source_id=auction.pk,
            source_fingerprint=auction.loan_event.payload_fingerprint,
        )
        if response is not None: return response
        result = PawnLoanDocumentService.render_auction_recovery_memo(auction)
    except (PawnLoanDocumentError, ValueError) as exc:
        return HttpResponse(str(exc), status=409)
    return PawnLoanDocumentService.build_pdf_response(result)


@loans_workspace_required
def pawn_loan_renewal_pdf(request, renewal_pk):
    renewal = _pawn_renewal_for_workspace(request, renewal_pk)
    payload = PawnLoanDocumentProjectionBuilder.renewal_memo(renewal)
    response = _configurable_document_response(
        request, payload=payload, loan=renewal.source_loan,
        source_type="PawnLoanRenewal", source_id=renewal.pk,
        source_fingerprint=renewal.settlement_event.payload_fingerprint,
    )
    if response is not None: return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_renewal_memo(renewal))


@loans_action_required("data.edit")
def pawn_loan_transfer_setup(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnSetupTransferForm(request.POST or None, workspace=request.loans_workspace)
    if request.method == "POST" and form.is_valid():
        try:
            transfer_expired_draft_setup(
                loan.pk,
                license_id=form.cleaned_data["license"].pk,
                series_id=form.cleaned_data["series"].pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnLifecycleError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Draft moved to active license setup and requires approval again.")
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    return render(request, "loans/pawn/transition_form.html", {"loan": loan, "form": form, "action_label": "Transfer setup"})


@require_POST
@loans_setup_required
def pawn_risk_refresh_batch(request):
    as_of_date = _risk_refresh_date(request)
    if as_of_date is None:
        messages.error(request, "Risk assessment date must use YYYY-MM-DD.")
    else:
        try:
            result = reassess_pawn_loans_batch(
                workspace_id=request.loans_workspace.pk,
                as_of_date=as_of_date,
                batch_size=50,
            )
        except RiskSnapshotRefreshError as exc:
            messages.error(request, str(exc))
        else:
            if result["errors"]:
                messages.warning(
                    request,
                    f"Refreshed {result['current']} of {result['selected']} selected loans; "
                    f"{len(result['errors'])} assessment(s) need review.",
                )
            else:
                messages.success(
                    request,
                    f"Refreshed {result['current']} of {result['selected']} selected risk assessments.",
                )
    return _risk_portfolio_redirect(request)


@require_POST
@loans_setup_required
def pawn_risk_refresh_one(request, pk):
    loan = get_object_or_404(
        PawnLoan.objects.filter(
            workspace=request.loans_workspace,
            state=PawnLoanState.ACTIVE.value,
        ),
        pk=pk,
    )
    as_of_date = _risk_refresh_date(request)
    if as_of_date is None:
        messages.error(request, "Risk assessment date must use YYYY-MM-DD.")
    else:
        try:
            refresh_loan_risk_snapshot(loan.pk, as_of_date=as_of_date)
        except RiskSnapshotRefreshError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"Risk assessment refreshed for {loan.loan_number} as of {as_of_date}.",
            )
    return _risk_portfolio_redirect(request)


def _risk_refresh_date(request):
    raw = (request.POST.get("as_of") or timezone.localdate().isoformat()).strip()
    return parse_date(raw)


def _risk_portfolio_redirect(request):
    if request.headers.get("HX-Request") == "true":
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse('workspace_loans:pawn_risk_portfolio', kwargs={'workspace_slug': request.workspace.slug})
        return response
    return redirect('workspace_loans:pawn_risk_portfolio', workspace_slug=request.workspace.slug)


# Compatibility exports: URLs continue importing ``loans.views`` while the
# focused module owns FundingLoan mutation handlers.
from apps.tenant_apps.loans.web.funding_actions import (
    funding_loan_begin_settlement,
    funding_loan_close,
    funding_loan_draft_activate,
    funding_loan_draft_cancel,
    funding_loan_draft_create,
    funding_loan_draft_inputs,
    funding_loan_repayment,
    funding_loan_return_collateral,
    funding_loan_reverse_event,
    funding_loan_reverse_pledge,
    funding_loan_reverse_return,
)
from apps.tenant_apps.loans.web.license_setup import (
    license_list,
    license_register_pdf,
    license_detail,
    license_expiry_notice_create,
    license_create,
    license_update,
    license_renew,
    license_revision_document,
    license_expire,
    license_activate,
    series_create,
    series_update,
    _license_for_workspace,
)
from apps.tenant_apps.loans.web.economic_setup import pawn_economics_setup
from apps.tenant_apps.loans.web.product_setup import (
    loan_product_list,
    loan_product_seed_defaults,
    loan_product_version_activate,
    loan_product_version_create,
    loan_product_version_retire,
)
from apps.tenant_apps.loans.web.pawn_draft_actions import (
    get_pawn_draft_readiness,
    pawn_collateral_photo_add,
    pawn_loan_approve,
    pawn_loan_cancel,
    pawn_loan_create,
    pawn_loan_reopen,
    pawn_loan_split,
    pawn_loan_update,
)
from apps.tenant_apps.loans.web.pawn_financial_actions import (
    pawn_loan_accrue,
    pawn_loan_capitalize,
    pawn_loan_disburse,
    pawn_loan_repay,
    pawn_loan_reverse_event,
)
from apps.tenant_apps.loans.web.pawn_release_actions import (
    pawn_loan_release_full,
    pawn_loan_release_partial,
)
from apps.tenant_apps.loans.web.pawn_custody_actions import (
    pawn_collateral_storage_transfer,
    pawn_physical_verification_complete,
    pawn_physical_verification_discrepancy_notice,
    pawn_physical_verification_resolve,
    pawn_storage_location_create,
)
from apps.tenant_apps.loans.web.pawn_notice_actions import (
    pawn_loan_notice_create,
    pawn_loan_notice_retry,
)
from apps.tenant_apps.loans.web.pawn_auction_actions import (
    pawn_loan_auction_cancel,
    pawn_loan_auction_complete,
    pawn_loan_auction_initiate,
    pawn_loan_auction_reverse,
    pawn_loan_auction_start,
)
from apps.tenant_apps.loans.web.pawn_renewal_actions import (
    pawn_loan_renew,
    pawn_loan_renewal_reverse,
)


@loans_setup_required
@require_POST
def operational_notice_retry(request, notice_pk):
    notice = get_object_or_404(
        LoanOperationalNotice,
        pk=notice_pk,
        workspace=request.loans_workspace,
    )
    try:
        result = retry_operational_notice(notice.pk, actor=request.user)
    except (LoanOperationalNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, f"Operational alert delivery is {result.delivery.status.lower()}."
        )
    if notice.source_license_id:
        return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=notice.source_license_id)
    return redirect(
        "workspace_loans:pawn_physical_verification_detail",
        workspace_slug=request.loans_workspace.slug,
        pk=notice.source_verification_observation.session_id,
    )


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items",
            "collateral_items__photos",
            "collateral_items__storage_movements__from_location",
            "collateral_items__storage_movements__to_location",
            "collateral_items__storage_movements__moved_by",
            "interest_accruals__lines__collateral_item",
            "change_log__actor",
            "loan_events",
            "loan_events__reversed_by_event",
            "loan_events__repayment_allocation_lines__collateral_item",
            "releases__items__collateral_item",
            "approval_snapshots",
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _pawn_auction_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoanAuction.objects.select_related(
            "loan",
            "loan__workspace",
            "loan__license",
            "loan__borrower",
            "loan_event",
        ).prefetch_related("items__collateral_item"),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _pawn_renewal_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoanRenewal.objects.select_related(
            "source_loan",
            "source_loan__workspace",
            "source_loan__license",
            "source_loan__borrower",
            "successor_loan",
            "settlement_event",
            "opening_event",
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _primary_action(loan, context):
    if loan.state == PawnLoanState.DRAFT.value:
        if context.get("simple_owner"):
            return {"label": "Review and disburse", "url": reverse('workspace_loans:pawn_loan_review_disburse', args=[loan.workspace.slug, loan.pk]), "message": "Review the summary and confirm payment in one action."}
        if not context.get("can_approve", False):
            return None
        return {
            "label": "Approve loan",
            "url": reverse('workspace_loans:pawn_loan_approve', args=[loan.workspace.slug, loan.pk]),
            "method": "post",
            "message": "Review the frozen terms, then approve this draft.",
        }
    if loan.state == PawnLoanState.APPROVED.value:
        if not context.get("can_disburse", False):
            return None
        return {
            "label": "Disburse loan",
            "url": reverse('workspace_loans:pawn_loan_disburse', args=[loan.workspace.slug, loan.pk]),
            "message": "Record disbursal to activate the loan.",
        }
    if loan.state == PawnLoanState.ACTIVE.value:
        if not context.get("can_repay", False):
            return None
        return {
            "label": "Record repayment",
            "url": reverse('workspace_loans:pawn_loan_repay', args=[loan.workspace.slug, loan.pk]),
            "message": "Continue with repayment, accrual, or collateral release.",
        }
    if loan.state == PawnLoanState.CLOSED.value:
        return {
            "label": "Review event history",
            "url": "#business-events",
            "message": "This loan is closed. Administrators can reverse eligible events in order.",
        }
    return None


def _can_administer(request):
    return request.loans_workspace_access.can(LOANS_ADMIN_ACTION)


def _can_manage_storage(request):
    return request.loans_workspace_access.can(LOANS_OWNER_ACTION)


def _event_rows(loan, *, can_administer):
    events = tuple(
        loan.loan_events.select_related(
            "reversed_by_event", "loan__workspace"
        ).order_by("-effective_date", "-pk")
    )
    latest_event_id = next(
        (
            event.pk
            for event in events
            if event.event_kind != TransactionKind.REVERSAL.value
            and not hasattr(event, "reversed_by_event")
        ),
        None,
    )
    rows = []
    for event in events:
        try:
            reversed_event = event.reversed_by_event
        except PawnLoanEvent.DoesNotExist:
            reversed_event = None
        readiness = assess_pawn_loan_event_reversal(
            event, latest_event_id=latest_event_id
        )
        rows.append(
            {
                "event": event,
                "can_reverse": can_administer and readiness.can_reverse,
                "reversal_blocker": readiness.blocker,
                "reversed_event": reversed_event,
            }
        )
    return rows
