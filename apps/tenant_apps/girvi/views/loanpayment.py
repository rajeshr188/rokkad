import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc

from ..forms import GivenLoanRepaymentForm, TakenLoanRepaymentForm
from ..models import GivenLoan, TakenLoan

logger = logging.getLogger(__name__)


@login_required
def loan_payment_create_view(request, pk=None):
    if not pk:
        raise Http404("A loan pk is required to record a payment.")

    loan = get_object_or_404(GivenLoan, pk=pk)

    if request.method == "POST":
        form = GivenLoanRepaymentForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            total = cd["total_amount"]
            interest = cd.get("interest_amount")
            principal = (total - interest) if interest is not None else None

            payment = loan.create_payment(
                amount=total,
                payment_date=cd["payment_date"],
                payment_method=cd["payment_method"],
                reference_number=cd.get("reference_number", ""),
                interest=interest,
                principal=principal,
                description=cd.get("description", ""),
                is_final=cd.get("is_final_payment", False),
                create_release=cd.get("create_release", False),
                created_by=request.user,
            )
            try:
                create_and_post_voucher_for_doc(
                    doc=payment,
                    user=request.user,
                    voucher_type_input=payment.get_voucher_type(),
                    engine=DjangoPostingEngine(),
                )
                payment.posted = True
                payment.save(update_fields=["posted"])
                messages.success(
                    request,
                    f"Payment {payment.payment_id} recorded and posted to accounting.",
                )
            except Exception as exc:
                logger.exception(
                    "Accounting post failed for payment %s", payment.payment_id
                )
                messages.warning(
                    request,
                    f"Payment {payment.payment_id} saved but accounting posting failed: {exc}",
                )
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
            cd = form.cleaned_data
            total = cd["total_amount"]
            interest = cd.get("interest_amount")
            principal = (total - interest) if interest is not None else None

            payment = loan.create_payment(
                amount=total,
                payment_date=cd["payment_date"],
                payment_method=cd["payment_method"],
                reference_number=cd.get("reference_number", ""),
                interest=interest,
                principal=principal,
                description=cd.get("description", ""),
                is_final=cd.get("is_final_payment", False),
                created_by=request.user,
            )
            try:
                create_and_post_voucher_for_doc(
                    doc=payment,
                    user=request.user,
                    voucher_type_input=payment.get_voucher_type(),
                    engine=DjangoPostingEngine(),
                )
                payment.posted = True
                payment.save(update_fields=["posted"])
                messages.success(
                    request,
                    f"Payment {payment.payment_id} recorded and posted to accounting.",
                )
            except Exception as exc:
                logger.exception(
                    "Accounting post failed for taken loan payment %s",
                    payment.payment_id,
                )
                messages.warning(
                    request,
                    f"Payment {payment.payment_id} saved but accounting posting failed: {exc}",
                )
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

