"""Loans-to-Notify v2 adapter; provider details stay outside Loans."""

from dataclasses import dataclass

from django.db import transaction


@dataclass(frozen=True)
class PawnNoticeJobReference:
    event_id: int
    job_id: int


@dataclass(frozen=True)
class PawnNoticeDeliveryReceipt:
    status: str
    external_reference: str = ""
    failure_reason: str = ""
    sent_at: object | None = None
    attempt_count: int = 0
    last_attempt_at: object | None = None


PawnNoticeDeliveryState = PawnNoticeDeliveryReceipt


_EVENT_DEFAULTS = {
    "REPAYMENT_REMINDER": (
        "pawn_loan.repayment_reminder",
        "Pawn loan repayment reminder",
        "Dear {{ customer.name }}, repayment reminder for pawn loan {{ loans.0.loan_id }}. Total due INR {{ loans.0.total_due }} as of {{ loans.0.as_of_date }}.",
    ),
    "INTEREST_DUE": (
        "pawn_loan.interest_due",
        "Pawn loan interest due",
        "Dear {{ customer.name }}, interest of INR {{ loans.0.interest_due }} is due on pawn loan {{ loans.0.loan_id }} as of {{ loans.0.as_of_date }}.",
    ),
    "OVERDUE_NOTICE": (
        "pawn_loan.overdue_notice",
        "Pawn loan overdue notice",
        "Dear {{ customer.name }}, pawn loan {{ loans.0.loan_id }} is overdue. Total due is INR {{ loans.0.total_due }} as of {{ loans.0.as_of_date }}.",
    ),
    "RELEASE_CONFIRMATION": (
        "pawn_loan.release_confirmation",
        "Pawn loan release confirmation",
        "Dear {{ customer.name }}, pawn loan {{ loans.0.loan_id }} has been settled and its collateral release recorded.",
    ),
    "AUCTION_NOTICE": (
        "pawn_loan.auction_notice",
        "Pawn loan auction notice",
        "Dear {{ customer.name }}, collateral for pawn loan {{ loans.0.loan_id }} is scheduled for auction on {{ auction.scheduled_date }}. Total due is INR {{ loans.0.total_due }} as of {{ loans.0.as_of_date }}.",
    ),
}

_OPERATIONAL_EVENT_DEFAULTS = {
    "LICENSE_EXPIRY": (
        "loans.license_expiry",
        "Loan license expiry alert",
        "Loan license {{ license.number }} expires on {{ license.expires_on }} ({{ license.days_remaining }} days remaining).",
    ),
    "VERIFICATION_DISCREPANCY": (
        "loans.verification_discrepancy",
        "Collateral verification discrepancy",
        "Physical verification recorded {{ verification.classification }} for {{ collateral.description }} on loan {{ collateral.loan_number }} at {{ verification.scope }}.",
    ),
}


@transaction.atomic
def create_pawn_notice_job(notice) -> PawnNoticeJobReference:
    from apps.tenant_apps.notify_v2.models import (
        NotificationEventType,
        NotificationJob,
        NotificationPolicy,
        NotificationRecipient,
        NotificationTemplate,
    )
    from apps.tenant_apps.notify_v2.services import emit_event

    try:
        event_key, name, body = _EVENT_DEFAULTS[notice.notice_kind]
    except KeyError as exc:
        raise ValueError("This PawnLoan notice kind has no delivery workflow.") from exc

    event_type, _ = NotificationEventType.objects.update_or_create(
        key=event_key,
        defaults={
            "name": name,
            "domain": NotificationEventType.Domain.LOAN,
            "description": f"Loans-owned {name.lower()} event.",
            "is_active": True,
        },
    )
    NotificationPolicy.objects.update_or_create(
        event_type=event_type,
        channel=notice.channel,
        defaults={"priority": 100, "is_active": True},
    )
    if notice.notification_template_id:
        template = NotificationTemplate.objects.get(
            pk=notice.notification_template_id,
            event_type=event_type,
            channel=notice.channel,
            locale=notice.notification_template_locale,
            version=notice.notification_template_version,
            is_active=True,
        )
    else:
        template, _ = NotificationTemplate.objects.get_or_create(
            event_type=event_type,
            channel=notice.channel,
            locale="en",
            version=1,
            defaults={
                "renderer_type": NotificationTemplate.RendererType.DJANGO,
                "name": name,
                "subject_template": name,
                "body_template": body,
                "is_active": True,
            },
        )
    recipient = NotificationRecipient.objects.create(
        party=notice.loan.borrower,
        name_snapshot=notice.recipient_name,
        email=notice.recipient_email,
        phone=notice.recipient_phone,
    )
    event = emit_event(
        recipient=recipient,
        event_type=event_type,
        payload=notice.payload_snapshot,
        source_app="loans",
        source_model="PawnLoan",
        source_pk=notice.loan_id,
        dedupe_key=f"pawn-loan-notice:{notice.pk}",
    )
    job = NotificationJob.objects.create(
        event=event,
        channel=notice.channel,
        template=template,
        scheduled_for=notice.scheduled_for,
    )
    return PawnNoticeJobReference(event.pk, job.pk)


@transaction.atomic
def create_operational_notice_job(notice) -> PawnNoticeJobReference:
    from apps.tenant_apps.notify_v2.models import (
        NotificationEventType,
        NotificationJob,
        NotificationPolicy,
        NotificationRecipient,
        NotificationTemplate,
    )
    from apps.tenant_apps.notify_v2.services import emit_event

    try:
        event_key, name, body = _OPERATIONAL_EVENT_DEFAULTS[notice.notice_kind]
    except KeyError as exc:
        raise ValueError("This Loans operational notice has no delivery workflow.") from exc
    event_type, _ = NotificationEventType.objects.update_or_create(
        key=event_key,
        defaults={
            "name": name,
            "domain": NotificationEventType.Domain.LOAN,
            "description": f"Loans-owned {name.lower()} event.",
            "is_active": True,
        },
    )
    NotificationPolicy.objects.update_or_create(
        event_type=event_type,
        channel="EMAIL",
        defaults={"priority": 100, "is_active": True},
    )
    template, _ = NotificationTemplate.objects.get_or_create(
        event_type=event_type,
        channel="EMAIL",
        locale="en",
        version=1,
        defaults={
            "renderer_type": NotificationTemplate.RendererType.DJANGO,
            "name": name,
            "subject_template": name,
            "body_template": body,
            "is_active": True,
        },
    )
    recipient = NotificationRecipient.objects.create(
        name_snapshot=notice.recipient_name,
        email=notice.recipient_email,
    )
    source = notice.source_license or notice.source_verification_observation
    source_model = "LoanLicense" if notice.source_license_id else "PawnPhysicalVerificationObservation"
    event = emit_event(
        recipient=recipient,
        event_type=event_type,
        payload=notice.payload_snapshot,
        source_app="loans",
        source_model=source_model,
        source_pk=source.pk,
        dedupe_key=f"loans-operational-notice:{notice.pk}",
    )
    job = NotificationJob.objects.create(
        event=event,
        channel="EMAIL",
        template=template,
        scheduled_for=notice.scheduled_for,
    )
    return PawnNoticeJobReference(event.pk, job.pk)


def deliver_pawn_notice_job(job_id: int) -> PawnNoticeDeliveryReceipt:
    from apps.tenant_apps.notify_v2.models import NotificationJob
    from apps.tenant_apps.notify_v2.services import dispatch_job

    job = NotificationJob.objects.select_related(
        "event__recipient", "event__event_type", "template"
    ).get(pk=job_id)
    try:
        dispatch_job(job)
    except Exception as exc:
        job.mark_failed(reason=f"Notification delivery failed: {exc}")
    job.refresh_from_db()
    return PawnNoticeDeliveryReceipt(
        status=job.status,
        external_reference=job.provider_message_id,
        failure_reason=job.failure_reason,
        sent_at=job.sent_at,
        attempt_count=job.attempt_count,
        last_attempt_at=job.last_attempt_at,
    )


def get_pawn_notice_delivery_states(job_ids) -> dict[int, PawnNoticeDeliveryState]:
    from apps.tenant_apps.notify_v2.models import NotificationJob

    ids = tuple({int(job_id) for job_id in job_ids if job_id})
    if not ids:
        return {}
    return {
        job.pk: PawnNoticeDeliveryState(
            status=job.status,
            external_reference=job.provider_message_id,
            failure_reason=job.failure_reason,
            sent_at=job.sent_at,
            attempt_count=job.attempt_count,
            last_attempt_at=job.last_attempt_at,
        )
        for job in NotificationJob.objects.filter(pk__in=ids)
    }


__all__ = [
    "PawnNoticeDeliveryReceipt",
    "PawnNoticeDeliveryState",
    "PawnNoticeJobReference",
    "create_pawn_notice_job",
    "deliver_pawn_notice_job",
    "get_pawn_notice_delivery_states",
]
