"""Standalone PawnLoan custody mutation endpoints."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import LOANS_OWNER_ACTION, loans_owner_required
from apps.tenant_apps.loans.forms import (
    PawnPhysicalVerificationResolutionForm, PawnStorageLocationForm,
    PawnStorageTransferForm,
)
from apps.tenant_apps.loans.models import (
    PawnCollateralItem, PawnLoan, PawnPhysicalVerificationObservation,
)
from apps.tenant_apps.loans.services import (
    LoanOperationalNoticeError, PawnPhysicalVerificationError, PawnStorageError,
    complete_physical_verification, create_storage_location,
    create_verification_discrepancy_notice, place_or_transfer_collateral,
    resolve_physical_verification_discrepancy,
)

_PENDING_STORAGE_ITEM_SESSION_KEY = "loans_pending_storage_item"


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items", "collateral_items__photos"
        ), pk=pk, workspace=request.loans_workspace,
    )


def _can_manage_storage(request):
    return request.loans_workspace_access.can(LOANS_OWNER_ACTION)

@loans_owner_required
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

@loans_owner_required
def pawn_collateral_storage_transfer(request, pk, item_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    item = get_object_or_404(PawnCollateralItem, pk=item_pk, loan=loan)
    initial = {}
    if request.method == "GET" and request.GET.get("destination"):
        initial["destination"] = request.GET["destination"]
    if (
        request.method == "GET"
        and _can_manage_storage(request)
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

@loans_owner_required
@require_POST
def pawn_physical_verification_complete(request, pk):
    try:
        complete_physical_verification(pk, actor=request.user)
    except (PawnPhysicalVerificationError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Physical-verification session completed and frozen.")
    return redirect("loans:pawn_physical_verification_detail", pk=pk)


@loans_owner_required
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


@loans_owner_required
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
