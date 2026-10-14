"""Commit the claim before IO; never promote captured history or retry uncertainty."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, IntegrityError, transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.checks import check_restricted_runtime_role
from apps.tenancy.context import current_workspace_id, workspace_context
from .configuration import template_mapping, transport_blockers, transport_fingerprint
from .intents import _paid_facts, _render, _trial_facts, fingerprint
from .models import Attempt, Contact, Delivery
from .controls import reserve, check_reservation, next_window
from .receipts import attempt_summary, reconcile_attempt, delivery_summary
from .transport import send_cloud, TransportFailure

CLAIM_LIFETIME = timedelta(minutes=5)


def _standalone():
    if connection.in_atomic_block or current_workspace_id() is not None:
        raise PermissionDenied("Dispatch/reconciliation must start outside a caller transaction and Workspace context.")
    if check_restricted_runtime_role(None, databases=["default"]):
        raise PermissionDenied("A restricted runtime database role is required.")


def _message(row):
    rendered = _render(row)
    if not rendered["eligible"] or row.capture_only:
        raise ValidationError("source_or_consent_unavailable")
    if row.purpose == "paid" and row.provider_mode != "live":
        raise ValidationError("test_payment_not_chargeable_message")
    mapping = template_mapping(row.purpose, row.template_revision)
    if row.purpose == "setup":
        params = [row.workspace_name, rendered["link"]]
    elif row.purpose in {"trial", "ending"}:
        end = (row.reminder.trial_end if row.purpose == "ending"
               else datetime.fromisoformat(_trial_facts(row.trial_event)["trial_end"]))
        params = [row.workspace_name, timezone.localtime(end).strftime("%d %b %Y, %H:%M %Z"), rendered["link"]]
    elif row.purpose == "service":
        source = row.announcement_target.announcement
        params = [source.text, timezone.localtime(source.impact_start).strftime("%d %b %Y, %H:%M %Z"),
            timezone.localtime(source.impact_end).strftime("%d %b %Y, %H:%M %Z"), rendered["link"]]
    else:
        facts = _paid_facts(row.invoice)
        params = [facts["amount"], facts["invoice_number"], rendered["link"]]
    if any(not value or len(value) > 1024 for value in params):
        raise ValidationError("invalid_template_parameters")
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual",
        "to": row.recipient_phone.lstrip("+"), "type": "template",
        "template": {"name": mapping["name"], "language": {"code": mapping["language"]},
                     "components": [{"type": "body", "parameters": [{"type": "text", "text": value} for value in params]}]}}
    return payload, mapping


def _locked_delivery(workspace_id, delivery_id):
    # Consistent Company -> Contact -> Delivery lock order, matching owner choices.
    workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
    row = Delivery.objects.select_related("workspace__owner", "setup_request", "trial_event__subscription",
        "invoice__subscription", "reminder__trial_event__subscription", "announcement_target__announcement").get(pk=delivery_id, workspace=workspace)
    Contact.objects.select_for_update().get(pk=row.contact_id)
    return Delivery.objects.select_for_update(of=("self",)).select_related("workspace__owner", "setup_request",
        "trial_event__subscription", "invoice__subscription", "reminder__trial_event__subscription", "announcement_target__announcement").get(pk=row.pk)


@contextmanager
def _locked_scope(workspace_id, delivery_id):
    # The broadcast is a global control-plane job with successive scoped units.
    # Never replace or suspend an active Workspace identity to inspect another.
    with transaction.atomic(durable=True):
        with workspace_context(workspace_id):
            peek = Delivery.objects.select_related("announcement_target__announcement").get(
                pk=delivery_id, workspace_id=workspace_id)
        current = True
        if peek.purpose == "service" and not peek.capture_only:
            target = peek.announcement_target
            ids = [v["workspace_id"] for v in target.announcement.affected_workspaces
                if v["eligible"] and v["owner_id"] == target.owner_id]
            list(Company.all_objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            Contact.objects.select_for_update().get(pk=peek.contact_id)
            from .announcements import announcement_current
            current = announcement_current(target)
        with workspace_context(workspace_id):
            yield _locked_delivery(workspace_id, delivery_id), current


def _claim(workspace_id, delivery_id):
    with _locked_scope(workspace_id, delivery_id) as (row, group_current):
        if row.capture_only:
            return None, "captured"
        previous = row.attempts.order_by("-number").first()
        if previous:
            reconcile_attempt(previous)
            summary = delivery_summary(row)
            if (previous.outcome != Attempt.Outcome.REJECTED or not previous.retryable
                    or summary["status"] in {"read", "delivered", "sent", "failed"}
                    or previous.number >= 3):
                return None, summary["status"]
            if timezone.now() < previous.finished_at+timedelta(minutes=previous.number):
                return None, "backoff"
        if not group_current:
            raise ValidationError("service_group_review_changed")
        payload, mapping = _message(row)
        now = timezone.now()
        attempt_id = uuid.uuid4()
        reserve(row, attempt_id, at=now)
        attempt = Attempt.objects.create(id=attempt_id, workspace_id=workspace_id, delivery=row,
            number=previous.number+1 if previous else 1, claimed_at=now,
            phone_id=settings.PLATFORM_WHATSAPP_PHONE_ID, waba_id=settings.PLATFORM_WHATSAPP_WABA_ID,
            sender_fingerprint=row.sender_fingerprint, transport_fingerprint=transport_fingerprint(),
            content_fingerprint=fingerprint(payload), template_name=mapping["name"], language=mapping["language"])
        return attempt.pk, "claimed"


def _before_request(workspace_id, attempt_id):
    # Fresh checks immediately before IO; no transaction/lock spans the request.
    with workspace_context(workspace_id):
        delivery_id = Attempt.objects.get(pk=attempt_id).delivery_id
    with _locked_scope(workspace_id, delivery_id) as (row, group_current):
        attempt = Attempt.objects.select_for_update(of=("self",)).select_related("delivery").get(pk=attempt_id)
        if (not group_current or attempt.outcome != Attempt.Outcome.CLAIMED or attempt.claimed_at+CLAIM_LIFETIME <= timezone.now()
                or transport_blockers() or attempt.transport_fingerprint != transport_fingerprint()):
            raise ValidationError("claim_or_configuration_changed")
        check_reservation(attempt)
        payload, _ = _message(row)
        if fingerprint(payload) != attempt.content_fingerprint:
            raise ValidationError("reviewed_content_changed")
        return payload


def _finish(workspace_id, attempt_id, *, outcome, message_id="", diagnostic="", retryable=False, http_status=None):
    with transaction.atomic(durable=True), workspace_context(workspace_id):
        attempt = Attempt.objects.select_for_update(of=("self",)).select_related("delivery").get(pk=attempt_id)
        if attempt.outcome != Attempt.Outcome.CLAIMED:
            return attempt_summary(attempt)["status"]
        attempt.outcome, attempt.provider_message_id = outcome, message_id
        attempt.diagnostic, attempt.retryable, attempt.http_status = diagnostic, retryable, http_status
        attempt.finished_at = timezone.now()
        attempt.save(update_fields=["outcome", "provider_message_id", "diagnostic", "retryable", "http_status", "finished_at"])
        reconcile_attempt(attempt)
        return attempt_summary(attempt)["status"]


def dispatch_one(*, workspace_id, delivery_id):
    _standalone()
    if transport_blockers():
        raise ValidationError("Platform WhatsApp dispatch is disabled or lacks release controls.")
    try:
        attempt_id, status = _claim(workspace_id, delivery_id)
    except ValidationError as exc:
        code = exc.messages[0] if exc.messages else ""
        if code not in {"quiet_hours", "daily_capacity_unavailable"}:
            raise
        with workspace_context(workspace_id):
            row = Delivery.objects.get(pk=delivery_id, workspace_id=workspace_id)
            window = next_window(row, capacity=code == "daily_capacity_unavailable")
            return "deferred" if window else "expired"
    if attempt_id is None:
        return status
    try:
        payload = _before_request(workspace_id, attempt_id)
    except ValidationError:
        return _finish(workspace_id, attempt_id, outcome=Attempt.Outcome.CANCELLED,
                       diagnostic="pre_request_checks_failed")
    try:
        message_id = send_cloud(payload)
    except TransportFailure as failure:
        return _finish(workspace_id, attempt_id, outcome=failure.outcome,
            diagnostic=failure.code, retryable=failure.retryable, http_status=failure.http_status)
    except Exception:
        # Unexpected provider/adapter errors are uncertain, never automatic retry.
        return _finish(workspace_id, attempt_id, outcome=Attempt.Outcome.UNKNOWN,
                       diagnostic="unexpected_transport_uncertainty")
    try:
        return _finish(workspace_id, attempt_id, outcome=Attempt.Outcome.ACCEPTED,
                       message_id=message_id, http_status=200)
    except IntegrityError:
        return _finish(workspace_id, attempt_id, outcome=Attempt.Outcome.UNKNOWN,
                       diagnostic="provider_identity_conflict")


def reconcile_delivery(*, workspace_id, delivery_id, recover_stale=False):
    _standalone()
    with transaction.atomic(durable=True), workspace_context(workspace_id):
        row = Delivery.objects.select_for_update().get(pk=delivery_id, workspace_id=workspace_id)
        for attempt in row.attempts.select_for_update().order_by("number"):
            if (recover_stale and attempt.outcome == Attempt.Outcome.CLAIMED
                    and attempt.claimed_at+CLAIM_LIFETIME <= timezone.now()):
                attempt.outcome, attempt.finished_at = Attempt.Outcome.UNKNOWN, timezone.now()
                attempt.diagnostic = "interrupted_claim_unknown"
                attempt.save(update_fields=["outcome", "finished_at", "diagnostic"])
            reconcile_attempt(attempt)
        return delivery_summary(row)
