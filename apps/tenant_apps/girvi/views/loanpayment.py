from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, reverse

from django.template.response import TemplateResponse
from django.utils import timezone

from ..forms import GivenLoanRepaymentForm, TakenLoanRepaymentForm
from ..models import GivenLoan, TakenLoan
from ..service_modules.repayment import (
    GivenLoanRepaymentService,
    RepaymentCommand,
    TakenLoanRepaymentService,
)


@login_required
def loan_payment_create_view(request, pk=None):
    if not pk:
        raise Http404("A loan pk is required to record a payment.")

    loan = get_object_or_404(GivenLoan, pk=pk)

    if request.method == "POST":
        form = GivenLoanRepaymentForm(request.POST)
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
            if result.success_message:
                messages.success(request, result.success_message)
            return redirect(reverse("girvi:girvi_loan_detail", args=[loan.pk]))
    else:
        form = GivenLoanRepaymentForm(initial={"payment_date": timezone.now()})

    if request.htmx:
        return TemplateResponse(
            request,
            "girvi/loanpayment/givenloan_repayment_form.html#content",
            {"form": form, "loan": loan},
        )
    return TemplateResponse(
        request,
        "girvi/loanpayment/givenloan_repayment_form.html",
        {"form": form, "loan": loan},
    )


@login_required
def taken_loan_payment_create_view(request, pk):
    loan = get_object_or_404(TakenLoan, pk=pk)

    if request.method == "POST":
        form = TakenLoanRepaymentForm(request.POST)
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
            if result.success_message:
                messages.success(request, result.success_message)
            return redirect(loan.get_absolute_url())
    else:
        form = TakenLoanRepaymentForm(initial={"payment_date": timezone.now()})

    if request.htmx:
        return TemplateResponse(
            request,
            "girvi/loanpayment/takenloan_repayment_form.html#content",
            {"form": form, "loan": loan},
        )
    return TemplateResponse(
        request,
        "girvi/loanpayment/takenloan_repayment_form.html",
        {"form": form, "loan": loan},
    )

