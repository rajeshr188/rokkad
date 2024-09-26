from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant_apps.notify.models import NoticeGroup, Notification

from ..models import Customer, Loan


@login_required
def create_loan_notification(request, pk=None):
    # get loan instance
    loan = get_object_or_404(Loan, pk=pk)
    # create a noticegroup
    import random
    import string

    # Generate a random string of 3 letters
    random_string = "".join(random.choice(string.ascii_letters) for _ in range(3))
    ng = NoticeGroup.objects.create(
        name=f"{loan.loan_id}-{random_string}-{datetime.now().date()}"
    )
    notification = Notification.objects.create(
        group=ng,
        customer=loan.customer,
    )
    # add the loan to the notification
    notification.loans.add(loan)
    notification.save()
    return redirect(notification.get_absolute_url())


@login_required
def notice(request):
    qyr = request.GET.get("qyr", 0)

    a_yr_ago = timezone.now() - relativedelta(years=int(qyr))

    # get all loans with selected ids
    selected_loans = (
        Loan.objects.unreleased()
        .filter(loan_date__lt=a_yr_ago)
        .order_by("customer")
        .select_related("customer")
    )

    # get a list of unique customers for the selected loans
    # customers = selected_loans.values('customer').distinct().count()
    customers = (
        Customer.objects.filter(loan__in=selected_loans)
        .distinct()
        .prefetch_related("loan_set", "address", "contactno")
    )

    data = {}
    data["loans"] = selected_loans
    data["loancount"] = selected_loans.count()
    data["total"] = selected_loans.total_loanamount()
    data["interest"] = selected_loans.with_total_interest()
    data["cust"] = customers

    return render(request, "girvi/loan/notice.html", context={"data": data})
