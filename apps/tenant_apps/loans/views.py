import hashlib
import uuid
from copy import deepcopy
from decimal import Decimal

import fitz

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseGone, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.access import loans_setup_required, loans_workspace_required
from apps.tenant_apps.loans.domain import (
    CollateralEconomicsError,
    LoanDocumentKind,
    LoanOutboxStatus,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.feature_flags import (
    get_loan_module_feature_state,
    set_new_loans_enabled,
)
from apps.tenant_apps.loans.forms import (
    LoanLicenseForm,
    LoanLicenseRenewalForm,
    LoanDocumentAssetUploadForm,
    LoanDocumentAssignmentForm,
    LoanDocumentLayoutCreateForm,
    LoanDocumentLayoutDefinitionForm,
    LoanDocumentFlowBlockForm,
    LoanDocumentFlowSettingsForm,
    LoanDocumentOverlayBlockForm,
    LoanDocumentOverlaySettingsForm,
    LoanDocumentLayoutPackImportForm,
    LoanModuleFeatureGateForm,
    LoanSeriesSetupForm,
    FundingLoanActivationForm,
    FundingLoanCancellationForm,
    FundingCollateralReturnForm,
    FundingCorrectionForm,
    FundingLoanClosureForm,
    FundingLoanDraftForm,
    FundingLoanDraftInputsForm,
    FundingLoanRepaymentForm,
    PawnEconomicConfigurationForm,
    PawnFeePolicyForm,
    PawnAccrualForm,
    PawnAdditionalCollateralFormSet,
    PawnCapitalizationForm,
    PawnCollateralDraftFormSet,
    PawnCollateralPhotoForm,
    PawnStorageLocationForm,
    PawnStorageTransferForm,
    PawnPhysicalVerificationStartForm,
    PawnPhysicalVerificationObservationForm,
    PawnPhysicalVerificationResolutionForm,
    PawnDisbursalForm,
    PawnDraftForm,
    PawnFullReleaseForm,
    PawnLoanNoticeForm,
    PawnAuctionInitiateForm,
    PawnAuctionCompletionForm,
    PawnRenewalForm,
    PawnRenewalRetainedItemFormSet,
    PawnRepaymentForm,
    PawnReversalForm,
    PawnSetupTransferForm,
    PawnTransitionReasonForm,
)


_OVERLAY_PAGE_DIMENSIONS_MM = {
    "A4": (210, 297), "A5": (148, 210), "LETTER": (216, 279),
}

_PENDING_STORAGE_ITEM_SESSION_KEY = "loans_pending_storage_item"

_PILOT_REPORT_EXPORT_SECTIONS = (
    ("active", "Active loans"),
    ("daily", "Daily disbursals / repayments"),
    ("interest_due", "Interest due"),
    ("overdue", "Overdue loans"),
    ("releases_renewals", "Releases / renewals"),
    ("storage", "Storage inventory"),
    ("license_expiry", "License expiry"),
)
_PILOT_REPORT_EXPORT_FORMATS = (("csv", "CSV"), ("xlsx", "XLSX"), ("pdf", "PDF"))


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
from apps.tenant_apps.loans.models import (
    FundingLoan,
    FundingLoanEvent,
    FundingReturn,
    LoanDocumentLayout,
    LoanDocumentLayoutRevision,
    LoanLicense,
    LoanOperationalNotice,
    LoanLicenseRevision,
    LoanSeries,
    PawnLoan,
    PawnCollateralItem,
    PawnCollateralPhoto,
    PawnPhysicalVerificationObservation,
    PawnPhysicalVerificationSession,
    PawnStorageLocation,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanAuction,
    PawnLoanEconomicPolicy,
    PawnLoanFeePolicy,
    PawnLoanNotice,
    PawnLoanRelease,
    PawnLoanRenewal,
    PawnMetalInterestRatePolicy,
)
from apps.tenant_apps.loans.selectors import (
    FundingLoanSelectorError,
    get_funding_loan_detail,
    get_funding_loan_draft_inputs,
    get_funding_loan_integrity_findings,
    get_funding_settlement_readiness,
    get_funding_loan_summaries,
    get_loan_license_register,
    get_pawn_loan_balance,
    get_pawn_loan_notice_rows,
    get_physical_verification_detail,
    get_pawn_loan_operations_snapshot,
    get_pawn_loan_reports,
    get_pawn_party_statement,
)
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    ActivateSavedFundingLoanDraft,
    BeginFundingSettlement,
    CloseFundingLoan,
    CancelFundingLoanDraft,
    CreateFundingLoanDraft,
    CreatePawnDraftCommand,
    FundingLoanServiceError,
    FundingLoanDocumentService,
    FundingCollateralInput,
    RecordFundingRepayment,
    ReverseFundingEvent,
    ReverseFundingPledge,
    ReverseFundingReturn,
    ReturnFundingCollateral,
    LicenseSeriesError,
    LoanAccountingOutboxError,
    NumberAllocationError,
    PawnBorrowerAccountingSetupError,
    PawnDraftError,
    PawnLifecycleError,
    PawnLoanDocumentError,
    PawnLoanDocumentService,
    DocumentLayoutServiceError,
    LoanDocumentLayoutService,
    PawnLoanNoticeError,
    PawnAuctionError,
    PawnRenewalError,
    RetainedCollateralInput,
    SaveFundingLoanDraftInputs,
    UpdatePawnDraftCommand,
    activate_license,
    activate_saved_funding_loan_draft,
    begin_funding_settlement,
    close_funding_loan,
    approve_pawn_loan,
    assess_pawn_loan_accounting_readiness,
    cancel_pawn_loan,
    cancel_funding_loan_draft,
    capitalize_pawn_loan_interest,
    configure_sequence,
    create_license,
    create_funding_loan_draft,
    create_pawn_draft,
    append_collateral_photo,
    create_pawn_loan_economic_policy,
    create_pawn_loan_fee_policy,
    create_pawn_metal_interest_rate_policy,
    create_pawn_loan_notice,
    create_series,
    record_funding_repayment,
    reverse_funding_event,
    reverse_funding_pledge,
    reverse_funding_return,
    return_funding_collateral,
    save_funding_loan_draft_inputs,
    disburse_pawn_loan,
    dispatch_pawn_loan_notice,
    dispatch_operational_notice,
    PawnLoanReportExportError,
    build_party_statement_dataset,
    build_pawn_loan_report_dataset,
    render_report_dataset,
    ensure_pawn_borrower_accounting,
    initiate_pawn_loan_auction,
    start_pawn_loan_auction,
    cancel_pawn_loan_auction,
    complete_pawn_loan_auction,
    reverse_pawn_loan_auction,
    renew_pawn_loan,
    renew_license,
    reverse_pawn_loan_renewal,
    expire_license,
    finalize_pawn_loan_accrual,
    preview_number,
    preview_pawn_loan_full_release,
    preview_pawn_loan_renewal_plan,
    preview_pawn_loan_renewal_source,
    preview_pawn_loan_repayment,
    preview_pawn_loan_accruals,
    record_pawn_loan_repayment,
    resolve_pawn_draft_economics,
    resolve_pawn_loan_economic_policy,
    resolve_pawn_metal_interest_rate_policy,
    release_pawn_loan_in_full,
    reopen_pawn_loan,
    retry_failed_outbox_event,
    assess_pawn_loan_event_reversal,
    reverse_pawn_loan_event,
    set_series_active,
    transfer_expired_draft_setup,
    render_collateral_label,
    PawnCollateralMediaError,
    PawnStorageError,
    PawnPhysicalVerificationError,
    LoanOperationalNoticeError,
    complete_physical_verification,
    create_license_expiry_notice,
    create_verification_discrepancy_notice,
    create_storage_location,
    place_or_transfer_collateral,
    record_physical_verification_observation,
    resolve_physical_verification_discrepancy,
    start_physical_verification,
    render_storage_location_label,
    update_license,
    update_pawn_draft,
    update_series,
    render_loan_license_register_pdf,
)
from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer,
    DocumentAsset,
    DocumentLayoutValidator,
    PawnLoanDocumentProjectionBuilder,
    starter_layout,
)
from apps.tenant_apps.loans.documents.integrity import get_document_integrity_findings
from apps.tenant_apps.loans.documents.packs import (
    LayoutPackError,
    export_layout_pack,
    import_layout_pack,
)
from apps.tenant_apps.loans.services.pawn_tranches import (
    PawnTrancheBalanceError,
    get_pawn_principal_tranche_balances,
)


@loans_workspace_required
def pawn_loan_list(request):
    loans = PawnLoan.objects.filter(workspace=request.loans_workspace).select_related(
        "borrower", "license", "series"
    ).order_by("-created_at")
    readiness = _draft_readiness(request.loans_workspace)
    return render(request, "loans/pawn/list.html", {"loans": loans, "readiness": readiness})


@loans_workspace_required
def pawn_loan_reports(request):
    as_of_date = _report_as_of_date(request)
    report = get_pawn_loan_reports(as_of_date=as_of_date)
    parties = Party.objects.filter(pawn_loans__workspace=request.loans_workspace).distinct().order_by("display_name")
    return render(
        request,
        "loans/pawn/reports.html",
        {
            "report": report,
            "parties": parties,
            "can_administer": _can_administer(request),
            "report_is_current": as_of_date == timezone.localdate(),
            "report_export_sections": _PILOT_REPORT_EXPORT_SECTIONS,
            "report_export_formats": _PILOT_REPORT_EXPORT_FORMATS,
        },
    )


@loans_workspace_required
def pawn_loan_report_export(request, section, export_format):
    as_of_date = _report_as_of_date(request)
    try:
        dataset = build_pawn_loan_report_dataset(
            get_pawn_loan_reports(as_of_date=as_of_date), section
        )
        content, content_type = render_report_dataset(dataset, export_format)
    except PawnLoanReportExportError as exc:
        return HttpResponse(str(exc), status=400)
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = content_disposition_header(
        True, f"pawn-loans-{section}-{as_of_date}.{export_format}"
    )
    return response


@loans_workspace_required
def pawn_party_statement(request, party_pk, export_format=None):
    party = get_object_or_404(
        Party.objects.filter(pawn_loans__workspace=request.loans_workspace).distinct(),
        pk=party_pk,
    )
    statement = get_pawn_party_statement(
        party_id=party.pk, as_of_date=_report_as_of_date(request)
    )
    if export_format:
        try:
            content, content_type = render_report_dataset(
                build_party_statement_dataset(statement), export_format
            )
        except PawnLoanReportExportError as exc:
            return HttpResponse(str(exc), status=400)
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = content_disposition_header(
            True, f"party-statement-{party.pk}-{statement.as_of_date}.{export_format}"
        )
        return response
    return render(
        request, "loans/pawn/party_statement.html", {"statement": statement}
    )


def _report_as_of_date(request):
    raw = (request.GET.get("as_of") or "").strip()
    if not raw:
        return timezone.localdate()
    value = parse_date(raw)
    if value is None:
        raise Http404("Report date must use YYYY-MM-DD.")
    return value


@loans_setup_required
def loan_module_feature_gate(request):
    state = get_loan_module_feature_state(request.loans_workspace)
    form = LoanModuleFeatureGateForm(
        request.POST if request.method == "POST" else None,
        initial={"enabled": state.enabled},
    )
    if request.method == "POST" and form.is_valid():
        state = set_new_loans_enabled(
            request.loans_workspace,
            enabled=form.cleaned_data["enabled"],
            actor=request.user,
        )
        if state.enabled:
            messages.success(
                request,
                "Loans is now the new-loan entrypoint. Existing Girvi loans remain serviceable in Girvi.",
            )
        else:
            messages.success(
                request,
                "Girvi is again the new-loan entrypoint. Existing Loans records were preserved.",
            )
        return redirect("loans:loan_module_feature_gate")
    return render(
        request,
        "loans/setup/feature_gate.html",
        {"form": form, "feature_state": state},
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
                    document_type, schema_version=2,
                    layout_mode=form.cleaned_data["layout_mode"] or "FLOW",
                ).canonical_dict(),
                actor=request.user, request=request,
            )
        except (DocumentLayoutServiceError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Starter document layout created as a draft.")
            return redirect("loans:document_layout_detail", revision_pk=revision.pk)
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
        return redirect("loans:document_layout_detail", revision_pk=revision.pk)
    if layout.schema_version != 2 or layout.layout_mode != "FLOW":
        messages.error(request, "The visual editor supports Flow schema-v2 drafts only.")
        return redirect("loans:document_layout_detail", revision_pk=revision.pk)
    if request.method == "POST":
        if revision.state != revision.State.DRAFT:
            messages.error(request, "Published revisions are immutable. Clone this revision before editing.")
            return redirect("loans:document_layout_detail", revision_pk=revision.pk)
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
        return redirect("loans:document_layout_designer", revision_pk=revision.pk)
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
def document_layout_overlay_background(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    layout = DocumentLayoutValidator.load(revision.definition)
    if layout.layout_mode != "ABSOLUTE_OVERLAY":
        return HttpResponseGone("This revision is not an absolute overlay layout.")
    background_key = (
        layout.sheet.background("original_front") if layout.sheet
        else layout.background_asset_key
    )
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
        return redirect("loans:document_layout_detail", revision_pk=revision.pk)
    if layout.schema_version != 2 or layout.layout_mode != "ABSOLUTE_OVERLAY":
        messages.error(request, "The overlay editor supports absolute-overlay schema-v2 drafts only.")
        return redirect("loans:document_layout_detail", revision_pk=revision.pk)
    background_keys = tuple(revision.assets.filter(kind="BACKGROUND").values_list("key", flat=True))
    image_keys = tuple(revision.assets.filter(kind="IMAGE").values_list("key", flat=True))
    if request.method == "POST":
        if revision.state != revision.State.DRAFT:
            messages.error(request, "Published revisions are immutable. Clone this revision before editing.")
            return redirect("loans:document_layout_detail", revision_pk=revision.pk)
        definition = deepcopy(revision.definition)
        operation = request.POST.get("operation")
        try:
            if operation == "save_settings":
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
        return redirect("loans:document_layout_overlay_designer", revision_pk=revision.pk)
    page_width_mm, page_height_mm = _OVERLAY_PAGE_DIMENSIONS_MM[layout.page_size]
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
        "sheet_composition_enabled": layout.document_type == "loan_ticket",
        "preview_background_key": (
            layout.sheet.background("original_front") if layout.sheet
            else layout.background_asset_key
        ),
        "has_background": (
            layout.sheet.background("original_front") if layout.sheet
            else layout.background_asset_key
        ) in background_keys,
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
    return redirect("loans:document_layout_detail", revision_pk=revision.pk)


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
    return redirect("loans:document_layout_detail", revision_pk=revision.pk)


@loans_setup_required
@require_POST
def document_layout_clone(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    clone = LoanDocumentLayoutService.clone_revision(revision=revision, actor=request.user, request=request)
    messages.success(request, f"Created draft revision {clone.version}.")
    return redirect("loans:document_layout_detail", revision_pk=clone.pk)


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
    return redirect("loans:document_layout_detail", revision_pk=revision.pk)


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
    return redirect("loans:document_layout_detail", revision_pk=revision.pk)


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
    return redirect("loans:document_layout_detail", revision_pk=revision.pk)


def _revision_assets(revision):
    values = []
    for asset in revision.assets.all():
        asset.file.open("rb")
        content = asset.file.read()
        asset.file.close()
        values.append(DocumentAsset(asset.key, asset.kind, asset.mime_type, content, asset.workspace_id, asset.sha256, asset.width, asset.height, asset.page_count))
    return tuple(values)


@loans_setup_required
def document_layout_preview(request, revision_pk):
    revision = _document_revision(request, revision_pk)
    try:
        payload = _preview_document_payload(request, revision)
        if payload is None:
            return HttpResponse("Create an eligible source document before previewing this layout.", status=409, content_type="text/plain")
        layout = DocumentLayoutValidator.load(revision.definition)
        result = ConfigurableDocumentRenderer.render(payload, layout, preview=True, assets=_revision_assets(revision))
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
        return redirect("loans:document_layout_list")
    upload = form.cleaned_data["pack"]
    try:
        revision = import_layout_pack(
            workspace=request.loans_workspace, content=upload.read(),
            actor=request.user, request=request, name=form.cleaned_data["name"] or None,
        )
    except (LayoutPackError, DocumentLayoutServiceError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
        return redirect("loans:document_layout_list")
    messages.success(request, "Layout pack imported as an unpublished draft for review.")
    return redirect("loans:document_layout_detail", revision_pk=revision.pk)


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
        source = PawnLoanAccountingEvent.objects.filter(loan__workspace=workspace, event_kind=TransactionKind.REPAYMENT.value).select_related("loan__workspace", "loan__license", "loan__borrower", "outbox").order_by("-pk").first()
        return PawnLoanDocumentProjectionBuilder.repayment_receipt(source) if source else None
    if kind == "release_memo":
        source = PawnLoanRelease.objects.filter(workspace=workspace).select_related("loan__workspace", "loan__license", "loan__borrower", "accounting_event", "accounting_event__outbox").prefetch_related("items__collateral_item").order_by("-pk").first()
        return PawnLoanDocumentProjectionBuilder.release_memo(source) if source else None
    if kind in {"auction_notice", "auction_recovery"}:
        source = PawnLoanAuction.objects.filter(workspace=workspace).select_related("loan__workspace", "loan__license", "loan__borrower", "accounting_event", "accounting_event__outbox", "notice").prefetch_related("items__collateral_item").order_by("-pk").first()
        if not source: return None
        return PawnLoanDocumentProjectionBuilder.auction_notice(source) if kind == "auction_notice" else PawnLoanDocumentProjectionBuilder.auction_recovery_memo(source)
    source = PawnLoanRenewal.objects.filter(workspace=workspace).select_related("source_loan__workspace", "source_loan__license", "source_loan__borrower", "successor_loan", "settlement_event__outbox", "opening_event__outbox").order_by("-pk").first()
    return PawnLoanDocumentProjectionBuilder.renewal_memo(source) if source else None


def _configurable_document_response(request, *, payload, loan, source_type, source_id, source_fingerprint):
    use_fixed = request.GET.get("renderer") == "fixed"
    if use_fixed and not _can_administer(request):
        return HttpResponse("Fixed-renderer recovery requires workspace administration access.", status=403, content_type="text/plain")
    if use_fixed:
        LoanDocumentLayoutService.audit_fixed_recovery(
            workspace=request.loans_workspace, source_type=source_type,
            source_id=source_id, actor=request.user, request=request,
        )
        return None
    revision = LoanDocumentLayoutService.resolve(
        workspace=request.loans_workspace, document_type=payload.document_type,
        license=loan.license, series=loan.series,
    )
    if revision is None:
        return None
    try:
        rendered = ConfigurableDocumentRenderer.render(
            payload, DocumentLayoutValidator.load(revision.definition), assets=_revision_assets(revision)
        )
        issue = LoanDocumentLayoutService.issue(
            workspace=request.loans_workspace, document_type=payload.document_type,
            source_type=source_type, source_id=source_id,
            source_fingerprint=source_fingerprint,
            payload_schema_version=payload.schema_version, render_result=rendered,
            filename=payload.file_name, actor=request.user, revision=revision,
        )
        issue.artifact.open("rb"); pdf = issue.artifact.read(); issue.artifact.close()
    except (ValueError, ValidationError, DocumentLayoutServiceError) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{payload.file_name}"'
    response["X-Rokkad-Verification-ID"] = payload.verification_id
    response["X-Rokkad-Document-Issue"] = str(issue.pk)
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
def pawn_repayment_receipt_pdf(request, pk, event_pk):
    event = get_object_or_404(
        PawnLoanAccountingEvent.objects.select_related(
            "loan",
            "loan__workspace",
            "loan__license",
            "loan__borrower",
            "outbox",
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
        source_type="PawnLoanAccountingEvent", source_id=event.pk,
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
            "accounting_event",
            "accounting_event__outbox",
            "reversal",
        ).prefetch_related("items__collateral_item"),
        pk=release_pk,
        workspace=request.loans_workspace,
    )
    payload = PawnLoanDocumentProjectionBuilder.release_memo(release)
    response = _configurable_document_response(
        request, payload=payload, loan=release.loan,
        source_type="PawnLoanRelease", source_id=release.pk,
        source_fingerprint=release.accounting_event.payload_fingerprint,
    )
    if response is not None:
        return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_release_memo(release))


@loans_workspace_required
def pawn_loan_create(request):
    readiness = _draft_readiness(request.loans_workspace)
    if not readiness["ready"]:
        return render(request, "loans/pawn/blocked.html", {"readiness": readiness})
    initial = {"loan_date": timezone.localdate()}
    if request.method == "GET" and request.GET.get("party"):
        initial["borrower"] = request.GET["party"]
    form = PawnDraftForm(
        request.POST or None,
        workspace=request.loans_workspace,
        initial=initial,
    )
    formset = PawnCollateralDraftFormSet(
        request.POST or None, request.FILES or None, prefix="collateral"
    )
    economics_preview = None
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        command = _create_command(request.loans_workspace.pk, form, formset)
        try:
            if request.POST.get("action") == "preview":
                economics_preview = resolve_pawn_draft_economics(
                    workspace_id=request.loans_workspace.pk,
                    license_id=command.license_id,
                    as_of_date=command.loan_date,
                    collateral=command.collateral,
                )
                loan = None
            else:
                with transaction.atomic():
                    loan = create_pawn_draft(command, actor=request.user)
                    _persist_formset_photos(
                        loan, formset, actor=request.user, workflow_source="DRAFT"
                    )
        except (PawnDraftError, ValidationError, ValueError) as exc:
            _add_pawn_draft_error(form, formset, exc)
        else:
            if loan is not None:
                messages.success(request, f"Draft {loan.loan_number} created.")
                return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(
        request,
        "loans/pawn/form.html",
        {
            "form": form,
            "formset": formset,
            "economics_preview": economics_preview,
            "number_preview_rows": _pawn_number_preview_rows(form),
        },
    )


@loans_workspace_required
def pawn_loan_update(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    if loan.state != PawnLoanState.DRAFT.value:
        messages.error(request, "Only draft PawnLoans can be edited.")
        return redirect("loans:pawn_loan_detail", pk=loan.pk)
    form = PawnDraftForm(request.POST or None, workspace=request.loans_workspace, instance=loan)
    initial = [
        {
            "description": item.description,
            "collateral_item_id": item.pk,
            "metal": item.metal,
            "gross_weight": item.gross_weight,
            "net_weight": item.net_weight,
            "purity_percentage": item.purity_percentage,
            "latest_appraised_value": item.latest_appraised_value,
            "allocated_principal": item.allocated_principal,
        }
        for item in loan.collateral_items.all()
    ]
    formset = PawnCollateralDraftFormSet(
        request.POST or None,
        request.FILES or None,
        prefix="collateral",
        initial=None if request.method == "POST" else initial,
    )
    economics_preview = None
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        command = _update_command(form, formset)
        try:
            if request.POST.get("action") == "preview":
                economics_preview = resolve_pawn_draft_economics(
                    workspace_id=request.loans_workspace.pk,
                    license_id=loan.license_id,
                    as_of_date=command.loan_date,
                    collateral=command.collateral,
                )
            else:
                with transaction.atomic():
                    loan = update_pawn_draft(loan.pk, command, actor=request.user)
                    _persist_formset_photos(
                        loan, formset, actor=request.user, workflow_source="DRAFT"
                    )
        except (PawnDraftError, ValidationError, ValueError) as exc:
            _add_pawn_draft_error(form, formset, exc)
        else:
            if request.POST.get("action") != "preview":
                messages.success(request, f"Draft {loan.loan_number} updated.")
                return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(
        request,
        "loans/pawn/form.html",
        {
            "form": form,
            "formset": formset,
            "loan": loan,
            "economics_preview": economics_preview,
            "number_preview_rows": _pawn_number_preview_rows(form),
        },
    )


@loans_workspace_required
def pawn_loan_detail(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    context = {
        "loan": loan,
        "today": timezone.localdate(),
        "can_administer": _can_administer(request),
        "can_manage_storage": request.loans_workspace.owner_id == request.user.pk,
        "notice_rows": get_pawn_loan_notice_rows(loan),
        "auctions": loan.auctions.select_related("accounting_event__outbox").order_by("-attempt_number"),
        "renewals": PawnLoanRenewal.objects.filter(
            Q(source_loan=loan) | Q(successor_loan=loan)
        ).select_related(
            "source_loan",
            "successor_loan",
            "settlement_event__outbox",
            "opening_event__outbox",
        ),
    }
    if loan.state in {PawnLoanState.ACTIVE.value, PawnLoanState.CLOSED.value}:
        try:
            context["balance"] = get_pawn_loan_balance(
                loan.pk,
                as_of_date=context["today"],
            )
        except (ValidationError, ValueError) as exc:
            context["balance_error"] = str(exc)
    if loan.state == PawnLoanState.ACTIVE.value:
        try:
            context["accrual_previews"] = preview_pawn_loan_accruals(
                loan.pk,
                as_of_date=context["today"],
                include_partial=True,
            )
        except (ValidationError, ValueError) as exc:
            context["accrual_error"] = str(exc)
    context["accounting_rows"] = _accounting_rows(
        loan,
        can_administer=context["can_administer"],
    )
    context["primary_action"] = _primary_action(loan, context)
    return render(request, "loans/pawn/detail.html", context)


@loans_workspace_required
@require_POST
def pawn_collateral_photo_add(request, pk, item_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    item = get_object_or_404(PawnCollateralItem, pk=item_pk, loan=loan)
    form = PawnCollateralPhotoForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            append_collateral_photo(
                item.pk,
                upload=form.cleaned_data["photograph"],
                actor=request.user,
            )
        except (PawnCollateralMediaError, ValidationError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Photograph appended to {item.description}.")
    else:
        messages.error(request, "Select a valid collateral photograph.")
    return redirect(f"{reverse('loans:pawn_loan_detail', args=[loan.pk])}#collateral-{item.public_id}")


@loans_workspace_required
def pawn_collateral_photo_document(request, pk, item_pk, photo_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    photo = get_object_or_404(
        PawnCollateralPhoto,
        pk=photo_pk,
        collateral_item_id=item_pk,
        collateral_item__loan=loan,
    )
    photo.file.open("rb")
    response = HttpResponse(photo.file.read(), content_type=photo.mime_type)
    response["Content-Disposition"] = content_disposition_header(
        True, photo.original_filename
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@loans_workspace_required
def pawn_collateral_label_pdf(request, pk, item_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    item = get_object_or_404(PawnCollateralItem, pk=item_pk, loan=loan)
    action = request.GET.get("action", "PREVIEW").upper()
    scan_url = request.build_absolute_uri(
        reverse("loans:pawn_collateral_scan", args=[item.public_id])
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
        session = get_object_or_404(
            PawnPhysicalVerificationSession,
            public_id=verification,
            workspace=request.loans_workspace,
        )
        return redirect(
            f"{reverse('loans:pawn_physical_verification_detail', args=[session.pk])}?item={item.pk}"
        )
    if (
        request.loans_workspace.owner_id == request.user.pk
        and item.custody_state == "IN_VAULT"
    ):
        request.session[_PENDING_STORAGE_ITEM_SESSION_KEY] = {
            "workspace_id": request.loans_workspace.pk,
            "item_public_id": str(item.public_id),
        }
    return redirect(
        f"{reverse('loans:pawn_loan_detail', args=[item.loan_id])}#collateral-{item.public_id}"
    )


@loans_setup_required
def pawn_storage_location_list(request):
    locations = PawnStorageLocation.objects.filter(
        workspace=request.loans_workspace
    ).select_related("parent", "parent__parent", "parent__parent__parent")
    return render(
        request,
        "loans/storage/location_list.html",
        {"locations": locations},
    )


@loans_setup_required
def pawn_storage_location_create(request):
    form = PawnStorageLocationForm(
        request.POST or None,
        workspace=request.loans_workspace,
    )
    if request.method == "POST" and form.is_valid():
        try:
            location = create_storage_location(
                workspace=request.loans_workspace,
                parent=form.cleaned_data.get("parent"),
                level=form.cleaned_data["level"],
                code=form.cleaned_data["code"],
                name=form.cleaned_data["name"],
                capacity=form.cleaned_data.get("capacity"),
                actor=request.user,
            )
        except (PawnStorageError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Storage location {location.code} created.")
            return redirect("loans:pawn_storage_location_list")
    return render(
        request,
        "loans/storage/location_form.html",
        {"form": form},
    )


@loans_setup_required
def pawn_storage_location_label(request, pk):
    location = get_object_or_404(
        PawnStorageLocation,
        pk=pk,
        workspace=request.loans_workspace,
    )
    qr_target = request.build_absolute_uri(
        reverse("loans:pawn_storage_location_scan", args=[location.public_id])
    )
    content = render_storage_location_label(location, qr_target=qr_target)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        False, f"storage-{location.code}.pdf"
    )
    return response


@loans_workspace_required
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
            f"{reverse('loans:pawn_physical_verification_detail', args=[session.pk])}{query}"
        )
    if location.level not in {
        PawnStorageLocation.Level.BOX,
        PawnStorageLocation.Level.SLOT,
    }:
        messages.info(request, "Collateral can only be placed in a Box or Slot.")
        return redirect("loans:pawn_storage_location_list")
    if item_public_id:
        item = get_object_or_404(
            PawnCollateralItem,
            public_id=item_public_id,
            loan__workspace=request.loans_workspace,
        )
        return redirect(
            f"{reverse('loans:pawn_collateral_storage_transfer', args=[item.loan_id, item.pk])}?destination={location.pk}"
        )
    pending = request.session.get(_PENDING_STORAGE_ITEM_SESSION_KEY, {})
    if (
        request.loans_workspace.owner_id == request.user.pk
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
                f"{reverse('loans:pawn_collateral_storage_transfer', args=[item.loan_id, item.pk])}?destination={location.pk}"
            )
        request.session.pop(_PENDING_STORAGE_ITEM_SESSION_KEY, None)
    messages.info(request, "Scan an in-vault collateral item before scanning its destination.")
    return redirect("loans:pawn_storage_location_list")


@loans_workspace_required
def pawn_collateral_storage_transfer(request, pk, item_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    item = get_object_or_404(PawnCollateralItem, pk=item_pk, loan=loan)
    initial = {}
    if request.method == "GET" and request.GET.get("destination"):
        initial["destination"] = request.GET["destination"]
    if (
        request.method == "GET"
        and request.loans_workspace.owner_id == request.user.pk
        and item.custody_state == "IN_VAULT"
    ):
        request.session[_PENDING_STORAGE_ITEM_SESSION_KEY] = {
            "workspace_id": request.loans_workspace.pk,
            "item_public_id": str(item.public_id),
        }
    form = PawnStorageTransferForm(
        request.POST or None,
        workspace=request.loans_workspace,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            movement = place_or_transfer_collateral(
                item.pk,
                destination_id=form.cleaned_data["destination"].pk,
                reason=form.cleaned_data.get("reason", ""),
                actor=request.user,
            )
        except (PawnStorageError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            request.session.pop(_PENDING_STORAGE_ITEM_SESSION_KEY, None)
            messages.success(
                request,
                f"{item.description} {movement.get_kind_display().lower()} recorded.",
            )
            return redirect(
                f"{reverse('loans:pawn_loan_detail', args=[loan.pk])}#collateral-{item.public_id}"
            )
    return render(
        request,
        "loans/storage/transfer_form.html",
        {"loan": loan, "item": item, "form": form},
    )


@loans_setup_required
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
            return redirect("loans:pawn_physical_verification_detail", pk=session.pk)
    sessions = PawnPhysicalVerificationSession.objects.filter(
        workspace=request.loans_workspace
    ).select_related("scope_location", "started_by", "completed_by")
    return render(
        request,
        "loans/verification/session_list.html",
        {"form": form, "sessions": sessions},
    )


@loans_setup_required
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
            return redirect("loans:pawn_physical_verification_detail", pk=session.pk)
    detail = get_physical_verification_detail(session)
    return render(
        request,
        "loans/verification/session_detail.html",
        {"session": session, "detail": detail, "form": form},
    )


@loans_setup_required
@require_POST
def pawn_physical_verification_complete(request, pk):
    try:
        complete_physical_verification(pk, actor=request.user)
    except (PawnPhysicalVerificationError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Physical-verification session completed and frozen.")
    return redirect("loans:pawn_physical_verification_detail", pk=pk)


@loans_setup_required
def pawn_physical_verification_resolve(request, observation_pk):
    observation = get_object_or_404(
        PawnPhysicalVerificationObservation.objects.select_related("session", "collateral_item__loan", "observed_location"),
        pk=observation_pk,
        session__workspace=request.loans_workspace,
    )
    form = PawnPhysicalVerificationResolutionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            resolve_physical_verification_discrepancy(
                observation.pk,
                outcome=form.cleaned_data["outcome"],
                reason=form.cleaned_data["reason"],
                current_market_value=form.cleaned_data.get("current_market_value"),
                agreed_compensation=form.cleaned_data.get("agreed_compensation"),
                compensation_reference=form.cleaned_data.get("compensation_reference", ""),
                actor=request.user,
            )
        except (PawnPhysicalVerificationError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Immutable discrepancy resolution recorded.")
            return redirect("loans:pawn_physical_verification_detail", pk=observation.session_id)
    return render(request, "loans/verification/resolution_form.html", {"observation": observation, "form": form})


@loans_setup_required
@require_POST
def pawn_physical_verification_discrepancy_notice(request, observation_pk):
    observation = get_object_or_404(
        PawnPhysicalVerificationObservation,
        pk=observation_pk,
        session__workspace=request.loans_workspace,
    )
    try:
        create_verification_discrepancy_notice(
            observation.pk,
            request_key=f"verification-discrepancy:{observation.pk}",
            actor=request.user,
        )
    except (LoanOperationalNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, "Verification discrepancy alert intent is ready for the workspace Owner."
        )
    return redirect("loans:pawn_physical_verification_detail", pk=observation.session_id)


@loans_workspace_required
@require_POST
def pawn_loan_approve(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    try:
        approve_pawn_loan(loan.pk, actor=request.user)
        messages.success(request, f"{loan.loan_number} approved. Its economic payload is frozen.")
    except (PawnLifecycleError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("loans:pawn_loan_detail", pk=loan.pk)


@loans_workspace_required
def pawn_loan_reopen(request, pk):
    return _reason_transition(request, pk, "reopen")


@loans_workspace_required
def pawn_loan_cancel(request, pk):
    return _reason_transition(request, pk, "cancel")


@loans_workspace_required
def pawn_loan_disburse(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnDisbursalForm(
        request.POST or None,
        initial={"effective_date": timezone.localdate()},
    )
    if request.method == "POST" and form.is_valid():
        try:
            disburse_pawn_loan(
                loan.pk,
                effective_date=form.cleaned_data["effective_date"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{loan.loan_number} disbursed and queued for accounting.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    readiness = None
    readiness_error = ""
    effective_date = (
        form.cleaned_data.get("effective_date")
        if form.is_bound and form.is_valid()
        else timezone.localdate()
    )
    try:
        readiness = assess_pawn_loan_accounting_readiness(
            loan,
            effective_date=effective_date,
        )
    except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
        readiness_error = str(exc)
    return _render_action(
        request,
        loan,
        form,
        "Disburse loan",
        "This posts the approved principal through DEA and activates the loan.",
        {
            "accounting_readiness": readiness,
            "accounting_readiness_error": readiness_error,
            "can_administer": _can_administer(request),
        },
    )


@loans_setup_required
def pawn_borrower_account_setup(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    if request.method == "POST":
        try:
            result = ensure_pawn_borrower_accounting(
                loan.pk,
                actor=request.user,
                request=request,
            )
        except PawnBorrowerAccountingSetupError as exc:
            messages.error(request, str(exc))
        else:
            if result.mapping_created:
                messages.success(
                    request,
                    f"Borrower accounting account {result.account} is ready.",
                )
            else:
                messages.info(request, "The borrower accounting mapping was already ready.")
            return redirect("loans:pawn_loan_disburse", pk=loan.pk)
    return render(
        request,
        "loans/pawn/borrower_account_setup.html",
        {"loan": loan},
    )


@loans_workspace_required
def pawn_loan_repay(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    repayment_preview = None
    form = PawnRepaymentForm(
        request.POST or None,
        initial={"request_key": uuid.uuid4().hex},
    )
    if request.method == "POST" and form.is_valid():
        try:
            if request.POST.get("action") == "preview":
                repayment_preview = preview_pawn_loan_repayment(
                    loan.pk,
                    amount=form.cleaned_data["amount"],
                )
            else:
                result = record_pawn_loan_repayment(
                    loan.pk,
                    amount=form.cleaned_data["amount"],
                    request_key=form.cleaned_data["request_key"],
                    actor=request.user,
                )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            if repayment_preview is None:
                delivery = result.outbox.get_status_display()
                allocation = result.allocation
                messages.success(
                    request,
                    "Repayment "
                    f"{allocation.amount_received} recorded: fees {allocation.fees}, "
                    f"overdue interest {allocation.overdue_interest}, current interest "
                    f"{allocation.current_interest}, principal {allocation.principal}. "
                    f"Accounting delivery: {delivery}.",
                )
                return redirect("loans:pawn_loan_detail", pk=loan.pk)
    balance = _safe_balance(loan)
    item_by_id = {item.pk: item for item in loan.collateral_items.all()}
    return _render_action(
        request,
        loan,
        form,
        "Record repayment",
        "Allocation is fixed: fees, overdue interest, current interest, then principal.",
        {
            "balance": balance,
            "supports_preview": True,
            "preview_action_label": "Preview allocation",
            "repayment_preview": repayment_preview,
            "repayment_item_rows": tuple(
                {
                    "allocation": row,
                    "item": item_by_id.get(row.collateral_item_id),
                }
                for row in (
                    repayment_preview.item_allocations
                    if repayment_preview is not None
                    else ()
                )
            ),
        },
    )


@loans_workspace_required
def pawn_loan_accrue(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    previews = _safe_accrual_previews(loan, include_partial=False)
    initial = {"period_number": previews[0].period_number} if previews else None
    form = PawnAccrualForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            result = finalize_pawn_loan_accrual(
                loan.pk,
                period_number=form.cleaned_data["period_number"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            disposition = (
                result.outbox.get_status_display()
                if result.outbox is not None
                else "No accounting event required by the cash-recognition policy"
            )
            messages.success(
                request,
                f"Interest accrual finalized. Accounting disposition: {disposition}.",
            )
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Finalize interest accrual",
        "Only the next eligible completed monthly period can be finalized.",
        {
            "previews": previews,
            "accrual_preview_rows": _accrual_preview_rows(loan, previews),
        },
    )


@loans_workspace_required
def pawn_loan_capitalize(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnCapitalizationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            capitalize_pawn_loan_interest(
                loan.pk,
                through_period_number=form.cleaned_data["through_period_number"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Interest capitalization recorded and queued.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Capitalize interest",
        "Available only at the snapshotted compound-interest boundary.",
    )


@loans_workspace_required
def pawn_loan_release_full(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    quote = _full_release_quote(loan)
    initial = {"request_key": uuid.uuid4().hex}
    minimum_settlement = (
        quote.get("minimum_settlement")
        if isinstance(quote, dict)
        else quote.minimum_settlement
    )
    if minimum_settlement is not None:
        initial["settlement_amount"] = minimum_settlement
    form = PawnFullReleaseForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            result = release_pawn_loan_in_full(
                loan.pk,
                settlement_amount=form.cleaned_data["settlement_amount"],
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Release {result.release.release_number} completed: "
                f"{result.release.settlement_amount} collected, "
                f"{result.release.items.count()} collateral item(s) returned, "
                f"loan closed. Accounting delivery: "
                f"{result.outbox.get_status_display()}.",
            )
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Full release",
        "Collect the exact displayed settlement before returning all remaining collateral.",
        {"quote": quote},
    )


@loans_workspace_required
def pawn_loan_release_partial(request, pk):
    _pawn_loan_for_workspace(request, pk)
    return HttpResponseGone(
        "Partial collateral release is no longer supported. "
        "Use full release or release and renew into a newly numbered PawnLoan."
    )


@loans_workspace_required
def pawn_loan_reverse_event(request, pk, event_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    event = get_object_or_404(
        PawnLoanAccountingEvent.objects.select_related("outbox", "loan__workspace"),
        pk=event_pk,
        loan=loan,
    )
    readiness = assess_pawn_loan_event_reversal(event)
    form = PawnReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            result = reverse_pawn_loan_event(
                event.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            balance = _safe_balance(loan)
            disposition = (
                "Accounting delivery is deferred."
                if readiness.accounting_mode == "DEFERRED"
                else "The compensating event is queued through DEA."
            )
            balance_text = (
                f" Resulting Loans total due is {balance.total_due}." if balance else ""
            )
            messages.success(
                request,
                f"Reversal event #{result.reversal_event.pk} recorded.{balance_text} {disposition}",
            )
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        f"Reverse {event.get_event_kind_display()}",
        "Administrator-only. Correct events newest-first; the original evidence is never edited.",
        {
            "accounting_event": event,
            "balance": _safe_balance(loan),
            "reversal_readiness": readiness,
            "reversal_values": (event.payload.get("values") or {}).items(),
            "custody_items": loan.collateral_items.all(),
        },
    )


@loans_workspace_required
def pawn_loan_notice_create(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    requested_kind = request.GET.get("kind", "")
    allowed_kinds = {
        value for value, _label in PawnLoanNoticeForm.base_fields["notice_kind"].choices
    }
    form = PawnLoanNoticeForm(
        request.POST or None,
        initial={
            "request_key": uuid.uuid4().hex,
            "notice_kind": requested_kind if requested_kind in allowed_kinds else "",
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            notice = create_pawn_loan_notice(
                loan.pk,
                notice_kind=form.cleaned_data["notice_kind"],
                channel=form.cleaned_data["channel"],
                scheduled_for=form.cleaned_data.get("scheduled_for"),
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (PawnLoanNoticeError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"{notice.get_notice_kind_display()} queued through Notify.",
            )
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Create loan notice",
        "Review and confirm the immutable notice source. Loans owns the intent; Notify owns templates, provider delivery, and attempts.",
        {"balance": _safe_balance(loan), "notice_preview": True},
    )


@loans_workspace_required
@require_POST
def pawn_loan_notice_retry(request, pk, notice_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    notice = get_object_or_404(
        PawnLoanNotice,
        pk=notice_pk,
        loan=loan,
        workspace=request.loans_workspace,
    )
    try:
        result = dispatch_pawn_loan_notice(notice.pk)
    except (PawnLoanNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        if result.delivery.status == "SENT":
            messages.success(request, "PawnLoan notice sent.")
        elif result.delivery.status == "FAILED":
            messages.error(
                request,
                result.delivery.failure_reason or "Notice delivery failed.",
            )
        else:
            messages.info(request, "PawnLoan notice remains queued.")
    return redirect("loans:pawn_loan_detail", pk=loan.pk)


@loans_workspace_required
def pawn_loan_auction_initiate(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnAuctionInitiateForm(
        request.POST or None,
        initial={"request_key": uuid.uuid4().hex},
    )
    if request.method == "POST" and form.is_valid():
        try:
            auction = initiate_pawn_loan_auction(
                loan.pk,
                scheduled_date=form.cleaned_data["scheduled_date"],
                channel=form.cleaned_data["channel"],
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} initiated and notice queued.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Initiate auction recovery",
        "Administrator-only. The loan must be overdue and all collateral must remain in the vault.",
    )


@loans_workspace_required
@require_POST
def pawn_loan_auction_start(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    try:
        start_pawn_loan_auction(auction.pk, actor=request.user)
    except (PawnAuctionError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Auction {auction.auction_number} started.")
    return redirect("loans:pawn_loan_detail", pk=auction.loan_id)


@loans_workspace_required
def pawn_loan_auction_cancel(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnTransitionReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_pawn_loan_auction(
                auction.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} cancelled.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Cancel auction",
        "An initiated or in-progress auction can be cancelled. A reason is required.",
        {"auction": auction},
    )


@loans_workspace_required
def pawn_loan_auction_complete(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnAuctionCompletionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_pawn_loan_auction(
                auction.pk,
                recovery_amount=form.cleaned_data["recovery_amount"],
                buyer_name=form.cleaned_data["buyer_name"],
                buyer_reference=form.cleaned_data["buyer_reference"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} completed and recovery queued through DEA.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Complete auction recovery",
        "Recovery must exactly clear the canonical debt. Shortfall and surplus workflows fail closed.",
        {"auction": auction},
    )


@loans_workspace_required
def pawn_loan_auction_reverse(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_pawn_loan_auction(
                auction.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} reversed.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Reverse auction recovery",
        "Administrator-only. Accounting and custody are restored through compensating evidence.",
        {"auction": auction},
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
            source_fingerprint=auction.accounting_event.payload_fingerprint,
        )
        if response is not None: return response
        result = PawnLoanDocumentService.render_auction_recovery_memo(auction)
    except (PawnLoanDocumentError, ValueError) as exc:
        return HttpResponse(str(exc), status=409)
    return PawnLoanDocumentService.build_pdf_response(result)


@loans_workspace_required
def pawn_loan_renew(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    is_exact_preview = (
        request.method == "POST" and request.POST.get("action") == "preview"
    )
    form_data = request.POST.copy() if is_exact_preview else (request.POST or None)
    if is_exact_preview:
        form_data["confirm_renewal_plan"] = "on"
    try:
        renewal_quote = preview_pawn_loan_renewal_source(loan.pk)
    except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
        renewal_quote = {"error": str(exc)}
    source_items = tuple(
        loan.collateral_items.filter(custody_state="IN_VAULT").order_by("pk")
    )
    try:
        current_tranches = {
            row.collateral_item_id: row.principal_outstanding
            for row in get_pawn_principal_tranche_balances(loan)
        }
    except PawnTrancheBalanceError:
        current_tranches = {}
    retained_initial = [
        {
            "collateral_item_id": item.pk,
            "retain": True,
            "allocated_principal": current_tranches.get(
                item.pk, item.allocated_principal
            ),
        }
        for item in source_items
    ]
    initial = {
        "request_key": uuid.uuid4().hex,
        "successor_license": loan.license_id,
        "successor_series": loan.series_id,
        "tenure_months": loan.tenure_months,
    }
    form = PawnRenewalForm(
        form_data,
        workspace=request.loans_workspace,
        initial=initial,
    )
    retained_formset = PawnRenewalRetainedItemFormSet(
        form_data,
        prefix="retained",
        initial=retained_initial,
    )
    additional_formset = PawnAdditionalCollateralFormSet(
        form_data,
        request.FILES or None,
        prefix="additional",
    )
    forms_valid = (
        request.method == "POST"
        and form.is_valid()
        and retained_formset.is_valid()
        and additional_formset.is_valid()
    )
    if is_exact_preview and not forms_valid:
        return JsonResponse(
            {
                "ok": False,
                "message": "Correct the highlighted renewal fields before previewing.",
                "form_errors": form.errors.get_json_data(),
                "retained_errors": [
                    errors.get_json_data() for errors in retained_formset.errors
                ],
                "additional_errors": [
                    errors.get_json_data() for errors in additional_formset.errors
                ],
            },
            status=400,
        )
    if forms_valid:
        retained = tuple(
            RetainedCollateralInput(
                collateral_item_id=row["collateral_item_id"],
                allocated_principal=row["allocated_principal"],
            )
            for row in retained_formset.cleaned_data
            if row and row.get("retain")
        )
        additional = _collateral_inputs(additional_formset)
        try:
            exact_preview = preview_pawn_loan_renewal_plan(
                loan.pk,
                mode=form.cleaned_data["mode"],
                principal_paid=form.cleaned_data["principal_paid"],
                top_up_amount=form.cleaned_data["top_up_amount"],
                successor_license_id=form.cleaned_data["successor_license"].pk,
                successor_series_id=form.cleaned_data["successor_series"].pk,
                tenure_months=form.cleaned_data["tenure_months"],
                retained_collateral=retained,
                additional_collateral=additional,
            )
        except (PawnRenewalError, ValidationError, ValueError) as exc:
            if is_exact_preview:
                return JsonResponse(
                    {"ok": False, "message": str(exc)},
                    status=409,
                )
            form.add_error(None, str(exc))
            exact_preview = None
        if is_exact_preview and exact_preview is not None:
            return JsonResponse(
                {
                    "ok": True,
                    "fingerprint": exact_preview.fingerprint,
                    "successor_principal": str(exact_preview.successor_principal),
                    "successor_monthly_interest": str(
                        exact_preview.successor_monthly_interest
                    ),
                    "successor_advance_interest": str(
                        exact_preview.successor_advance_interest
                    ),
                    "successor_deducted_fees": str(
                        exact_preview.successor_deducted_fees
                    ),
                    "source_interest_and_fees": str(
                        exact_preview.source.base_cash_received
                    ),
                    "principal_paid": str(exact_preview.principal_paid),
                    "top_up_amount": str(exact_preview.top_up_amount),
                    "total_cash_received": str(exact_preview.total_cash_received),
                    "net_cash_amount": str(abs(exact_preview.net_cash_amount)),
                    "net_cash_direction": exact_preview.net_cash_direction,
                    "retained_count": len(exact_preview.retained_item_ids),
                    "returned_count": len(exact_preview.returned_item_ids),
                    "successor_collateral_count": (
                        exact_preview.successor_collateral_count
                    ),
                }
            )
        if exact_preview is not None and (
            form.cleaned_data.get("preview_fingerprint")
            != exact_preview.fingerprint
        ):
            form.add_error(
                None,
                "Calculate and review the exact renewal after the latest changes before completing it.",
            )
            exact_preview = None
        if exact_preview is None:
            pass
        else:
            try:
                result = renew_pawn_loan(
                    loan.pk,
                    mode=form.cleaned_data["mode"],
                    renewal_date=timezone.localdate(),
                    principal_paid=form.cleaned_data["principal_paid"],
                    top_up_amount=form.cleaned_data["top_up_amount"],
                    successor_license_id=form.cleaned_data["successor_license"].pk,
                    successor_series_id=form.cleaned_data["successor_series"].pk,
                    tenure_months=form.cleaned_data["tenure_months"],
                    request_key=form.cleaned_data["request_key"],
                    retained_collateral=retained,
                    additional_collateral=additional,
                    additional_photo_uploads=tuple(
                        row["photograph"]
                        for row in additional_formset.cleaned_data
                        if row and not row.get("DELETE")
                    ),
                    expected_preview_fingerprint=exact_preview.fingerprint,
                    actor=request.user,
                )
            except (PawnRenewalError, ValidationError, ValueError) as exc:
                form.add_error(None, str(exc))
            else:
                snapshot = result.renewal.valuation_snapshot
                messages.success(
                    request,
                    f"Release and renew {result.renewal.renewal_number} completed: "
                    f"source loan closed, successor {result.successor_loan.loan_number} active; "
                    f"{len(snapshot.get('returned_source_item_ids') or [])} item(s) returned, "
                    f"{len(snapshot.get('retained_source_item_ids') or [])} retained, "
                    f"{len(snapshot.get('additional_successor_item_ids') or [])} added. "
                    f"Accounting delivery: settlement "
                    f"{result.settlement_outbox.get_status_display()}, successor opening "
                    f"{result.opening_outbox.get_status_display()}.",
                )
                return redirect("loans:pawn_loan_detail", pk=result.successor_loan.pk)
    return render(
        request,
        "loans/pawn/release_and_renew.html",
        {
            "loan": loan,
            "form": form,
            "retained_formset": retained_formset,
            "retained_rows": tuple(zip(source_items, retained_formset.forms)),
            "additional_formset": additional_formset,
            "renewal_quote": renewal_quote,
        },
    )


@loans_workspace_required
def pawn_loan_renewal_reverse(request, renewal_pk):
    renewal = _pawn_renewal_for_workspace(request, renewal_pk)
    form = PawnReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_pawn_loan_renewal(
                renewal.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnRenewalError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Renewal {renewal.renewal_number} reversed.")
            return redirect("loans:pawn_loan_detail", pk=renewal.source_loan_id)
    return _render_action(
        request,
        renewal.source_loan,
        form,
        "Reverse renewal",
        "Administrator-only. The successor must have no later activity and both collateral records must remain in compatible custody.",
        {"renewal": renewal},
    )


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


@loans_workspace_required
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
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(request, "loans/pawn/transition_form.html", {"loan": loan, "form": form, "action_label": "Transfer setup"})


@loans_setup_required
@require_POST
def pawn_outbox_retry(request, pk):
    outbox = get_object_or_404(
        PawnLoanAccountingOutbox.objects.select_related("event__loan"),
        pk=pk,
        event__loan__workspace=request.loans_workspace,
    )
    try:
        retry_failed_outbox_event(outbox.pk)
        messages.success(request, f"Accounting outbox event #{outbox.pk} queued for retry.")
    except LoanAccountingOutboxError as exc:
        messages.error(request, str(exc))
    if request.POST.get("next") == "operations":
        return redirect("loans:pawn_operations_console")
    return redirect("loans:pawn_loan_detail", pk=outbox.event.loan_id)


@loans_setup_required
def pawn_operations_console(request):
    return render(
        request,
        "loans/setup/operations_console.html",
        {"snapshot": get_pawn_loan_operations_snapshot()},
    )


@loans_setup_required
def pawn_operations_runbook(request):
    return render(request, "loans/setup/operations_runbook.html")


@loans_setup_required
def funding_loan_read_console(request):
    return render(
        request,
        "loans/setup/funding/list.html",
        {
            "funding_loans": get_funding_loan_summaries(),
            "findings": get_funding_loan_integrity_findings(),
        },
    )


@loans_setup_required
def funding_loan_draft_create(request):
    form = FundingLoanDraftForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            funding_loan = create_funding_loan_draft(
                CreateFundingLoanDraft(
                    workspace_id=request.loans_workspace.pk,
                    lender_id=form.cleaned_data["lender"].pk,
                ),
                actor=request.user,
            )
        except FundingLoanServiceError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"FundingLoan draft {funding_loan.funding_number} created.",
            )
            return redirect("loans:funding_loan_read_detail", pk=funding_loan.pk)
    return render(
        request,
        "loans/setup/funding/form.html",
        {"form": form},
    )


@loans_setup_required
def funding_loan_draft_inputs(request, pk):
    try:
        draft = get_funding_loan_draft_inputs(pk)
    except FundingLoanSelectorError as exc:
        raise Http404(str(exc)) from exc
    initial = {
        "principal_amount": draft.principal_amount,
        "monthly_interest_rate": draft.monthly_interest_rate,
        "activated_on": draft.activated_on,
        "maturity_on": draft.maturity_on,
        "maximum_funding_ltv_ratio": draft.maximum_funding_ltv_ratio,
        "currency_quantum": draft.currency_quantum,
        "collateral": draft.collateral_item_ids,
    }
    form = FundingLoanDraftInputsForm(
        request.POST if request.method == "POST" else None,
        workspace=request.loans_workspace,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        collateral = tuple(
            FundingCollateralInput(item.pk, item.latest_appraised_value)
            for item in form.cleaned_data["collateral"]
        )
        try:
            save_funding_loan_draft_inputs(
                SaveFundingLoanDraftInputs(
                    workspace_id=request.loans_workspace.pk,
                    funding_loan_id=pk,
                    principal_amount=form.cleaned_data["principal_amount"],
                    monthly_interest_rate=form.cleaned_data["monthly_interest_rate"],
                    activated_on=form.cleaned_data["activated_on"],
                    maturity_on=form.cleaned_data["maturity_on"],
                    maximum_funding_ltv_ratio=form.cleaned_data["maximum_funding_ltv_ratio"],
                    currency_quantum=form.cleaned_data["currency_quantum"],
                    collateral=collateral,
                ),
                actor=request.user,
            )
        except FundingLoanServiceError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "FundingLoan draft inputs saved and ready for review.")
            return redirect("loans:funding_loan_read_detail", pk=pk)
    return render(
        request,
        "loans/setup/funding/draft_inputs.html",
        {"form": form, "funding_loan_id": pk, "draft": draft},
    )


@require_POST
@loans_setup_required
def funding_loan_draft_cancel(request, pk):
    form = FundingLoanCancellationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A cancellation reason is required.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    try:
        funding_loan = cancel_funding_loan_draft(
            CancelFundingLoanDraft(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                reason=form.cleaned_data["reason"],
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"FundingLoan draft {funding_loan.funding_number} cancelled.")
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_draft_activate(request, pk):
    form = FundingLoanActivationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter ACTIVATE exactly to confirm activation.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    try:
        result = activate_saved_funding_loan_draft(
            ActivateSavedFundingLoanDraft(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"FundingLoan {result.funding_loan.funding_number} activated; "
            f"{result.pledge.items.count()} collateral item(s) handed to the lender.",
        )
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_repayment(request, pk):
    form = FundingLoanRepaymentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid repayment amount and effective date.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    try:
        event = record_funding_repayment(
            RecordFundingRepayment(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                amount=form.cleaned_data["amount"],
                effective_date=form.cleaned_data["effective_date"],
                request_key=str(form.cleaned_data["request_key"]),
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Funding repayment recorded: "
            f"fees {event.fee_amount}, interest {event.interest_amount}, "
            f"principal {event.principal_amount}.",
        )
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_begin_settlement(request, pk):
    try:
        funding_loan = begin_funding_settlement(
            BeginFundingSettlement(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"FundingLoan {funding_loan.funding_number} entered settlement review.",
        )
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_return_collateral(request, pk):
    try:
        detail = get_funding_loan_detail(pk)
    except FundingLoanSelectorError as exc:
        raise Http404(str(exc)) from exc
    if detail.summary.state != "SETTLEMENT_PENDING":
        messages.error(request, "Begin settlement review before returning collateral.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    form = FundingCollateralReturnForm(
        request.POST,
        collateral_rows=detail.collateral,
        include_inactive=True,
    )
    if not form.is_valid():
        messages.error(request, "Select valid active collateral and an effective date.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    try:
        funding_return = return_funding_collateral(
            ReturnFundingCollateral(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                collateral_item_ids=tuple(
                    int(item_id) for item_id in form.cleaned_data["collateral"]
                ),
                effective_date=form.cleaned_data["effective_date"],
                request_key=str(form.cleaned_data["request_key"]),
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"Returned {funding_return.items.count()} collateral item(s) to the branch vault.",
        )
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_close(request, pk):
    form = FundingLoanClosureForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter CLOSE exactly to confirm closure.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    try:
        funding_loan = close_funding_loan(
            CloseFundingLoan(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            f"FundingLoan {funding_loan.funding_number} closed.",
        )
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_reverse_event(request, pk, event_pk):
    form = FundingCorrectionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a correction date and reason.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    try:
        reverse_funding_event(
            ReverseFundingEvent(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                original_event_id=event_pk,
                effective_date=form.cleaned_data["effective_date"],
                reason=form.cleaned_data["reason"],
                request_key=str(form.cleaned_data["request_key"]),
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Funding financial event corrected.")
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_reverse_return(request, pk, return_pk):
    form = FundingCorrectionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a correction date and reason.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    try:
        reverse_funding_return(
            ReverseFundingReturn(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                funding_return_id=return_pk,
                effective_date=form.cleaned_data["effective_date"],
                reason=form.cleaned_data["reason"],
                request_key=str(form.cleaned_data["request_key"]),
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Funding collateral return corrected.")
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_reverse_pledge(request, pk):
    form = FundingCorrectionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a correction date and reason.")
        return redirect("loans:funding_loan_read_detail", pk=pk)
    try:
        reverse_funding_pledge(
            ReverseFundingPledge(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                effective_date=form.cleaned_data["effective_date"],
                reason=form.cleaned_data["reason"],
                request_key=str(form.cleaned_data["request_key"]),
            ),
            actor=request.user,
        )
    except FundingLoanServiceError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Funding pledge handoff corrected.")
    return redirect("loans:funding_loan_read_detail", pk=pk)


def _funding_document_loan(request, pk):
    try:
        return FundingLoan.objects.select_related(
            "workspace", "lender", "terms_snapshot", "pledge"
        ).get(pk=pk, workspace=request.loans_workspace)
    except FundingLoan.DoesNotExist as exc:
        raise Http404("FundingLoan was not found in the active workspace.") from exc


@loans_setup_required
def funding_loan_agreement_pdf(request, pk):
    loan = _funding_document_loan(request, pk)
    if not hasattr(loan, "terms_snapshot") or not hasattr(loan, "pledge"):
        raise Http404("Funding agreement is available only after activation.")
    detail = get_funding_loan_detail(pk)
    return PawnLoanDocumentService.build_pdf_response(
        FundingLoanDocumentService.render_agreement(loan, detail)
    )


@loans_setup_required
def funding_loan_repayment_receipt_pdf(request, pk, event_pk):
    loan = _funding_document_loan(request, pk)
    try:
        event = loan.events.get(pk=event_pk, event_kind="REPAYMENT")
    except FundingLoanEvent.DoesNotExist as exc:
        raise Http404("Funding repayment evidence was not found.") from exc
    return PawnLoanDocumentService.build_pdf_response(
        FundingLoanDocumentService.render_repayment_receipt(event)
    )


@loans_setup_required
def funding_loan_return_receipt_pdf(request, pk, return_pk):
    loan = _funding_document_loan(request, pk)
    try:
        funding_return = loan.returns.prefetch_related(
            "items__pledge_item__collateral_item__loan"
        ).get(pk=return_pk)
    except FundingReturn.DoesNotExist as exc:
        raise Http404("Funding return evidence was not found.") from exc
    return PawnLoanDocumentService.build_pdf_response(
        FundingLoanDocumentService.render_return_receipt(funding_return)
    )


@loans_setup_required
def funding_loan_statement_pdf(request, pk):
    loan = _funding_document_loan(request, pk)
    if not hasattr(loan, "terms_snapshot"):
        raise Http404("Funding statement is available only after activation.")
    detail = get_funding_loan_detail(pk)
    return PawnLoanDocumentService.build_pdf_response(
        FundingLoanDocumentService.render_statement(loan, detail)
    )


@loans_setup_required
def funding_loan_read_detail(request, pk):
    try:
        detail = get_funding_loan_detail(pk)
    except FundingLoanSelectorError as exc:
        raise Http404(str(exc)) from exc
    draft = None
    if detail.summary.state == "DRAFT":
        draft = get_funding_loan_draft_inputs(pk)
    settlement = None
    if detail.summary.state in {"ACTIVE", "SETTLEMENT_PENDING"}:
        settlement = get_funding_settlement_readiness(pk, detail=detail)
    return render(
        request,
        "loans/setup/funding/detail.html",
        {
            "detail": detail,
            "draft": draft,
            "settlement": settlement,
            "activation_form": FundingLoanActivationForm(),
            "cancellation_form": FundingLoanCancellationForm(),
            "closure_form": FundingLoanClosureForm(),
            "correction_form": FundingCorrectionForm(
                initial={
                    "effective_date": timezone.localdate(),
                    "request_key": uuid.uuid4(),
                }
            ),
            "repayment_form": FundingLoanRepaymentForm(
                initial={
                    "effective_date": timezone.localdate(),
                    "request_key": uuid.uuid4(),
                }
            ),
            "return_form": FundingCollateralReturnForm(
                collateral_rows=detail.collateral,
                initial={
                    "effective_date": timezone.localdate(),
                    "request_key": uuid.uuid4(),
                },
            ),
        },
    )


@loans_setup_required
def license_list(request):
    register_rows = get_loan_license_register(request.loans_workspace.pk)
    return render(
        request,
        "loans/setup/license_list.html",
        {
            "register_rows": register_rows,
            "as_of_date": timezone.localdate(),
        },
    )


@loans_setup_required
def license_register_pdf(request):
    as_of_date = timezone.localdate()
    rows = get_loan_license_register(
        request.loans_workspace.pk,
        as_of_date=as_of_date,
    )
    content = render_loan_license_register_pdf(
        workspace=request.loans_workspace,
        rows=rows,
        as_of_date=as_of_date,
    )
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(
        True,
        f"loan-license-register-{as_of_date.isoformat()}.pdf",
    )
    return response


@loans_setup_required
def pawn_economics_setup(request):
    action = request.POST.get("action") if request.method == "POST" else None
    configuration_form = PawnEconomicConfigurationForm(
        request.POST if action == "configuration" else None,
        workspace=request.loans_workspace,
        initial={"effective_from": timezone.localdate()},
        prefix="configuration",
    )
    fee_form = PawnFeePolicyForm(
        request.POST if action == "fee" else None,
        workspace=request.loans_workspace,
        initial={"effective_from": timezone.localdate()},
        prefix="fee",
    )
    if action == "configuration" and configuration_form.is_valid():
        data = configuration_form.cleaned_data
        try:
            with transaction.atomic():
                create_pawn_loan_economic_policy(
                    workspace=request.loans_workspace,
                    license=data["license"],
                    valuation_method=data["valuation_method"],
                    maximum_ltv_ratio=data["maximum_ltv_ratio"],
                    advance_interest_periods=data["advance_interest_periods"],
                    interest_method=data["interest_method"],
                    partial_month_method=data["partial_month_method"],
                    partial_month_cutoff_days=data["partial_month_cutoff_days"],
                    partial_month_lower_fraction=data[
                        "partial_month_lower_fraction"
                    ],
                    capitalization_interval_periods=data[
                        "capitalization_interval_periods"
                    ],
                    accounting_recognition=data["accounting_recognition"],
                    rounding_method=data["rounding_method"],
                    currency_quantum=data["currency_quantum"],
                    effective_from=data["effective_from"],
                    actor=request.user,
                )
                for metal, rate in (
                    ("GOLD", data["gold_monthly_interest_rate"]),
                    ("SILVER", data["silver_monthly_interest_rate"]),
                ):
                    create_pawn_metal_interest_rate_policy(
                        workspace=request.loans_workspace,
                        license=data["license"],
                        metal=metal,
                        monthly_interest_rate=rate,
                        effective_from=data["effective_from"],
                        actor=request.user,
                    )
        except (ValidationError, ValueError) as exc:
            configuration_form.add_error(None, str(exc))
        else:
            messages.success(request, "PawnLoan economic configuration added.")
            return redirect("loans:pawn_economics_setup")
    if action == "fee" and fee_form.is_valid():
        try:
            create_pawn_loan_fee_policy(
                workspace=request.loans_workspace,
                actor=request.user,
                **fee_form.cleaned_data,
            )
        except (ValidationError, ValueError) as exc:
            fee_form.add_error(None, str(exc))
        else:
            messages.success(request, "PawnLoan fee policy added.")
            return redirect("loans:pawn_economics_setup")
    context = {
        "configuration_form": configuration_form,
        "fee_form": fee_form,
        "economic_policies": PawnLoanEconomicPolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
        "rate_policies": PawnMetalInterestRatePolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
        "fee_policies": PawnLoanFeePolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
    }
    return render(request, "loans/setup/economics.html", context)


@loans_setup_required
def license_detail(request, pk):
    license = _license_for_workspace(request, pk)
    revisions = license.revisions.select_related("created_by").order_by(
        "-revision_number"
    )
    series_rows = []
    for series in license.series.prefetch_related("number_sequences").all():
        series_rows.append(
            {
                "series": series,
                "loan_preview": _safe_preview(series, LoanDocumentKind.PAWN_LOAN),
                "release_preview": _safe_preview(
                    series, LoanDocumentKind.PAWN_LOAN_RELEASE
                ),
            }
        )
    return render(
        request,
        "loans/setup/license_detail.html",
        {
            "license": license,
            "series_rows": series_rows,
            "revisions": revisions,
            "expiry_notices": license.operational_notices.order_by("-created_at"),
        },
    )


@loans_setup_required
@require_POST
def license_expiry_notice_create(request, pk):
    license = _license_for_workspace(request, pk)
    try:
        create_license_expiry_notice(
            license.pk, request_key=uuid.uuid4().hex, actor=request.user
        )
    except (LoanOperationalNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "License expiry alert queued for the workspace Owner.")
    return redirect("loans:license_detail", pk=license.pk)


@loans_setup_required
@require_POST
def operational_notice_retry(request, notice_pk):
    notice = get_object_or_404(
        LoanOperationalNotice,
        pk=notice_pk,
        workspace=request.loans_workspace,
    )
    try:
        result = dispatch_operational_notice(notice.pk)
    except (LoanOperationalNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, f"Operational alert delivery is {result.delivery.status.lower()}."
        )
    if notice.source_license_id:
        return redirect("loans:license_detail", pk=notice.source_license_id)
    return redirect(
        "loans:pawn_physical_verification_detail",
        pk=notice.source_verification_observation.session_id,
    )


@loans_setup_required
def license_create(request):
    form = LoanLicenseForm(request.POST or None, request.FILES or None)
    form.instance.workspace = request.loans_workspace
    if request.method == "POST" and form.is_valid():
        try:
            license = create_license(
                workspace=request.loans_workspace,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except LicenseSeriesError as exc:
            form.add_error("supporting_document", str(exc))
        else:
            messages.success(request, "Loan license and initial evidence created.")
            return redirect("loans:license_detail", pk=license.pk)
    return render(request, "loans/setup/license_form.html", {"form": form})


@loans_setup_required
def license_update(request, pk):
    license = _license_for_workspace(request, pk)
    form = LoanLicenseForm(
        request.POST or None,
        request.FILES or None,
        instance=license,
    )
    if request.method == "POST" and form.is_valid():
        try:
            update_license(
                license,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except LicenseSeriesError as exc:
            form.add_error("supporting_document", str(exc))
        else:
            messages.success(request, "License amendment evidence recorded.")
            return redirect("loans:license_detail", pk=license.pk)
    return render(
        request,
        "loans/setup/license_form.html",
        {"form": form, "license": license},
    )


@loans_setup_required
def license_renew(request, pk):
    license = _license_for_workspace(request, pk)
    form = LoanLicenseRenewalForm(
        request.POST or None,
        request.FILES or None,
        license=license,
    )
    if request.method == "POST" and form.is_valid():
        try:
            renew_license(
                license,
                actor=request.user,
                request=request,
                **form.cleaned_data,
            )
        except LicenseSeriesError as exc:
            form.add_error("supporting_document", str(exc))
        else:
            messages.success(request, "License renewal evidence recorded and activated.")
            return redirect("loans:license_detail", pk=license.pk)
    return render(
        request,
        "loans/setup/license_renewal_form.html",
        {"form": form, "license": license},
    )


@loans_setup_required
def license_revision_document(request, pk, revision_pk):
    license = _license_for_workspace(request, pk)
    revision = get_object_or_404(
        LoanLicenseRevision,
        pk=revision_pk,
        license=license,
    )
    if not revision.has_document:
        raise Http404("This license revision has no supporting document.")
    revision.supporting_document.open("rb")
    content = revision.supporting_document.read()
    revision.supporting_document.close()
    response = HttpResponse(content, content_type=revision.mime_type)
    response["Content-Disposition"] = content_disposition_header(
        True,
        revision.original_filename,
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


@loans_setup_required
@require_POST
def license_expire(request, pk):
    license = _license_for_workspace(request, pk)
    expire_license(license, actor=request.user)
    messages.success(request, "Loan license deactivated; existing loans remain linked.")
    return redirect("loans:license_detail", pk=license.pk)


@loans_setup_required
@require_POST
def license_activate(request, pk):
    license = _license_for_workspace(request, pk)
    try:
        activate_license(license, actor=request.user)
        messages.success(request, "Loan license activated.")
    except LicenseSeriesError as exc:
        messages.error(request, str(exc))
    return redirect("loans:license_detail", pk=license.pk)


@loans_setup_required
def series_create(request, license_pk):
    license = _license_for_workspace(request, license_pk)
    form = LoanSeriesSetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            series = create_series(
                license=license,
                name=form.cleaned_data["name"],
                code=form.cleaned_data["code"],
                is_active=form.cleaned_data["is_active"],
            )
            _configure_both_sequences(series, form.cleaned_data, request)
        messages.success(request, "Loan series and numbering sequences created.")
        return redirect("loans:license_detail", pk=license.pk)
    return render(
        request,
        "loans/setup/series_form.html",
        {"form": form, "license": license},
    )


@loans_setup_required
def series_update(request, pk):
    series = _series_for_workspace(request, pk)
    initial = _series_initial(series)
    form = LoanSeriesSetupForm(request.POST or None, instance=series, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            update_series(
                series,
                name=form.cleaned_data["name"],
                code=form.cleaned_data["code"],
            )
            set_series_active(series, is_active=form.cleaned_data["is_active"])
            _configure_both_sequences(series, form.cleaned_data, request)
        messages.success(request, "Loan series setup updated.")
        return redirect("loans:license_detail", pk=series.license_id)
    return render(
        request,
        "loans/setup/series_form.html",
        {"form": form, "license": series.license, "series": series},
    )


def _license_for_workspace(request, pk):
    return get_object_or_404(
        LoanLicense, pk=pk, workspace=request.loans_workspace
    )


def _series_for_workspace(request, pk):
    return get_object_or_404(
        LoanSeries.objects.select_related("license"),
        pk=pk,
        license__workspace=request.loans_workspace,
    )


def _safe_preview(series, kind):
    try:
        return {"value": preview_number(series=series, document_kind=kind).value}
    except NumberAllocationError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}


def _series_initial(series):
    sequences = {item.document_kind: item for item in series.number_sequences.all()}
    loan = sequences.get(LoanDocumentKind.PAWN_LOAN.value)
    release = sequences.get(LoanDocumentKind.PAWN_LOAN_RELEASE.value)
    baseline = loan or release
    return {
        "pawn_loan_prefix": loan.prefix if loan else "PL-",
        "release_prefix": release.prefix if release else "RL-",
        "number_width": baseline.width if baseline else 5,
        "maximum_number": baseline.maximum_number if baseline else 10000,
    }


def _configure_both_sequences(series, cleaned_data, request):
    common = {
        "series": series,
        "width": cleaned_data["number_width"],
        "maximum_number": cleaned_data["maximum_number"],
        "actor": request.user,
        "request": request,
    }
    configure_sequence(
        document_kind=LoanDocumentKind.PAWN_LOAN,
        prefix=cleaned_data["pawn_loan_prefix"],
        **common,
    )
    configure_sequence(
        document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE,
        prefix=cleaned_data["release_prefix"],
        **common,
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
            "accounting_events__outbox",
            "accounting_events__reversed_by_event",
            "accounting_events__repayment_allocation_lines__collateral_item",
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
            "accounting_event__outbox",
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
            "settlement_event__outbox",
            "opening_event__outbox",
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _draft_readiness(workspace):
    from apps.tenant_apps.party.models import Party

    if not Party.objects.filter(status=Party.PartyStatus.ACTIVE).exists():
        return {
            "ready": False,
            "message": "Create an active Party before starting a pawn-loan draft.",
            "action_label": "Create Party",
            "action_url": reverse("party:party_create"),
        }
    candidates = LoanSeries.objects.filter(
        license__workspace=workspace,
        license__is_active=True,
        is_active=True,
    ).select_related("license")
    for series in candidates:
        try:
            preview_number(series=series, document_kind=LoanDocumentKind.PAWN_LOAN)
            if series.license.is_expired():
                continue
            today = timezone.localdate()
            resolve_pawn_loan_economic_policy(
                workspace_id=workspace.pk,
                license_id=series.license_id,
                as_of_date=today,
            )
            for metal in ("GOLD", "SILVER"):
                resolve_pawn_metal_interest_rate_policy(
                    workspace_id=workspace.pk,
                    license_id=series.license_id,
                    metal=metal,
                    as_of_date=today,
                )
            return {"ready": True}
        except (NumberAllocationError, ValueError):
            continue
    return {
        "ready": False,
        "message": "Configure numbering and current PawnLoan economics before drafting.",
        "action_label": "Open Economic Setup",
        "action_url": reverse("loans:pawn_economics_setup"),
    }


def _collateral_inputs(formset):
    return tuple(
        CollateralDraftInput(
            collateral_item_id=row.get("collateral_item_id"),
            description=row["description"],
            metal=row["metal"],
            gross_weight=row["gross_weight"],
            net_weight=row["net_weight"],
            purity_percentage=row["purity_percentage"],
            latest_appraised_value=row.get("latest_appraised_value"),
            allocated_principal=row["allocated_principal"],
        )
        for row in formset.cleaned_data
        if row and not row.get("DELETE")
    )


def _add_pawn_draft_error(form, formset, exc):
    """Attach item-specific economic failures to the field an operator can fix."""

    if isinstance(exc, CollateralEconomicsError) and exc.reference and exc.field:
        try:
            item_form = formset.forms[int(exc.reference) - 1]
        except (IndexError, TypeError, ValueError):
            pass
        else:
            if exc.field in item_form.fields:
                item_form.add_error(exc.field, str(exc))
                return
    form.add_error(None, str(exc))


def _pawn_number_preview_rows(form):
    """Expose non-consuming official-number previews for selectable series."""

    return tuple(
        {
            "series": series,
            "preview": _safe_preview(series, LoanDocumentKind.PAWN_LOAN),
        }
        for series in form.fields["series"].queryset
    )


def _persist_formset_photos(loan, formset, *, actor, workflow_source):
    rows = [
        row
        for row in formset.cleaned_data
        if row and not row.get("DELETE")
    ]
    supplied_ids = {
        row["collateral_item_id"]
        for row in rows
        if row.get("collateral_item_id")
    }
    new_items = iter(
        loan.collateral_items.exclude(pk__in=supplied_ids).order_by("pk")
    )
    for row in rows:
        item = (
            loan.collateral_items.get(pk=row["collateral_item_id"])
            if row.get("collateral_item_id")
            else next(new_items)
        )
        upload = row.get("photograph")
        if upload:
            append_collateral_photo(
                item.pk,
                upload=upload,
                actor=actor,
                workflow_source=workflow_source,
            )


def _create_command(workspace_id, form, formset):
    data = form.cleaned_data
    return CreatePawnDraftCommand(
        workspace_id=workspace_id,
        borrower_id=data["borrower"].pk,
        license_id=data["license"].pk,
        series_id=data["series"].pk,
        principal_amount=Decimal("0.01"),
        monthly_interest_rate=Decimal("0"),
        loan_date=data["loan_date"],
        tenure_months=data["tenure_months"],
        collateral=_collateral_inputs(formset),
    )


def _update_command(form, formset):
    data = form.cleaned_data
    return UpdatePawnDraftCommand(
        borrower_id=data["borrower"].pk,
        principal_amount=Decimal("0.01"),
        monthly_interest_rate=Decimal("0"),
        loan_date=data["loan_date"],
        tenure_months=data["tenure_months"],
        collateral=_collateral_inputs(formset),
    )


def _reason_transition(request, pk, action):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnTransitionReasonForm(request.POST or None)
    labels = {"reopen": "Return to draft", "cancel": "Cancel loan"}
    if request.method == "POST" and form.is_valid():
        try:
            if action == "reopen":
                reopen_pawn_loan(
                    loan.pk, reason=form.cleaned_data["reason"], actor=request.user
                )
            else:
                cancel_pawn_loan(
                    loan.pk, reason=form.cleaned_data["reason"], actor=request.user
                )
        except (PawnLifecycleError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{loan.loan_number}: {labels[action].lower()} completed.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(
        request,
        "loans/pawn/transition_form.html",
        {"loan": loan, "form": form, "action_label": labels[action]},
    )


def _render_action(request, loan, form, title, description, extra_context=None):
    context = {
        "loan": loan,
        "form": form,
        "action_label": title,
        "description": description,
    }
    context.update(extra_context or {})
    return render(request, "loans/pawn/action_form.html", context)


def _safe_balance(loan):
    try:
        return get_pawn_loan_balance(loan.pk, as_of_date=timezone.localdate())
    except (ObjectDoesNotExist, ValidationError, ValueError):
        return None


def _safe_accrual_previews(loan, *, include_partial):
    try:
        return preview_pawn_loan_accruals(
            loan.pk,
            as_of_date=timezone.localdate(),
            include_partial=include_partial,
        )
    except (ObjectDoesNotExist, ValidationError, ValueError):
        return ()


def _accrual_preview_rows(loan, previews):
    item_by_id = {item.pk: item for item in loan.collateral_items.all()}
    return tuple(
        {
            "preview": preview,
            "lines": tuple(
                {
                    "line": line,
                    "item": item_by_id.get(line.collateral_item_id),
                }
                for line in preview.lines
            ),
        }
        for preview in previews
    )


def _full_release_quote(loan):
    try:
        return preview_pawn_loan_full_release(loan.pk)
    except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
        return {"error": str(exc), "minimum_settlement": None}


def _primary_action(loan, context):
    if loan.state == PawnLoanState.DRAFT.value:
        return {
            "label": "Approve loan",
            "url": reverse("loans:pawn_loan_approve", args=[loan.pk]),
            "method": "post",
            "message": "Review the frozen terms, then approve this draft.",
        }
    if loan.state == PawnLoanState.APPROVED.value:
        return {
            "label": "Disburse loan",
            "url": reverse("loans:pawn_loan_disburse", args=[loan.pk]),
            "message": "Record disbursal to activate the loan and queue DEA posting.",
        }
    if loan.state == PawnLoanState.ACTIVE.value:
        balance = context.get("balance")
        if balance and not balance.posting_ready:
            return {
                "label": "Resolve accounting delivery",
                "url": "#accounting-delivery",
                "message": "A pending or failed accounting event blocks dependent operations.",
            }
        return {
            "label": "Record repayment",
            "url": reverse("loans:pawn_loan_repay", args=[loan.pk]),
            "message": "Continue with repayment, accrual, or collateral release.",
        }
    if loan.state == PawnLoanState.CLOSED.value:
        return {
            "label": "Review accounting history",
            "url": "#accounting-delivery",
            "message": "This loan is closed. Administrators can reverse eligible events in order.",
        }
    return None


def _can_administer(request):
    user = request.user
    workspace = request.loans_workspace
    return bool(
        is_platform_admin(user)
        or workspace.owner_id == user.pk
        or get_workspace_role_name(user, workspace) in {"Owner", "Admin"}
    )


def _accounting_rows(loan, *, can_administer):
    events = tuple(
        loan.accounting_events.select_related(
            "outbox", "reversed_by_event", "loan__workspace"
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
        outbox = event.outbox
        try:
            reversed_event = event.reversed_by_event
        except PawnLoanAccountingEvent.DoesNotExist:
            reversed_event = None
        readiness = assess_pawn_loan_event_reversal(
            event, latest_event_id=latest_event_id
        )
        rows.append(
            {
                "event": event,
                "outbox": outbox,
                "can_retry": can_administer and outbox.status == LoanOutboxStatus.FAILED.value,
                "can_reverse": can_administer and readiness.can_reverse,
                "reversal_blocker": readiness.blocker,
                "reversed_event": reversed_event,
                "accounting_mode": readiness.accounting_mode,
            }
        )
    return rows
