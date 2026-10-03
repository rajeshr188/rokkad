"""Operational paper-book progress; does not certify financial completeness."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.tenancy.models import WorkspaceOwnedModel


class PaperBacklogCheckpoint(WorkspaceOwnedModel):
    book_reference = models.CharField(max_length=160)
    through_date = models.DateField()
    last_page_reference = models.CharField(max_length=160)
    state = models.CharField(max_length=16, choices=(("IN_PROGRESS", "Entry in progress"),
        ("ENTERED", "Entry finished for this book/date"), ("NEEDS_REVIEW", "Needs reconciliation")))
    note = models.CharField(max_length=500, blank=True)
    request_key = models.CharField(max_length=120)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-id",)
        constraints = [models.UniqueConstraint(fields=("workspace", "request_key"), name="loans_backlog_request_unique")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Backlog checkpoints are immutable; record new progress.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Backlog checkpoints cannot be deleted.")
