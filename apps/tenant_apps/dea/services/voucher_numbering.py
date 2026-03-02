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


class VoucherNumberingService:
    """
    Service for generating unique voucher numbers.

    Numbering Formats Supported:
    1. Sequential by period: INV-2024-01-0001
    2. Continuous (no period): INV-0001
    3. Date-based: INV-20240115-001
    4. Custom format via template
    """

    @staticmethod
    @transaction.atomic
    def generate_voucher_number(voucher_type, period=None, custom_prefix=None):
        """
        Generate next voucher number for given type and period.

        Args:
            voucher_type: VoucherType instance
            period: AccountingPeriod instance (optional)
            custom_prefix: Custom prefix override (optional)

        Returns:
            str: Generated voucher number
        """
        # Get or create sequence record with lock
        (
            sequence,
            created,
        ) = VoucherNumberSequence.objects.select_for_update().get_or_create(
            voucher_type=voucher_type,
            period=period,
            defaults={"next_number": 1, "prefix": custom_prefix or ""},
        )

        # Allocate current number
        current_number = sequence.next_number

        # Increment for next use
        sequence.next_number += 1
        sequence.save(update_fields=["next_number"])

        # Build voucher number
        prefix = custom_prefix or sequence.prefix or voucher_type.name[:3].upper()

        if period:
            # Format: PREFIX-YYYY-MM-NNNN
            period_code = period.start_date.strftime("%Y-%m")
            voucher_no = f"{prefix}-{period_code}-{current_number:04d}"
        else:
            # Format: PREFIX-NNNNNN
            voucher_no = f"{prefix}-{current_number:06d}"

        return voucher_no

    @staticmethod
    @transaction.atomic
    def generate_date_based_number(voucher_type, transaction_date, custom_prefix=None):
        """
        Generate date-based voucher number: PREFIX-YYYYMMDD-NNN

        Args:
            voucher_type: VoucherType instance
            transaction_date: Date of transaction
            custom_prefix: Custom prefix override (optional)

        Returns:
            str: Generated voucher number like INV-20240115-001
        """
        from apps.tenant_apps.dea.models import Voucher

        prefix = custom_prefix or voucher_type.name[:3].upper()
        date_str = transaction_date.strftime("%Y%m%d")

        # Get count of vouchers with same prefix and date
        pattern = f"{prefix}-{date_str}-%"
        count = Voucher.objects.filter(
            voucher_type=voucher_type, voucher_no__startswith=f"{prefix}-{date_str}-"
        ).count()

        next_seq = count + 1
        return f"{prefix}-{date_str}-{next_seq:03d}"

    @staticmethod
    def validate_voucher_number(voucher_no, voucher_type, period=None):
        """
        Validate that voucher number is unique for given type and period.

        Args:
            voucher_no: Voucher number to validate
            voucher_type: VoucherType instance
            period: AccountingPeriod instance (optional)

        Raises:
            ValidationError: If voucher number already exists
        """
        from apps.tenant_apps.dea.models import Voucher

        filters = {"voucher_no": voucher_no, "voucher_type": voucher_type}

        if period:
            # Check within period date range
            filters["voucher_date__gte"] = period.start_date
            filters["voucher_date__lte"] = period.end_date

        if Voucher.objects.filter(**filters).exists():
            raise ValidationError(
                f"Voucher number '{voucher_no}' already exists for "
                f"{voucher_type.name}" + (f" in period {period}" if period else "")
            )

        return True

    @staticmethod
    def get_next_preview(voucher_type, period=None):
        """
        Preview the next voucher number without allocating it.

        Args:
            voucher_type: VoucherType instance
            period: AccountingPeriod instance (optional)

        Returns:
            str: Next voucher number that will be generated
        """
        sequence = VoucherNumberSequence.objects.filter(
            voucher_type=voucher_type, period=period
        ).first()

        next_num = sequence.next_number if sequence else 1
        prefix = sequence.prefix if sequence else voucher_type.name[:3].upper()

        if period:
            period_code = period.start_date.strftime("%Y-%m")
            return f"{prefix}-{period_code}-{next_num:04d}"
        else:
            return f"{prefix}-{next_num:06d}"

    @staticmethod
    @transaction.atomic
    def reset_sequence(voucher_type, period=None, start_from=1):
        """
        Reset sequence counter (use with caution!).

        Args:
            voucher_type: VoucherType instance
            period: AccountingPeriod instance (optional)
            start_from: Number to start from (default: 1)
        """
        (
            sequence,
            created,
        ) = VoucherNumberSequence.objects.select_for_update().get_or_create(
            voucher_type=voucher_type,
            period=period,
            defaults={"next_number": start_from},
        )

        if not created:
            sequence.next_number = start_from
            sequence.save(update_fields=["next_number"])

        return sequence


# Convenience functions
def generate_voucher_number(voucher_type, period=None, custom_prefix=None):
    """Shortcut to generate voucher number"""
    return VoucherNumberingService.generate_voucher_number(
        voucher_type, period, custom_prefix
    )


def generate_date_based_voucher_number(
    voucher_type, transaction_date, custom_prefix=None
):
    """Shortcut to generate date-based voucher number"""
    return VoucherNumberingService.generate_date_based_number(
        voucher_type, transaction_date, custom_prefix
    )
