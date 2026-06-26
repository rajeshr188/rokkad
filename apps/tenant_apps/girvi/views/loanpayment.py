from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, reverse

from django.template.response import TemplateResponse

from ..forms import GivenLoanRepaymentForm, TakenLoanRepaymentForm
from ..models import GivenLoan, TakenLoan
from ..policies import assert_can_record_repayment
from ..service_modules.repayment import (
    GivenLoanRepaymentService,
    RepaymentCommand,
    TakenLoanRepaymentService,
)
from ..service_modules.repayment_workflow import RepaymentWorkflowService
from .access import girvi_permission_required


@girvi_permission_required("girvi_loan_payment")
def loan_payment_create_view(request, pk=None):
    if not pk:
        raise Http404("A loan pk is required to record a payment.")

    loan = get_object_or_404(GivenLoan, pk=pk)
    try:
        assert_can_record_repayment(loan, loan_kind="given")
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("girvi:girvi_loan_detail", args=[loan.pk]))
    repayment_preview = RepaymentWorkflowService.build_preview(loan, loan_kind="given")

    if request.method == "POST":
        form = GivenLoanRepaymentForm(request.POST, loan=loan)
        if form.is_valid():
            result = GivenLoanRepaymentService.execute(
                RepaymentCommand(
                    loan=loan,
                    cleaned_data=form.cleaned_data,
                    created_by=request.user,
                )
            )
            RepaymentWorkflowService.emit_result_messages(request, result)
            return redirect(reverse("girvi:girvi_loan_detail", args=[loan.pk]))
    else:
        form = GivenLoanRepaymentForm(
            initial=RepaymentWorkflowService.initial_form_data(repayment_preview),
            loan=loan,
        )

    context = {
        "form": form,
        "loan": loan,
        "repayment_preview": repayment_preview,
        "settlement": repayment_preview.settlement,
        "payment_options": RepaymentWorkflowService.payment_options(repayment_preview),
        "return_url": reverse("girvi:girvi_loan_detail", args=[loan.pk]),
    }
    if request.htmx:
        return TemplateResponse(
            request,
            "girvi/loanpayment/givenloan_repayment_form.html#content",
            context,
        )
    return TemplateResponse(
        request,
        "girvi/loanpayment/givenloan_repayment_form.html",
        context,
    )


@girvi_permission_required("girvi_loan_payment")
def taken_loan_payment_create_view(request, pk):
    loan = get_object_or_404(TakenLoan, pk=pk)
    try:
        assert_can_record_repayment(loan, loan_kind="taken")
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect(loan.get_absolute_url())
    repayment_preview = RepaymentWorkflowService.build_preview(loan, loan_kind="taken")

    if request.method == "POST":
        form = TakenLoanRepaymentForm(request.POST, loan=loan)
        if form.is_valid():
            result = TakenLoanRepaymentService.execute(
                RepaymentCommand(
                    loan=loan,
                    cleaned_data=form.cleaned_data,
                    created_by=request.user,
                )
            )
            RepaymentWorkflowService.emit_result_messages(request, result)
            return redirect(loan.get_absolute_url())
    else:
        form = TakenLoanRepaymentForm(
            initial=RepaymentWorkflowService.initial_form_data(repayment_preview),
            loan=loan,
        )

    context = {
        "form": form,
        "loan": loan,
        "repayment_preview": repayment_preview,
        "settlement": repayment_preview.settlement,
        "payment_options": RepaymentWorkflowService.payment_options(repayment_preview),
        "return_url": loan.get_absolute_url(),
    }
    if request.htmx:
        return TemplateResponse(
            request,
            "girvi/loanpayment/takenloan_repayment_form.html#content",
            context,
        )
    return TemplateResponse(
        request,
        "girvi/loanpayment/takenloan_repayment_form.html",
        context,
    )
