"""Control-plane delivery evidence; never stores borrower notification content."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AccountEmail(models.Model):
    """Global identity intent, with no token, message body or Workspace data."""
    class Kind(models.TextChoices):
        VERIFICATION = "verification", "Email verification"
        PASSWORD_RESET = "password_reset", "Password reset"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    email_address = models.ForeignKey("account.EmailAddress", null=True, blank=True,
                                      on_delete=models.SET_NULL)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()


class Delivery(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        CAPTURED = "captured", "Preview only — not sent"
        SENDING = "sending", "Sending"
        ACCEPTED = "accepted", "Accepted by email provider"
        DELIVERED = "delivered", "Delivered to recipient mail server"
        FAILED = "failed", "Failed"
        UNKNOWN = "unknown", "Acceptance uncertain — review required"
        CANCELLED = "cancelled", "Cancelled"
        BOUNCED = "bounced", "Bounced"
        COMPLAINT = "complaint", "Spam complaint"
        SUPPRESSED = "suppressed", "Recipient suppressed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=150, unique=True)
    invitation = models.OneToOneField("orgs.CompanyInvitation", null=True, blank=True,
                                     on_delete=models.PROTECT, related_name="email_delivery")
    invoice = models.OneToOneField("subscriptions.Invoice", null=True, blank=True,
                                  on_delete=models.PROTECT, related_name="email_delivery")
    account_email = models.OneToOneField(AccountEmail, null=True, blank=True,
                                        on_delete=models.PROTECT, related_name="delivery")
    recipient = models.EmailField(blank=True)
    source_fingerprint = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=64, blank=True)
    available_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(models.Q(invitation__isnull=False, invoice__isnull=True, account_email__isnull=True) |
                       models.Q(invitation__isnull=True, invoice__isnull=False, account_email__isnull=True) |
                       models.Q(invitation__isnull=True, invoice__isnull=True, account_email__isnull=False)),
            name="platform_mail_one_source",
        )]
        indexes = [models.Index(fields=["status", "available_at"])]
        default_permissions = ()


class Attempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(Delivery, on_delete=models.PROTECT, related_name="attempts")
    status = models.CharField(max_length=16, default=Delivery.Status.SENDING)
    provider_message_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()


class ProviderEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    attempt = models.ForeignKey(Attempt, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=32)
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()


class Suppression(models.Model):
    recipient_hash = models.CharField(max_length=64, unique=True)
    reason = models.CharField(max_length=32)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
