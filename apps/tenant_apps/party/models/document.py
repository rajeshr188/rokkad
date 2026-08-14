from django.db import models
from django.utils.translation import gettext_lazy as _


class PartyIdentifier(models.Model):
    class IdentifierType(models.TextChoices):
        PAN = "PAN", _("PAN")
        AADHAAR = "AADHAAR", _("Aadhaar")
        GSTIN = "GSTIN", _("GSTIN")
        CIN = "CIN", _("CIN")
        UDYAM = "UDYAM", _("Udyam")
        PASSPORT = "PASSPORT", _("Passport")
        DRIVING_LICENSE = "DRIVING_LICENSE", _("Driving License")
        OTHER = "OTHER", _("Other")

    party = models.ForeignKey(
        "party.Party",
        on_delete=models.CASCADE,
        related_name="identifiers",
    )
    identifier_type = models.CharField(max_length=32, choices=IdentifierType.choices)
    value = models.CharField(max_length=128)
    masked_value = models.CharField(max_length=128, blank=True)
    value_hash = models.CharField(max_length=128, blank=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("party", "identifier_type")
        constraints = [
            models.UniqueConstraint(
                fields=["party", "identifier_type"],
                name="party_one_identifier_per_type",
            ),
        ]
        indexes = [
            models.Index(fields=["identifier_type", "value_hash"]),
            models.Index(fields=["party", "identifier_type"]),
        ]
        verbose_name = _("Party Identifier")
        verbose_name_plural = _("Party Identifiers")

    def __str__(self):
        return f"{self.party} - {self.identifier_type}"


def party_document_upload_to(instance, filename):
    return f"party_documents/{instance.party_id}/{filename}"


class PartyDocument(models.Model):
    class DocumentType(models.TextChoices):
        KYC = "KYC", _("KYC")
        TAX = "TAX", _("Tax")
        CONTRACT = "CONTRACT", _("Contract")
        LICENSE = "LICENSE", _("License")
        OTHER = "OTHER", _("Other")

    party = models.ForeignKey(
        "party.Party",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(max_length=32, choices=DocumentType.choices)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to=party_document_upload_to, blank=True)
    identifier = models.ForeignKey(
        "party.PartyIdentifier",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="documents",
    )
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("party", "document_type", "title")
        indexes = [
            models.Index(fields=["party", "document_type"]),
            models.Index(fields=["expires_on"]),
        ]
        verbose_name = _("Party Document")
        verbose_name_plural = _("Party Documents")

    def __str__(self):
        return f"{self.party} - {self.title}"
