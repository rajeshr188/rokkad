"""Accepted source evidence, deliberately unrelated to operational loan rows."""
import uuid
from django.conf import settings
from django.db import models
from apps.tenancy.models import WorkspaceOwnedModel
from django.core.exceptions import ValidationError
from django_cleanup import cleanup


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


@cleanup.ignore
class HistoricalLoanAttachment(WorkspaceOwnedModel):
    """Append-only media sidecar; the accepted source document is never edited."""
    evidence = models.ForeignKey(HistoricalLoanEvidence, on_delete=models.PROTECT, related_name="attachments")
    file = models.FileField(max_length=500)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField()
    source_evidence = models.JSONField()
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    imported_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_blank_legacy_image(self):
        from helpers.legacy_media import BLANK_LEGACY_IMAGE_SHA256
        return self.sha256 in BLANK_LEGACY_IMAGE_SHA256

    def save(self, *args, **kwargs):
        if self.pk or self.evidence.workspace_id != self.workspace_id:
            raise ValidationError("Historical media is immutable and must belong to its evidence Workspace.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical media is immutable.")
