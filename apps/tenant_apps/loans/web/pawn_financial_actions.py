"""Ordinary Django adapters for PawnLoan financial actions."""

import uuid

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant_apps.loans.access import (
    LOANS_ADMIN_ACTION, loans_action_required,
    loans_setup_required,
)
from apps.tenant_apps.loans.forms import (
    PawnAccrualForm, PawnCapitalizationForm, PawnDisbursalForm,
    PawnRepaymentForm, PawnReversalForm,
)
from apps.tenant_apps.loans.models import PawnLoan, PawnLoanEvent
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.loans.services import (
    assess_pawn_loan_event_reversal, capitalize_pawn_loan_interest,
    disburse_pawn_loan,
    finalize_pawn_loan_accrual, preview_pawn_loan_accruals,
    preview_pawn_loan_repayment, record_pawn_loan_repayment,
    reverse_pawn_loan_event,
)


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items", "loan_events"
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _render_action(request, loan, form, title, description, extra_context=None):
    context = {"loan": loan, "form": form, "action_label": title, "description": description}
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
            loan.pk, as_of_date=timezone.localdate(), include_partial=include_partial
        )
    except (ObjectDoesNotExist, ValidationError, ValueError):
        return ()


def _accrual_preview_rows(loan, previews):
    item_by_id = {item.pk: item for item in loan.collateral_items.all()}
    return tuple({"preview": preview, "lines": tuple(
        {"line": line, "item": item_by_id.get(line.collateral_item_id)}
        for line in preview.lines
    )} for preview in previews)


def _can_administer(request):
    return request.loans_workspace_access.can(LOANS_ADMIN_ACTION)

@loans_action_required("loan.disburse")
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
            messages.success(request, f"{loan.loan_number} disbursed successfully.")
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    return _render_action(
        request,
        loan,
        form,
        "Disburse loan",
        "This records the approved disbursal and activates the loan.",
        {"can_administer": _can_administer(request), "quote_recovery": True,
         "can_edit_loan": request.loans_workspace_access.can("data.edit")},
    )


@loans_action_required("loan.repay")
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
                allocation = result.allocation
                messages.success(
                    request,
                    "Repayment "
                    f"{allocation.amount_received} recorded: fees {allocation.fees}, "
                    f"overdue interest {allocation.overdue_interest}, current interest "
                    f"{allocation.current_interest}, principal {allocation.principal}.",
                )
                return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
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


@loans_action_required("loan.accrue")
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
            messages.success(
                request,
                "Interest accrual finalized.",
            )
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
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


@loans_action_required("loan.capitalize")
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
            messages.success(request, "Interest capitalization recorded.")
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    return _render_action(
        request,
        loan,
        form,
        "Capitalize interest",
        "Available only at the snapshotted compound-interest boundary.",
    )

@loans_setup_required
def pawn_loan_reverse_event(request, pk, event_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    event = get_object_or_404(
        PawnLoanEvent.objects.select_related("loan__workspace"),
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
            balance_text = (
                f" Resulting Loans total due is {balance.total_due}." if balance else ""
            )
            messages.success(
                request,
                f"Reversal event #{result.reversal_event.pk} recorded.{balance_text}",
            )
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    return _render_action(
        request,
        loan,
        form,
        f"Reverse {event.get_event_kind_display()}",
        "Administrator-only. Correct events newest-first; the original evidence is never edited.",
        {
            "loan_event": event,
            "balance": _safe_balance(loan),
            "reversal_readiness": readiness,
            "reversal_values": (event.payload.get("values") or {}).items(),
            "custody_items": loan.collateral_items.all(),
        },
    )
