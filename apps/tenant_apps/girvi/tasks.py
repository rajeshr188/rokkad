from __future__ import absolute_import, unicode_literals

from django.core.management import call_command
from django.utils import timezone

try:
    from celery import shared_task
    from celery.utils.log import get_task_logger
except ImportError:
    import logging

    def shared_task(*decorator_args, **decorator_kwargs):
        def decorator(func):
            func.run = func
            return func

        if decorator_args and callable(decorator_args[0]):
            return decorator(decorator_args[0])
        return decorator

    get_task_logger = logging.getLogger

from apps.tenant_apps.notify.models import Notification
from apps.tenant_apps.notify.services import (
    DEFAULT_LOAN_REMINDER_CODE,
    create_bulk_loan_reminder_group,
)

logger = get_task_logger(__name__)

from django_tables2.export.export import TableExport

from .filters import LoanFilter
from .models import GivenLoan
from .tables import LoanTable


@shared_task
def export_table(export_format, query_params):
    filter = LoanFilter(
        query_params,
        queryset=GivenLoan.objects.order_by("-id")
        .for_table_display()
        .prefetch_related("notifications", "loanitems"),
    )
    table = LoanTable(filter.qs)
    exporter = TableExport(
        export_format,
        table,
        exclude_columns=(
            "selection",
            "notified",
            "months_since_created",
            "total_current_value",
            "total_due",
            "total_interest",
        ),
        dataset_kwargs={"title": "loans"},
    )
    return exporter.response(f"table.{export_format}")


# import datetime
# @shared_task(name="twilio status")
# def notify(name="twilio_up"):

#     client = Client(env('TWILIO_ACCOUNT_SID'), env('TWILIO_AUTH_TOKEN'))

#     message = client.messages.create(
#                                 body=f'J Champalal PawnBroker:\
#                                          {datetime.datetime.now()}you have loans that are overdue,pls contact: 7904286981',
#                                 from_=env('TWILIO_NUMBER'),
#                                 to='+917598260045'
#                             )

#     return message.sid


# this runs at the start of everymonth
@shared_task(name="pending_loans")
def notify_pending_loans():
    logger.warning(
        "Legacy pending_loans task is disabled. Use notify_Loan_reminder or "
        "notify_v2 reminder batches for active Girvi reminder generation."
    )
    return {
        "status": "disabled",
        "reason": "legacy_pending_loans_task_references_removed_loan_models",
    }


# this runs everyday selecting the loans that were created on this day of month and notify users the no of months
@shared_task(name="interest_overdue_permonth")
def notify_interest_overdue():
    logger.warning(
        "Legacy interest_overdue_permonth task is disabled. Use "
        "accrue_loan_interest_batch for interest recognition and notify_v2 "
        "reminder batches for borrower communication."
    )
    return {
        "status": "disabled",
        "reason": "legacy_interest_overdue_task_references_removed_loan_models",
    }


@shared_task(name="one_year_reminder")
def notify_Loan_reminder():
    today = timezone.localdate()
    reminder_loans = (
        GivenLoan.objects.filter(
            release__isnull=True,
            loan_date__day=today.day,
            loan_date__month=today.month,
        )
        .select_related("borrower")
        .order_by("borrower")
    )

    if not reminder_loans.exists():
        logger.info("No loan reminder notifications due for %s", today)
        return 0

    group = create_bulk_loan_reminder_group(
        reminder_loans,
        notice_code=DEFAULT_LOAN_REMINDER_CODE,
        medium_type=Notification.MediumType.Letter,
    )
    created_count = group.notifications.count()
    logger.info(
        "Created %s loan reminder notifications in group %s",
        created_count,
        group.name,
    )
    return created_count


@shared_task(name="accrue_loan_interest_batch")
def accrue_loan_interest_batch(as_of_date=None, schema=None, post_to_accounting=True):
    """Scheduled batch entry point for the tenant-aware interest accrual command."""
    return call_command(
        "accrue_loan_interest",
        as_of_date=as_of_date,
        schema=schema,
        trigger_source="SCHEDULED",
        skip_accounting=not post_to_accounting,
        respect_timing=True,
    )
