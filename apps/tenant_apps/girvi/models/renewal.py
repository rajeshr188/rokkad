from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class RenewalMode(models.TextChoices):
    PAY_AND_RENEW = "PAY_AND_RENEW", "Pay & Renew"
    TOPUP_RENEW = "TOPUP_RENEW", "Top-Up Renew"


class LoanRenewal(models.Model):
    """
    Audit record linking a source GivenLoan that was renewed to its successor loan.

    Created by LoanRenewalService.execute() inside a single atomic transaction.
    The source_loan is transitioned to REPLEDGED status; renewed_loan is the
    new GivenLoan that inherits the items with rebalanced loanamount values.
    """

    source_loan = models.ForeignKey(
        "girvi.GivenLoan",
        on_delete=models.PROTECT,
        related_name="renewals_as_source",
        verbose_name=_("Source Loan"),
    )
    renewed_loan = models.ForeignKey(
        "girvi.GivenLoan",
        on_delete=models.PROTECT,
        related_name="renewal_record",
        null=True,
        blank=True,
        verbose_name=_("Renewed Loan"),
    )
    mode = models.CharField(
        max_length=20,
        choices=RenewalMode.choices,
        verbose_name=_("Renewal Mode"),
    )
    renewal_date = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Renewal Date"),
    )
    interest_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name=_("Interest Paid"),
    )
    principal_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name=_("Principal Paid"),
    )
    requested_extra_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name=_("Requested Extra Amount"),
        help_text=_("Additional amount borrowed (Top-Up mode only)"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="renewals_created",
        verbose_name=_("Created By"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, default="", verbose_name=_("Notes"))

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Loan Renewal")
        verbose_name_plural = _("Loan Renewals")

    def __str__(self):
        return (
            f"Renewal of {self.source_loan_id} "
            f"→ {self.renewed_loan_id} ({self.mode})"
        )
