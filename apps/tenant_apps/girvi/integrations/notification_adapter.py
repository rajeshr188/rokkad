"""Notification adapter boundary for Girvi reminder flows.

Girvi runtime code should use this module instead of importing notify/notify_v2
models/services directly.
"""

def _get_notification_model():
    from apps.tenant_apps.notify.models import Notification

    return Notification


def _get_notification_job_model():
    from apps.tenant_apps.notify_v2.models import NotificationJob

    return NotificationJob


def get_default_loan_reminder_code():
    from apps.tenant_apps.notify.services import DEFAULT_LOAN_REMINDER_CODE

    return DEFAULT_LOAN_REMINDER_CODE


def get_default_medium_type():
    Notification = _get_notification_model()
    return Notification.MediumType.Letter


def event_key_for_notice_code(notice_code):
    event_by_notice_code = {
        "LOAN_FIRST_REMINDER": "loan.first_reminder_due",
        "LOAN_SECOND_REMINDER": "loan.second_reminder_due",
        "LOAN_FINAL_NOTICE": "loan.final_notice_due",
        "LOAN_AUCTION_NOTICE": "loan.auction_notice_due",
    }
    return event_by_notice_code.get(notice_code, "loan.first_reminder_due")


def channel_for_medium_type(medium_type):
    Notification = _get_notification_model()
    NotificationJob = _get_notification_job_model()
    channel_by_medium_type = {
        Notification.MediumType.Email: NotificationJob.Channel.EMAIL,
        Notification.MediumType.Letter: NotificationJob.Channel.LETTER,
        Notification.MediumType.Post: NotificationJob.Channel.POST,
        Notification.MediumType.SMS: NotificationJob.Channel.SMS,
        Notification.MediumType.Whatsapp: NotificationJob.Channel.WHATSAPP,
    }
    return channel_by_medium_type.get(medium_type, NotificationJob.Channel.LETTER)


def get_default_notice_channel():
    NotificationJob = _get_notification_job_model()
    return NotificationJob.Channel.LETTER


def get_draft_notice_status_value():
    Notification = _get_notification_model()
    return Notification.StatusType.Draft


def get_total_notifications_count():
    Notification = _get_notification_model()
    return Notification.objects.count()


def get_pending_notifications_count():
    Notification = _get_notification_model()
    return Notification.objects.filter(status=get_draft_notice_status_value()).count()


def create_girvi_reminder_batch(*, loans, created_by, event_key, channel, notes):
    from apps.tenant_apps.notify_v2.services import create_girvi_reminder_batch as _create_batch

    return _create_batch(
        loans=loans,
        created_by=created_by,
        event_key=event_key,
        channel=channel,
        notes=notes,
    )
