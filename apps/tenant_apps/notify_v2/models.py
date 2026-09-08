from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.models import WorkspaceOwnedModel


def _inherit_workspace(instance, *parents):
    workspace_ids = {parent.workspace_id for parent in parents if parent is not None}
    if len(workspace_ids) > 1:
        raise ValidationError("Related notification records must share a Workspace.")
    parent_workspace_id = next(iter(workspace_ids), None)
    if instance.workspace_id is None:
        instance.workspace_id = parent_workspace_id
    elif parent_workspace_id is not None and instance.workspace_id != parent_workspace_id:
        raise ValidationError("Notification record conflicts with its parent Workspace.")


class TimestampedModel(WorkspaceOwnedModel):
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        abstract = True


class NotificationEventType(TimestampedModel):
    class Domain(models.TextChoices):
        LOAN = "LOAN", "Loan / Girvi"
        SALES = "SALES", "Sales"
        PURCHASE = "PURCHASE", "Purchase"
        INVENTORY = "INVENTORY", "Inventory"
        ACCOUNTING = "ACCOUNTING", "Accounting"
        HR = "HR", "Human Resources"
        GENERAL = "GENERAL", "General"

    key = models.CharField(max_length=100)
    name = models.CharField(max_length=150)
    domain = models.CharField(max_length=20, choices=Domain.choices)
    description = models.TextField(blank=True)
    payload_schema = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["domain", "sort_order", "name"]
        indexes = [
            models.Index(fields=["domain", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "key"],
                name="notify_v2_workspace_event_type_key_uniq",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.key})"


class NotificationChannel(models.TextChoices):
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    LETTER = "LETTER", "Letter"
    POST = "POST", "Post"
    IN_APP = "IN_APP", "In-App"


class WhatsAppCloudIntegration(TimestampedModel):
    """Workspace-owned Meta WhatsApp Cloud API configuration."""

    workspace = models.OneToOneField(
        "orgs.Company", editable=False, on_delete=models.PROTECT,
        related_name="whatsapp_cloud_integration"
    )
    api_version = models.CharField(max_length=16, default="v20.0")
    phone_number_id = models.CharField(max_length=64)
    access_token_ciphertext = models.TextField()
    webhook_verify_token_ciphertext = models.TextField()
    app_secret_ciphertext = models.TextField()
    is_enabled = models.BooleanField(default=False)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="whatsapp_cloud_integrations_updated",
    )

    def __str__(self):
        return f"WhatsApp Cloud for workspace {self.workspace_id}"

    def clean(self):
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class NotificationRenderer(models.TextChoices):
    PDF = "PDF", "PDF"
    DJANGO = "DJANGO", "Django Template"
    TEXT = "TEXT", "Plain Text"
    HTML = "HTML", "HTML"


class NotificationPolicy(TimestampedModel):
    Channel = NotificationChannel

    event_type = models.ForeignKey(
        NotificationEventType,
        on_delete=models.CASCADE,
        related_name="policies",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    priority = models.PositiveIntegerField(default=100)
    is_required = models.BooleanField(default=False)
    batch_enabled = models.BooleanField(
        default=False,
        help_text="Allow operators to generate this policy as part of a batch print/post run.",
    )
    cooldown_rule = models.JSONField(default=dict, blank=True)
    schedule_rule = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["event_type", "priority", "channel"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "event_type", "channel"],
                name="notify_v2_unique_policy_per_event_channel",
            )
        ]

    def save(self, *args, **kwargs):
        _inherit_workspace(self, self.event_type)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event_type.key} → {self.get_channel_display()}"


class NotificationRecipient(TimestampedModel):
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="notify_v2_recipients",
        null=True,
        blank=True,
        help_text="Canonical Party receiving this notification when it represents a business counterparty.",
    )
    name_snapshot = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    postal_address_json = models.JSONField(default=dict, blank=True)
    preferred_locale = models.CharField(max_length=10, default="en")
    consent_flags = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name_snapshot", "id"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["party", "is_active"]),
        ]

    def __str__(self):
        return self.name_snapshot or f"Recipient {self.pk}"

    def save(self, *args, **kwargs):
        _inherit_workspace(self, self.party if self.party_id else None)
        return super().save(*args, **kwargs)

class NotificationTemplate(TimestampedModel):
    Channel = NotificationChannel
    RendererType = NotificationRenderer

    event_type = models.ForeignKey(
        NotificationEventType,
        on_delete=models.CASCADE,
        related_name="templates",
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    locale = models.CharField(max_length=10, default="en")
    renderer_type = models.CharField(
        max_length=20,
        choices=RendererType.choices,
        default=RendererType.DJANGO,
    )
    name = models.CharField(max_length=150)
    subject_template = models.CharField(max_length=200, blank=True)
    body_template = models.TextField(blank=True)
    layout_key = models.CharField(max_length=100, blank=True)
    sample_payload = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["event_type", "channel", "locale", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "event_type", "channel", "locale", "version"],
                name="notify_v2_unique_template_version",
            )
        ]

    def save(self, *args, **kwargs):
        _inherit_workspace(self, self.event_type)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event_type.key} [{self.channel}] v{self.version}"


class NotificationBatch(TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        RENDERED = "RENDERED", "Rendered"
        PRINTED = "PRINTED", "Printed"
        POSTED = "POSTED", "Posted"
        CANCELLED = "CANCELLED", "Cancelled"

    event_type = models.ForeignKey(
        NotificationEventType,
        on_delete=models.PROTECT,
        related_name="batches",
    )
    name = models.CharField(max_length=150)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="notify_v2_batches",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    job_count = models.PositiveIntegerField(default=0)
    selection_snapshot = models.JSONField(
        default=list,
        blank=True,
        help_text="Original source selection (for example loan ids) used to create this batch.",
    )
    printed_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["status", "created"])]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("workspace_notify:notify_v2_batch_detail", args=[self.workspace.slug, self.pk])

    def save(self, *args, **kwargs):
        _inherit_workspace(self, self.event_type)
        return super().save(*args, **kwargs)

    def mark_rendered(self, *, save=True):
        self.status = self.Status.RENDERED
        if save:
            self.save(update_fields=["status", "modified"])
        return self

    def mark_printed(self, *, save=True):
        now = timezone.now()
        self.status = self.Status.PRINTED
        self.printed_at = now
        if save:
            self.save(update_fields=["status", "printed_at", "modified"])
        return self

    def mark_posted(self, *, save=True):
        now = timezone.now()
        if not self.printed_at:
            self.printed_at = now
        self.status = self.Status.POSTED
        self.posted_at = now
        if save:
            self.save(update_fields=["status", "printed_at", "posted_at", "modified"])
        return self


class NotificationEvent(TimestampedModel):
    event_type = models.ForeignKey(
        NotificationEventType,
        on_delete=models.PROTECT,
        related_name="events",
    )
    recipient = models.ForeignKey(
        NotificationRecipient,
        on_delete=models.PROTECT,
        related_name="events",
    )
    batch = models.ForeignKey(
        NotificationBatch,
        on_delete=models.SET_NULL,
        related_name="events",
        null=True,
        blank=True,
    )
    source_app = models.CharField(max_length=50, blank=True)
    source_model = models.CharField(max_length=100, blank=True)
    source_pk = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta:
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["event_type", "created"]),
        ]

    def __str__(self):
        return f"{self.event_type.key} for {self.recipient}"

    def save(self, *args, **kwargs):
        _inherit_workspace(
            self,
            self.event_type,
            self.recipient,
            self.batch if self.batch_id else None,
        )
        return super().save(*args, **kwargs)


class NotificationJob(TimestampedModel):
    Channel = NotificationChannel

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        RENDERED = "RENDERED", "Rendered"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    event = models.ForeignKey(
        NotificationEvent,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    batch = models.ForeignKey(
        NotificationBatch,
        on_delete=models.SET_NULL,
        related_name="jobs",
        null=True,
        blank=True,
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        related_name="jobs",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    provider_message_id = models.CharField(max_length=150, blank=True)
    failure_reason = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["scheduled_for", "created"]
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "event", "channel"],
                name="notify_v2_unique_job_per_event_channel",
            ),
            models.UniqueConstraint(
                fields=["workspace", "provider_message_id"],
                condition=models.Q(channel="WHATSAPP") & ~models.Q(provider_message_id=""),
                name="notify_v2_unique_whatsapp_provider_id",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "scheduled_for"]),
        ]

    def __str__(self):
        return f"{self.event.event_type.key} [{self.channel}]"

    def save(self, *args, **kwargs):
        _inherit_workspace(
            self,
            self.event,
            self.batch if self.batch_id else None,
            self.template if self.template_id else None,
        )
        return super().save(*args, **kwargs)

    def _record_transition(self, *, to_status, message="", provider_payload=None, save=True):
        previous_status = self.status
        self.status = to_status
        self.attempt_count += 1
        self.last_attempt_at = timezone.now()
        if to_status == self.Status.SENT and not self.sent_at:
            self.sent_at = self.last_attempt_at
        if save:
            self.save(
                update_fields=[
                    "status",
                    "attempt_count",
                    "last_attempt_at",
                    "sent_at",
                    "provider_message_id",
                    "failure_reason",
                    "modified",
                ]
            )
        log_payload = {
            "job": self,
            "attempt_number": self.attempt_count,
            "status_before": previous_status,
            "status_after": to_status,
            "message": message,
            "provider_payload": provider_payload or {},
        }
        if save and self.pk:
            return NotificationAttemptLog.objects.create(**log_payload)
        return NotificationAttemptLog(**log_payload)

    def mark_rendered(self, *, message="", save=True):
        return self._record_transition(
            to_status=self.Status.RENDERED,
            message=message or "Artifact rendered.",
            save=save,
        )

    def mark_sent(self, *, message="", provider_payload=None, save=True):
        self.failure_reason = ""
        return self._record_transition(
            to_status=self.Status.SENT,
            message=message or "Notification dispatched.",
            provider_payload=provider_payload,
            save=save,
        )

    def mark_failed(self, *, reason, provider_payload=None, save=True):
        self.failure_reason = reason
        return self._record_transition(
            to_status=self.Status.FAILED,
            message=reason,
            provider_payload=provider_payload,
            save=save,
        )


class NotificationArtifact(TimestampedModel):
    class ArtifactType(models.TextChoices):
        PDF = "PDF", "PDF"
        HTML = "HTML", "HTML"
        TEXT = "TEXT", "Text"

    job = models.ForeignKey(
        NotificationJob,
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    artifact_type = models.CharField(max_length=10, choices=ArtifactType.choices)
    file = models.FileField(upload_to="notify_v2/artifacts/", null=True, blank=True)
    rendered_text = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["job", "artifact_type", "-created"]

    def save(self, *args, **kwargs):
        _inherit_workspace(self, self.job)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job} → {self.artifact_type}"


class NotificationAttemptLog(WorkspaceOwnedModel):
    job = models.ForeignKey(
        NotificationJob,
        on_delete=models.CASCADE,
        related_name="attempt_logs",
    )
    attempt_number = models.PositiveIntegerField(default=1)
    status_before = models.CharField(max_length=20, blank=True)
    status_after = models.CharField(max_length=20)
    message = models.TextField(blank=True)
    provider_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ["job", "attempt_number", "created_at"]

    def __str__(self):
        return f"Attempt {self.attempt_number} for job {self.job_id}"

    def save(self, *args, **kwargs):
        _inherit_workspace(self, self.job)
        return super().save(*args, **kwargs)


class WhatsAppCloudWebhookReceipt(WorkspaceOwnedModel):
    """Replay-safe tenant evidence for one authenticated Cloud API status event."""

    class ProcessingStatus(models.TextChoices):
        PROCESSED = "PROCESSED", "Processed"
        UNKNOWN_JOB = "UNKNOWN_JOB", "Unknown job"

    event_key = models.CharField(max_length=64)
    payload_hash = models.CharField(max_length=64)
    phone_number_id = models.CharField(max_length=64)
    provider_message_id = models.CharField(max_length=150, db_index=True)
    external_status = models.CharField(max_length=32)
    provider_timestamp = models.CharField(max_length=32, blank=True)
    signature_digest = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    job = models.ForeignKey(
        NotificationJob,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="whatsapp_webhook_receipts",
    )
    processing_status = models.CharField(max_length=16, choices=ProcessingStatus.choices)
    duplicate_count = models.PositiveIntegerField(default=0)
    received_at = models.DateTimeField(auto_now_add=True)
    last_received_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-received_at", "-pk")
        indexes = [
            models.Index(fields=("processing_status", "received_at"), name="notify_wa_receipt_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "event_key"),
                name="notify_v2_workspace_webhook_event_uniq",
            )
        ]

    def save(self, *args, **kwargs):
        _inherit_workspace(self, self.job if self.job_id else None)
        return super().save(*args, **kwargs)
