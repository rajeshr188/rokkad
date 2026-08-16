from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from apps.tenancy.models import WorkspaceOwnedModel


class PartyContactMethod(WorkspaceOwnedModel):
    class ContactType(models.TextChoices):
        PHONE = "PHONE", _("Phone")
        MOBILE = "MOBILE", _("Mobile")
        WHATSAPP = "WHATSAPP", _("WhatsApp")
        EMAIL = "EMAIL", _("Email")
        WEBSITE = "WEBSITE", _("Website")
        OTHER = "OTHER", _("Other")

    party = models.ForeignKey(
        "party.Party",
        on_delete=models.CASCADE,
        related_name="contact_methods",
    )
    contact_type = models.CharField(max_length=16, choices=ContactType.choices)
    label = models.CharField(max_length=64, blank=True)
    value = models.CharField(max_length=255)
    normalized_value = models.CharField(max_length=255, blank=True, db_index=True)
    is_primary = models.BooleanField(default=False, db_index=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("party", "-is_primary", "contact_type")
        constraints = [
            models.UniqueConstraint(
                fields=["party", "contact_type"],
                condition=Q(is_primary=True),
                name="party_one_primary_contact_per_type",
            ),
        ]
        indexes = [
            models.Index(fields=["party", "contact_type"]),
            models.Index(fields=["normalized_value"]),
        ]
        verbose_name = _("Party Contact Method")
        verbose_name_plural = _("Party Contact Methods")

    def __str__(self):
        return f"{self.party} - {self.contact_type}: {self.value}"

    def save(self, *args, **kwargs):
        self.workspace_id = self.party.workspace_id
        self.normalized_value = self.value.strip().lower()
        super().save(*args, **kwargs)
