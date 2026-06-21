from django.db import models
from django.utils import timezone


class GirviPostingEventType(models.TextChoices):
    DISBURSAL = "DISBURSAL", "Disbursal"
    REPAYMENT = "REPAYMENT", "Repayment"
    RELEASE = "RELEASE", "Release"
    ACCRUAL = "ACCRUAL", "Accrual"
    AUCTION_RECOVERY = "AUCTION_RECOVERY", "Auction Recovery"
    SALE_RECOVERY = "SALE_RECOVERY", "Sale Recovery"


class GirviPostingOutboxStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    POSTED = "POSTED", "Posted"
    FAILED = "FAILED", "Failed"
    DEAD_LETTER = "DEAD_LETTER", "Dead Letter"


class GirviPostingOutboxEvent(models.Model):
    """Outbox row for Girvi posting events destined for DEA consumers."""

    event_type = models.CharField(
        max_length=32,
        choices=GirviPostingEventType.choices,
        db_index=True,
    )
    dedupe_key = models.CharField(max_length=128, unique=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=16,
        choices=GirviPostingOutboxStatus.choices,
        default=GirviPostingOutboxStatus.PENDING,
        db_index=True,
    )
    source_app = models.CharField(max_length=64, default="girvi")
    source_model = models.CharField(max_length=64)
    source_pk = models.CharField(max_length=64)
    contract_version = models.PositiveSmallIntegerField(default=1)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(fields=["status", "available_at"]),
            models.Index(fields=["event_type", "status"]),
            models.Index(fields=["source_app", "source_model", "source_pk"]),
        ]

    def __str__(self):
        return f"{self.event_type}#{self.id} [{self.status}]"

    def mark_posted(self):
        self.status = GirviPostingOutboxStatus.POSTED
        self.published_at = timezone.now()
        self.last_error = ""
        self.save(update_fields=["status", "published_at", "last_error", "updated_at"])

    def mark_failed(self, message):
        self.status = GirviPostingOutboxStatus.FAILED
        self.attempt_count = self.attempt_count + 1
        self.last_error = (message or "")[:4000]
        self.save(update_fields=["status", "attempt_count", "last_error", "updated_at"])
