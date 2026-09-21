"""Immutable provenance and shared identity for accepted historical loan origins."""
import uuid
from django.conf import settings
from django.db import models
from apps.tenancy.models import WorkspaceOwnedModel


class HistoricalLoanImport(WorkspaceOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    loan = models.OneToOneField("loans.PawnLoan", on_delete=models.PROTECT, related_name="historical_import")
    source_namespace = models.UUIDField()
    source_id = models.CharField(max_length=120)
    source_sha256 = models.CharField(max_length=64)
    document = models.JSONField()
    references = models.JSONField()
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "source_namespace", "source_id"], name="loans_history_source_unique")]
