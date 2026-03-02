"""
JournalEntryVoucher Model - Manual GL adjustments

JOURNAL ENTRY WORKFLOW:
- Accountant creates manual GL entries (no source document)
- Used for corrections, accruals, period-end adjustments
- Must be balanced (Total DR = Total CR)
- Requires review and approval
- Posts immediately upon approval

No automatic creation - always manually created by accountant.
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money
from decimal import Decimal

from .doc import BusinessDoc


class JournalEntryType(models.TextChoices):
    """type of journal entry"""

    CLOSING = "CLOSING", "Closing Entry"
    ACCRUAL = "ACCRUAL", "Accrual"
    CORRECTION = "CORRECTION", "Correction/Reversal"
    ADJUSTMENT = "ADJUSTMENT", "Period-End Adjustment"
    INTERCORP = "INTERCORP", "Inter-Company"
    EXCHANGE = "EXCHANGE", "Exchange Rate Adjustment"
    OTHER = "OTHER", "Other"


class JournalEntryVoucher(BusinessDoc):
    """
    Journal Entry Voucher - Manual GL adjustments.

    CHARACTERISTICS:
    - Completely manual data entry (user enters DR/CR lines)
    - No automatic posting from business documents
    - Used for corrections, period-end adjustments, accruals
    - Must be balanced (Total DR = Total CR)
    - Requires review and approval before posting
    - Posts immediately to GL upon approval

    Examples:
    - Depreciation accrual at month-end
    - Inter-company adjustments
    - Reversal of incorrect entries
    - Exchange rate adjustments
    - Manual corrections

    ACCOUNTING ENTRY:
    DR: User-selected account
    CR: User-selected account
    (User provides line-by-line entries)
    """

    # === Core Identity ===
    je_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique journal entry reference (auto-generated)",
    )

    je_date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Journal entry date (may differ from posting date)",
    )

    # === Classification ===
    entry_type = models.CharField(
        max_length=50,
        choices=JournalEntryType.choices,
        default=JournalEntryType.OTHER,
        help_text="Type of journal entry",
    )

    # === Description ===
    description = models.TextField(
        help_text="Detailed description of the journal entry"
    )

    memo = models.CharField(
        max_length=255, blank=True, help_text="Short memo/reference"
    )

    # === Reference (Optional) ===
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference to source document (if applicable)",
    )

    # === Amounts ===
    total_debit = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Total of all debit lines",
    )

    total_credit = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Total of all credit lines",
    )

    # === Approval ===
    reviewed_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_journal_entries",
        help_text="User who reviewed and approved",
    )

    reviewed_at = models.DateTimeField(
        null=True, blank=True, help_text="When journal entry was reviewed"
    )

    class Meta:
        ordering = ["-je_date", "-created_at"]
        verbose_name = "Journal Entry Voucher"
        verbose_name_plural = "Journal Entry Vouchers"
        indexes = [
            models.Index(fields=["je_date", "entry_type"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.je_number} - {self.get_entry_type_display()} - DR: {self.total_debit} CR: {self.total_credit}"

    def clean(self):
        """Validate journal entry"""
        super().clean()

        # Check if balanced
        if abs(self.total_debit.amount - self.total_credit.amount) > Decimal("0.01"):
            raise ValidationError(
                f"Journal entry not balanced: DR {self.total_debit} ≠ CR {self.total_credit}"
            )

        # Check if has line items
        line_count = self.line_items.count()
        if line_count < 2:
            raise ValidationError(
                "Journal entry must have at least 2 line items (1 DR and 1 CR)"
            )

    def save(self, *args, **kwargs):
        """Auto-generate JE number if not set"""
        if not self.je_number:
            self.je_number = self._generate_je_number()

        super().save(*args, **kwargs)

    def _generate_je_number(self) -> str:
        """Generate unique journal entry number"""
        today = timezone.now()
        prefix = f"JE-{today.year}-{today.month:02d}"

        last_je = (
            JournalEntryVoucher.objects.filter(je_number__startswith=prefix)
            .order_by("-je_number")
            .first()
        )

        if last_je:
            try:
                last_seq = int(last_je.je_number.split("-")[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1

        return f"{prefix}-{next_seq:04d}"

    def get_voucher_type(self) -> str:
        """Return voucher type for posting"""
        return f"JOURNAL_ENTRY_{self.entry_type}"

    @property
    def is_balanced(self) -> bool:
        """Check if journal entry is balanced"""
        return abs(self.total_debit.amount - self.total_credit.amount) <= Decimal(
            "0.01"
        )

    @property
    def balance_difference(self) -> Money:
        """Return the balance difference (should be 0)"""
        return Money(
            self.total_debit.amount - self.total_credit.amount,
            self.total_debit.currency,
        )

    def get_economic_payload(self) -> dict:
        """Return economic fields for posting fingerprint"""
        return {
            "je_number": self.je_number,
            "total_debit": float(self.total_debit.amount),
            "total_credit": float(self.total_credit.amount),
            "entry_type": self.entry_type,
            "currency": str(self.total_debit.currency),
            "is_balanced": self.is_balanced,
        }


class JournalEntryLineItem(models.Model):
    """Line items in a journal entry (DR/CR transactions)"""

    SIDE_CHOICES = [("DR", "Debit"), ("CR", "Credit")]

    journal_entry = models.ForeignKey(
        JournalEntryVoucher,
        on_delete=models.CASCADE,
        related_name="line_items",
        help_text="Parent journal entry",
    )

    line_number = models.PositiveIntegerField(
        default=1, help_text="Line sequence number"
    )

    # === Account ===
    ledger_id = models.IntegerField(help_text="GL account ID (Ledger)")

    ledger_name = models.CharField(
        max_length=255, help_text="GL account name (for display)"
    )

    # === DR/CR ===
    side = models.CharField(
        max_length=2, choices=SIDE_CHOICES, help_text="Debit or Credit side"
    )

    amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Amount (always positive, side determines direction)",
    )

    # === Description ===
    description = models.TextField(help_text="Line description")

    class Meta:
        ordering = ["journal_entry", "line_number"]
        verbose_name = "Journal Entry Line Item"
        verbose_name_plural = "Journal Entry Line Items"
        unique_together = [["journal_entry", "line_number"]]

    def __str__(self):
        return f"{self.journal_entry.je_number} - Line {self.line_number}: {self.side} {self.amount}"

    def clean(self):
        """Validate line item"""
        if self.amount.amount < 0:
            raise ValidationError("Amount must be positive (side determines DR/CR)")

        if self.amount.amount == 0:
            raise ValidationError("Amount cannot be zero")

    def save(self, *args, **kwargs):
        """Auto-calculate line number if not set"""
        if not self.line_number or self.line_number == 0:
            max_line = JournalEntryLineItem.objects.filter(
                journal_entry=self.journal_entry
            ).aggregate(models.Max("line_number"))["line_number__max"]

            self.line_number = (max_line or 0) + 1

        super().save(*args, **kwargs)
