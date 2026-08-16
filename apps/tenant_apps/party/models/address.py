from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from apps.tenancy.models import WorkspaceOwnedModel


class PartyAddress(WorkspaceOwnedModel):
    class AddressType(models.TextChoices):
        REGISTERED = "REGISTERED", _("Registered")
        BILLING = "BILLING", _("Billing")
        SHIPPING = "SHIPPING", _("Shipping")
        HOME = "HOME", _("Home")
        WORK = "WORK", _("Work")
        KYC = "KYC", _("KYC")
        OTHER = "OTHER", _("Other")

    party = models.ForeignKey(
        "party.Party",
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        max_length=16,
        choices=AddressType.choices,
        default=AddressType.BILLING,
    )
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    area = models.CharField(max_length=128, blank=True)
    city = models.CharField(max_length=128)
    state = models.CharField(max_length=128, blank=True)
    postal_code = models.CharField(max_length=24, blank=True)
    country = models.CharField(max_length=2, default="IN")
    is_default = models.BooleanField(default=False, db_index=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("party", "-is_default", "address_type")
        constraints = [
            models.UniqueConstraint(
                fields=["party", "address_type"],
                condition=Q(is_default=True),
                name="party_one_default_address_per_type",
            ),
        ]
        indexes = [
            models.Index(fields=["party", "address_type"]),
            models.Index(fields=["city", "state"]),
        ]
        verbose_name = _("Party Address")
        verbose_name_plural = _("Party Addresses")

    def __str__(self):
        parts = [self.line1, self.line2, self.area, self.city, self.postal_code]
        return ", ".join(part for part in parts if part)

    def save(self, *args, **kwargs):
        self.workspace_id = self.party.workspace_id
        super().save(*args, **kwargs)
