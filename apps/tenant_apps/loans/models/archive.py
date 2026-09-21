"""Accepted source evidence, deliberately unrelated to operational loan rows."""
import uuid
from django.conf import settings
from django.db import models
from apps.tenancy.models import WorkspaceOwnedModel


class HistoricalLoanEvidence(WorkspaceOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source_namespace = models.UUIDField()
    source_system = models.CharField(max_length=120)
    source_id = models.CharField(max_length=255)
    source_sha256 = models.CharField(max_length=64)
    document = models.JSONField()
    review = models.JSONField()
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["workspace", "source_namespace", "source_system", "source_id", "source_sha256"],
            name="loans_archive_snapshot_unique")]
