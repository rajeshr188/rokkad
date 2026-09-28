"""Private operator workflows for the global platform-mail queue."""
import re
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Min
from django.utils import timezone

from .models import Delivery, Suppression
from .services import recipient_hash, source_problem


@transaction.atomic
def suppress_recipient(*, operator, recipient, reference):
    # CLI-only: authority comes from privileged deployment access, not membership.
    # Never expose this helper through an ordinary workspace endpoint.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}", operator or ""):
        raise ValidationError("A deployment operator identifier is required.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}", reference or ""):
        raise ValidationError("Use a 3-80 character request reference, not message content.")
    address = recipient.strip().casefold()
    validate_email(address)
    digest = recipient_hash(address)
    row, created = Suppression.objects.get_or_create(
        recipient_hash=digest, defaults={"reason": "recipient_request"})
    from apps.orgs.audit import AuditLog
    AuditLog.log("SETTINGS_UPDATE", user=None,
        description="Platform mail recipient suppression requested",
        data={"operation": "platform_mail_suppress", "operator": operator, "recipient_hash": digest,
              "reference": reference, "created": created})
    return row, created


def queue_health(*, since=None, review_limit=200):
    """No sends, mutations, message bodies, tokens or recipient addresses."""
    now = timezone.now()
    since = since or now - timedelta(hours=24)
    rows = Delivery.objects.all()
    counts = dict(rows.values_list("status").annotate(total=Count("pk")))
    queued = rows.filter(status=Delivery.Status.QUEUED)
    due = queued.filter(available_at__lte=now)
    oldest = due.aggregate(value=Min("available_at"))["value"]
    flags = []
    if rows.filter(status=Delivery.Status.UNKNOWN).exists():
        flags.append("uncertain_acceptance")
    if rows.filter(status=Delivery.Status.SENDING, updated_at__lt=now-timedelta(minutes=10)).exists():
        flags.append("stale_claim")
    if rows.filter(status=Delivery.Status.FAILED).exists():
        flags.append("failed_delivery")
    if settings.PLATFORM_EMAIL_ENABLED and oldest and oldest < now-timedelta(minutes=15):
        flags.append("overdue_queue")
    for status in (Delivery.Status.BOUNCED, Delivery.Status.COMPLAINT):
        if rows.filter(status=status, updated_at__gte=since).exists():
            flags.append("recent_" + status)
    review = []
    for row in queued.order_by("created_at")[:review_limit]:
        problem = source_problem(row)
        if not problem and Suppression.objects.filter(recipient_hash=recipient_hash(row.recipient)).exists():
            problem = "recipient_suppressed"
        if problem:
            review.append({"delivery_id": str(row.pk), "problem": problem})
    return {"sending_enabled": settings.PLATFORM_EMAIL_ENABLED, "counts": counts,
        "due": due.count(), "oldest_due_seconds": int((now-oldest).total_seconds()) if oldest else 0,
        "flags": flags, "queued_source_problems": review,
        "review_truncated": queued.count() > review_limit, "checked_at": now.isoformat()}
