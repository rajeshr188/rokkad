"""Consume only envelopes retrieved from the configured private SNS-to-SQS path.

No public HTTP endpoint calls this service. Queue access policy must restrict
SendMessage to the configured SNS topic; runtime can receive/delete, never send.
"""
import json
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Attempt, Delivery, ProviderEvent, Suppression
from .services import recipient_hash


RANK = {Delivery.Status.ACCEPTED: 1, Delivery.Status.FAILED: 2,
        Delivery.Status.DELIVERED: 3, Delivery.Status.BOUNCED: 4, Delivery.Status.COMPLAINT: 5}


@transaction.atomic
def reconcile_sqs_envelope(envelope):
    """Validate source and exact attempt correlation before updating any state."""
    if not settings.PLATFORM_SES_TOPIC_ARN or not settings.PLATFORM_SES_ACCOUNT_ID:
        raise ValidationError("Event source configuration is missing.")
    if (not isinstance(envelope, dict) or envelope.get("Type") != "Notification" or
            envelope.get("TopicArn") != settings.PLATFORM_SES_TOPIC_ARN):
        raise ValidationError("Unexpected event source.")
    event_id = envelope.get("MessageId")
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 255:
        raise ValidationError("Invalid event identity.")
    try:
        event = json.loads(envelope["Message"])
        mail = event["mail"]
        tags = mail["tags"]
        if any(not isinstance(tags[name], list) or len(tags[name]) != 1 or not isinstance(tags[name][0], str)
               for name in ("rokkad_attempt", "rokkad_delivery")):
            raise ValueError
        attempt_id = UUID(tags["rokkad_attempt"][0])
        delivery_id = UUID(tags["rokkad_delivery"][0])
        message_id = mail["messageId"]
        kind = event["eventType"]
        if not isinstance(kind, str):
            raise ValueError
        source_arn = f"arn:aws:ses:{settings.PLATFORM_SES_REGION}:{settings.PLATFORM_SES_ACCOUNT_ID}:identity/{settings.PLATFORM_EMAIL_SENDER_DOMAIN}"
        if (mail["sendingAccountId"] != settings.PLATFORM_SES_ACCOUNT_ID or
                mail["sourceArn"] != source_arn or
                tags["ses:configuration-set"] != [settings.PLATFORM_SES_CONFIGURATION_SET] or
                not isinstance(message_id, str) or not 1 <= len(message_id) <= 255):
            raise ValueError
    except (KeyError, TypeError, ValueError, IndexError):
        raise ValidationError("Invalid SES event correlation.") from None
    row = Delivery.objects.select_for_update().filter(pk=delivery_id).first()
    attempt = Attempt.objects.select_for_update().filter(pk=attempt_id, delivery_id=delivery_id).first()
    if not row or not attempt:
        raise ValidationError("Unknown delivery attempt.")
    if mail.get("destination") != [row.recipient]:
        raise ValidationError("Unexpected event recipient.")
    if attempt.provider_message_id and attempt.provider_message_id != message_id:
        raise ValidationError("Provider message identity mismatch.")
    existing = ProviderEvent.objects.filter(event_id=event_id).first()
    if existing:
        if existing.attempt_id != attempt.pk or existing.kind != kind:
            raise ValidationError("Event identity conflict.")
        return False
    outcome = {"Send": Delivery.Status.ACCEPTED, "Delivery": Delivery.Status.DELIVERED,
               "Reject": Delivery.Status.FAILED, "Rendering Failure": Delivery.Status.FAILED,
               "Bounce": Delivery.Status.BOUNCED, "Complaint": Delivery.Status.COMPLAINT,
               "DeliveryDelay": Delivery.Status.ACCEPTED}.get(kind)
    if outcome is None:
        raise ValidationError("Unsupported SES event type.")
    # Validate affected recipients as well as the envelope destination.
    if kind in {"Bounce", "Complaint"}:
        payload = event.get(kind.lower(), {})
        recipient_key = "bouncedRecipients" if kind == "Bounce" else "complainedRecipients"
        if not isinstance(payload, dict) or not isinstance(payload.get(recipient_key), list):
            raise ValidationError("Invalid feedback recipients.")
        if [r.get("emailAddress") for r in payload.get(recipient_key, []) if isinstance(r, dict)] != [row.recipient]:
            raise ValidationError("Unexpected feedback recipient.")
        if kind == "Complaint" or payload.get("bounceType") == "Permanent":
            Suppression.objects.get_or_create(recipient_hash=recipient_hash(row.recipient), defaults={"reason": kind.lower()})
    ProviderEvent.objects.create(event_id=event_id, attempt=attempt, kind=kind)
    attempt.provider_message_id = message_id
    if RANK.get(outcome, 0) > RANK.get(attempt.status, 0):
        attempt.status = outcome
    attempt.finished_at = timezone.now()
    attempt.save(update_fields=["provider_message_id", "status", "finished_at"])
    if RANK.get(outcome, 0) > RANK.get(row.status, 0):
        row.status, row.last_error = outcome, ""
        row.save(update_fields=["status", "last_error", "updated_at"])
    return True
