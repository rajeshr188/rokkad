from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AccrualStatus(models.TextChoices):
    DRAFT = "DRAFT", _("Draft")
    POSTED = "POSTED", _("Posted")
    SKIPPED = "SKIPPED", _("Skipped")
    REVERSED = "REVERSED", _("Reversed")


class AccrualTriggerSource(models.TextChoices):
    MANUAL = "MANUAL", _("Manual")
    SCHEDULED = "SCHEDULED", _("Scheduled Batch")
    PERIOD_CLOSE = "PERIOD_CLOSE", _("Period Close")
    RELEASE = "RELEASE", _("Release Catch-up")
    RENEWAL = "RENEWAL", _("Renewal Catch-up")
    RECEIPT = "RECEIPT", _("Receipt Catch-up")
    BACKFILL = "BACKFILL", _("Backfill")


class LoanInterestAccrual(models.Model):
    """Persistent audit row for each completed interest-accrual period on a GivenLoan."""

    loan = models.ForeignKey(
        "girvi.GivenLoan",
        on_delete=models.CASCADE,
        related_name="interest_accruals",
        verbose_name=_("Loan"),
    )
    period_start = models.DateField(verbose_name=_("Period Start"))
    period_end = models.DateField(verbose_name=_("Period End"))
    accrued_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name=_("Accrued Amount"),
    )
    base_interest_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name=_("Base Interest Snapshot"),
        help_text=_("Per-period interest amount used when this accrual row was generated."),
    )
    months_covered = models.PositiveIntegerField(default=1, verbose_name=_("Months Covered"))
    trigger_source = models.CharField(
        max_length=20,
        choices=AccrualTriggerSource.choices,
        default=AccrualTriggerSource.MANUAL,
        verbose_name=_("Trigger Source"),
    )
    status = models.CharField(
        max_length=10,
        choices=AccrualStatus.choices,
        default=AccrualStatus.DRAFT,
        db_index=True,
        verbose_name=_("Status"),
    )
    recognized_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name=_("Recognized At"),
    )
    journal_entry_voucher = models.ForeignKey(
        "dea.JournalEntryVoucher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_interest_accruals",
        verbose_name=_("Journal Entry Voucher"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="loan_interest_accruals_created",
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="", verbose_name=_("Notes"))

    class Meta:
        ordering = ("-period_end", "-created_at")
        verbose_name = _("Loan Interest Accrual")
        verbose_name_plural = _("Loan Interest Accruals")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(period_end__gt=models.F("period_start")),
                name="loan_interest_accrual_period_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["loan", "period_start", "period_end"],
                name="unique_loan_interest_accrual_period",
            ),
        ]
        indexes = [
            models.Index(fields=["loan", "period_end"]),
            models.Index(fields=["status", "recognized_at"]),
        ]

    def __str__(self):
        return (
            f"{self.loan.loan_id} | {self.period_start} → {self.period_end} | "
            f"₹{self.accrued_amount}"
        )
