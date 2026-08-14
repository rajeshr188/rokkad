"""Ordinary Django adapters for PawnLoan renewal actions."""

import uuid

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant_apps.loans.access import loans_setup_required, loans_workspace_required
from apps.tenant_apps.loans.forms import (
    PawnAdditionalCollateralFormSet, PawnRenewalForm,
    PawnRenewalRetainedItemFormSet, PawnReversalForm,
)
from apps.tenant_apps.loans.models import PawnLoan, PawnLoanRenewal
from apps.tenant_apps.loans.services import (
    CollateralDraftInput, PawnRenewalError,
    RetainedCollateralInput,
    preview_pawn_loan_renewal_plan, preview_pawn_loan_renewal_source,
    renew_pawn_loan, reverse_pawn_loan_renewal,
)
from apps.tenant_apps.loans.services.pawn_tranches import (
    PawnTrancheBalanceError,
    get_pawn_principal_tranche_balances,
)


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related("collateral_items"),
        pk=pk, workspace=request.loans_workspace,
    )


def _pawn_renewal_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoanRenewal.objects.select_related("source_loan", "source_loan__workspace", "successor_loan", "settlement_event__outbox", "opening_event__outbox"),
        pk=pk, workspace=request.loans_workspace,
    )


def _collateral_inputs(formset):
    return tuple(
        CollateralDraftInput(
            collateral_item_id=row.get("collateral_item_id"), description=row["description"],
            metal=row["metal"], gross_weight=row["gross_weight"], net_weight=row["net_weight"],
            purity_percentage=row["purity_percentage"], latest_appraised_value=row.get("latest_appraised_value"),
            allocated_principal=row["allocated_principal"],
        ) for row in formset.cleaned_data if row and not row.get("DELETE")
    )


def _render_action(request, loan, form, title, description, extra_context=None):
    context={"loan": loan, "form": form, "action_label": title, "description": description}
    context.update(extra_context or {})
    return render(request, "loans/pawn/action_form.html", context)

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


@loans_setup_required
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
