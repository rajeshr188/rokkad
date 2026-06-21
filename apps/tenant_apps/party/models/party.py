import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def party_profile_photo_upload_to(instance, filename):
    ext = filename.split(".")[-1]
    return f"party_profile_photos/{uuid.uuid4()}.{ext}"


class PartyCodeSequence(models.Model):
    key = models.CharField(max_length=32, unique=True)
    next_number = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Party Code Sequence")
        verbose_name_plural = _("Party Code Sequences")

    def __str__(self):
        return f"{self.key}: {self.next_number}"


class Party(models.Model):
    class PartyType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", _("Individual")
        ORGANIZATION = "ORGANIZATION", _("Organization")
        BANK = "BANK", _("Bank")
        GOVERNMENT = "GOVERNMENT", _("Government Body")
        INTERNAL_WORKSPACE = "INTERNAL_WORKSPACE", _("Internal Workspace Entity")
        OTHER = "OTHER", _("Other")

    class PartyStatus(models.TextChoices):
        ACTIVE = "ACTIVE", _("Active")
        INACTIVE = "INACTIVE", _("Inactive")
        BLOCKED = "BLOCKED", _("Blocked")
        ARCHIVED = "ARCHIVED", _("Archived")

    class RelationLabel(models.TextChoices):
        SON_OF = "SON_OF", _("S/o")
        DAUGHTER_OF = "DAUGHTER_OF", _("D/o")
        CARE_OF = "CARE_OF", _("C/o")
        PARENT_OF = "PARENT_OF", _("P/o")
        FATHER_OF = "FATHER_OF", _("F/o")
        WIFE_OF = "WIFE_OF", _("W/o")
        HUSBAND_OF = "HUSBAND_OF", _("H/o")
        OTHER = "OTHER", _("O/o")

    party_code = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Tenant-scoped party code. Unique inside each tenant schema.",
    )
    party_type = models.CharField(
        max_length=32,
        choices=PartyType.choices,
        default=PartyType.INDIVIDUAL,
        db_index=True,
    )
    display_name = models.CharField(max_length=255, db_index=True)
    legal_name = models.CharField(max_length=255, blank=True)
    normalized_name = models.CharField(max_length=255, blank=True, db_index=True)
    relation_label = models.CharField(
        max_length=16,
        choices=RelationLabel.choices,
        blank=True,
    )
    relation_name = models.CharField(max_length=255, blank=True)

    primary_phone = models.CharField(max_length=32, blank=True)
    primary_email = models.EmailField(blank=True)
    profile_photo = models.ImageField(
        upload_to=party_profile_photo_upload_to,
        blank=True,
    )

    tax_pan = models.CharField(max_length=16, blank=True, db_index=True)
    gstin = models.CharField(max_length=24, blank=True, db_index=True)

    risk_level = models.CharField(max_length=32, blank=True)
    credit_hold = models.BooleanField(default=False, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=PartyStatus.choices,
        default=PartyStatus.ACTIVE,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="parties_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="parties_updated",
    )

    class Meta:
        ordering = ("display_name", "party_code")
        indexes = [
            models.Index(fields=["status", "party_type"]),
            models.Index(fields=["normalized_name"]),
            models.Index(fields=["tax_pan"]),
            models.Index(fields=["gstin"]),
        ]
        verbose_name = _("Party")
        verbose_name_plural = _("Parties")

    def __str__(self):
        return f"{self.display_name} ({self.party_code})"

    @property
    def relation_display(self):
        if not self.relation_label or not self.relation_name:
            return ""
        return f"{self.get_relation_label_display()} {self.relation_name}"

    def save(self, *args, **kwargs):
        if not self.party_code:
            self.party_code = generate_party_code()
        if not self.normalized_name:
            self.normalized_name = slugify(self.display_name or "").replace("-", " ")
        super().save(*args, **kwargs)


def generate_party_code(prefix="P"):
    with transaction.atomic():
        sequence, _created = (
            PartyCodeSequence.objects.select_for_update()
            .get_or_create(key="PARTY", defaults={"next_number": 1})
        )
        while True:
            candidate = f"{prefix}-{sequence.next_number:06d}"
            sequence.next_number += 1
            if not Party.objects.filter(party_code=candidate).exists():
                sequence.save(update_fields=["next_number", "updated_at"])
                return candidate
