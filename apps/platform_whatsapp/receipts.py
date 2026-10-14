"""Authenticated evidence is global until an explicit scoped attempt proves a match."""
from datetime import datetime, timedelta, timezone as dt_timezone
import re

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from .intents import fingerprint
from .models import Attempt, ProviderReceipt, ReceiptLink
from .phones import normalize_phone
from .services import digest
from .transport import valid_message_id


def parse_status(value, *, phone_id, waba_id):
    if not isinstance(value, dict) or not valid_message_id(value.get("id")):
        raise ValueError("invalid_status_id")
    status = value.get("status")
    if status not in ProviderReceipt.Status.values:
        raise ValueError("invalid_status")
    recipient = value.get("recipient_id")
    if not isinstance(recipient, str) or not re.fullmatch(r"[0-9]{7,15}", recipient):
        raise ValueError("invalid_status_recipient")
    phone = normalize_phone("+" + recipient)
    stamp = value.get("timestamp")
    if not isinstance(stamp, str) or not re.fullmatch(r"[0-9]{1,12}", stamp):
        raise ValueError("invalid_status_time")
    at = datetime.fromtimestamp(int(stamp), tz=dt_timezone.utc)
    if at > timezone.now()+timedelta(minutes=5):
        raise ValueError("future_status_time")
    errors = value.get("errors", [])
    if not isinstance(errors, list) or len(errors) > 5 or any(not isinstance(e, dict) or
            type(e.get("code")) is not int or not 0 <= e["code"] <= 2147483647 for e in errors):
        raise ValueError("invalid_status_errors")
    pricing = value.get("pricing", {})
    if not isinstance(pricing, dict):
        raise ValueError("invalid_status_pricing")
    category, model, billable = pricing.get("category", ""), pricing.get("pricing_model", ""), pricing.get("billable")
    if not isinstance(category, str) or len(category) > 32 or not isinstance(model, str) or len(model) > 24:
        raise ValueError("invalid_pricing_fields")
    if category not in {"", "utility", "authentication", "authentication_international", "marketing", "service"}:
        category = "unknown"  # Preserve delivery proof without retaining arbitrary provider text.
    if model not in {"", "CBP", "PMP"}:
        model = "unknown"
    if billable is not None and type(billable) is not bool:
        raise ValueError("invalid_pricing_model")
    facts = {"phone_id": phone_id, "waba_id": waba_id, "provider_message_id": value["id"],
             "recipient_hash": digest(phone), "status": status, "provider_at": at.isoformat(),
             "error_codes": sorted({e["code"] for e in errors}), "pricing_category": category,
             "pricing_model": model, "billable": billable}
    result = {**facts, "provider_at": at}
    result["event_digest"] = fingerprint(facts)
    return result


def record_receipt(facts):
    """Internal only: HTTP boundary authenticates and validates the whole batch first."""
    if current_workspace_id() is not None:
        raise PermissionDenied("Provider receipt ingestion requires global context.")
    row, _ = ProviderReceipt.objects.get_or_create(event_digest=facts["event_digest"],
        defaults={key: value for key,value in facts.items() if key != "event_digest"})
    return row


def reconcile_attempt(attempt):
    if current_workspace_id() != attempt.workspace_id:
        raise PermissionDenied("Explicit matching Workspace context required.")
    if not attempt.provider_message_id:
        return 0
    receipts = ProviderReceipt.objects.filter(phone_id=attempt.phone_id, waba_id=attempt.waba_id,
        provider_message_id=attempt.provider_message_id,
        recipient_hash=digest(attempt.delivery.recipient_phone),
        provider_at__gte=attempt.claimed_at-timedelta(minutes=5), match__isnull=True).order_by("pk")[:100]
    count = 0
    for receipt in receipts:
        _, created = ReceiptLink.objects.get_or_create(receipt=receipt,
            defaults={"workspace_id": attempt.workspace_id, "attempt": attempt})
        from .controls import reconcile_cost
        reconcile_cost(attempt, receipt)
        count += created
    return count


def attempt_summary(attempt):
    """Read-only projection; a late failure never erases delivery/read evidence."""
    if current_workspace_id() != attempt.workspace_id:
        raise PermissionDenied("Explicit matching Workspace context required.")
    statuses = set(attempt.receipt_links.values_list("receipt__status", flat=True))
    status = attempt.outcome
    if "read" in statuses:
        status = "read"
    elif "delivered" in statuses:
        status = "delivered"
    elif "failed" in statuses:
        status = "failed"
    elif "sent" in statuses:
        status = "sent"
    return {"status": status, "conflict": bool("failed" in statuses and statuses & {"sent", "delivered", "read"}),
            "deleted": "deleted" in statuses, "attempt_id": str(attempt.pk)}


def delivery_summary(delivery):
    if current_workspace_id() != delivery.workspace_id:
        raise PermissionDenied("Explicit matching Workspace context required.")
    if delivery.capture_only:
        return {"status": "captured", "conflict": False}
    attempts = list(delivery.attempts.order_by("number"))
    if not attempts:
        return {"status": "queued", "conflict": False}
    summaries = [attempt_summary(attempt) for attempt in attempts]
    # Preserve any confirmed delivery across attempts as well as callback order.
    for proven in ("read", "delivered"):
        if any(row["status"] == proven for row in summaries):
            return {"status": proven, "conflict": any(row["conflict"] or row["status"] == "failed" for row in summaries)}
    return summaries[-1]
