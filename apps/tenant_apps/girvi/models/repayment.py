from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class LoanRepaymentDirection(models.TextChoices):
    RECEIPT = "RECEIPT", "Receipt"
    PAYMENT = "PAYMENT", "Payment"


class LoanRepayment(models.Model):
    """Immutable operational evidence for a Girvi loan repayment."""

    given_loan = models.ForeignKey(
        "girvi.GivenLoan",
        on_delete=models.PROTECT,
        related_name="repayment_evidence",
        null=True,
        blank=True,
    )
    taken_loan = models.ForeignKey(
        "girvi.TakenLoan",
        on_delete=models.PROTECT,
        related_name="repayment_evidence",
        null=True,
        blank=True,
    )
    direction = models.CharField(
        max_length=8,
        choices=LoanRepaymentDirection.choices,
    )
    total_amount = models.DecimalField(max_digits=18, decimal_places=2)
    principal_amount = models.DecimalField(max_digits=18, decimal_places=2)
    interest_amount = models.DecimalField(max_digits=18, decimal_places=2)
    payment_date = models.DateTimeField(db_index=True)
    payment_method = models.CharField(max_length=32)
    reference_number = models.CharField(max_length=128)
    description = models.TextField(blank=True, default="")
    is_final_payment = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="girvi_loan_repayments_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="reversal",
        null=True,
        blank=True,
    )
    accounting_voucher_pk = models.PositiveBigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("payment_date", "pk")
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(given_loan__isnull=False) & Q(taken_loan__isnull=True))
                    | (Q(given_loan__isnull=True) & Q(taken_loan__isnull=False))
                ),
                name="girvi_repayment_exactly_one_loan",
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gt=0),
                name="girvi_repayment_positive_total",
            ),
            models.CheckConstraint(
                condition=Q(principal_amount__gte=0) & Q(interest_amount__gte=0),
                name="girvi_repayment_nonnegative_split",
            ),
            models.CheckConstraint(
                condition=Q(total_amount=F("principal_amount") + F("interest_amount")),
                name="girvi_repayment_split_matches_total",
            ),
            models.CheckConstraint(
                condition=(
                    (Q(given_loan__isnull=False) & Q(direction=LoanRepaymentDirection.RECEIPT))
                    | (Q(taken_loan__isnull=False) & Q(direction=LoanRepaymentDirection.PAYMENT))
                ),
                name="girvi_repayment_direction_matches_loan",
            ),
            models.UniqueConstraint(
                fields=("given_loan", "reference_number"),
                condition=Q(given_loan__isnull=False),
                name="girvi_repayment_given_reference_uniq",
            ),
            models.UniqueConstraint(
                fields=("taken_loan", "reference_number"),
                condition=Q(taken_loan__isnull=False),
                name="girvi_repayment_taken_reference_uniq",
            ),
        ]

    def clean(self):
        super().clean()
        if self.reversal_of_id:
            original = self.reversal_of
            if original.reversal_of_id:
                raise ValidationError("A repayment reversal cannot itself be reversed.")
            if (
                self.given_loan_id != original.given_loan_id
                or self.taken_loan_id != original.taken_loan_id
            ):
                raise ValidationError("A repayment reversal must belong to the original loan.")
            if (
                self.total_amount != original.total_amount
                or self.principal_amount != original.principal_amount
                or self.interest_amount != original.interest_amount
            ):
                raise ValidationError(
                    "A repayment reversal must exactly compensate the original amounts."
                )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Loan repayment evidence is immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Loan repayment evidence is immutable.")

    def __str__(self):
        loan = self.given_loan or self.taken_loan
        return f"{self.direction} {self.total_amount} for {loan}"