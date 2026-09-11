"""Pawn custody views; existing services own business rules."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.cache import never_cache
from django.urls import reverse
from django.utils.http import content_disposition_header

from apps.tenant_apps.loans.access import (
    assert_loans_owner_access,
    loans_owner_required,
    loans_workspace_required,
)
from apps.tenant_apps.loans.filters import (
    PawnPhysicalVerificationSessionFilter,
    PawnStorageLocationFilter,
)
from apps.tenant_apps.loans.web.custody_forms import (
    PawnPhysicalVerificationObservationForm,
    PawnPhysicalVerificationStartForm,
)
from apps.tenant_apps.loans.models import (
    PawnCollateralItem,
    PawnCollateralPhoto,
    PawnPhysicalVerificationObservation,
    PawnPhysicalVerificationSession,
    PawnStorageLocation,
)
from apps.tenant_apps.loans.selectors import get_physical_verification_detail
from apps.tenant_apps.loans.services import (
    PawnCollateralMediaError,
    PawnPhysicalVerificationError,
    record_physical_verification_observation,
    render_collateral_label,
    render_storage_location_label,
    start_physical_verification,
)
from apps.tenant_apps.loans.web.pawn_read_helpers import (
    _can_manage_storage,
    _pawn_loan_for_workspace,
)


_PENDING_STORAGE_ITEM_SESSION_KEY = "loans_pending_storage_item"


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
