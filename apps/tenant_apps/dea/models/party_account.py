from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _


class PartyAccountPurpose(models.TextChoices):
    CUSTOMER_RECEIVABLE = "CUSTOMER_RECEIVABLE", _("Customer Receivable")
    SUPPLIER_PAYABLE = "SUPPLIER_PAYABLE", _("Supplier Payable")
    BORROWER_LOAN_RECEIVABLE = (
        "BORROWER_LOAN_RECEIVABLE",
        _("Borrower Loan Receivable"),
    )
    LENDER_LOAN_PAYABLE = "LENDER_LOAN_PAYABLE", _("Lender Loan Payable")
    CUSTOMER_ADVANCE = "CUSTOMER_ADVANCE", _("Customer Advance")
    SUPPLIER_ADVANCE = "SUPPLIER_ADVANCE", _("Supplier Advance")


class PartyAccountMappingStatus(models.TextChoices):
    ACTIVE = "ACTIVE", _("Active")
    INACTIVE = "INACTIVE", _("Inactive")
    CLOSED = "CLOSED", _("Closed")


class PartyAccountMapping(models.Model):
    """Maps a party role/purpose to a DEA subledger account.

    This is the bridge between the long-term Party model and the current DEA
    Account model. While Account still stores the legacy Contact customer FK,
    this mapping records why a party is using a specific account.
    """

    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="dea_account_mappings",
    )
    role_key = models.CharField(max_length=64, db_index=True)
    purpose = models.CharField(
        max_length=64,
        choices=PartyAccountPurpose.choices,
        db_index=True,
    )
    account = models.ForeignKey(
        "dea.Account",
        on_delete=models.PROTECT,
        related_name="party_mappings",
    )
    control_ledger = models.ForeignKey(
        "dea.Ledger",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="party_account_mappings",
    )
    is_default = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=PartyAccountMappingStatus.choices,
        default=PartyAccountMappingStatus.ACTIVE,
        db_index=True,
    )
    event_type = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional event-specific mapping discriminator.",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("party", "role_key", "purpose", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["party", "role_key", "purpose", "event_type"],
                condition=Q(status=PartyAccountMappingStatus.ACTIVE),
                name="dea_one_active_party_account_mapping",
            ),
            models.UniqueConstraint(
                fields=["party", "role_key", "purpose"],
                condition=Q(status=PartyAccountMappingStatus.ACTIVE, is_default=True),
                name="dea_one_default_party_account_mapping",
            ),
        ]
        indexes = [
            models.Index(fields=["party", "status"]),
            models.Index(fields=["role_key", "purpose", "status"]),
            models.Index(fields=["account", "status"]),
        ]
        verbose_name = _("Party Account Mapping")
        verbose_name_plural = _("Party Account Mappings")

    def __str__(self):
        return f"{self.party} | {self.role_key} | {self.purpose} -> {self.account}"

    def save(self, *args, **kwargs):
        self.role_key = (self.role_key or "").strip().upper()
        self.purpose = (self.purpose or "").strip().upper()
        self.event_type = (self.event_type or "").strip().upper()
        super().save(*args, **kwargs)
