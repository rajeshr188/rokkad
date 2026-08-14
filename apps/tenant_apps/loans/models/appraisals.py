from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .core import current_tenant_workspace_id


class CollateralAppraisal(models.Model):
    class Status(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        DISPUTED = "DISPUTED", "Disputed"

    workspace = models.ForeignKey("orgs.Company", on_delete=models.PROTECT, related_name="collateral_appraisals")
    collateral_item = models.ForeignKey("loans.PawnCollateralItem", on_delete=models.PROTECT, related_name="appraisals")
    version = models.PositiveIntegerField()
    effective_at = models.DateTimeField(db_index=True)
    appraised_value = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.APPROVED)
    method = models.CharField(max_length=80)
    evidence_reference = models.CharField(max_length=255, blank=True)
    review_notes = models.TextField(blank=True)
    supersedes = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="collateral_appraisals_created")

    class Meta:
        ordering = ("collateral_item_id", "version")
        constraints = [
            models.UniqueConstraint(fields=("collateral_item", "version"), name="loans_appraisal_item_version_uniq"),
            models.CheckConstraint(condition=Q(appraised_value__gt=0), name="loans_appraisal_value_positive"),
        ]
        indexes = [models.Index(fields=("workspace", "collateral_item", "effective_at", "status"), name="loans_appraisal_asof_idx")]

    def clean(self):
        errors = {}
        workspace_id = current_tenant_workspace_id()
        if workspace_id and self.workspace_id != workspace_id:
            errors["workspace"] = "Appraisal must belong to the active workspace."
        if self.collateral_item_id and self.collateral_item.loan.workspace_id != self.workspace_id:
            errors["collateral_item"] = "Collateral must belong to the appraisal workspace."
        if self.supersedes_id and self.supersedes.collateral_item_id != self.collateral_item_id:
            errors["supersedes"] = "An appraisal can supersede evidence for the same item only."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("CollateralAppraisal is immutable; create a new version.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("CollateralAppraisal is immutable and cannot be deleted.")
