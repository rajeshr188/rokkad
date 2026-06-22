from dateutil.relativedelta import relativedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant_apps.notify.models import Notification
from apps.tenant_apps.notify.services import (
    DEFAULT_LOAN_REMINDER_CODE,
)
from apps.tenant_apps.notify_v2.models import NotificationJob
from apps.tenant_apps.notify_v2.services import create_girvi_reminder_batch

from ..models import Customer, GivenLoan
from .access import girvi_permission_required, girvi_workspace_required


_NOTIFY_V2_EVENT_MAP = {
    "LOAN_FIRST_REMINDER": "loan.first_reminder_due",
    "LOAN_SECOND_REMINDER": "loan.second_reminder_due",
    "LOAN_FINAL_NOTICE": "loan.final_notice_due",
    "LOAN_AUCTION_NOTICE": "loan.auction_notice_due",
}

_NOTIFY_V2_CHANNEL_MAP = {
    Notification.MediumType.Email: NotificationJob.Channel.EMAIL,
    Notification.MediumType.Letter: NotificationJob.Channel.LETTER,
    Notification.MediumType.Post: NotificationJob.Channel.POST,
    Notification.MediumType.SMS: NotificationJob.Channel.SMS,
    Notification.MediumType.Whatsapp: NotificationJob.Channel.WHATSAPP,
}


@girvi_permission_required("girvi_report_view")
def create_loan_notification(request, pk=None):
    loan = get_object_or_404(GivenLoan.objects.select_related("borrower"), pk=pk)
    notice_code = request.GET.get("notice_code", DEFAULT_LOAN_REMINDER_CODE)
    medium_type = request.GET.get(
        "medium_type",
        Notification.MediumType.Letter,
    )
    event_key = _NOTIFY_V2_EVENT_MAP.get(notice_code, "loan.first_reminder_due")
    channel = _NOTIFY_V2_CHANNEL_MAP.get(medium_type, NotificationJob.Channel.LETTER)

    batch_result = create_girvi_reminder_batch(
        loans=[loan],
        created_by=request.user,
        event_key=event_key,
        channel=channel,
        notes="Created from single-loan notice entrypoint.",
    )
    return redirect(batch_result.batch.get_absolute_url())


@girvi_workspace_required
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
