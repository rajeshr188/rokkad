"""Ordinary Django adapters for PawnLoan financial actions."""

import uuid

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.tenant_apps.loans.access import loans_setup_required, loans_workspace_required
from apps.tenant_apps.loans.forms import (
    PawnAccrualForm, PawnCapitalizationForm, PawnDisbursalForm,
    PawnRepaymentForm, PawnReversalForm,
)
from apps.tenant_apps.loans.models import PawnLoan, PawnLoanAccountingEvent
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.loans.services import (
    PawnBorrowerAccountingSetupError, assess_pawn_loan_accounting_readiness,
    assess_pawn_loan_event_reversal, capitalize_pawn_loan_interest,
    disburse_pawn_loan, ensure_pawn_borrower_accounting,
    finalize_pawn_loan_accrual, preview_pawn_loan_accruals,
    preview_pawn_loan_repayment, record_pawn_loan_repayment,
    reverse_pawn_loan_event,
)


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items", "accounting_events__outbox"
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
    user, workspace = request.user, request.loans_workspace
    return bool(is_platform_admin(user) or workspace.owner_id == user.pk or
                get_workspace_role_name(user, workspace) in {"Owner", "Admin"})

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

@loans_setup_required
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

