from django.db import models
from django.shortcuts import reverse

from django.utils import timezone


class Statement(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    completed = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="loan_statements_created",
    )
    # New tracking fields
    completed_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        related_name="statements_completed",
    )
    reopened_at = models.DateTimeField(null=True)
    reopened_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        related_name="statements_reopened",
    )
    statement_type = models.CharField(
        max_length=20,
        choices=[
            ("REGULAR", "Regular Verification"),
            ("SPOT", "Spot Check"),
            ("ANNUAL", "Annual Audit"),
        ],
        default="REGULAR",
    )
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ("DRAFT", "In Progress"),
            ("COMPLETED", "Completed"),
            ("REOPENED", "Reopened"),
        ],
        default="DRAFT",
    )
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.created}"

    def get_absolute_url(self):
        return reverse("girvi:statement_detail", args=(self.pk,))

    @property
    def next(self):
        return Statement.objects.filter(id__gt=self.id).order_by("id").first()

    @property
    def previous(self):
        return Statement.objects.filter(id__lt=self.id).order_by("id").last()

    def get_missing_loans(self):
        from .loan_refactored import GivenLoan  # Import here to avoid circular imports

        """
        Returns unreleased loans that were not physically present during verification
        """
        verified_loans = self.statementitem_set.values_list("loan_id", flat=True)
        if self.is_complete:
            return GivenLoan.objects.unreleased().exclude(id__in=verified_loans)
        else:
            return GivenLoan.objects.filter(
                statementitem__statement=self, statementitem__descrepancy_type="MISSING"
            )

    def get_released_items_present(self):
        """
        Returns statement items where loan is released but physically present
        """
        return self.statementitem_set.filter(
            loan__release__isnull=False,
            descrepancy_found=True,
            descrepancy_note="Loan already released",
        )

    def get_verification_summary(self):
        """
        Returns summary of verification
        """
        missing_loans = self.get_missing_loans()
        released_present = self.get_released_items_present()

        return {
            "total_verified": self.statementitem_set.count(),
            "missing_loans": list(missing_loans),
            "released_present": list(released_present),
            "missing_count": missing_loans.count(),
            "released_present_count": released_present.count(),
        }

    def mark_complete(self, completed_by=None):
        """
        Mark verification as complete and record discrepancies
        """
        missing_loans = self.get_missing_loans()

        # Create statement items for missing loans
        for loan in missing_loans:
            StatementItem.objects.create(
                statement=self,
                loan=loan,
                descrepancy_found=True,
                descrepancy_note="Loan collateral missing",
                auto_generated=True,
            )

        self.completed = timezone.now()
        self.completed_by = completed_by
        self.save()

        return self.get_verification_summary()

    @property
    def is_complete(self):
        return bool(self.completed)

    def toggle_complete(self, completed_by=None):
        if self.is_complete:
            self.completed = None
            self.reopened_at = timezone.now()
            self.reopened_by = completed_by
        else:
            self.mark_complete(completed_by=completed_by)
        self.save()
        return self.is_complete


class StatementItem(models.Model):
    statement = models.ForeignKey(
        Statement,
        on_delete=models.CASCADE,
    )
    loan = models.ForeignKey("girvi.GivenLoan", on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="statement_items_created",
    )
    verified_at = models.DateTimeField(default=timezone.now)
    descrepancy_found = models.BooleanField(default=False)
    descrepancy_type = models.CharField(
        max_length=20,
        choices=[
            ("MISSING", "Item Missing"),
            ("WEIGHT", "Weight Mismatch"),
            ("CONDITION", "Condition Changed"),
            ("RELEASED", "Released but Present"),
        ],
        null=True,
        blank=True,
    )
    descrepancy_note = models.TextField(blank=True, null=True)
    auto_generated = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["statement", "loan"], name="unique_loan_per_statement"
            )
        ]

    def __str__(self):
        return f"{self.loan.loan_id} - {self.statement.created} - {self.verified_at} - {self.descrepancy_found} - {self.descrepancy_note}"
