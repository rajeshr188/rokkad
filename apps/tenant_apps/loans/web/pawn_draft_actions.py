"""Ordinary Django adapters for PawnLoan draft origination."""

from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_workspace_required, loans_action_required
from apps.tenant_apps.loans.domain import CollateralEconomicsError, LoanDocumentKind, PawnLoanState
from apps.tenant_apps.loans.forms import (
    PawnCollateralDraftFormSet, PawnCollateralPhotoForm, PawnDraftForm,
    PawnDraftSplitForm, PawnTransitionReasonForm,
)
from apps.tenant_apps.loans.models import PawnCollateralItem, PawnLoan
from apps.tenant_apps.loans.services import (
    CollateralDraftInput, CreatePawnDraftCommand, DraftCollateralPhotoInput,
    NumberAllocationError, PawnCollateralMediaError, PawnDraftError,
    PawnLifecycleError, UpdatePawnDraftCommand, append_collateral_photo,
    approve_pawn_loan, cancel_pawn_loan, create_pawn_draft_with_photos,
    preview_number, reopen_pawn_loan, resolve_pawn_draft_economics,
    update_pawn_draft_with_photos,
)
from apps.tenant_apps.loans.services.pawn_draft_split import (
    PawnDraftSplitError, preview_pawn_draft_split, split_pawn_draft,
)


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items", "collateral_items__photos"
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


@loans_action_required("data.create")
def pawn_loan_create(request):
    readiness = get_pawn_draft_readiness(request.loans_workspace)
    if not readiness["ready"]:
        return render(request, "loans/pawn/blocked.html", {
            "readiness": readiness,
            "can_manage_loan_setup": request.loans_workspace_access.can("workspace.settings.manage"),
        })
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
                loan = create_pawn_draft_with_photos(
                    command,
                    photos=_draft_photo_inputs(formset),
                    actor=request.user,
                )
        except (PawnDraftError, ValidationError, ValueError) as exc:
            _add_pawn_draft_error(form, formset, exc)
        else:
            if loan is not None:
                messages.success(request, f"Draft {loan.loan_number} created.")
                return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
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


@loans_action_required("data.edit")
def pawn_loan_update(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    if loan.state != PawnLoanState.DRAFT.value:
        messages.error(request, "Only draft PawnLoans can be edited.")
        return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    form = PawnDraftForm(request.POST or None, workspace=request.loans_workspace, instance=loan)
    existing_items = tuple(loan.collateral_items.all())
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
        for item in existing_items
    ]
    formset = PawnCollateralDraftFormSet(
        request.POST or None,
        request.FILES or None,
        prefix="collateral",
        initial=None if request.method == "POST" else initial,
    )
    _attach_existing_collateral(formset, existing_items)
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
                loan = update_pawn_draft_with_photos(
                    loan.pk,
                    command,
                    photos=_draft_photo_inputs(formset),
                    actor=request.user,
                )
        except (PawnDraftError, ValidationError, ValueError) as exc:
            _add_pawn_draft_error(form, formset, exc)
        else:
            if request.POST.get("action") != "preview":
                messages.success(request, f"Draft {loan.loan_number} updated.")
                return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
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


@loans_action_required("data.edit")
@loans_action_required("data.create")
def pawn_loan_split(request, pk):
    from apps.tenant_apps.loans.forms import PawnDraftSplitForm
    from apps.tenant_apps.loans.services.pawn_draft_split import (
        PawnDraftSplitError,
        preview_pawn_draft_split,
        split_pawn_draft,
    )
    loan = _pawn_loan_for_workspace(request, pk)
    if loan.state != PawnLoanState.DRAFT.value:
        messages.error(request, "Only a draft PawnLoan can be split.")
        return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    initial = {"series": loan.series_id, "product_version": loan.product_version_id, "loan_date": loan.loan_date, "tenure_months": loan.tenure_months}
    if request.method == "GET" and request.GET.get("item"):
        initial["collateral_items"] = [request.GET["item"]]
    form = PawnDraftSplitForm(
        request.POST or None,
        workspace=request.loans_workspace,
        source=loan,
        initial=initial,
    )
    preview = None
    if request.method == "POST" and form.is_valid():
        values = form.cleaned_data
        try:
            preview = preview_pawn_draft_split(
                loan.pk,
                collateral_item_ids=tuple(values["collateral_items"].values_list("pk", flat=True)),
                series=values["series"], product_version=values["product_version"],
                loan_date=values["loan_date"], tenure_months=values["tenure_months"],
            )
            if request.POST.get("action") == "confirm":
                new_loan = split_pawn_draft(
                    loan.pk,
                    collateral_item_ids=tuple(values["collateral_items"].values_list("pk", flat=True)),
                    series=values["series"], product_version=values["product_version"],
                    loan_date=values["loan_date"], tenure_months=values["tenure_months"],
                    expected_fingerprint=request.POST.get("fingerprint", ""), actor=request.user,
                )
                messages.success(request, f"Moved selected collateral into new draft {new_loan.loan_number}.")
                return redirect('workspace_loans:pawn_loan_detail', pk=new_loan.pk, workspace_slug=request.workspace.slug)
        except (PawnDraftSplitError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
    template = "loans/pawn/_split_form.html" if request.headers.get("HX-Request") else "loans/pawn/split.html"
    return render(request, template, {"loan": loan, "form": form, "preview": preview})


@loans_action_required("data.edit")
@require_POST
def pawn_collateral_photo_delete(request, pk, item_pk, photo_pk):
    from apps.tenant_apps.loans.models import PawnCollateralPhoto
    from apps.tenant_apps.loans.services.collateral_media import delete_draft_collateral_photo
    loan = _pawn_loan_for_workspace(request, pk)
    item = get_object_or_404(PawnCollateralItem, pk=item_pk, loan=loan)
    get_object_or_404(PawnCollateralPhoto, pk=photo_pk, collateral_item=item)
    try:
        delete_draft_collateral_photo(item.pk, photo_pk, actor=request.user)
    except (PawnCollateralMediaError, ValidationError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Draft photograph deleted. Each collateral item needs a photograph before approval.")
    return redirect(f"{reverse('workspace_loans:pawn_loan_detail', args=[request.workspace.slug, loan.pk])}#collateral-{item.public_id}")


@loans_action_required("data.edit")
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
    return redirect(f"{reverse('workspace_loans:pawn_loan_detail', args=[request.workspace.slug, loan.pk])}#collateral-{item.public_id}")


@loans_action_required("loan.approve")
@require_POST
def pawn_loan_approve(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    try:
        approve_pawn_loan(loan.pk, actor=request.user)
        messages.success(request, f"{loan.loan_number} approved. Its economic payload is frozen.")
    except (PawnLifecycleError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)


@loans_action_required("data.edit")
def pawn_loan_reopen(request, pk):
    return _reason_transition(request, pk, "reopen")


@loans_action_required("data.edit")
def pawn_loan_cancel(request, pk):
    return _reason_transition(request, pk, "cancel")


def _safe_preview(series, kind):
    try:
        return {"value": preview_number(series=series, document_kind=kind).value}
    except NumberAllocationError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}


def get_pawn_draft_readiness(workspace):
    from apps.tenant_apps.party.models import Party

    from apps.tenant_apps.loans.selectors.setup import get_pawn_setup_checklist

    checklist = get_pawn_setup_checklist(workspace)
    for step in checklist["steps"]:
        if not step["complete"]:
            return {
                "ready": False, "requires_setup": True,
                "message": step["description"],
                "action_label": step["action_label"], "action_url": step["action_url"],
            }
    if not Party.objects.filter(
        workspace=workspace, status=Party.PartyStatus.ACTIVE,
    ).exists():
        return {
            "ready": False,
            "message": "Create an active Party before starting a pawn-loan draft.",
            "action_label": "Create Party",
            "action_url": reverse(
                "workspace_party:party_create",
                kwargs={"workspace_slug": workspace.slug},
            ),
        }
    return {"ready": True}


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


def _draft_photo_inputs(formset):
    return tuple(
        DraftCollateralPhotoInput(
            collateral_item_id=row.get("collateral_item_id"),
            upload=row.get("photograph"),
        )
        for row in formset.cleaned_data
        if row and not row.get("DELETE") and row.get("photograph")
    )


def _attach_existing_collateral(formset, items):
    """Attach trusted persisted items to their draft forms for photo display."""

    items_by_id = {str(item.pk): item for item in items}
    for item_form in formset.forms:
        item_form.existing_collateral_item = items_by_id.get(
            str(item_form["collateral_item_id"].value() or "")
        )


def _create_command(workspace_id, form, formset):
    data = form.cleaned_data
    return CreatePawnDraftCommand(
        workspace_id=workspace_id,
        borrower_id=data["borrower"].pk,
        license_id=data["series"].license_id,
        series_id=data["series"].pk,
        product_version_id=data["product_version"].pk,
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
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    return render(
        request,
        "loans/pawn/transition_form.html",
        {"loan": loan, "form": form, "action_label": labels[action]},
    )
