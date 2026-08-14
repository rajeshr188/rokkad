from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_GET

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.orgs.tenant_context import resolve_request_workspace
from apps.tenant_apps.dea.forms_business_events import (
    FixedPurchasePreviewForm,
    FixedSalePreviewForm,
    KarigarMovementPreviewForm,
    MonetarySettlementPreviewForm,
    PurchaseRateFixingPreviewForm,
    SaleRateFixingPreviewForm,
    UnfixedPurchasePreviewForm,
    UnfixedSalePreviewForm,
)
from apps.tenant_apps.dea.models import (
    AccountTransaction,
    BusinessEventDraft,
    CommodityMovement,
    ExposureLine,
    JournalEntry,
    LedgerTransaction,
    PaymentVoucher,
    RateFixing,
    Voucher,
    VoucherStatus,
)
from apps.tenant_apps.dea.services.business_event_posting import (
    confirm_fixed_purchase_draft,
    confirm_fixed_sale_draft,
    confirm_karigar_movement_draft,
    confirm_monetary_settlement_draft,
    confirm_purchase_rate_fixing_draft,
    confirm_sale_rate_fixing_draft,
    confirm_unfixed_purchase_draft,
    confirm_unfixed_sale_draft,
)
from apps.tenant_apps.dea.services.business_event_preview import (
    build_fixed_sale_preview,
    build_fixed_sale_posting_readiness,
    build_fixed_purchase_preview,
    build_fixed_purchase_posting_readiness,
    build_karigar_movement_preview,
    build_karigar_movement_posting_readiness,
    build_monetary_settlement_preview,
    build_monetary_settlement_posting_readiness,
    build_unfixed_purchase_preview,
    build_unfixed_purchase_posting_readiness,
    build_unfixed_sale_preview,
    build_unfixed_sale_posting_readiness,
    build_purchase_rate_fixing_preview,
    build_purchase_rate_fixing_posting_readiness,
    build_sale_rate_fixing_preview,
    build_sale_rate_fixing_posting_readiness,
    save_fixed_purchase_preview_draft,
    save_fixed_sale_preview_draft,
    save_karigar_movement_preview_draft,
    save_monetary_settlement_preview_draft,
    save_purchase_rate_fixing_preview_draft,
    save_sale_rate_fixing_preview_draft,
    save_unfixed_purchase_preview_draft,
    save_unfixed_sale_preview_draft,
)
from apps.tenant_apps.dea.services.fixed_purchase import FIXED_PURCHASE_VOUCHER_TYPE
from apps.tenant_apps.dea.services.fixed_sale import FIXED_SALE_VOUCHER_TYPE
from apps.tenant_apps.dea.services.rate_fixing import (
    PURCHASE_RATE_FIXING_VOUCHER_TYPE,
    SALE_RATE_FIXING_VOUCHER_TYPE,
)
from apps.tenant_apps.dea.services.unfixed_purchase import UNFIXED_PURCHASE_VOUCHER_TYPE
from apps.tenant_apps.dea.services.unfixed_sale import UNFIXED_SALE_VOUCHER_TYPE


@login_required
@require_GET
def business_events_dashboard(request):
    event_groups = [
        {
            "title": "Purchases",
            "events": [
                _event(
                    "Fixed Purchase",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_fixed_purchase_preview"),
                    action_label="Open preview",
                ),
                _event(
                    "Unfixed Purchase",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_unfixed_purchase_preview"),
                    action_label="Open preview",
                ),
                _event(
                    "Purchase Rate Fixing",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_purchase_rate_fixing_preview"),
                    action_label="Open preview",
                    report_url=reverse("dea_exposure_report"),
                ),
            ],
        },
        {
            "title": "Sales",
            "events": [
                _event(
                    "Fixed Sale",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_fixed_sale_preview"),
                    action_label="Open preview",
                ),
                _event(
                    "Unfixed Sale",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_unfixed_sale_preview"),
                    action_label="Open preview",
                ),
                _event(
                    "Sale Rate Fixing",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_sale_rate_fixing_preview"),
                    action_label="Open preview",
                    report_url=reverse("dea_exposure_report"),
                ),
            ],
        },
        {
            "title": "Settlement",
            "events": [
                _event(
                    "Receipt From Customer",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_monetary_settlement_preview"),
                    action_label="Open preview",
                ),
                _event(
                    "Payment To Supplier",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_monetary_settlement_preview"),
                    action_label="Open preview",
                ),
            ],
        },
        {
            "title": "Karigar",
            "events": [
                _event(
                    "Issue Metal To Karigar",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_karigar_movement_preview"),
                    action_label="Open preview",
                    report_url=reverse("dea_metal_balance_report"),
                ),
                _event(
                    "Receive Metal From Karigar",
                    "Preview ready",
                    "Preview only",
                    action_url=reverse("dea_karigar_movement_preview"),
                    action_label="Open preview",
                    report_url=reverse("dea_metal_balance_report"),
                ),
            ],
        },
        {
            "title": "Reports",
            "events": [
                _event(
                    "Metal Balance",
                    "Report ready",
                    "Read-only",
                    report_url=reverse("dea_metal_balance_report"),
                ),
                _event(
                    "Commodity Exposure",
                    "Report ready",
                    "Read-only",
                    report_url=reverse("dea_exposure_report"),
                ),
                _event(
                    "Commodity Valuation",
                    "Report ready",
                    "Read-only",
                    report_url=reverse("dea_valuation_report"),
                ),
                _event(
                    "Financial Trial Balance",
                    "Report ready",
                    "Read-only",
                    report_url=reverse("trial_balance"),
                ),
            ],
        },
    ]
    return TemplateResponse(
        request,
        "dea/business_events/dashboard.html",
        {
            "title": "Business Events",
            "event_groups": event_groups,
            "fixed_purchase_drafts": _recent_fixed_purchase_drafts(),
            "unfixed_purchase_drafts": _recent_unfixed_purchase_drafts(),
            "purchase_rate_fixing_drafts": _recent_purchase_rate_fixing_drafts(),
            "sale_rate_fixing_drafts": _recent_sale_rate_fixing_drafts(),
            "monetary_settlement_drafts": _recent_monetary_settlement_drafts(),
            "karigar_movement_drafts": _recent_karigar_movement_drafts(),
            "fixed_sale_drafts": _recent_fixed_sale_drafts(),
            "unfixed_sale_drafts": _recent_unfixed_sale_drafts(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def fixed_purchase_preview(request):
    preview = None
    draft = None
    readiness = None
    confirm_disabled = False
    can_confirm_draft = False
    confirm_attempted = False
    if request.method == "POST":
        confirm_attempted = request.POST.get("action") == "confirm"
        form = FixedPurchasePreviewForm(request.POST)
        if not confirm_attempted and form.is_valid():
            preview = build_fixed_purchase_preview(form.cleaned_data)
            draft = save_fixed_purchase_preview_draft(
                form.cleaned_data,
                preview,
                actor=request.user,
            )
            readiness = build_fixed_purchase_posting_readiness(
                draft,
                actor=request.user,
            )
            can_confirm_draft = readiness["ready"] and _can_confirm_business_event(request)
    else:
        form = FixedPurchasePreviewForm()

    return TemplateResponse(
        request,
        "dea/business_events/fixed_purchase_preview.html",
        {
            "title": "Fixed Purchase Preview",
            "form": form,
            "preview": preview,
            "draft": draft,
            "readiness": readiness,
            "confirm_disabled": confirm_disabled,
            "can_confirm_draft": can_confirm_draft,
            "confirm_attempted": confirm_attempted,
        },
        status=400 if confirm_attempted else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def unfixed_purchase_preview(request):
    preview = None
    draft = None
    readiness = None
    confirm_disabled = False
    can_confirm_draft = False
    confirm_attempted = False
    if request.method == "POST":
        confirm_attempted = request.POST.get("action") == "confirm"
        form = UnfixedPurchasePreviewForm(request.POST)
        if not confirm_attempted and form.is_valid():
            preview = build_unfixed_purchase_preview(form.cleaned_data)
            draft = save_unfixed_purchase_preview_draft(
                form.cleaned_data,
                preview,
                actor=request.user,
            )
            readiness = build_unfixed_purchase_posting_readiness(
                draft,
                actor=request.user,
            )
            can_confirm_draft = readiness["ready"] and _can_confirm_business_event(request)
    else:
        form = UnfixedPurchasePreviewForm()

    return TemplateResponse(
        request,
        "dea/business_events/unfixed_purchase_preview.html",
        {
            "title": "Unfixed Purchase Preview",
            "form": form,
            "preview": preview,
            "draft": draft,
            "readiness": readiness,
            "confirm_disabled": confirm_disabled,
            "can_confirm_draft": can_confirm_draft,
            "confirm_attempted": confirm_attempted,
        },
        status=400 if confirm_attempted else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def purchase_rate_fixing_preview(request):
    preview = None
    draft = None
    readiness = None
    confirm_disabled = False
    can_confirm_draft = False
    confirm_attempted = False
    if request.method == "POST":
        confirm_attempted = request.POST.get("action") == "confirm"
        form = PurchaseRateFixingPreviewForm(request.POST)
        if not confirm_attempted and form.is_valid():
            preview = build_purchase_rate_fixing_preview(form.cleaned_data)
            draft = save_purchase_rate_fixing_preview_draft(
                form.cleaned_data,
                preview,
                actor=request.user,
            )
            readiness = build_purchase_rate_fixing_posting_readiness(
                draft,
                actor=request.user,
            )
            can_confirm_draft = readiness["ready"] and _can_confirm_business_event(request)
    else:
        form = PurchaseRateFixingPreviewForm()

    return TemplateResponse(
        request,
        "dea/business_events/purchase_rate_fixing_preview.html",
        {
            "title": "Purchase Rate Fixing Preview",
            "form": form,
            "preview": preview,
            "draft": draft,
            "readiness": readiness,
            "confirm_disabled": confirm_disabled,
            "can_confirm_draft": can_confirm_draft,
            "confirm_attempted": confirm_attempted,
        },
        status=400 if confirm_attempted else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def sale_rate_fixing_preview(request):
    preview = None
    draft = None
    readiness = None
    confirm_disabled = False
    can_confirm_draft = False
    confirm_attempted = False
    if request.method == "POST":
        confirm_attempted = request.POST.get("action") == "confirm"
        form = SaleRateFixingPreviewForm(request.POST)
        if not confirm_attempted and form.is_valid():
            preview = build_sale_rate_fixing_preview(form.cleaned_data)
            draft = save_sale_rate_fixing_preview_draft(
                form.cleaned_data,
                preview,
                actor=request.user,
            )
            readiness = build_sale_rate_fixing_posting_readiness(
                draft,
                actor=request.user,
            )
            can_confirm_draft = readiness["ready"] and _can_confirm_business_event(request)
    else:
        form = SaleRateFixingPreviewForm()

    return TemplateResponse(
        request,
        "dea/business_events/sale_rate_fixing_preview.html",
        {
            "title": "Sale Rate Fixing Preview",
            "form": form,
            "preview": preview,
            "draft": draft,
            "readiness": readiness,
            "confirm_disabled": confirm_disabled,
            "can_confirm_draft": can_confirm_draft,
            "confirm_attempted": confirm_attempted,
        },
        status=400 if confirm_attempted else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def monetary_settlement_preview(request):
    preview = None
    draft = None
    readiness = None
    confirm_disabled = False
    can_confirm_draft = False
    confirm_attempted = False
    if request.method == "POST":
        confirm_attempted = request.POST.get("action") == "confirm"
        form = MonetarySettlementPreviewForm(request.POST)
        if not confirm_attempted and form.is_valid():
            preview = build_monetary_settlement_preview(form.cleaned_data)
            draft = save_monetary_settlement_preview_draft(
                form.cleaned_data,
                preview,
                actor=request.user,
            )
            readiness = build_monetary_settlement_posting_readiness(
                draft,
                actor=request.user,
            )
            can_confirm_draft = readiness["ready"] and _can_confirm_business_event(request)
    else:
        form = MonetarySettlementPreviewForm()

    return TemplateResponse(
        request,
        "dea/business_events/monetary_settlement_preview.html",
        {
            "title": "Receipt / Payment Preview",
            "form": form,
            "preview": preview,
            "draft": draft,
            "readiness": readiness,
            "confirm_disabled": confirm_disabled,
            "can_confirm_draft": can_confirm_draft,
            "confirm_attempted": confirm_attempted,
        },
        status=400 if confirm_attempted else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def karigar_movement_preview(request):
    preview = None
    draft = None
    readiness = None
    confirm_disabled = False
    can_confirm_draft = False
    confirm_attempted = False
    if request.method == "POST":
        confirm_attempted = request.POST.get("action") == "confirm"
        form = KarigarMovementPreviewForm(request.POST)
        if not confirm_attempted and form.is_valid():
            preview = build_karigar_movement_preview(form.cleaned_data)
            draft = save_karigar_movement_preview_draft(
                form.cleaned_data,
                preview,
                actor=request.user,
            )
            readiness = build_karigar_movement_posting_readiness(
                draft,
                actor=request.user,
            )
            can_confirm_draft = readiness["ready"] and _can_confirm_business_event(request)
    else:
        form = KarigarMovementPreviewForm()

    return TemplateResponse(
        request,
        "dea/business_events/karigar_movement_preview.html",
        {
            "title": "Karigar Custody Preview",
            "form": form,
            "preview": preview,
            "draft": draft,
            "readiness": readiness,
            "confirm_disabled": confirm_disabled,
            "can_confirm_draft": can_confirm_draft,
            "confirm_attempted": confirm_attempted,
        },
        status=400 if confirm_attempted else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def fixed_sale_preview(request):
    preview = None
    draft = None
    readiness = None
    confirm_disabled = False
    can_confirm_draft = False
    confirm_attempted = False
    if request.method == "POST":
        confirm_attempted = request.POST.get("action") == "confirm"
        form = FixedSalePreviewForm(request.POST)
        if not confirm_attempted and form.is_valid():
            preview = build_fixed_sale_preview(form.cleaned_data)
            draft = save_fixed_sale_preview_draft(
                form.cleaned_data,
                preview,
                actor=request.user,
            )
            readiness = build_fixed_sale_posting_readiness(
                draft,
                actor=request.user,
            )
            can_confirm_draft = readiness["ready"] and _can_confirm_business_event(request)
    else:
        form = FixedSalePreviewForm()

    return TemplateResponse(
        request,
        "dea/business_events/fixed_sale_preview.html",
        {
            "title": "Fixed Sale Preview",
            "form": form,
            "preview": preview,
            "draft": draft,
            "readiness": readiness,
            "confirm_disabled": confirm_disabled,
            "can_confirm_draft": can_confirm_draft,
            "confirm_attempted": confirm_attempted,
        },
        status=400 if confirm_attempted else 200,
    )


@login_required
@require_http_methods(["GET", "POST"])
def unfixed_sale_preview(request):
    preview = None
    draft = None
    readiness = None
    confirm_disabled = False
    can_confirm_draft = False
    confirm_attempted = False
    if request.method == "POST":
        confirm_attempted = request.POST.get("action") == "confirm"
        form = UnfixedSalePreviewForm(request.POST)
        if not confirm_attempted and form.is_valid():
            preview = build_unfixed_sale_preview(form.cleaned_data)
            draft = save_unfixed_sale_preview_draft(
                form.cleaned_data,
                preview,
                actor=request.user,
            )
            readiness = build_unfixed_sale_posting_readiness(
                draft,
                actor=request.user,
            )
    else:
        form = UnfixedSalePreviewForm()

    return TemplateResponse(
        request,
        "dea/business_events/unfixed_sale_preview.html",
        {
            "title": "Unfixed Sale Preview",
            "form": form,
            "preview": preview,
            "draft": draft,
            "readiness": readiness,
            "confirm_disabled": confirm_disabled,
            "can_confirm_draft": can_confirm_draft,
            "confirm_attempted": confirm_attempted,
        },
        status=400 if confirm_attempted else 200,
    )


@login_required
@require_http_methods(["POST"])
def fixed_purchase_confirm(request, draft_id):
    if not _can_confirm_business_event(request):
        return HttpResponseForbidden(
            "Only workspace owner, admin, or accountant can post this event."
        )
    try:
        result = confirm_fixed_purchase_draft(draft_id, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_error_message(exc))
        return redirect("dea_fixed_purchase_detail", draft_id=draft_id)

    if result.created:
        messages.success(request, "Fixed purchase posted successfully.")
    else:
        messages.info(request, "Fixed purchase was already posted; showing existing result.")
    return redirect("dea_fixed_purchase_detail", draft_id=draft_id)


@login_required
@require_http_methods(["POST"])
def unfixed_purchase_confirm(request, draft_id):
    if not _can_confirm_business_event(request):
        return HttpResponseForbidden(
            "Only workspace owner, admin, or accountant can post this event."
        )
    try:
        result = confirm_unfixed_purchase_draft(draft_id, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_error_message(exc))
        return redirect("dea_unfixed_purchase_detail", draft_id=draft_id)

    if result.created:
        messages.success(request, "Unfixed purchase posted successfully.")
    else:
        messages.info(
            request,
            "Unfixed purchase was already posted; showing existing result.",
        )
    return redirect("dea_unfixed_purchase_detail", draft_id=draft_id)


@login_required
@require_http_methods(["POST"])
def purchase_rate_fixing_confirm(request, draft_id):
    if not _can_confirm_business_event(request):
        return HttpResponseForbidden(
            "Only workspace owner, admin, or accountant can post this event."
        )
    try:
        result = confirm_purchase_rate_fixing_draft(draft_id, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_error_message(exc))
        return redirect("dea_purchase_rate_fixing_detail", draft_id=draft_id)

    if result.created:
        messages.success(request, "Purchase rate fixing posted successfully.")
    else:
        messages.info(
            request,
            "Purchase rate fixing was already posted; showing existing result.",
        )
    return redirect("dea_purchase_rate_fixing_detail", draft_id=draft_id)


@login_required
@require_http_methods(["POST"])
def sale_rate_fixing_confirm(request, draft_id):
    if not _can_confirm_business_event(request):
        return HttpResponseForbidden(
            "Only workspace owner, admin, or accountant can post this event."
        )
    try:
        result = confirm_sale_rate_fixing_draft(draft_id, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_error_message(exc))
        return redirect("dea_sale_rate_fixing_detail", draft_id=draft_id)

    if result.created:
        messages.success(request, "Sale rate fixing posted successfully.")
    else:
        messages.info(
            request,
            "Sale rate fixing was already posted; showing existing result.",
        )
    return redirect("dea_sale_rate_fixing_detail", draft_id=draft_id)


@login_required
@require_http_methods(["POST"])
def fixed_sale_confirm(request, draft_id):
    if not _can_confirm_business_event(request):
        return HttpResponseForbidden(
            "Only workspace owner, admin, or accountant can post this event."
        )
    try:
        result = confirm_fixed_sale_draft(draft_id, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_error_message(exc))
        return redirect("dea_fixed_sale_detail", draft_id=draft_id)

    if result.created:
        messages.success(request, "Fixed sale posted successfully.")
    else:
        messages.info(request, "Fixed sale was already posted; showing existing result.")
    return redirect("dea_fixed_sale_detail", draft_id=draft_id)


@login_required
@require_http_methods(["POST"])
def unfixed_sale_confirm(request, draft_id):
    if not _can_confirm_business_event(request):
        return HttpResponseForbidden(
            "Only workspace owner, admin, or accountant can post this event."
        )
    try:
        result = confirm_unfixed_sale_draft(draft_id, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_error_message(exc))
        return redirect("dea_unfixed_sale_detail", draft_id=draft_id)

    if result.created:
        messages.success(request, "Unfixed sale posted successfully.")
    else:
        messages.info(request, "Unfixed sale was already posted; showing existing result.")
    return redirect("dea_unfixed_sale_detail", draft_id=draft_id)


@login_required
@require_http_methods(["POST"])
def monetary_settlement_confirm(request, draft_id):
    if not _can_confirm_business_event(request):
        return HttpResponseForbidden(
            "Only workspace owner, admin, or accountant can post this event."
        )
    try:
        result = confirm_monetary_settlement_draft(draft_id, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_error_message(exc))
        return redirect("dea_monetary_settlement_detail", draft_id=draft_id)

    if result.created:
        messages.success(request, "Receipt/payment posted successfully.")
    else:
        messages.info(
            request,
            "Receipt/payment was already posted; showing existing result.",
        )
    return redirect("dea_monetary_settlement_detail", draft_id=draft_id)


@login_required
@require_http_methods(["POST"])
def karigar_movement_confirm(request, draft_id):
    if not _can_confirm_business_event(request):
        return HttpResponseForbidden(
            "Only workspace owner, admin, or accountant can post this event."
        )
    try:
        result = confirm_karigar_movement_draft(draft_id, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_error_message(exc))
        return redirect("dea_karigar_movement_detail", draft_id=draft_id)

    if result.created:
        messages.success(request, "Karigar custody movement posted successfully.")
    else:
        messages.info(
            request,
            "Karigar custody movement was already posted; showing existing result.",
        )
    return redirect("dea_karigar_movement_detail", draft_id=draft_id)


@login_required
@require_GET
def fixed_purchase_detail(request, draft_id):
    draft = get_object_or_404(
        BusinessEventDraft,
        pk=draft_id,
        event_type=BusinessEventDraft.EventType.FIXED_PURCHASE,
    )
    context = _fixed_purchase_detail_context(draft, request=request)
    return TemplateResponse(
        request,
        "dea/business_events/fixed_purchase_detail.html",
        context,
    )


@login_required
@require_GET
def unfixed_purchase_detail(request, draft_id):
    draft = get_object_or_404(
        BusinessEventDraft,
        pk=draft_id,
        event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
    )
    return TemplateResponse(
        request,
        "dea/business_events/unfixed_purchase_detail.html",
        _unfixed_purchase_detail_context(draft, request=request),
    )


@login_required
@require_GET
def purchase_rate_fixing_detail(request, draft_id):
    draft = get_object_or_404(
        BusinessEventDraft,
        pk=draft_id,
        event_type=BusinessEventDraft.EventType.PURCHASE_RATE_FIXING,
    )
    return TemplateResponse(
        request,
        "dea/business_events/purchase_rate_fixing_detail.html",
        _purchase_rate_fixing_detail_context(draft, request=request),
    )


@login_required
@require_GET
def sale_rate_fixing_detail(request, draft_id):
    draft = get_object_or_404(
        BusinessEventDraft,
        pk=draft_id,
        event_type=BusinessEventDraft.EventType.SALE_RATE_FIXING,
    )
    return TemplateResponse(
        request,
        "dea/business_events/sale_rate_fixing_detail.html",
        _sale_rate_fixing_detail_context(draft, request=request),
    )


@login_required
@require_GET
def monetary_settlement_detail(request, draft_id):
    draft = get_object_or_404(
        BusinessEventDraft,
        pk=draft_id,
        event_type__in=[
            BusinessEventDraft.EventType.CUSTOMER_RECEIPT,
            BusinessEventDraft.EventType.SUPPLIER_PAYMENT,
        ],
    )
    return TemplateResponse(
        request,
        "dea/business_events/monetary_settlement_detail.html",
        _monetary_settlement_detail_context(draft, request=request),
    )


@login_required
@require_GET
def karigar_movement_detail(request, draft_id):
    draft = get_object_or_404(
        BusinessEventDraft,
        pk=draft_id,
        event_type__in=[
            BusinessEventDraft.EventType.KARIGAR_ISSUE,
            BusinessEventDraft.EventType.KARIGAR_RECEIPT,
        ],
    )
    return TemplateResponse(
        request,
        "dea/business_events/karigar_movement_detail.html",
        _karigar_movement_detail_context(draft, request=request),
    )


@login_required
@require_GET
def fixed_sale_detail(request, draft_id):
    draft = get_object_or_404(
        BusinessEventDraft,
        pk=draft_id,
        event_type=BusinessEventDraft.EventType.FIXED_SALE,
    )
    return TemplateResponse(
        request,
        "dea/business_events/fixed_sale_detail.html",
        _fixed_sale_detail_context(draft, request=request),
    )


@login_required
@require_GET
def unfixed_sale_detail(request, draft_id):
    draft = get_object_or_404(
        BusinessEventDraft,
        pk=draft_id,
        event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
    )
    return TemplateResponse(
        request,
        "dea/business_events/unfixed_sale_detail.html",
        _unfixed_sale_detail_context(draft, request=request),
    )


def _event(name, backend_status, ui_status, *, report_url="", action_url="", action_label=""):
    return {
        "name": name,
        "backend_status": backend_status,
        "ui_status": ui_status,
        "report_url": report_url,
        "action_url": action_url,
        "action_label": action_label,
    }


def _recent_fixed_purchase_drafts(limit=8):
    drafts = (
        BusinessEventDraft.objects.filter(
            event_type=BusinessEventDraft.EventType.FIXED_PURCHASE,
        )
        .order_by("-updated_at", "-id")[:limit]
    )
    rows = []
    for draft in drafts:
        business_facts = (draft.preview_payload or {}).get("business_facts", {})
        voucher = _posted_fixed_purchase_voucher(draft)
        rows.append(
            {
                "draft": draft,
                "reference": draft.source_reference,
                "event_date": draft.event_date,
                "draft_status": draft.get_status_display(),
                "posting_status": "Posted" if voucher else "Not posted",
                "is_posted": voucher is not None,
                "amount": business_facts.get("money_amount", ""),
                "currency": business_facts.get("currency", ""),
                "fine_weight": business_facts.get("fine_weight", ""),
                "commodity": business_facts.get("commodity", ""),
            }
        )
    return rows


def _recent_unfixed_purchase_drafts(limit=8):
    drafts = (
        BusinessEventDraft.objects.filter(
            event_type=BusinessEventDraft.EventType.UNFIXED_PURCHASE,
        )
        .order_by("-updated_at", "-id")[:limit]
    )
    rows = []
    for draft in drafts:
        business_facts = (draft.preview_payload or {}).get("business_facts", {})
        voucher = _posted_unfixed_purchase_voucher(draft)
        rows.append(
            {
                "draft": draft,
                "reference": draft.source_reference,
                "event_date": draft.event_date,
                "draft_status": draft.get_status_display(),
                "posting_status": "Posted" if voucher else "Not posted",
                "is_posted": voucher is not None,
                "party": business_facts.get("party", ""),
                "fine_weight": business_facts.get("fine_weight", ""),
                "commodity": business_facts.get("commodity", ""),
            }
        )
    return rows


def _recent_purchase_rate_fixing_drafts(limit=8):
    drafts = (
        BusinessEventDraft.objects.filter(
            event_type=BusinessEventDraft.EventType.PURCHASE_RATE_FIXING,
        )
        .order_by("-updated_at", "-id")[:limit]
    )
    rows = []
    for draft in drafts:
        business_facts = (draft.preview_payload or {}).get("business_facts", {})
        rate_fixing = _posted_purchase_rate_fixing(draft)
        rows.append(
            {
                "draft": draft,
                "reference": draft.source_reference,
                "event_date": draft.event_date,
                "draft_status": draft.get_status_display(),
                "posting_status": "Posted" if rate_fixing else "Not posted",
                "is_posted": rate_fixing is not None,
                "party": business_facts.get("party", ""),
                "amount": business_facts.get("amount", ""),
                "currency": business_facts.get("currency", ""),
                "fine_weight": business_facts.get("fine_weight", ""),
                "commodity": business_facts.get("commodity", ""),
            }
        )
    return rows


def _recent_sale_rate_fixing_drafts(limit=8):
    drafts = (
        BusinessEventDraft.objects.filter(
            event_type=BusinessEventDraft.EventType.SALE_RATE_FIXING,
        )
        .order_by("-updated_at", "-id")[:limit]
    )
    rows = []
    for draft in drafts:
        business_facts = (draft.preview_payload or {}).get("business_facts", {})
        rate_fixing = _posted_sale_rate_fixing(draft)
        rows.append(
            {
                "draft": draft,
                "reference": draft.source_reference,
                "event_date": draft.event_date,
                "draft_status": draft.get_status_display(),
                "posting_status": "Posted" if rate_fixing else "Not posted",
                "is_posted": rate_fixing is not None,
                "party": business_facts.get("party", ""),
                "amount": business_facts.get("amount", ""),
                "currency": business_facts.get("currency", ""),
                "fine_weight": business_facts.get("fine_weight", ""),
                "commodity": business_facts.get("commodity", ""),
            }
        )
    return rows


def _recent_monetary_settlement_drafts(limit=8):
    drafts = (
        BusinessEventDraft.objects.filter(
            event_type__in=[
                BusinessEventDraft.EventType.CUSTOMER_RECEIPT,
                BusinessEventDraft.EventType.SUPPLIER_PAYMENT,
            ],
        )
        .order_by("-updated_at", "-id")[:limit]
    )
    rows = []
    for draft in drafts:
        business_facts = (draft.preview_payload or {}).get("business_facts", {})
        payment = _existing_monetary_settlement_payment(draft)
        rows.append(
            {
                "draft": draft,
                "reference": draft.source_reference,
                "event_date": draft.event_date,
                "event_type": draft.get_event_type_display(),
                "draft_status": draft.get_status_display(),
                "posting_status": "Posted" if payment and payment.posted else "Not posted",
                "is_posted": bool(payment and payment.posted),
                "settlement_label": business_facts.get("settlement_label", ""),
                "party_account": business_facts.get("party_account", ""),
                "amount": business_facts.get("money_amount", ""),
                "currency": business_facts.get("currency", ""),
                "payment_method": business_facts.get("payment_method", ""),
            }
        )
    return rows


def _recent_karigar_movement_drafts(limit=8):
    drafts = (
        BusinessEventDraft.objects.filter(
            event_type__in=[
                BusinessEventDraft.EventType.KARIGAR_ISSUE,
                BusinessEventDraft.EventType.KARIGAR_RECEIPT,
            ],
        )
        .order_by("-updated_at", "-id")[:limit]
    )
    rows = []
    for draft in drafts:
        business_facts = (draft.preview_payload or {}).get("business_facts", {})
        voucher = _posted_karigar_voucher(draft)
        rows.append(
            {
                "draft": draft,
                "reference": draft.source_reference,
                "event_date": draft.event_date,
                "event_type": draft.get_event_type_display(),
                "draft_status": draft.get_status_display(),
                "posting_status": "Posted" if voucher else "Not posted",
                "is_posted": voucher is not None,
                "movement_label": business_facts.get("movement_label", ""),
                "karigar": business_facts.get("karigar", ""),
                "fine_weight": business_facts.get("fine_weight", ""),
                "commodity": business_facts.get("commodity", ""),
            }
        )
    return rows


def _recent_fixed_sale_drafts(limit=8):
    drafts = (
        BusinessEventDraft.objects.filter(
            event_type=BusinessEventDraft.EventType.FIXED_SALE,
        )
        .order_by("-updated_at", "-id")[:limit]
    )
    rows = []
    for draft in drafts:
        business_facts = (draft.preview_payload or {}).get("business_facts", {})
        voucher = _posted_fixed_sale_voucher(draft)
        rows.append(
            {
                "draft": draft,
                "reference": draft.source_reference,
                "event_date": draft.event_date,
                "draft_status": draft.get_status_display(),
                "posting_status": "Posted" if voucher else "Not posted",
                "is_posted": voucher is not None,
                "amount": business_facts.get("money_amount", ""),
                "currency": business_facts.get("currency", ""),
                "fine_weight": business_facts.get("fine_weight", ""),
                "commodity": business_facts.get("commodity", ""),
            }
        )
    return rows


def _recent_unfixed_sale_drafts(limit=8):
    drafts = (
        BusinessEventDraft.objects.filter(
            event_type=BusinessEventDraft.EventType.UNFIXED_SALE,
        )
        .order_by("-updated_at", "-id")[:limit]
    )
    rows = []
    for draft in drafts:
        business_facts = (draft.preview_payload or {}).get("business_facts", {})
        voucher = _posted_unfixed_sale_voucher(draft)
        rows.append(
            {
                "draft": draft,
                "reference": draft.source_reference,
                "event_date": draft.event_date,
                "draft_status": draft.get_status_display(),
                "posting_status": "Posted" if voucher else "Not posted",
                "is_posted": voucher is not None,
                "party": business_facts.get("party", ""),
                "fine_weight": business_facts.get("fine_weight", ""),
                "commodity": business_facts.get("commodity", ""),
            }
        )
    return rows


def _fixed_purchase_detail_context(draft: BusinessEventDraft, *, request):
    actor = getattr(request, "user", None)
    voucher = _posted_fixed_purchase_voucher(draft)
    journal_entry = None
    ledger_transactions = []
    account_transactions = []
    commodity_movements = []
    if voucher:
        journal_entry = (
            JournalEntry.objects.filter(voucher=voucher).order_by("-id").first()
        )
        if journal_entry:
            ledger_transactions = list(
                LedgerTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("ledgerno", "ledgerno_dr")
                .order_by("id")
            )
            account_transactions = list(
                AccountTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("Account", "ledgerno", "XactTypeCode")
                .order_by("id")
            )
        commodity_movements = list(
            CommodityMovement.objects.filter(voucher=voucher)
            .select_related("commodity", "from_account", "to_account")
            .order_by("id")
        )

    return {
        "title": "Fixed Purchase Result",
        "draft": draft,
        "preview": draft.preview_payload or {},
        "readiness": build_fixed_purchase_posting_readiness(draft, actor=actor),
        "voucher": voucher,
        "journal_entry": journal_entry,
        "ledger_transactions": ledger_transactions,
        "account_transactions": account_transactions,
        "commodity_movements": commodity_movements,
        "can_confirm": _can_confirm_business_event(request),
    }


def _unfixed_purchase_detail_context(draft: BusinessEventDraft, *, request):
    actor = getattr(request, "user", None)
    voucher = _posted_unfixed_purchase_voucher(draft)
    commodity_movements = []
    exposures = []
    if voucher:
        commodity_movements = list(
            CommodityMovement.objects.filter(voucher=voucher)
            .select_related("commodity", "from_account", "to_account")
            .order_by("id")
        )
        exposures = list(
            ExposureLine.objects.filter(voucher=voucher)
            .select_related("commodity", "party")
            .order_by("id")
        )

    return {
        "title": "Unfixed Purchase Result",
        "draft": draft,
        "preview": draft.preview_payload or {},
        "readiness": build_unfixed_purchase_posting_readiness(
            draft,
            actor=actor,
        ),
        "voucher": voucher,
        "commodity_movements": commodity_movements,
        "exposures": exposures,
        "can_confirm": _can_confirm_business_event(request),
    }


def _purchase_rate_fixing_detail_context(draft: BusinessEventDraft, *, request):
    actor = getattr(request, "user", None)
    rate_fixing = _posted_purchase_rate_fixing(draft)
    voucher = rate_fixing.voucher if rate_fixing else None
    journal_entry = None
    ledger_transactions = []
    account_transactions = []
    allocations = []
    if voucher:
        journal_entry = (
            JournalEntry.objects.filter(voucher=voucher).order_by("-id").first()
        )
        if journal_entry:
            ledger_transactions = list(
                LedgerTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("ledgerno", "ledgerno_dr")
                .order_by("id")
            )
            account_transactions = list(
                AccountTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("Account", "ledgerno", "XactTypeCode")
                .order_by("id")
            )
        allocations = list(
            rate_fixing.allocations.select_related("exposure", "exposure__commodity")
            .order_by("id")
        )

    return {
        "title": "Purchase Rate Fixing Result",
        "draft": draft,
        "preview": draft.preview_payload or {},
        "readiness": build_purchase_rate_fixing_posting_readiness(
            draft,
            actor=actor,
        ),
        "rate_fixing": rate_fixing,
        "voucher": voucher,
        "journal_entry": journal_entry,
        "ledger_transactions": ledger_transactions,
        "account_transactions": account_transactions,
        "allocations": allocations,
        "can_confirm": _can_confirm_business_event(request),
    }


def _sale_rate_fixing_detail_context(draft: BusinessEventDraft, *, request):
    actor = getattr(request, "user", None)
    rate_fixing = _posted_sale_rate_fixing(draft)
    voucher = rate_fixing.voucher if rate_fixing else None
    journal_entry = None
    ledger_transactions = []
    account_transactions = []
    allocations = []
    if voucher:
        journal_entry = (
            JournalEntry.objects.filter(voucher=voucher).order_by("-id").first()
        )
        if journal_entry:
            ledger_transactions = list(
                LedgerTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("ledgerno", "ledgerno_dr")
                .order_by("id")
            )
            account_transactions = list(
                AccountTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("Account", "ledgerno", "XactTypeCode")
                .order_by("id")
            )
        allocations = list(
            rate_fixing.allocations.select_related("exposure", "exposure__commodity")
            .order_by("id")
        )

    return {
        "title": "Sale Rate Fixing Result",
        "draft": draft,
        "preview": draft.preview_payload or {},
        "readiness": build_sale_rate_fixing_posting_readiness(
            draft,
            actor=actor,
        ),
        "rate_fixing": rate_fixing,
        "voucher": voucher,
        "journal_entry": journal_entry,
        "ledger_transactions": ledger_transactions,
        "account_transactions": account_transactions,
        "allocations": allocations,
        "can_confirm": _can_confirm_business_event(request),
    }


def _fixed_sale_detail_context(draft: BusinessEventDraft, *, request):
    actor = getattr(request, "user", None)
    voucher = _posted_fixed_sale_voucher(draft)
    journal_entry = None
    ledger_transactions = []
    account_transactions = []
    commodity_movements = []
    if voucher:
        journal_entry = (
            JournalEntry.objects.filter(voucher=voucher).order_by("-id").first()
        )
        if journal_entry:
            ledger_transactions = list(
                LedgerTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("ledgerno", "ledgerno_dr")
                .order_by("id")
            )
            account_transactions = list(
                AccountTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("Account", "ledgerno", "XactTypeCode")
                .order_by("id")
            )
        commodity_movements = list(
            CommodityMovement.objects.filter(voucher=voucher)
            .select_related("commodity", "from_account", "to_account")
            .order_by("id")
        )

    return {
        "title": "Fixed Sale Result",
        "draft": draft,
        "preview": draft.preview_payload or {},
        "readiness": build_fixed_sale_posting_readiness(draft, actor=actor),
        "voucher": voucher,
        "journal_entry": journal_entry,
        "ledger_transactions": ledger_transactions,
        "account_transactions": account_transactions,
        "commodity_movements": commodity_movements,
        "can_confirm": _can_confirm_business_event(request),
    }


def _unfixed_sale_detail_context(draft: BusinessEventDraft, *, request):
    actor = getattr(request, "user", None)
    voucher = _posted_unfixed_sale_voucher(draft)
    commodity_movements = []
    exposures = []
    if voucher:
        commodity_movements = list(
            CommodityMovement.objects.filter(voucher=voucher)
            .select_related("commodity", "from_account", "to_account")
            .order_by("id")
        )
        exposures = list(
            ExposureLine.objects.filter(voucher=voucher)
            .select_related("commodity", "party")
            .order_by("id")
        )

    return {
        "title": "Unfixed Sale Result",
        "draft": draft,
        "preview": draft.preview_payload or {},
        "readiness": build_unfixed_sale_posting_readiness(
            draft,
            actor=actor,
        ),
        "voucher": voucher,
        "commodity_movements": commodity_movements,
        "exposures": exposures,
        "can_confirm": _can_confirm_business_event(request),
    }


def _monetary_settlement_detail_context(draft: BusinessEventDraft, *, request):
    actor = getattr(request, "user", None)
    payment = _existing_monetary_settlement_payment(draft)
    voucher = _posted_monetary_settlement_voucher(payment) if payment else None
    journal_entry = None
    ledger_transactions = []
    account_transactions = []
    if voucher:
        journal_entry = (
            JournalEntry.objects.filter(voucher=voucher).order_by("-id").first()
        )
        if journal_entry:
            ledger_transactions = list(
                LedgerTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("ledgerno", "ledgerno_dr")
                .order_by("id")
            )
            account_transactions = list(
                AccountTransaction.objects.filter(journal_entry=journal_entry)
                .select_related("Account", "ledgerno", "XactTypeCode")
                .order_by("id")
            )

    return {
        "title": "Receipt / Payment Result",
        "draft": draft,
        "preview": draft.preview_payload or {},
        "readiness": build_monetary_settlement_posting_readiness(
            draft,
            actor=actor,
        ),
        "payment": payment,
        "voucher": voucher,
        "journal_entry": journal_entry,
        "ledger_transactions": ledger_transactions,
        "account_transactions": account_transactions,
        "can_confirm": _can_confirm_business_event(request),
    }


def _karigar_movement_detail_context(draft: BusinessEventDraft, *, request):
    actor = getattr(request, "user", None)
    voucher = _posted_karigar_voucher(draft)
    commodity_movements = []
    if voucher:
        commodity_movements = list(
            CommodityMovement.objects.filter(voucher=voucher)
            .select_related("commodity", "from_account", "to_account")
            .order_by("id")
        )

    return {
        "title": "Karigar Custody Result",
        "draft": draft,
        "preview": draft.preview_payload or {},
        "readiness": build_karigar_movement_posting_readiness(
            draft,
            actor=actor,
        ),
        "voucher": voucher,
        "commodity_movements": commodity_movements,
        "can_confirm": _can_confirm_business_event(request),
    }


def _posted_fixed_purchase_voucher(draft: BusinessEventDraft):
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return None
    return (
        Voucher.objects.filter(
            doc_content_type=content_type,
            doc_object_id=draft.pk,
            voucher_type__name=FIXED_PURCHASE_VOUCHER_TYPE,
            status=VoucherStatus.POSTED,
        )
        .select_related("voucher_type")
        .order_by("-id")
        .first()
    )


def _posted_unfixed_purchase_voucher(draft: BusinessEventDraft):
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return None
    return (
        Voucher.objects.filter(
            doc_content_type=content_type,
            doc_object_id=draft.pk,
            voucher_type__name=UNFIXED_PURCHASE_VOUCHER_TYPE,
            status=VoucherStatus.POSTED,
        )
        .select_related("voucher_type")
        .order_by("-id")
        .first()
    )


def _posted_fixed_sale_voucher(draft: BusinessEventDraft):
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return None
    return (
        Voucher.objects.filter(
            doc_content_type=content_type,
            doc_object_id=draft.pk,
            voucher_type__name=FIXED_SALE_VOUCHER_TYPE,
            status=VoucherStatus.POSTED,
        )
        .select_related("voucher_type")
        .order_by("-id")
        .first()
    )


def _posted_unfixed_sale_voucher(draft: BusinessEventDraft):
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return None
    return (
        Voucher.objects.filter(
            doc_content_type=content_type,
            doc_object_id=draft.pk,
            voucher_type__name=UNFIXED_SALE_VOUCHER_TYPE,
            status=VoucherStatus.POSTED,
        )
        .select_related("voucher_type")
        .order_by("-id")
        .first()
    )


def _posted_purchase_rate_fixing(draft: BusinessEventDraft):
    payload = draft.normalized_payload or {}
    if not payload:
        return None
    return (
        RateFixing.objects.filter(
            allocations__exposure_id=payload.get("exposure"),
            fixing_date=draft.event_date,
            fine_weight=payload.get("fine_weight"),
            rate=payload.get("rate"),
            currency=payload.get("currency", ""),
            side=ExposureLine.Side.PURCHASE,
            status=RateFixing.Status.POSTED,
            voucher__voucher_type__name=PURCHASE_RATE_FIXING_VOUCHER_TYPE,
            voucher__status=VoucherStatus.POSTED,
        )
        .select_related("voucher", "commodity", "party")
        .order_by("-id")
        .first()
    )


def _posted_sale_rate_fixing(draft: BusinessEventDraft):
    payload = draft.normalized_payload or {}
    if not payload:
        return None
    return (
        RateFixing.objects.filter(
            allocations__exposure_id=payload.get("exposure"),
            fixing_date=draft.event_date,
            fine_weight=payload.get("fine_weight"),
            rate=payload.get("rate"),
            currency=payload.get("currency", ""),
            side=ExposureLine.Side.SALE,
            status=RateFixing.Status.POSTED,
            voucher__voucher_type__name=SALE_RATE_FIXING_VOUCHER_TYPE,
            voucher__status=VoucherStatus.POSTED,
        )
        .select_related("voucher", "commodity", "party")
        .order_by("-id")
        .first()
    )


def _existing_monetary_settlement_payment(draft: BusinessEventDraft):
    payload = draft.normalized_payload or {}
    reference_number = (payload.get("reference_number") or "").strip()
    if not reference_number:
        return None
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return None
    return (
        PaymentVoucher.objects.filter(
            source_content_type=content_type,
            source_object_id=draft.pk,
            reference_number=reference_number,
        )
        .order_by("-id")
        .first()
    )


def _posted_monetary_settlement_voucher(payment: PaymentVoucher | None):
    if payment is None:
        return None
    content_type = ContentType.objects.filter(
        app_label=payment._meta.app_label,
        model=payment._meta.model_name,
    ).first()
    if content_type is None:
        return None
    return (
        Voucher.objects.filter(
            doc_content_type=content_type,
            doc_object_id=payment.pk,
            status=VoucherStatus.POSTED,
        )
        .select_related("voucher_type")
        .order_by("-id")
        .first()
    )


def _posted_karigar_voucher(draft: BusinessEventDraft):
    content_type = ContentType.objects.filter(
        app_label=draft._meta.app_label,
        model=draft._meta.model_name,
    ).first()
    if content_type is None:
        return None
    voucher_type_name = (
        "COMMODITY_KARIGAR_ISSUE"
        if draft.event_type == BusinessEventDraft.EventType.KARIGAR_ISSUE
        else "COMMODITY_KARIGAR_RECEIPT"
    )
    return (
        Voucher.objects.filter(
            doc_content_type=content_type,
            doc_object_id=draft.pk,
            voucher_type__name=voucher_type_name,
            status=VoucherStatus.POSTED,
        )
        .select_related("voucher_type")
        .order_by("-id")
        .first()
    )


def _can_confirm_business_event(request):
    workspace = resolve_request_workspace(request)
    return _can_confirm_business_event_from_user_context(
        getattr(request, "user", None),
        workspace=workspace,
    )


def _can_confirm_business_event_from_user_context(user, *, workspace=None):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if is_platform_admin(user) or getattr(user, "is_staff", False):
        return True
    if workspace is None:
        return False
    if getattr(workspace, "owner", None) == user:
        return True
    role_name = get_workspace_role_name(user, workspace)
    return role_name in {"Owner", "Admin", "Accountant"}


def _validation_error_message(exc: ValidationError):
    if hasattr(exc, "message_dict"):
        parts = []
        for field, errors in exc.message_dict.items():
            joined = "; ".join(str(error) for error in errors)
            parts.append(f"{field}: {joined}")
        return " ".join(parts)
    return "; ".join(str(error) for error in exc.messages)
