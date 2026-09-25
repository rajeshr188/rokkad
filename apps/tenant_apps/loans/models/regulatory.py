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
        LEGACY_REFERENCE = "LEGACY_REFERENCE", "Legacy reference (validity unknown)"
        VERIFICATION = "VERIFICATION", "Verified legacy license continuation"
        ATTESTATION = "ATTESTATION", "Owner attestation (document pending)"

    license = models.ForeignKey(
        LoanLicense,
        on_delete=models.PROTECT,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    name = models.CharField(max_length=255)
    business_name = models.CharField(max_length=255, blank=True, default="")
    proprietor_name = models.CharField(max_length=255, blank=True, default="")
    business_address = models.TextField(max_length=1000, blank=True, default="")
    license_number = models.CharField(max_length=100)
    issuing_authority = models.CharField(max_length=255, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    verification_evidence = models.JSONField(default=dict, blank=True)
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
                condition=(Q(kind="LEGACY_REFERENCE", issued_on__isnull=True, expires_on__isnull=True)
                           | (~Q(kind="LEGACY_REFERENCE") & Q(issued_on__isnull=False, expires_on__isnull=False))),
                name="loans_licrev_validity_evidence",
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

    @property
    def is_legacy_reference(self):
        return self.kind == self.Kind.LEGACY_REFERENCE

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
        if self.kind == self.Kind.ATTESTATION:
            if (not self.license.is_legacy_reference or self.has_document or self.supporting_document
                    or self.created_by_id != self.license.workspace.owner_id
                    or self.verification_evidence.get("document_deferred") is not True
                    or self.verification_evidence.get("validity_basis") != "owner_attested"
                    or not isinstance(self.verification_evidence.get("document_deferral_reason"), str)
                    or not self.verification_evidence["document_deferral_reason"].strip()):
                raise ValidationError("Document deferral requires an owner attestation, reason and no substitute document.")
        elif self.kind == self.Kind.VERIFICATION:
            if not self.license.is_legacy_reference or not self.has_document or not self.verification_evidence:
                raise ValidationError("Legacy verification requires an imported reference, document and numbering evidence.")
        elif self.license_id and ((self.kind == self.Kind.LEGACY_REFERENCE) != self.license.is_legacy_reference):
            raise ValidationError("Legacy references and verified licence revisions must remain separate.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("License revision evidence cannot be deleted.")

    def __str__(self):
        return f"{self.license_number} revision {self.revision_number}"
