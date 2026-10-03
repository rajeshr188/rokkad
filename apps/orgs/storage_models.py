"""Storage reconciliation evidence, separate from pricing and file deletion."""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenancy.models import WorkspaceOwnedModel


class StorageInventoryRun(models.Model):
    class State(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True)
    state = models.CharField(max_length=12, choices=State.choices, default=State.RUNNING)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    # Scope is a non-secret bucket/location identifier, never credentials or URLs.
    scope = models.CharField(max_length=500)
    totals = models.JSONField(default=dict)
    coverage = models.JSONField(default=dict)
    failure_code = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ("-started_at", "-pk")


class StorageInventoryObject(models.Model):
    """Global physical-object metadata, visible only to the platform operator."""
    run = models.ForeignKey(StorageInventoryRun, on_delete=models.CASCADE, related_name="inventory_objects")
    key = models.CharField(max_length=1024)
    key_digest = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField(default=0)
    modified_at = models.DateTimeField(null=True)
    state = models.CharField(max_length=24)
    category = models.CharField(max_length=40)
    workspace_count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("run", "key_digest"), name="storage_run_object_unique")]
        indexes = [models.Index(fields=("run", "state", "id"), name="storage_review_page_idx")]


class WorkspaceStorageUsage(WorkspaceOwnedModel):
    """Dated, RLS-isolated aggregates; no object paths or customer identifiers."""
    run = models.ForeignKey(StorageInventoryRun, on_delete=models.PROTECT)
    totals = models.JSONField(default=dict)
    categories = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace", "run"), name="storage_workspace_run_unique")]
        ordering = ("-run_id",)
