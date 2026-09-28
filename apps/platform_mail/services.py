from datetime import timedelta
from email.utils import parseaddr
from hashlib import sha256
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from invitations.app_settings import app_settings

from .models import Attempt, Delivery, Suppression


MAX_ATTEMPTS = 5


def fingerprint(value):
    return sha256(value.encode("utf-8")).hexdigest()


def recipient_hash(value):
    return fingerprint(value.strip().casefold())


@transaction.atomic
def enqueue_invitation(invitation):
    from apps.orgs.models import CompanyInvitation
    locked = CompanyInvitation.objects.select_for_update().get(pk=invitation.pk)
    existing = Delivery.objects.filter(invitation=locked).first()
    if existing:
        return existing
    if not locked.is_pending:
        raise ValidationError("Only a current pending invitation can be queued.")
    # Preserve the package's expiry contract. 'sent' starts link validity, not
    # delivery proof; the separate delivery state is the only mail status.
    if not locked.sent:
        locked.sent = timezone.now()
        locked.save(update_fields=["sent"])
    invitation.sent = locked.sent
    return Delivery.objects.create(
        key=f"invitation:{locked.pk}", invitation=locked, recipient=locked.email,
        source_fingerprint=fingerprint(locked.key),
        expires_at=locked.sent + timedelta(days=app_settings.INVITATION_EXPIRY),
    )


def enqueue_receipt(invoice):
    row, _ = Delivery.objects.get_or_create(key=f"receipt:{invoice.pk}", defaults={
        "invoice": invoice, "recipient": invoice.billing_contact_email or "",
        "status": Delivery.Status.QUEUED if invoice.billing_contact_email else Delivery.Status.FAILED,
        "last_error": "" if invoice.billing_contact_email else "missing_recipient",
    })
    return row


def source_problem(row):
    if row.expires_at and row.expires_at <= timezone.now():
        return "expired"
    if row.invitation_id:
        inv = row.invitation
        if not inv.is_pending or fingerprint(inv.key) != row.source_fingerprint:
            return "invitation_no_longer_valid"
        if inv.email.casefold() != row.recipient.casefold():
            return "recipient_changed"
        from apps.orgs.services.workspace_roles import role_grant_fingerprint
        if not inv.role_fingerprint or inv.role_fingerprint != role_grant_fingerprint(inv.company_id, inv.role_id):
            return "invitation_role_changed"
        if not inv.inviter_id:
            return "inviter_missing"
        if inv.inviter_id:
            from apps.orgs.services import role_policy
            try:
                role_policy.assert_can_invite_role(actor=inv.inviter, workspace=inv.company, role=inv.role)
            except (ValidationError, PermissionDenied):
                return "inviter_no_longer_authorized"
    elif row.invoice.status != "paid":
        return "invoice_not_paid"
    return ""


def render_delivery(row):
    """Render committed source data at dispatch; never persist token-bearing bodies."""
    origin = getattr(settings, "PLATFORM_EMAIL_BASE_URL", "").rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValidationError("canonical_https_origin_required")
    validate_email(row.recipient)
    if row.invitation_id:
        inv = row.invitation
        context = {"invitation": inv, "expires_at": row.expires_at,
                   "invite_url": origin + reverse("team_accept_invitation", kwargs={"key": inv.key})}
        subject = f"Invitation to {inv.company.name} on Rokkad"
        html = render_to_string("platform_mail/invitation.html", context)
        text = render_to_string("platform_mail/invitation.txt", context)
        sender, reply = settings.DEFAULT_FROM_EMAIL, settings.PLATFORM_EMAIL_REPLY_TO
    else:
        from apps.subscriptions.provider_configuration import invoice_mode
        mode = invoice_mode(row.invoice)
        subject = f"Rokkad payment received: {row.invoice.invoice_number}"
        if mode == "test":
            subject = "[TEST] " + subject
        html = render_to_string("subscriptions/emails/subscription_confirmation.html", {"invoice": row.invoice, "billing_provider_mode": mode})
        text = strip_tags(html)
        sender, reply = settings.BILLING_EMAIL_SENDER, settings.BILLING_EMAIL_REPLY_TO
    # Headers are neither free-form UI content nor tenant-controlled sender identities.
    for value in (sender, reply):
        if "\n" in value or "\r" in value:
            raise ValidationError("invalid_sender")
        validate_email(parseaddr(value)[1])
    if parseaddr(sender)[1].rsplit("@", 1)[-1].lower() != settings.PLATFORM_EMAIL_SENDER_DOMAIN:
        raise ValidationError("unverified_sender_domain")
    return {"subject": " ".join(subject.splitlines()), "text": text, "html": html,
            "sender": sender, "reply_to": reply, "recipient": row.recipient}


@transaction.atomic
def retry_delivery(delivery_id, *, actor):
    from apps.orgs.audit import AuditLog
    from apps.orgs.services import role_policy
    from apps.subscriptions.checkout import require_billing_owner
    row = Delivery.objects.select_for_update().get(pk=delivery_id)
    if row.invitation_id:
        inv = row.invitation
        role_policy.assert_can_invite_role(actor=actor, workspace=inv.company, role=inv.role)
        company = inv.company
    else:
        company = row.invoice.subscription.company
        require_billing_owner(workspace=company, actor=actor)
    if row.status not in (Delivery.Status.FAILED, Delivery.Status.CAPTURED):
        raise ValidationError("Only failed or preview-only mail can be retried. Uncertain sends need provider reconciliation.")
    if source_problem(row) or Suppression.objects.filter(recipient_hash=recipient_hash(row.recipient)).exists():
        raise ValidationError("This message is expired, no longer valid, or its recipient is suppressed.")
    if row.attempt_count >= MAX_ATTEMPTS:
        raise ValidationError("The delivery attempt limit has been reached. Contact platform support.")
    row.status, row.last_error, row.available_at = Delivery.Status.QUEUED, "", timezone.now()
    row.save(update_fields=["status", "last_error", "available_at", "updated_at"])
    AuditLog.log("EMAIL_RETRY", user=actor, company=company, description="Queued platform email retry",
                 data={"delivery_id": str(row.pk)}, success=True)
    return row


def dispatch_one(delivery_id, *, capture=False):
    from .transport import send_ses, TransportFailure
    if not capture and not settings.PLATFORM_EMAIL_ENABLED:
        raise ValidationError("Platform email sending is disabled.")
    if not capture:
        from .readiness import assess_platform_mail
        if not assess_platform_mail()["configuration_ready"]:
            raise ValidationError("Platform email configuration is incomplete. Run check_platform_mail privately.")
    with transaction.atomic(durable=True):
        row = Delivery.objects.select_for_update().get(pk=delivery_id)
        if row.status != Delivery.Status.QUEUED or row.available_at > timezone.now():
            return row.status
        if row.invoice_id and not capture:
            from apps.subscriptions.provider_configuration import invoice_mode
            if getattr(settings, "BILLING_PROVIDER_MODE", "disabled") != "live" or invoice_mode(row.invoice) != "live":
                raise ValidationError("Test or unclassified payment receipts require a separate controlled delivery rehearsal.")
        problem = source_problem(row)
        if problem:
            row.status, row.last_error = Delivery.Status.CANCELLED, problem
        elif Suppression.objects.filter(recipient_hash=recipient_hash(row.recipient)).exists():
            row.status, row.last_error = Delivery.Status.SUPPRESSED, "recipient_suppressed"
        elif row.attempt_count >= MAX_ATTEMPTS:
            row.status, row.last_error = Delivery.Status.FAILED, "attempt_limit"
        else:
            try:
                message = render_delivery(row)
            except ValidationError:
                row.status, row.last_error = Delivery.Status.FAILED, "invalid_message_configuration"
            else:
                if capture:
                    row.status = Delivery.Status.CAPTURED
                else:
                    row.status = Delivery.Status.SENDING
                    row.attempt_count += 1
                    attempt = Attempt.objects.create(delivery=row)
        row.save(update_fields=["status", "last_error", "attempt_count", "updated_at"])
        if row.status != Delivery.Status.SENDING:
            return row.status
    # Network I/O must not hold the business/claim transaction open.
    try:
        message_id = send_ses(message, delivery_id=row.pk, attempt_id=attempt.pk)
        outcome, code, retryable = Delivery.Status.ACCEPTED, "", False
    except TransportFailure as exc:
        message_id = None
        outcome, code, retryable = exc.outcome, exc.code, exc.retryable
    with transaction.atomic():
        row = Delivery.objects.select_for_update().get(pk=row.pk)
        attempt = Attempt.objects.select_for_update().get(pk=attempt.pk)
        # Feedback may arrive before the API response. Never downgrade that proof.
        if attempt.status != Delivery.Status.SENDING:
            return row.status
        attempt.status, attempt.error_code = outcome, code
        attempt.provider_message_id, attempt.finished_at = message_id, timezone.now()
        attempt.save()
        if retryable and row.attempt_count < MAX_ATTEMPTS:
            row.status = Delivery.Status.QUEUED
            row.available_at = timezone.now() + timedelta(minutes=2 ** row.attempt_count)
        else:
            row.status = outcome
        row.last_error = code
        row.save(update_fields=["status", "last_error", "available_at", "updated_at"])
    return row.status


@transaction.atomic
def recover_stale_sends():
    cutoff = timezone.now() - timedelta(minutes=10)
    rows = Delivery.objects.select_for_update().filter(status=Delivery.Status.SENDING, updated_at__lt=cutoff)
    count = 0
    for row in rows:
        row.status, row.last_error = Delivery.Status.UNKNOWN, "worker_interrupted"
        row.save(update_fields=["status", "last_error", "updated_at"])
        row.attempts.filter(status=Delivery.Status.SENDING).update(
            status=Delivery.Status.UNKNOWN, error_code="worker_interrupted", finished_at=timezone.now())
        count += 1
    return count
