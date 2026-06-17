import logging
import re
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Func, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.facade import (
    get_account_transactions_for_journal_entries,
    get_ledger_transactions_for_journal_entries,
)

# Import constants from refactored models (but NOT the new model classes - they're defined in loan_refactored.py)
from .loan_refactored import LoanStatus, InterestType

# Import old managers (deprecated, kept for backward compatibility)
from ..managers import LoanManager, LoanQuerySet, ReleasedManager, UnReleasedManager

_User = get_user_model()
logger = logging.getLogger(__name__)


class _LoanAuditMixin(models.Model):
    """
    Audit fields previously inherited from dea.BusinessDoc (decoupled 2026-05-03).
    Used only by the legacy Loan and LoanPayment models in this file.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        _User, on_delete=models.SET_NULL, null=True, related_name="%(class)s_created_by"
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        _User, on_delete=models.SET_NULL, null=True, related_name="%(class)s_updated_by"
    )

    class Meta:
        abstract = True


class Loan(_LoanAuditMixin):
    """
    DEPRECATED: Use GivenLoan and TakenLoan models instead.

    This model is being phased out in favor of separate GivenLoan and TakenLoan models
    that provide clearer semantics and eliminate dual-personality confusion.

    Legacy model kept for:
    - Data migration and historical data access
    - Backward compatibility during transition period
    - Reporting on existing loans

    Migration Guide:
    - See docs/MIGRATION_TO_GIVENLOAN_TAKENLOAN.md for detailed instructions
    - Use GivenLoan.objects instead of Loan.objects.filter(loan_type='Given')
    - Use TakenLoan.objects instead of Loan.objects.filter(loan_type='Taken')

    Timeline:
    - End of Q1 2026: Views migrated to new models
    - End of Q2 2026: Old Loan model read-only (data access only)
    - End of Q3 2026: Old Loan model removal from codebase
    """

    # Fields
    loan_date = models.DateTimeField(default=timezone.now, verbose_name=_("Loan Date"))
    loan_id = models.CharField(max_length=255, unique=True, db_index=True)

    class LoanType(models.TextChoices):
        TAKEN = "Taken", "Taken"
        GIVEN = "Given", "Given"

    loan_type = models.CharField(
        max_length=10,
        choices=LoanType.choices,
        default=LoanType.GIVEN,
        null=True,
        blank=True,
    )
    # ----------redundant fields
    weight = models.CharField(max_length=50, null=True, blank=True)
    item_desc = models.TextField(
        max_length=100,
        verbose_name="Item",
        blank=True,
        null=True,
    )
    loan_amount = models.PositiveIntegerField(
        verbose_name="Amount", default=0, null=True, blank=True
    )
    interest = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, null=True, blank=True
    )
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20,
        choices=LoanStatus.choices,
        default=LoanStatus.CREATED,
    )

    interest_type = models.CharField(
        max_length=10, choices=InterestType.choices, default=InterestType.SIMPLE
    )
    series = models.ForeignKey(
        "girvi.Series",
        on_delete=models.CASCADE,
        verbose_name="Series",
        # related_name="loans",
    )
    tenure = models.PositiveIntegerField(default=3)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
    )
    # journal_entries = GenericRelation(JournalEntry, related_query_name="loan_doc")
    # notifications = models.ManyToManyField(Notification)
    # Managers
    # objects = LoanManager.from_queryset(LoanQuerySet)()
    objects = LoanManager()
    released = ReleasedManager()
    unreleased = UnReleasedManager()
    lqs = LoanQuerySet.as_manager()

    class Meta:
        ordering = ("series", "loan_id")
        get_latest_by = "id"
        constraints = [
            models.UniqueConstraint(
                fields=["series", "loan_id"], name="unique_loan_id_per_series"
            )
        ]
        permissions = [
            ("can_approve_loan", "Can approve loan"),
            ("can_disburse_loan", "Can disburse loan"),
            ("can_release_loan", "Can release loan"),
            ("can_cancel_loan", "Can cancel loan"),
            ("can_mark_defaulted", "Can mark loan as defaulted"),
            ("can_mark_auctioned", "Can mark loan as auctioned"),
            ("can_mark_sold", "Can mark loan as sold"),
        ]

    def __str__(self):
        return f"{self.loan_id} - {self.loan_amount} - {self.loan_date.date()}"

    def get_absolute_url(self):
        return reverse("girvi:girvi_loan_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("girvi:girvi_loan_update", args=(self.pk,))

    @property
    def is_released(self):
        return hasattr(self, "release")

    @property
    def last_notified(self):
        notice = self.notification_set.last()
        return notice.created_at if notice else None

    @property
    def get_pure(self):
        return self.loanitems.values("itemtype").annotate(
            pure_weight=Sum(
                Func(
                    ExpressionWrapper(
                        F("weight") * F("purity") / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    function="ROUND",  # SQL function for rounding
                    template="%(function)s(%(expressions)s, 3)",  # 3 is the number of decimal places
                )
            )
        )

    @property
    def get_weight(self):
        return self.loanitems.values("itemtype").annotate(total_weight=Sum("weight"))

    def formatted_weight(self, joiner=","):
        return joiner.join(
            f"{item['itemtype']} {item['total_weight']}" for item in self.get_weight
        )

    def formatted_pure(self, joiner=", "):
        return joiner.join(
            [f" {item['itemtype']} {item['pure_weight']}" for item in self.get_pure]
        )

    @property
    def get_loanamount(self):
        if self.loan_type == self.LoanType.GIVEN:
            return self.loanitems.aggregate(Sum("loanamount"))["loanamount__sum"] or 0
        elif self.loan_type == self.LoanType.TAKEN:
            return (
                self.repledgedloanitems.aggregate(Sum("repledged_loanamount"))[
                    "repledged_loanamount__sum"
                ]
                or 0
            )

    @property
    def get_loanamount_with_currency(self):
        return Money(self.get_loanamount, "INR")

    def get_remaining_loanamount(self):
        payments = (
            self.loan_payments.aggregate(Sum("payment_amount"))["payment_amount__sum"]
            or 0
        )
        items_total = (
            self.loanitems.aggregate(Sum("loanamount"))["loanamount__sum"] or 0
        )
        return items_total - payments

    def get_total_payments(self):
        total_payments = self.loan_payments.aggregate(Sum("payment_amount"))[
            "payment_amount__sum"
        ]
        return total_payments or 0

    def get_total_interest_payments(self):
        return (
            self.loan_payments.aggregate(Sum("interest_payment"))[
                "interest_payment__sum"
            ]
            or 0
        )

    def get_total_principal_payments(self):
        return (
            self.loan_payments.aggregate(Sum("principal_payment"))[
                "principal_payment__sum"
            ]
            or 0
        )

    def noofmonths(self, date=None):
        from ..services import InterestCalculationService

        return InterestCalculationService.months_between(self.loan_date, date)

    def interestdue(self, date=None):
        return round(self.interest * self.noofmonths(date))

    def get_current_value(self):
        try:
            if self.loan_type == self.LoanType.GIVEN:
                total_current_value = sum(
                    loan_item.current_value() for loan_item in self.loanitems.all()
                )
            elif self.loan_type == self.LoanType.TAKEN:
                total_current_value = sum(
                    repledged_item.original_loanitem.current_value()
                    for repledged_item in self.repledgedloanitems.select_related(
                        "original_loanitem__item"
                    ).all()
                )
            else:
                total_current_value = 0
        except Exception as e:
            logger.error(f"An error occurred while calculating current value: {e}")
            return 0

        return total_current_value

    def total(self):
        return self.interestdue() + self.get_loanamount

    def due(self):
        total_payments = self.get_total_payments()
        return self.total() - total_payments

    def due_with_currency(self):
        return Money(self.due(), "INR")

    def is_worth(self):
        return self.get_current_value() < self.due()

    def get_worth(self):
        return self.get_current_value() - self.due()

    def calculate_months_to_exceed_value(self, current_value=None, due=None):
        value = current_value or self.get_current_value()
        due = due or self.due()
        try:
            if not self.is_released and self.loanitems.exists():
                return round((value - due) / self.interest, 1)
        except Exception:
            return 0
        return 0

    def create_release(self, release_date, released_by, created_by):
        from django.apps import apps

        Release = apps.get_model(
            "girvi", "Release"
        )  # Replace 'app_name' with the name of your app

        release = Release.objects.create(
            loan=self,
            release_date=release_date,
            released_by=released_by,
            created_by=created_by,
        )
        return release

    def get_next(self):
        return (
            Loan.objects.filter(series=self.series, loan_id__gt=self.loan_id)
            .order_by("loan_id")
            .first()
        )

    def get_previous(self):
        return (
            Loan.objects.filter(series=self.series, loan_id__lt=self.loan_id)
            .order_by("loan_id")
            .last()
        )

    def is_valid_loan_id(loan_id):
        return bool(re.match(r"^[A-Z]*\d{5}$", loan_id))

    def save(self, *args, **kwargs):
        """Auto-generate loan_id using LoanIDGenerator if not set."""
        if not self.loan_id:
            if not self.series:
                raise ValueError("Series is required to create a loan")

            # Use LoanIDGenerator for thread-safe generation
            from ..services import LoanIDGenerator

            self.loan_id = LoanIDGenerator.generate(self.series)

        super().save(*args, **kwargs)

        if self.loan_type:
            from django.apps import apps

            GivenLoan = apps.get_model("girvi", "GivenLoan")
            TakenLoan = apps.get_model("girvi", "TakenLoan")

            if self.loan_type == self.LoanType.GIVEN:
                GivenLoan.objects.get_or_create(loan_ptr_id=self.id)
                TakenLoan.objects.filter(loan_ptr_id=self.id).delete()
            elif self.loan_type == self.LoanType.TAKEN:
                TakenLoan.objects.get_or_create(loan_ptr_id=self.id)
                GivenLoan.objects.filter(loan_ptr_id=self.id).delete()

    @classmethod
    def validate_loan_id(cls, loan_id, series_prefix):
        """Validate loan ID format"""
        pattern = f"^{series_prefix}\\d{{{loan_id.series.max_limit}}}$"
        return bool(re.match(pattern, loan_id))

    def update(self):
        # # Aggregate the loan amounts and interests
        # aggregates = self.loanitems.aggregate(
        #     loan_amount=Coalesce(Sum("loanamount"), 0, output_field=DecimalField()),
        #     interest=Coalesce(Sum("interest"), 0, output_field=DecimalField()),
        # )
        # loan_amount = aggregates["loan_amount"]
        # interest = aggregates["interest"]
        from django.apps import apps

        LoanItem = apps.get_model("girvi", "LoanItem")
        RepledgedLoanItem = apps.get_model("girvi", "RepledgedLoanItem")

        if self.loan_type == self.LoanType.GIVEN:
            item_desc = ", ".join(
                [item.itemdesc for item in LoanItem.objects.filter(loan=self)]
            )
            print(f"in loan {self.loan_id} update Given")
            # Aggregate the loan amounts and interests for given loans
            aggregates = self.loanitems.aggregate(
                loan_amount=Coalesce(Sum("loanamount"), 0, output_field=DecimalField()),
                interest=Coalesce(Sum("interest"), 0, output_field=DecimalField()),
            )

        elif self.loan_type == self.LoanType.TAKEN:
            item_desc = ", ".join(
                [
                    item.original_loanitem.itemdesc
                    for item in RepledgedLoanItem.objects.filter(loan=self)
                ]
            )
            print("in loan update Taken")
            # Aggregate the loan amounts and interests for taken loans
            aggregates = self.repledgedloanitems.aggregate(
                loan_amount=Coalesce(
                    Sum("repledged_loanamount"), 0, output_field=DecimalField()
                ),
                interest=Coalesce(
                    Sum("original_loanitem__interest"), 0, output_field=DecimalField()
                ),
            )

        loan_amount = aggregates["loan_amount"] or 0
        interest = aggregates["interest"] or 0
        print(f"updating loan_amount: {loan_amount}, interest: {interest}")

        try:
            # Update the loan object with the aggregated values
            with transaction.atomic():
                # Loan.objects.filter(id=self.id).update(
                self.loan_amount = loan_amount
                self.interest = interest
                self.item_desc = item_desc
                self.weight = self.formatted_weight()
                self.value = self.get_current_value()
                self.save()
                # )

        except Exception as e:
            # Handle or log the error as needed
            print(f"update():An error occurred while updating the loan: {e}")
            raise

    def notify(self, notice_type, medium_type):
        from notify.models import Notification

        notification = Notification(
            loan=self, notice_type=notice_type, medium_type=medium_type
        )
        notification.save()
        return notification

    def get_atxns(self):
        """Retrieve all AccountTransactions for this loan's journal entries (audit/view purposes)."""
        journal_entries = self.journal_entries.all()
        account_transactions = get_account_transactions_for_journal_entries(
            journal_entries
        )
        return list(account_transactions)

    def get_ltxns(self):
        """Retrieve all LedgerTransactions for this loan's journal entries (audit/view purposes)."""
        journal_entries = self.journal_entries.all()
        ledger_transactions = get_ledger_transactions_for_journal_entries(
            journal_entries
        )
        return list(ledger_transactions)

    def get_storage_box(self):
        try:
            return LoanItemStorageBox.objects.filter(
                start_item_id__lte=self.id, end_item_id__gte=self.id
            ).first()
        except LoanItemStorageBox.DoesNotExist:
            return None
        except Exception:
            # Log the exception if needed
            # print(f"An error occurred: {e}")
            return None

    # Add to Loan class
    def create_split_loan(self, loan_item, created_by=None):
        """Creates a new loan from an existing loan item"""
        new_loan = Loan.objects.create(
            created_by=created_by or self.created_by,
            loan_date=self.loan_date,
            loan_type=self.loan_type,
            interest_type=self.interest_type,
            series=self.series,
            tenure=self.tenure,
            customer=self.customer,
            status=self.status,
        )

        # Move loan item to new loan
        loan_item.loan = new_loan
        loan_item.save()

        # Update both loans
        self.update()
        new_loan.update()

        return new_loan

    def split_loan_items(self, loan_item_ids=None):
        """
        Splits selected loan items into separate loans.
        If no loan_item_ids provided, splits all loan items except the first one.
        First loan item always stays with original loan.
        Only loans with more than one item can be split.

        Returns list of newly created loans.
        """
        if self.loanitems.count() <= 1:
            raise ValidationError("Loan must have more than one item to split")

        # Get loan items to split
        if loan_item_ids:
            # Exclude first loan item if it's in the list
            first_item = self.loanitems.earliest("id")
            items_to_split = self.loanitems.filter(id__in=loan_item_ids).exclude(
                id=first_item.id
            )
        else:
            # Get all items except first one
            items_to_split = self.loanitems.exclude(id=self.loanitems.earliest("id").id)

        if not items_to_split:
            raise ValidationError("No valid loan items found to split")

        new_loans = []

        try:
            with transaction.atomic():
                # Create new loan for each item
                for loan_item in items_to_split:
                    new_loan = self.create_split_loan(loan_item)

                    # Log the split
                    LoanChangeLog.objects.create(
                        loan=self,
                        source=f"Split loan item {loan_item.id}",
                        target=f"Created new loan {new_loan.id}",
                        author=self.created_by,
                    )

                    new_loans.append(new_loan)

        except Exception as e:
            logger.error(f"Error splitting loan {self.id}: {str(e)}")
            raise

        return new_loans

    # def merge_loans(self, loan_ids):
    #     """
    #     Merges selected loans into the current loan.
    #     """
    #     loans_to_merge = Loan.objects.filter(id__in=loan_ids)

    #     if not loans_to_merge:
    #         raise ValidationError("No valid loans found to merge")

    #     try:
    #         with transaction.atomic():
    #             for loan in loans_to_merge:
    #                 # Move all loan items to current loan
    #                 loan.loanitems.update(loan=self)

    #                 # Log the merge
    #                 LoanChangeLog.objects.create(
    #                     loan=self,
    #                     source=f"Merged loan {loan.id}",
    #                     target=f"Added loan items",
    #                     author=self.created_by
    #                 )

    #                 # Delete the merged loan
    #                 loan.delete()

    #     except Exception as e:
    #         logger.error(f"Error merging loans into loan {self.id}: {str(e)}")
    #         raise

    def merge_loans(self, loans_to_merge):
        """
        Merges multiple loans into this loan.
        Args:
            loans_to_merge: QuerySet or list of Loan objects to merge into this one
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not loans_to_merge:
            raise ValidationError("No loans provided to merge")

        # Validate merge conditions
        for loan in loans_to_merge:
            if loan.customer != self.customer:
                raise ValidationError(
                    f"Cannot merge loan {loan.loan_id} - different customer"
                )
            if loan.is_released:
                raise ValidationError(
                    f"Cannot merge loan {loan.loan_id} - already released"
                )
            if loan.id == self.id:
                raise ValidationError("Cannot merge loan with itself")

        try:
            with transaction.atomic():
                # Log the merge
                LoanChangeLog.objects.create(
                    loan=self,
                    source=f"Merging loans: {', '.join(l.loan_id for l in loans_to_merge)}",
                    target=f"Into loan: {self.loan_id}",
                    author=self.created_by,
                    diff=f"Merged {len(loans_to_merge)} loans",
                )

                # Move all loan items to this loan
                for loan in loans_to_merge:
                    # Reverse any transactions
                    loan.reverse_transactions()

                    # Move loan items
                    loan.loanitems.update(loan=self)

                    # Log individual loan merges
                    LoanChangeLog.objects.create(
                        loan=loan,
                        source="Loan merged",
                        target=f"Into loan: {self.loan_id}",
                        author=self.created_by,
                        diff="Loan merged and deleted",
                    )

                    # Delete the merged loan
                    loan.delete()

                # Update the merged loan
                self.update()

                return (
                    True,
                    f"Successfully merged {len(loans_to_merge)} loans into {self.loan_id}",
                )

        except Exception as e:
            logger.error(f"Error merging loans into {self.loan_id}: {str(e)}")
            raise ValidationError(f"Failed to merge loans: {str(e)}")

    @classmethod
    def validate_merge_selection(cls, loan_ids):
        """
        Validates if selected loans can be merged.
        Returns tuple of (can_merge: bool, message: str, base_loan: Loan)
        """
        if not loan_ids or len(loan_ids) < 2:
            return False, "Select at least two loans to merge", None

        loans = cls.objects.filter(id__in=loan_ids)

        # Get earliest loan as base
        base_loan = loans.earliest("created_at")

        # Check all loans have same customer
        customers = set(loans.values_list("customer_id", flat=True))
        if len(customers) > 1:
            return False, "Selected loans must belong to the same customer", None

        # Check none are released
        if loans.filter(status=LoanStatus.RELEASED).exists():
            return False, "Cannot merge released loans", None

        return True, f"Selected loans can be merged into {base_loan.loan_id}", base_loan

    def get_status_history(self):
        """Get complete status change history"""
        return self.loanchangelog_set.all().order_by("-changed")

    def get_voucher_type(self) -> str:
        # Always return the correct posting rule key for disbursal
        return "GIVENLOAN_PAYMENT"

    def get_economic_payload(self):
        return {
            "customer_id": self.customer.id,
            "loan_amount": self.loan_amount,
            "interest": self.interest,
            "loan_type": self.loan_type,
        }


class LoanChangeLog(models.Model):
    # Use ContentType framework for generic relation to support both GivenLoan and TakenLoan
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    loan = GenericForeignKey("content_type", "object_id")

    changed = models.DateTimeField(default=timezone.now)
    source = models.CharField(max_length=255)
    target = models.CharField(max_length=255)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    diff = models.TextField()
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)  # For additional data

    class Meta:
        ordering = ["-changed"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        loan = self.loan
        loan_id = getattr(loan, "loan_id", "Unknown")
        return f"{loan_id} - {self.source} → {self.target}"


class LoanPayment(_LoanAuditMixin):
    """
    DEPRECATED — do not use in new code.
    Legacy loan payment model superseded by apps.tenant_apps.dea.models.PaymentVoucher.
    Table is kept read-only for historical data access (managed=False prevents accidental
    schema changes). Use PaymentVoucher for all new payment recording.
    """

    loan = models.ForeignKey(
        "girvi.GivenLoan", on_delete=models.CASCADE, related_name="loan_payments"
    )
    payment_date = models.DateTimeField()
    payment_amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Payment"
    )
    principal_payment = models.DecimalField(max_digits=10, decimal_places=2)
    interest_payment = models.DecimalField(max_digits=10, decimal_places=2)
    with_release = models.BooleanField(default=False)

    class Meta:
        ordering = ("-id",)
        managed = False  # DEPRECATED: table kept for historical reads only

    def __str__(self):
        return f"{self.loan.loan_id} - {self.payment_date} - {self.payment_amount}"

    def get_absolute_url(self):
        return self.loan.get_absolute_url()

    def get_update_url(self):
        # DEPRECATED: update URL no longer exists; LoanPayment is read-only
        return self.loan.get_absolute_url()

    def save(self, *args, **kwargs):
        # Calculate principal and interest breakdown
        interest_due = getattr(self.loan, "interest_due", None)
        if callable(interest_due):
            interest_due = interest_due()
        elif hasattr(self.loan, "interestdue"):
            interest_due = self.loan.interestdue()
        else:
            interest_due = 0

        interest_payment = min(self.payment_amount, interest_due)
        principal_payment = self.payment_amount - interest_payment
        self.principal_payment = principal_payment
        self.interest_payment = interest_payment

        # Call parent save which triggers auto-posting
        super().save(*args, **kwargs)

        # Post-save processing
        if hasattr(self.loan, "update"):
            self.loan.update()
        if self.with_release and not self.loan.is_released:
            released_by = getattr(self.loan, "borrower", None) or getattr(
                self.loan, "customer", None
            )
            self.loan.create_release(
                self.payment_date, released_by, self.created_by
            )

    def delete(self, *args, **kwargs):
        loan = self.loan
        if self.with_release:
            try:
                self.loan.release.delete()
            except ObjectDoesNotExist:
                pass
        super().delete(*args, **kwargs)
        # Journal entries are cascaded automatically; no manual deletion needed

    # Override automatically called by BusinessDoc.save()
    def get_voucher_type(self) -> str:
        """Return the voucher type for this payment."""
        return "LOAN_REPAY"

    # Override automatically used by posting service for fingerprinting
    def get_economic_payload(self) -> dict:
        """
        Return the economically relevant data for fingerprinting and idempotency.
        Used by the posting service to detect if this payment has changed.
        """
        return {
            "payment_id": self.id,
            "loan_id": self.loan_id,
            "customer_id": self.loan.customer_id,
            "payment_date": str(self.payment_date),
            "principal_payment": str(self.principal_payment),
            "interest_payment": str(self.interest_payment),
            "payment_amount": str(self.payment_amount),
        }
