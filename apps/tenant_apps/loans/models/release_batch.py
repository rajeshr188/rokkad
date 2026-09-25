from django.conf import settings
from django.db import models

from apps.tenancy.models import WorkspaceOwnedModel


class PawnReleaseBatch(WorkspaceOwnedModel):
    mode = models.CharField(max_length=12, default="COUNTER", choices=(("COUNTER", "Counter collection"), ("PAPER", "Paper closures")))
    paper_reference = models.CharField(max_length=100, blank=True)
    exception_reason = models.CharField(max_length=255, blank=True)
    request_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    effective_date = models.DateField()
    total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    paid_by = models.CharField(max_length=255)
    payment_reference = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-id",)
        constraints = [
            models.UniqueConstraint(fields=("workspace", "request_key"), name="loans_batch_workspace_request_uniq"),
            models.CheckConstraint(condition=models.Q(total_amount__gte=0), name="loans_batch_total_nonnegative"),
        ]


class PawnReleaseBatchLine(WorkspaceOwnedModel):
    paid_by = models.CharField(max_length=255, blank=True)
    paper_reference = models.CharField(max_length=100, blank=True)
    batch = models.ForeignKey(PawnReleaseBatch, on_delete=models.PROTECT, related_name="lines")
    release = models.OneToOneField("loans.PawnLoanRelease", on_delete=models.PROTECT, related_name="batch_line")
    borrower_name = models.CharField(max_length=255)
    collector_name = models.CharField(max_length=255)
    collector_is_borrower = models.BooleanField()
    relationship = models.CharField(max_length=100, blank=True)
    authorization_note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("id",)


class PaperClosureTransition(WorkspaceOwnedModel):
    """Owner-controlled transition; completed evidence remains immutable."""
    system_first_date = models.DateField(null=True, blank=True)
    retired = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("workspace",), name="loans_paper_transition_workspace_uniq")]
