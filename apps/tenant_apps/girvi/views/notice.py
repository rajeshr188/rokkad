from dateutil.relativedelta import relativedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.tenant_apps.contact.facade import customer_queryset
from apps.tenant_apps.girvi.integrations.notification_adapter import (
    channel_for_medium_type,
    create_girvi_reminder_batch,
    event_key_for_notice_code,
    get_default_loan_reminder_code,
    get_default_medium_type,
)

from ..models import GivenLoan
from .access import girvi_permission_required, girvi_workspace_required


@girvi_permission_required("girvi_report_view")
def create_loan_notification(request, pk=None):
    loan = get_object_or_404(GivenLoan.objects.select_related("borrower"), pk=pk)
    notice_code = request.GET.get("notice_code", get_default_loan_reminder_code())
    medium_type = request.GET.get("medium_type", get_default_medium_type())
    event_key = event_key_for_notice_code(notice_code)
    channel = channel_for_medium_type(medium_type)

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
        customer_queryset().filter(loans_received__in=selected_loans)
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
