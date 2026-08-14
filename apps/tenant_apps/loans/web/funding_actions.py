"""Small HTTP adapters for FundingLoan state-changing actions."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.forms import (
    FundingCollateralReturnForm,
    FundingCorrectionForm,
    FundingLoanActivationForm,
    FundingLoanCancellationForm,
    FundingLoanClosureForm,
    FundingLoanDraftForm,
    FundingLoanDraftInputsForm,
    FundingLoanRepaymentForm,
)
from apps.tenant_apps.loans.selectors import (
    FundingLoanSelectorError,
    get_funding_loan_detail,
    get_funding_loan_draft_inputs,
)
from apps.tenant_apps.loans.services import (
    ActivateSavedFundingLoanDraft,
    BeginFundingSettlement,
    CancelFundingLoanDraft,
    CloseFundingLoan,
    CreateFundingLoanDraft,
    FundingCollateralInput,
    FundingLoanServiceError,
    RecordFundingRepayment,
    ReturnFundingCollateral,
    ReverseFundingEvent,
    ReverseFundingPledge,
    ReverseFundingReturn,
    SaveFundingLoanDraftInputs,
    activate_saved_funding_loan_draft,
    begin_funding_settlement,
    cancel_funding_loan_draft,
    close_funding_loan,
    create_funding_loan_draft,
    record_funding_repayment,
    return_funding_collateral,
    reverse_funding_event,
    reverse_funding_pledge,
    reverse_funding_return,
    save_funding_loan_draft_inputs,
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
    return render(request, "loans/setup/funding/form.html", {"form": form})


@loans_setup_required
def funding_loan_draft_inputs(request, pk):
    try:
        draft = get_funding_loan_draft_inputs(pk)
    except FundingLoanSelectorError as exc:
        raise Http404(str(exc)) from exc
    form = FundingLoanDraftInputsForm(
        request.POST if request.method == "POST" else None,
        workspace=request.loans_workspace,
        initial={
            "principal_amount": draft.principal_amount,
            "monthly_interest_rate": draft.monthly_interest_rate,
            "activated_on": draft.activated_on,
            "maturity_on": draft.maturity_on,
            "maximum_funding_ltv_ratio": draft.maximum_funding_ltv_ratio,
            "currency_quantum": draft.currency_quantum,
            "collateral": draft.collateral_item_ids,
        },
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
        messages.success(request, f"FundingLoan {funding_loan.funding_number} entered settlement review.")
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
        request.POST, collateral_rows=detail.collateral, include_inactive=True
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
        messages.success(request, f"Returned {funding_return.items.count()} collateral item(s) to the branch vault.")
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
        messages.success(request, f"FundingLoan {funding_loan.funding_number} closed.")
    return redirect("loans:funding_loan_read_detail", pk=pk)


def _correction_redirect(request, pk, form, action, success_message):
    if not form.is_valid():
        messages.error(request, "Enter a correction date and reason.")
    else:
        try:
            action(form.cleaned_data)
        except FundingLoanServiceError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, success_message)
    return redirect("loans:funding_loan_read_detail", pk=pk)


@require_POST
@loans_setup_required
def funding_loan_reverse_event(request, pk, event_pk):
    form = FundingCorrectionForm(request.POST)
    return _correction_redirect(
        request,
        pk,
        form,
        lambda data: reverse_funding_event(
            ReverseFundingEvent(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                original_event_id=event_pk,
                effective_date=data["effective_date"],
                reason=data["reason"],
                request_key=str(data["request_key"]),
            ),
            actor=request.user,
        ),
        "Funding financial event corrected.",
    )


@require_POST
@loans_setup_required
def funding_loan_reverse_return(request, pk, return_pk):
    form = FundingCorrectionForm(request.POST)
    return _correction_redirect(
        request,
        pk,
        form,
        lambda data: reverse_funding_return(
            ReverseFundingReturn(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                funding_return_id=return_pk,
                effective_date=data["effective_date"],
                reason=data["reason"],
                request_key=str(data["request_key"]),
            ),
            actor=request.user,
        ),
        "Funding collateral return corrected.",
    )


@require_POST
@loans_setup_required
def funding_loan_reverse_pledge(request, pk):
    form = FundingCorrectionForm(request.POST)
    return _correction_redirect(
        request,
        pk,
        form,
        lambda data: reverse_funding_pledge(
            ReverseFundingPledge(
                workspace_id=request.loans_workspace.pk,
                funding_loan_id=pk,
                effective_date=data["effective_date"],
                reason=data["reason"],
                request_key=str(data["request_key"]),
            ),
            actor=request.user,
        ),
        "Funding pledge handoff corrected.",
    )
