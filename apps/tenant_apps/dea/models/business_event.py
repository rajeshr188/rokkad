from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class BusinessEventDraft(models.Model):
    class EventType(models.TextChoices):
        FIXED_PURCHASE = "FIXED_PURCHASE", "Fixed purchase"
        UNFIXED_PURCHASE = "UNFIXED_PURCHASE", "Unfixed purchase"
        PURCHASE_RATE_FIXING = "PURCHASE_RATE_FIXING", "Purchase rate fixing"
        FIXED_SALE = "FIXED_SALE", "Fixed sale"
        UNFIXED_SALE = "UNFIXED_SALE", "Unfixed sale"
        SALE_RATE_FIXING = "SALE_RATE_FIXING", "Sale rate fixing"
        CUSTOMER_RECEIPT = "CUSTOMER_RECEIPT", "Customer receipt"
        SUPPLIER_PAYMENT = "SUPPLIER_PAYMENT", "Supplier payment"
        KARIGAR_ISSUE = "KARIGAR_ISSUE", "Karigar issue"
        KARIGAR_RECEIPT = "KARIGAR_RECEIPT", "Karigar receipt"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PREVIEWED = "PREVIEWED", "Previewed"

    event_type = models.CharField(max_length=32, choices=EventType.choices)
    source_reference = models.CharField(max_length=80)
    event_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    normalized_payload = models.JSONField(default=dict)
    preview_payload = models.JSONField(default=dict, blank=True)
    payload_hash = models.CharField(max_length=64, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dea_business_event_drafts_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dea_business_event_drafts_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-event_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "source_reference"],
                name="uniq_dea_business_event_draft_ref",
            ),
        ]
        indexes = [
            models.Index(
                fields=["event_type", "status", "event_date"],
                name="idx_dea_bus_event_status_date",
            ),
            models.Index(fields=["payload_hash"], name="idx_dea_bus_event_hash"),
        ]

    def clean(self):
        super().clean()
        self.source_reference = (self.source_reference or "").strip()
        if not self.source_reference:
            raise ValidationError({"source_reference": "Source reference is required."})
        if not self.payload_hash:
            raise ValidationError({"payload_hash": "Payload hash is required."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_event_type_display()} {self.source_reference}"
