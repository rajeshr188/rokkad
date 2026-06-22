from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, reverse

from django.template.response import TemplateResponse
from django.utils import timezone

from ..forms import GivenLoanRepaymentForm, TakenLoanRepaymentForm
from ..models import GivenLoan, TakenLoan
from ..selectors import build_repayment_preview
from ..service_modules.repayment import (
    GivenLoanRepaymentService,
    RepaymentCommand,
    TakenLoanRepaymentService,
)
from .access import girvi_permission_required


@girvi_permission_required("girvi_loan_payment")
def loan_payment_create_view(request, pk=None):
    if not pk:
        raise Http404("A loan pk is required to record a payment.")

    loan = get_object_or_404(GivenLoan, pk=pk)
    repayment_preview = build_repayment_preview(loan)

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
            for warning in result.warnings:
                messages.warning(request, warning)
            for error in result.errors:
                messages.error(request, error)
            if result.success_message:
                messages.success(request, result.success_message)
            return redirect(reverse("girvi:girvi_loan_detail", args=[loan.pk]))
    else:
        form = GivenLoanRepaymentForm(
            initial={
                "payment_date": timezone.now(),
                "interest_amount": repayment_preview.suggested_interest_amount,
            },
            loan=loan,
        )

    context = {
        "form": form,
        "loan": loan,
        "repayment_preview": repayment_preview,
        "settlement": repayment_preview.settlement,
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
    repayment_preview = build_repayment_preview(loan, loan_kind="taken")

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
            for warning in result.warnings:
                messages.warning(request, warning)
            for error in result.errors:
                messages.error(request, error)
            if result.success_message:
                messages.success(request, result.success_message)
            return redirect(loan.get_absolute_url())
    else:
        form = TakenLoanRepaymentForm(
            initial={
                "payment_date": timezone.now(),
                "interest_amount": repayment_preview.suggested_interest_amount,
            },
            loan=loan,
        )

    context = {
        "form": form,
        "loan": loan,
        "repayment_preview": repayment_preview,
        "settlement": repayment_preview.settlement,
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

