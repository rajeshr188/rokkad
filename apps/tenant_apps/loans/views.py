from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_setup_required, loans_workspace_required
from apps.tenant_apps.loans.domain import LoanDocumentKind, PawnLoanState
from apps.tenant_apps.loans.forms import (
    LoanLicenseForm,
    LoanSeriesSetupForm,
    PawnCollateralDraftFormSet,
    PawnDraftForm,
)
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnLoan
from apps.tenant_apps.loans.services import (
    LicenseSeriesError,
    NumberAllocationError,
    activate_license,
    configure_sequence,
    create_license,
    create_series,
    expire_license,
    preview_number,
    set_series_active,
    update_license,
    update_series,
    CollateralDraftInput,
    CreatePawnDraftCommand,
    PawnDraftError,
    UpdatePawnDraftCommand,
    create_pawn_draft,
    update_pawn_draft,
)


@loans_workspace_required
def pawn_loan_list(request):
    loans = PawnLoan.objects.filter(workspace=request.loans_workspace).select_related(
        "borrower", "license", "series"
    ).order_by("-created_at")
    readiness = _draft_readiness(request.loans_workspace)
    return render(request, "loans/pawn/list.html", {"loans": loans, "readiness": readiness})


@loans_workspace_required
def pawn_loan_create(request):
    readiness = _draft_readiness(request.loans_workspace)
    if not readiness["ready"]:
        return render(request, "loans/pawn/blocked.html", {"readiness": readiness})
    form = PawnDraftForm(request.POST or None, workspace=request.loans_workspace)
    formset = PawnCollateralDraftFormSet(request.POST or None, prefix="collateral")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            loan = create_pawn_draft(
                _create_command(request.loans_workspace.pk, form, formset), actor=request.user
            )
        except (PawnDraftError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Draft {loan.loan_number} created.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(request, "loans/pawn/form.html", {"form": form, "formset": formset})


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
            "metal": item.metal,
            "gross_weight": item.gross_weight,
            "net_weight": item.net_weight,
            "purity_percentage": item.purity_percentage,
            "latest_appraised_value": item.latest_appraised_value,
        }
        for item in loan.collateral_items.all()
    ]
    formset = PawnCollateralDraftFormSet(
        request.POST or None, prefix="collateral", initial=None if request.method == "POST" else initial
    )
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            update_pawn_draft(loan.pk, _update_command(form, formset), actor=request.user)
        except (PawnDraftError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Draft {loan.loan_number} updated.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(request, "loans/pawn/form.html", {"form": form, "formset": formset, "loan": loan})


@loans_workspace_required
def pawn_loan_detail(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    return render(request, "loans/pawn/detail.html", {"loan": loan})


@loans_setup_required
def license_list(request):
    licenses = LoanLicense.objects.filter(workspace=request.loans_workspace).prefetch_related(
        "series__number_sequences"
    )
    return render(request, "loans/setup/license_list.html", {"licenses": licenses})


@loans_setup_required
def license_detail(request, pk):
    license = _license_for_workspace(request, pk)
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
        {"license": license, "series_rows": series_rows},
    )


@loans_setup_required
def license_create(request):
    form = LoanLicenseForm(request.POST or None)
    form.instance.workspace = request.loans_workspace
    if request.method == "POST" and form.is_valid():
        license = create_license(
            workspace=request.loans_workspace,
            actor=request.user,
            **form.cleaned_data,
        )
        messages.success(request, "Loan license created.")
        return redirect("loans:license_detail", pk=license.pk)
    return render(request, "loans/setup/license_form.html", {"form": form})


@loans_setup_required
def license_update(request, pk):
    license = _license_for_workspace(request, pk)
    form = LoanLicenseForm(request.POST or None, instance=license)
    if request.method == "POST" and form.is_valid():
        update_license(license, actor=request.user, **form.cleaned_data)
        messages.success(request, "Loan license updated.")
        return redirect("loans:license_detail", pk=license.pk)
    return render(
        request,
        "loans/setup/license_form.html",
        {"form": form, "license": license},
    )


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
            "collateral_items", "change_log__actor"
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
            if not series.license.is_expired():
                return {"ready": True}
        except (NumberAllocationError, ValueError):
            continue
    return {
        "ready": False,
        "message": "Configure an active, unexpired license and available pawn-loan series.",
        "action_label": "Open Loan Setup",
        "action_url": reverse("loans:license_list"),
    }


def _collateral_inputs(formset):
    return tuple(
        CollateralDraftInput(
            description=row["description"],
            metal=row["metal"],
            gross_weight=row["gross_weight"],
            net_weight=row["net_weight"],
            purity_percentage=row["purity_percentage"],
            latest_appraised_value=row.get("latest_appraised_value"),
        )
        for row in formset.cleaned_data
        if row and not row.get("DELETE")
    )


def _create_command(workspace_id, form, formset):
    data = form.cleaned_data
    return CreatePawnDraftCommand(
        workspace_id=workspace_id,
        borrower_id=data["borrower"].pk,
        license_id=data["license"].pk,
        series_id=data["series"].pk,
        principal_amount=data["principal_amount"],
        monthly_interest_rate=data["monthly_interest_rate"],
        loan_date=data["loan_date"],
        tenure_months=data["tenure_months"],
        collateral=_collateral_inputs(formset),
    )


def _update_command(form, formset):
    data = form.cleaned_data
    return UpdatePawnDraftCommand(
        borrower_id=data["borrower"].pk,
        principal_amount=data["principal_amount"],
        monthly_interest_rate=data["monthly_interest_rate"],
        loan_date=data["loan_date"],
        tenure_months=data["tenure_months"],
        collateral=_collateral_inputs(formset),
    )
