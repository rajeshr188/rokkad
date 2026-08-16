import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.tenancy.models import WorkspaceOwnedModel


def collateral_photo_upload_to(instance, filename):
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return (
        f"loans/collateral/{instance.collateral_item.public_id}/"
        f"{uuid.uuid4().hex}.{suffix}"
    )


class PawnCollateralPhoto(WorkspaceOwnedModel):
    class WorkflowSource(models.TextChoices):
        DRAFT = "DRAFT", "Draft capture"
        RENEWAL = "RENEWAL", "Release and renew"
        POST_APPROVAL = "POST_APPROVAL", "Post-approval evidence"

    collateral_item = models.ForeignKey(
        "loans.PawnCollateralItem",
        on_delete=models.PROTECT,
        related_name="photos",
    )
    file = models.FileField(upload_to=collateral_photo_upload_to, max_length=500)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField()
    workflow_source = models.CharField(max_length=24, choices=WorkflowSource.choices)
    inherited_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="renewal_copies",
    )
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_collateral_photos_captured",
    )
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("collateral_item_id", "captured_at", "id")
        indexes = [
            models.Index(
                fields=("collateral_item", "captured_at"),
                name="loans_photo_item_time_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Collateral photographs are immutable.")
        if self.inherited_from_id and self.workflow_source != self.WorkflowSource.RENEWAL:
            raise ValidationError("Inherited photographs must be renewal evidence.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Collateral photographs cannot be deleted.")


class PawnCollateralLabelIssue(WorkspaceOwnedModel):
    class Action(models.TextChoices):
        PREVIEW = "PREVIEW", "Preview"
        PRINT = "PRINT", "Print or reprint"

    collateral_item = models.ForeignKey(
        "loans.PawnCollateralItem",
        on_delete=models.PROTECT,
        related_name="label_issues",
    )
    action = models.CharField(max_length=12, choices=Action.choices)
    qr_target = models.CharField(max_length=500)
    payload_sha256 = models.CharField(max_length=64)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pawn_collateral_labels_issued",
    )
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("collateral_item_id", "issued_at", "id")
        indexes = [
            models.Index(
                fields=("collateral_item", "issued_at"),
                name="loans_label_item_time_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Collateral label audit evidence is immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Collateral label audit evidence cannot be deleted.")
