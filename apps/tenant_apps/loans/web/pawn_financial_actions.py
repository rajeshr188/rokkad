"""Ordinary Django adapters for PawnLoan financial actions."""

import uuid

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans.access import (
    LOANS_ADMIN_ACTION, loans_action_required,
    loans_setup_required,
)
from apps.tenant_apps.loans.forms import (
    PawnAccrualForm, PawnCapitalizationForm, PawnDisbursalForm,
    PawnRepaymentForm, PawnReversalForm,
)
from apps.tenant_apps.loans.models import PawnLoan, PawnLoanEvent
from apps.tenant_apps.loans.services.pawn_disbursal import preview_approved_disbursal
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
@never_cache
def pawn_loan_disburse(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnDisbursalForm(
        request.POST if request.method == "POST" else None,
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
    economics = None
    review_error = None
    try:
        economics = preview_approved_disbursal(loan)
    except (ValidationError, ValueError) as exc:
        review_error = str(exc)
    from apps.tenant_apps.loans.services.valuation_review import valuation_refresh_reason
    refresh_reason = valuation_refresh_reason(loan)
    if refresh_reason:
        review_error = refresh_reason
    return _render_action(
        request,
        loan,
        form,
        _("Disburse loan"),
        _("Confirm only after paying the customer. This records payment and activates the loan; it does not send a bank transfer."),
        {"can_administer": _can_administer(request), "quote_recovery": True,
         "is_disbursal": True, "economics": economics, "review_error": review_error,
         "valuation_refresh_reason": refresh_reason,
         "can_edit_loan": request.loans_workspace_access.can("data.edit")},
    )


@loans_action_required("loan.repay")
@never_cache
def pawn_loan_repay(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    repayment_preview = None
    from apps.tenant_apps.loans.services.recorded_collections import recording_for
    from apps.tenant_apps.loans.services.servicing_eligibility import servicing_eligibility
    paper_eligibility = servicing_eligibility(loan, operation="REPAYMENT", purpose="PAPER", effective_date=timezone.localdate())
    paper_available = paper_eligibility.ready
    from apps.tenant_apps.loans.services.entry_purpose import default_entry_purpose
    purpose = default_entry_purpose(workspace=request.loans_workspace, series_id=loan.series_id)
    form = PawnRepaymentForm(
        request.POST if request.method == "POST" else None,
        initial={"request_key": uuid.uuid4().hex, "received_on": timezone.localdate(),
                 "recording_purpose": "PAPER" if paper_available and purpose == "PAPER" else "CURRENT"},
        allow_paper=paper_available,
        collateral_items=list(loan.collateral_items.order_by("pk")) if paper_available else [],
    )
    if request.method == "POST" and form.is_valid():
        try:
            if form.cleaned_data.get("recording_purpose") == "PAPER":
                from apps.tenant_apps.loans.services.paper_repayments import (
                    preview_paper_repayment, record_paper_repayment,
                )
                values = {name: form.cleaned_data[name] for name in (
                    "amount", "received_on", "receipt_reference", "request_key",
                )}
                values["item_principal_split"] = form.paper_item_split
                if request.POST.get("action") == "preview":
                    review = preview_paper_repayment(loan.pk, actor=request.user, **values)
                    repayment_preview = review.preview
                    form.data = form.data.copy()
                    form.data["review_token"] = review.review_token
                else:
                    result = record_paper_repayment(
                        loan.pk, actor=request.user, **values,
                        review_token=form.cleaned_data["review_token"],
                        confirmed_received=form.cleaned_data["confirmed_received"],
                    )
            elif request.POST.get("action") == "preview":
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
    balance_date = timezone.localdate()
    if (form.is_bound and form.cleaned_data.get("recording_purpose") == "PAPER"
            and form.cleaned_data.get("received_on")):
        balance_date = form.cleaned_data["received_on"]
    from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
    try:
        balance = get_servicing_position(loan, as_of_date=balance_date).balance
    except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
        balance = None
        form.add_error(None, str(exc))
    item_by_id = {item.pk: item for item in loan.collateral_items.all()}
    return _render_action(
        request,
        loan,
        form,
        _("Record repayment"),
        _("Preview how the amount will be applied, then record it only after receiving payment. This action does not return collateral or close the loan."),
        {
            "balance": balance,
            "balance_date": balance_date,
            "paper_entry_available": paper_available,
            "paper_entry_blockers": paper_eligibility.blockers,
            "paper_correction_available": bool(recording_for(loan)) and _can_administer(request),
            "paper_receipt_preview": bool(repayment_preview and form.cleaned_data.get("recording_purpose") == "PAPER"),
            "staff_item_split": bool(repayment_preview and form.cleaned_data.get("recording_purpose") == "PAPER" and form.paper_item_split is not None),
            "is_repayment": True,
            "supports_preview": True,
            "preview_action_label": _("Preview allocation"),
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
    from apps.tenant_apps.loans.services.pawn_interest import started_month_charge_allowed
    started = started_month_charge_allowed(loan.policy_snapshot)
    previews = _safe_accrual_previews(loan, include_partial=started)
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
        "Finalize the next eligible monthly charge." if started else "Only the next eligible completed monthly period can be finalized.",
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
