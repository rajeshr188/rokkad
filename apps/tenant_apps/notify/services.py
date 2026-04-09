from __future__ import annotations

from collections import OrderedDict

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

from .models import NoticeGroup, NoticeTypeConfig, Notification

DEFAULT_LOAN_REMINDER_CODE = "LOAN_FIRST_REMINDER"
DEFAULT_LOAN_AUCTION_NOTICE_CODE = "LOAN_AUCTION_NOTICE"
DEFAULT_LOAN_REMINDER_MEDIUM = Notification.MediumType.Letter

_LOAN_NOTICE_TYPE_FALLBACKS = {
    "LOAN_FIRST_REMINDER": Notification.NoticeType.First_Reminder,
    "LOAN_SECOND_REMINDER": Notification.NoticeType.Second_Reminder,
    "LOAN_FINAL_NOTICE": Notification.NoticeType.Final_Notice,
    "LOAN_AUCTION_NOTICE": Notification.NoticeType.Final_Notice,
    "LOAN_CREATED": Notification.NoticeType.Loan_created,
}


def _normalize_medium_type(medium_type: str | None) -> str:
    valid_mediums = {choice for choice, _label in Notification.MediumType.choices}
    if medium_type in valid_mediums:
        return medium_type
    return DEFAULT_LOAN_REMINDER_MEDIUM


def _resolve_legacy_notice_type(notice_code: str | None) -> str:
    return _LOAN_NOTICE_TYPE_FALLBACKS.get(
        notice_code or DEFAULT_LOAN_REMINDER_CODE,
        Notification.NoticeType.First_Reminder,
    )


def _resolve_due_date(loan):
    due_date = getattr(loan, "maturity_date", None)
    if due_date:
        return due_date.date() if hasattr(due_date, "date") else due_date

    loan_date = getattr(loan, "loan_date", None)
    if not loan_date:
        return None

    base_date = loan_date.date() if hasattr(loan_date, "date") else loan_date
    tenure = int(getattr(loan, "tenure", 0) or 0)
    return base_date + relativedelta(months=tenure)


def _resolve_amount(loan):
    amount = getattr(loan, "get_loan_amount", None)
    if callable(amount):
        return amount()
    if amount is not None:
        return amount
    return getattr(loan, "loanamount", None)


def _customer_email(customer) -> str | None:
    email = (getattr(customer, "email", None) or "").strip()
    return email or None


def _build_notification_record(
    *,
    customer,
    loan_list,
    notice_code,
    notice_type_config,
    medium_type,
    group=None,
):
    notification = Notification.objects.create(
        group=group,
        customer=customer,
        medium_type=medium_type,
        notice_type=_resolve_legacy_notice_type(notice_code),
        notice_type_config=notice_type_config,
        status=Notification.StatusType.Draft,
    )
    notification.loans.set(loan_list)

    for loan in loan_list:
        notification.add_item(
            loan,
            amount=_resolve_amount(loan),
            due_date=_resolve_due_date(loan),
            reference_number=getattr(loan, "loan_id", str(getattr(loan, "pk", ""))),
            notes=f"{notice_code} reminder for loan {getattr(loan, 'loan_id', getattr(loan, 'pk', ''))}",
        )

    notification.generate_message()
    notification.save()
    return notification


def create_loan_reminder_notification(
    *,
    customer,
    loans,
    notice_code: str = DEFAULT_LOAN_REMINDER_CODE,
    medium_type: str = DEFAULT_LOAN_REMINDER_MEDIUM,
    group=None,
    auto_send: bool = False,
    send_email_if_available: bool = True,
):
    """Create a configured notification for one customer's loan reminder flow."""
    loan_list = list(loans or [])
    if not loan_list:
        raise ValueError("At least one loan is required to create a reminder notification.")

    notice_type_config = NoticeTypeConfig.objects.filter(
        code=notice_code,
        is_active=True,
    ).first()
    normalized_medium = _normalize_medium_type(medium_type)

    with transaction.atomic():
        notification = _build_notification_record(
            customer=customer,
            loan_list=loan_list,
            notice_code=notice_code,
            notice_type_config=notice_type_config,
            medium_type=normalized_medium,
            group=group,
        )

        if auto_send or normalized_medium == Notification.MediumType.Email:
            notification.send_notification()

        if (
            send_email_if_available
            and _customer_email(customer)
            and normalized_medium != Notification.MediumType.Email
        ):
            # Keep auto-generated email copies outside printable groups so batch
            # print/detail flows stay aligned with the primary physical notice run.
            email_notification = _build_notification_record(
                customer=customer,
                loan_list=loan_list,
                notice_code=notice_code,
                notice_type_config=notice_type_config,
                medium_type=Notification.MediumType.Email,
                group=None,
            )
            email_notification.send_notification()

    return notification


def create_loan_auction_notice(
    *,
    loan,
    medium_type: str = DEFAULT_LOAN_REMINDER_MEDIUM,
    group=None,
    auto_send: bool = False,
):
    """Create a single auction notice for a loan entering the recovery path."""
    customer = getattr(loan, "borrower", None)
    if customer is None:
        raise ValueError("Loan must have a borrower before creating an auction notice.")

    return create_loan_reminder_notification(
        customer=customer,
        loans=[loan],
        notice_code=DEFAULT_LOAN_AUCTION_NOTICE_CODE,
        medium_type=medium_type,
        group=group,
        auto_send=auto_send,
    )


def create_bulk_loan_reminder_group(
    loans,
    *,
    notice_code: str = DEFAULT_LOAN_REMINDER_CODE,
    medium_type: str = DEFAULT_LOAN_REMINDER_MEDIUM,
    group_name: str | None = None,
    auto_send: bool = False,
):
    """Create one reminder notification per borrower for a batch of loans."""
    loan_list = list(loans or [])
    if not loan_list:
        raise ValueError("At least one loan is required to create a reminder group.")

    group_name = group_name or f"LoanReminder-{timezone.now():%y%m%d%H%M%S%f}"
    group = NoticeGroup.objects.create(name=group_name[:30])

    loans_by_customer = OrderedDict()
    for loan in loan_list:
        customer = getattr(loan, "borrower", None)
        if customer is None:
            raise ValueError("Each loan must have a borrower before creating reminders.")

        customer_key = getattr(customer, "pk", id(customer))
        bucket = loans_by_customer.setdefault(customer_key, {"customer": customer, "loans": []})
        bucket["loans"].append(loan)

    for payload in loans_by_customer.values():
        create_loan_reminder_notification(
            customer=payload["customer"],
            loans=payload["loans"],
            notice_code=notice_code,
            medium_type=medium_type,
            group=group,
            auto_send=auto_send,
        )

    return group
