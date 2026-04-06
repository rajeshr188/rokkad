from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant_apps.notify.models import Notification
from apps.tenant_apps.notify.services import (
    DEFAULT_LOAN_REMINDER_CODE,
    create_loan_reminder_notification,
)

from ..models import Customer, GivenLoan


@login_required
def create_loan_notification(request, pk=None):
    loan = get_object_or_404(GivenLoan.objects.select_related("borrower"), pk=pk)
    notice_code = request.GET.get("notice_code", DEFAULT_LOAN_REMINDER_CODE)
    medium_type = request.GET.get(
        "medium_type",
        Notification.MediumType.Letter,
    )

    notification = create_loan_reminder_notification(
        customer=loan.borrower,
        loans=[loan],
        notice_code=notice_code,
        medium_type=medium_type,
    )
    return redirect(notification.get_absolute_url())


@login_required
def notice(request):
    qyr = request.GET.get("qyr", 0)

    a_yr_ago = timezone.now() - relativedelta(years=int(qyr))

    # get all loans with selected ids
    selected_loans = (
        GivenLoan.objects.unreleased()
        .filter(loan_date__lt=a_yr_ago)
        .order_by("borrower")
        .select_related("borrower")
    )

    # get a list of unique customers for the selected loans
    # customers = selected_loans.values('customer').distinct().count()
    customers = (
        Customer.objects.filter(loans_received__in=selected_loans)
        .distinct()
        .prefetch_related("loans_received", "address", "contactno")
    )

    data = {}
    data["loans"] = selected_loans
    data["loancount"] = selected_loans.count()
    data["total"] = selected_loans.total_loanamount()
    data["interest"] = selected_loans.with_total_interest()
    data["cust"] = customers

    return render(request, "girvi/loan/notice.html", context={"data": data})
