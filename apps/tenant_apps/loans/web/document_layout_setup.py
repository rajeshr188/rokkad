"""Document layout setup; existing services own business rules."""

from copy import deepcopy
import fitz
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import (
    HttpResponse,
    HttpResponseGone,
)
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.domain import TransactionKind
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
)
from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer,
    DocumentLayoutValidator,
    PawnLoanDocumentProjectionBuilder,
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
    LoanDocumentLayout,
    LoanDocumentLayoutRevision,
    PawnLoan,
    PawnLoanEvent,
    PawnLoanAuction,
    PawnLoanRelease,
    PawnLoanRenewal,
)
from apps.tenant_apps.loans.services import (
    DocumentLayoutServiceError,
    LoanDocumentLayoutService,
)
from apps.tenant_apps.loans.web.document_assets import _revision_assets


_OVERLAY_PAGE_DIMENSIONS_MM = {
    "A4": (210, 297), "A5": (148, 210), "LETTER": (216, 279),
}


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
