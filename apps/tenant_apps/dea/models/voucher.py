from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

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
    fingerprint = models.CharField(max_length=128, db_index=True)
    last_posted_at = models.DateTimeField(null=True, blank=True)
    narration = models.TextField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doc_content_type", "doc_object_id"],
                condition=models.Q(status="POSTED"),
                name="unique_posted_voucher_per_doc",
            ),
        ]

    def __str__(self):
        return f"Voucher #{self.voucher_no} ({self.voucher_type.name})"

    def get_absolute_url(self):
        return f"/dea/vouchers/{self.pk}/"

    def clean(self):
        """Validate that only one POSTED voucher exists per business doc."""
        if self.status == VoucherStatus.POSTED:
            other_posted = (
                Voucher.objects.filter(
                    doc_content_type=self.doc_content_type,
                    doc_object_id=self.doc_object_id,
                    status=VoucherStatus.POSTED,
                )
                .exclude(pk=self.pk)
                .exists()
            )

            if other_posted:
                raise ValidationError(
                    f"Cannot have multiple POSTED vouchers for the same business document. "
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
