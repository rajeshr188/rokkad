from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from djmoney.models.fields import MoneyField

User = get_user_model()


class VoucherType(models.Model):

    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name


class VoucherStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    POSTED = "POSTED", "Posted"
    CORRECTED = "CORRECTED", "Corrected"
    REVERSED = "REVERSED", "Reversed"


class Voucher(models.Model):
    voucher_no = models.CharField(max_length=100)
    voucher_type = models.ForeignKey(VoucherType, on_delete=models.CASCADE)
    voucher_date = models.DateField()
    status = models.CharField(
        max_length=20, choices=VoucherStatus.choices, default=VoucherStatus.DRAFT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="vouchers_created"
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="vouchers_updated"
    )

    # generic link back to ANY business doc type
    doc_content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    doc_object_id = models.PositiveIntegerField()
    business_doc = GenericForeignKey("doc_content_type", "doc_object_id")

    corrected_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    fingerprint = models.CharField(max_length=128, db_index=True, blank=True, null=True)
    last_posted_at = models.DateTimeField(null=True, blank=True)
    narration = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doc_content_type", "doc_object_id", "voucher_type"],
                condition=models.Q(status="POSTED"),
                name="unique_posted_voucher_per_doc_type",
            ),
            models.UniqueConstraint(
                fields=["fingerprint"],
                condition=models.Q(status__in=["POSTED", "CORRECTED"]),
                name="unique_fingerprint_active",
            ),
        ]

    def __str__(self):
        return f"Voucher #{self.voucher_no} ({self.voucher_type.name})"

    def get_absolute_url(self):
        return f"/dea/vouchers/{self.pk}/"

    def clean(self):
        """Validate that only one POSTED voucher exists per business doc/type."""
        if self.status == VoucherStatus.POSTED:
            other_posted = (
                Voucher.objects.filter(
                    doc_content_type=self.doc_content_type,
                    doc_object_id=self.doc_object_id,
                    voucher_type=self.voucher_type,
                    status=VoucherStatus.POSTED,
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if other_posted:
                raise ValidationError(
                    f"Cannot have multiple POSTED vouchers for the same business document/type. "
                    f"Reverse the previous one first or let the posting engine handle it."
                )

    def save(self, *args, **kwargs):
        self.full_clean()  # Run validators
        super().save(*args, **kwargs)

    def get_economic_payload(self) -> dict:
        return {
            "voucher_id": self.id,
            "voucher_no": self.voucher_no,
            "voucher_type": self.voucher_type.name,
            "voucher_date": str(self.voucher_date),
            "status": self.status,
            "narration": self.narration,
        }

    @property
    def is_manual(self):
        """True if voucher was created manually (no BusinessDoc)"""
        return self.business_doc is None

    @property
    def source_description(self):
        """Human-readable source of this voucher"""
        if self.business_doc:
            return f"Auto from {self.business_doc.__class__.__name__} #{self.business_doc.id}"
        else:
            return f"Manual entry by {self.created_by}"


class VoucherLine(models.Model):
    class LineSide(models.TextChoices):
        DR = "Dr", "Debit"
        CR = "Cr", "Credit"

    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_no = models.PositiveIntegerField(help_text="1-based sequence within voucher")
    side = models.CharField(max_length=2, choices=LineSide.choices)

    ledger = models.ForeignKey(
        "Ledger",
        on_delete=models.PROTECT,
        related_name="voucher_lines",
    )
    account = models.ForeignKey(
        "Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="voucher_lines",
        help_text="Optional party/subledger attribution",
    )

    amount = MoneyField(max_digits=14, decimal_places=2, default_currency="INR")
    amount_base = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        null=True,
        blank=True,
        help_text="Base-currency amount for reporting checks",
    )
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1)
    xact_type_ext = models.CharField(max_length=4, default="TXN")

    tax_code = models.CharField(max_length=20, blank=True)
    narration = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["line_no", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["voucher", "line_no"],
                name="uniq_voucher_line_no",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="voucherline_amount_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["voucher", "side"]),
            models.Index(fields=["ledger", "side"]),
            models.Index(fields=["account", "side"]),
        ]

    def clean(self):
        super().clean()

        if self.voucher_id:
            voucher = self.voucher
            if voucher.status in {VoucherStatus.POSTED, VoucherStatus.REVERSED}:
                raise ValidationError(
                    "Cannot modify lines for posted/reversed voucher. "
                    "Create a correcting voucher instead."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.voucher.voucher_no} L{self.line_no} "
            f"{self.side} {self.ledger} {self.amount}"
        )
