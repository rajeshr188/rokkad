"""
Voucher Numbering Service
Generates unique sequential voucher numbers per voucher type per accounting period
"""
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone


class VoucherNumberSequence(models.Model):
    """
    Tracks the next voucher number for each voucher type within each period.
    Ensures unique sequential numbering per type per period.

    Format: <PREFIX><PERIOD_CODE><SEQ>
    Example: INV-2024-01-0001, PYT-2024-01-0023
    """

    voucher_type = models.ForeignKey(
        "dea.VoucherType", on_delete=models.CASCADE, related_name="number_sequences"
    )
    period = models.ForeignKey(
        "dea.AccountingPeriod",
        on_delete=models.CASCADE,
        related_name="voucher_sequences",
        null=True,
        blank=True,
        help_text="Period for this sequence (null = not period-specific)",
    )
    next_number = models.PositiveIntegerField(
        default=1, help_text="Next available sequence number"
    )
    prefix = models.CharField(
        max_length=10,
        blank=True,
        help_text="Custom prefix for this voucher type (e.g., INV, PYT, RCT)",
    )

    class Meta:
        app_label = "dea"
        unique_together = [("voucher_type", "period")]
        indexes = [
            models.Index(fields=["voucher_type", "period"]),
        ]
        verbose_name = "Voucher Number Sequence"
        verbose_name_plural = "Voucher Number Sequences"

    def __str__(self):
        period_str = f" ({self.period})" if self.period else " (Global)"
        return f"{self.voucher_type.name}{period_str}: Next={self.next_number}"
