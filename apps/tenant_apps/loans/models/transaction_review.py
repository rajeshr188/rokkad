"""Append-only, loan-scoped confirmation of entered transactions."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from apps.tenancy.models import WorkspaceOwnedModel


class LoanTransactionReview(WorkspaceOwnedModel):
    loan = models.ForeignKey("loans.PawnLoan", on_delete=models.PROTECT, related_name="transaction_reviews")
    through_date = models.DateField()
    confirmed_complete = models.BooleanField()
    source_reference = models.CharField(max_length=500)
    source_fingerprint = models.CharField(max_length=64)
    future_capture = models.CharField(max_length=16, default="PAPER_MIXED",
        choices=(("PAPER_MIXED", "Paper or mixed capture"), ("ROKKAD_ONLY", "All future activity in Rokkad")))
    capture_contract_fingerprint = models.CharField(max_length=64, blank=True, default="")
    capture_state = models.CharField(max_length=16, blank=True, default="")
    capture_event_id = models.PositiveBigIntegerField(null=True, blank=True)
    request_key = models.CharField(max_length=120)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("loan_id", "id")
        constraints = [models.UniqueConstraint(fields=("loan", "request_key"), name="loans_tx_review_request_unique")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Transaction reviews are immutable; record a new review.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Transaction reviews cannot be deleted.")
