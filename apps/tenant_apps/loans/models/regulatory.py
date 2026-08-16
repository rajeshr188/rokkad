"""Immutable regulatory evidence for loan licenses."""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.tenancy.models import WorkspaceOwnedModel

from .core import LoanLicense, current_tenant_workspace_id


def loan_license_document_upload(instance, filename):
    safe_name = Path(filename).name
    return (
        f"loans/regulatory/workspace-{instance.license.workspace_id}/"
        f"license-{instance.license_id}/revision-{instance.revision_number}/"
        f"{safe_name}"
    )


class LoanLicenseRevision(WorkspaceOwnedModel):
    class Kind(models.TextChoices):
        INITIAL = "INITIAL", "Initial issue"
        AMENDMENT = "AMENDMENT", "Amendment"
        RENEWAL = "RENEWAL", "Renewal"

    license = models.ForeignKey(
        LoanLicense,
        on_delete=models.PROTECT,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    name = models.CharField(max_length=255)
    license_number = models.CharField(max_length=100)
    issuing_authority = models.CharField(max_length=255, blank=True)
    issued_on = models.DateField()
    expires_on = models.DateField()
    notes = models.TextField(blank=True)
    supporting_document = models.FileField(
        upload_to=loan_license_document_upload,
        blank=True,
    )
    original_filename = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    byte_size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loan_license_revisions_created",
    )

    class Meta:
        ordering = ("license_id", "revision_number")
        constraints = [
            models.UniqueConstraint(
                fields=("license", "revision_number"),
                name="loans_license_revision_number_uniq",
            ),
            models.CheckConstraint(
                condition=Q(revision_number__gt=0),
                name="loans_license_revision_number_positive",
            ),
            models.CheckConstraint(
                condition=Q(expires_on__gte=F("issued_on")),
                name="loans_license_revision_dates_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(supporting_document="", sha256="", byte_size=0)
                    | (
                        ~Q(supporting_document="")
                        & ~Q(sha256="")
                        & Q(byte_size__gt=0)
                    )
                ),
                name="loans_license_revision_document_complete",
            ),
        ]
        indexes = [
            models.Index(
                fields=("license", "-revision_number"),
                name="loans_licrev_latest_idx",
            ),
            models.Index(
                fields=("expires_on", "kind"),
                name="loans_licrev_expiry_idx",
            ),
        ]

    @property
    def has_document(self):
        return bool(self.supporting_document and self.sha256 and self.byte_size)

    def clean(self):
        super().clean()
        active_workspace_id = current_tenant_workspace_id()
        if active_workspace_id and self.license_id:
            if self.license.workspace_id != active_workspace_id:
                raise ValidationError(
                    "License revision must belong to the active workspace."
                )
        if self.pk:
            raise ValidationError("License revision evidence is immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("License revision evidence cannot be deleted.")

    def __str__(self):
        return f"{self.license_number} revision {self.revision_number}"
