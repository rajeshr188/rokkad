import logging
import re
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Func, Sum
from django.db.models.functions import Coalesce
from django.forms.models import model_to_dict
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from moneyed import Money

from apps.orgs.models import Membership
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    AccountStatement,
    AccountTransaction,
    JournalEntry,
    LedgerTransaction,
)
from apps.tenant_apps.rates.models import Rate

from ..managers import LoanManager, LoanQuerySet, ReleasedManager, UnReleasedManager

logger = logging.getLogger(__name__)


class LoanStatus(models.TextChoices):
    CREATED = "Created", "Created"
    CANCELLED = "Cancelled", "Cancelled"
    APPROVED = "Approved", "Approved"
    REJECTED = "Rejected", "Rejected"
    DISBURSED = "Disbursed", "Disbursed"
    CLOSED = "Closed", "Closed"
    RELEASED = "Released", "Released"
    REPLEDGED = "Repledged", "Repledged"
    SOLD = "Sold", "Sold"
    DEFAULTED = "Defaulted", "Defaulted"
    AUCTIONED = "Auctioned", "Auctioned"


class ItemType(models.TextChoices):
    GOLD = "Gold", "Gold"
    SILVER = "Silver", "Silver"
    BRONZE = "Bronze", "Bronze"


class InterestType(models.TextChoices):
    SIMPLE = "Simple", "Simple"
    COMPOUND = "Compound", "Compound"


class Loan(models.Model):
    """
    Model representing a loan.
    """

    # Fields
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="loans_created",
    )
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
    journal_entries = GenericRelation(JournalEntry, related_query_name="loan_doc")
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
        if date is None:
            date = timezone.now()
        nom = relativedelta(date, self.loan_date)
        return nom.years * 12 + nom.months

    def interestdue(self, date=None):
        if date is None:
            date = timezone.now()
        return round(self.interest * self.noofmonths(date))

    def get_current_value(self):
        try:
            if self.loan_type == self.LoanType.GIVEN:
                total_current_value = sum(
                    loan_item.current_value()
                    for loan_item in self.loanitems.select_related("item").all()
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
        return self.geT_current_value() - self.due()

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

    # def save(self, *args, **kwargs):
    #     if not self.loan_id:
    #         self.loan_id = self.generate_loan_id()
    #     # elif not Loan.is_valid_loan_id(self.loan_id):
    #     #     raise ValidationError(f"Invalid loan_id format: {self.loan_id}")

    #     super(Loan, self).save(*args, **kwargs)

    def save(self, *args, **kwargs):
        if not self.loan_id:
            with transaction.atomic():
                # Generate and set loan ID
                self.loan_id = self.series.get_next_loan_id()
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

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

    # def delete(self, *args, **kwargs):
    #     try:
    #         with transaction.atomic():
    #             # Reverse transactions before deletion
    #             self.reverse_transactions()

    #             # Delete journal entries
    #             self.delete_journal_entry()

    #             # Call the superclass delete method
    #             super(Loan, self).delete(*args, **kwargs)
    #     except Exception as e:
    #         logger.error(f"An error occurred while deleting the loan: {e}")
    #         raise

    def get_atxns(self):
        journal_entries = self.journal_entries.all()

        # Retrieve all AccountTransactions and LedgerTransactions for the filtered JournalEntries
        account_transactions = (
            AccountTransaction.objects.filter(journal_entry__in=journal_entries)
            .select_related("Account", "ledgerno")
            .order_by("id")
        )
        # ledger_transactions = LedgerTransaction.objects.filter(journal_entry__in=journal_entries)

        # Combine the transactions into a single list
        # combined_transactions = list(account_transactions) + list(ledger_transactions)

        # return combined_transactions
        return list(account_transactions)

    def get_ltxns(self):
        journal_entries = self.journal_entries.all()
        # Retrieve all AccountTransactions and LedgerTransactions for the filtered JournalEntries
        # account_transactions = AccountTransaction.objects.filter(journal_entry__in=journal_entries)
        ledger_transactions = LedgerTransaction.objects.filter(
            journal_entry__in=journal_entries
        ).select_related("ledgerno", "ledgerno_dr")

        # Combine the transactions into a single list
        # combined_transactions = list(account_transactions) + list(ledger_transactions)

        # return combined_transactions
        return list(ledger_transactions)

    # def get_transactions(self):
    #     if not hasattr(self.customer, "account"):
    #         self.customer.save()
    #     if all([self.loan_amount, self.interest]) == 0:
    #         return None, None
    #     document_charge = Money(10, "INR")
    #     interest = Money(self.interest, "INR")
    #     amount = Money(self.loan_amount, "INR")

    #     if self.loan_type == self.LoanType.TAKEN:
    #         lt = [

    #             # {"ledgerno": "Loans", "ledgerno_dr": "Cash", "amount": amount},
    #             # {
    #             #     "ledgerno": "Cash",
    #             #     "ledgerno_dr": "Interest Paid",
    #             #     "amount": interest,
    #             # },
    #         ]
    #         at = [
    #             {
    #                 "ledgerno": "Cash",
    #                 "XactTypeCode": "Dr",
    #                 "XactTypeCode_Ext": "LT",
    #                 "Account": self.customer.account,
    #                 "amount": amount-interest-document_charge,
    #             },
    #             {
    #                 "ledgerno": "Interest Paid",
    #                 "XactTypeCode": "Dr",
    #                 "XactTypeCode_Ext": "IP",
    #                 "Account": self.customer.account,
    #                 "amount": interest,
    #             },
    #             {
    #                 "ledgerno": "Document Charge Expense",
    #                 "XactTypeCode": "Dr",
    #                 "XactTypeCode_Ext": "DCE",
    #                 "Account": self.customer.account,
    #                 "amount": document_charge,
    #             },
    #         ]
    #     else:
    #         lt = []
    #         at = [

    #             {
    #                 "ledgerno": "Cash",
    #                 "XactTypeCode": "Cr",
    #                 "XactTypeCode_Ext": "LG",
    #                 "Account": self.customer.account,
    #                 "amount": amount + interest + document_charge,
    #             },
    #             {
    #                 "ledgerno": "Interest Receivables",
    #                 "XactTypeCode": "Dr",
    #                 "XactTypeCode_Ext": "IR",
    #                 "Account": self.customer.account,
    #                 "amount": interest,
    #             },
    #             {
    #                 "ledgerno": "Document Charge",
    #                 "XactTypeCode": "Dr",
    #                 "XactTypeCode_Ext": "DC",
    #                 "Account": self.customer.account,
    #                 "amount": document_charge,
    #             },

    #         ]
    #     return lt, at

    def get_transactions(self):
        if not hasattr(self.customer, "account"):
            self.customer.save()
        if all([self.loan_amount, self.interest]) == 0:
            return None, None
        amount = Money(self.loan_amount, "INR")
        interest = Money(self.interest, "INR")
        document_charge = Money(10, "INR")
        if self.loan_type == self.LoanType.TAKEN:
            lt = {}
            at = [
                {
                    "ledgerno": "Cash",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_Ext": "LT",
                    "Account": self.customer.account,
                    "amount": amount + interest + document_charge,
                },
                {
                    "ledgerno": "Cash",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "IP",
                    "Account": self.customer.account,
                    "amount": interest,
                },
                {
                    "ledgerno": "Cash",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "DCE",
                    "Account": self.customer.account,
                    "amount": document_charge,
                },
            ]
        else:
            lt = {}
            at = [
                {
                    "ledgerno": "Cash",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "LG",
                    "Account": self.customer.account,
                    "amount": amount + interest + document_charge,
                },
                {
                    "ledgerno": "Cash",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_Ext": "IR",
                    "Account": self.customer.account,
                    "amount": interest,
                },
                {
                    "ledgerno": "Cash",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_Ext": "DC",
                    "Account": self.customer.account,
                    "amount": document_charge,
                },
            ]
        return lt, at

    def get_journal_entry(self, desc=None):
        if self.journal_entries.exists():
            return self.journal_entries.latest()
        else:
            return JournalEntry.objects.create(
                desc=self.__class__.__name__, content_object=self
            )

    def delete_journal_entry(self):
        for entry in self.journal_entries.all():
            entry.delete()

    def delete_txns(self):
        je = self.get_journal_entry()
        AccountTransaction.objects.filter(journal_entry=je).delete()
        LedgerTransaction.objects.filter(journal_entry=je).delete()

    def create_transactions(self):
        # print("Creating transactions")
        lt, at = self.get_transactions()
        if lt or at:
            journal_entry = self.get_journal_entry()
            journal_entry.transact(lt, at)

    def reverse_transactions(self):
        # i.e if je is older than the latest statement then reverse the transactions else do nothing
        # print("Reversing transactions")
        try:
            statement = self.customer.account.accountstatements.latest("created")
        except ObjectDoesNotExist:
            statement = None
        journal_entry = self.get_journal_entry()
        if journal_entry and statement and journal_entry.created < statement.created:
            lt, at = self.get_transactions()
            if lt or at:
                journal_entry.untransact(lt, at)
        else:
            self.delete_txns()

    def is_changed(self, old_instance):
        # https://stackoverflow.com/questions/31286330/django-compare-two-objects-using-fields-dynamically
        # TODO efficient way to compare old and new instances
        # Implement logic to compare old and new instances
        # Compare all fields using dictionaries
        return model_to_dict(
            self, fields=["customer", "loan_amount", "interest"]
        ) != model_to_dict(old_instance, fields=["customer", "loan_amount", "interest"])

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
                merge_log = LoanChangeLog.objects.create(
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
                        source=f"Loan merged",
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


class LoanChangeLog(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
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

    def __str__(self):
        return f"{self.loan.loan_id} - {self.source} → {self.target}"


class LoanItem(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="loanitems")
    item = models.ForeignKey(
        "product.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True
    )
    pic = models.ImageField(upload_to="loan_pics/", null=True, blank=True)
    itemtype = models.CharField(
        max_length=30, choices=ItemType.choices, default=ItemType.GOLD
    )
    quantity = models.PositiveIntegerField(default=1)
    weight = models.DecimalField(max_digits=10, decimal_places=3)
    purity = models.DecimalField(
        max_digits=10, decimal_places=2, default=75, blank=True, null=True
    )
    loanamount = models.DecimalField(max_digits=10, decimal_places=2)
    interestrate = models.DecimalField(max_digits=10, decimal_places=2)
    interest = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True
    )
    itemdesc = models.TextField(
        max_length=100, blank=True, null=True, verbose_name="Item"
    )
    is_repledged = models.BooleanField(default=False)
    journal_entries = GenericRelation(JournalEntry, related_query_name="loanitem_doc")

    class Meta:
        ordering = (
            "id",
            "loan",
        )
        get_latest_by = "id"

    def __str__(self):
        return (
            f"{self.loan.loan_id}:₹{self.loanamount}({self.itemdesc} - {self.quantity})"
        )

    def get_absolute_url(self):
        # return self.loan.get_absolute_url()
        return reverse("girvi:girvi_loanitem_detail", args=(self.pk,))

    def get_hx_edit_url(self):
        kwargs = {"parent_id": self.loan.id, "id": self.id}
        return reverse("girvi:loanitem_create_update", kwargs=kwargs)

    def get_delete_url(self):
        return reverse(
            "girvi:girvi_loanitem_delete",
            kwargs={"id": self.id, "parent_id": self.loan.id},
        )

    from django.core.cache import cache

    def current_value(self):
        if self.itemtype == "Gold":
            rate = cache.get("grate")
        elif self.itemtype == "Silver":
            rate = cache.get("srate")
        else:
            rate = cache.get("brate")
        if not rate:
            rate = (
                Rate.objects.filter(metal=self.itemtype).latest("timestamp").buying_rate
            )
            if self.itemtype == "Gold":
                cache.set("grate", rate, 60 * 60 * 24)
            elif self.itemtype == "Silver":
                cache.set("srate", rate, 60 * 60 * 24)
            else:
                cache.set("brate", rate, 60 * 60 * 24)
        return round(self.weight * self.purity * Decimal(0.01) * rate, 2)

    def save(self, *args, **kwargs):
        # if self.loan.is_released:
        #     raise ValidationError(
        #         "Cannot modify LoanItem because related Loan has a Release."
        #     )
        self.interest = (self.interestrate / 100) * self.loanamount
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.loan.is_released:
            raise ValidationError(
                "Cannot delete LoanItem because related Loan has a Release."
            )
        # loan = self.loan
        super().delete(*args, **kwargs)
        # loan.update()

    # def get_transactions(self):
    #     if not hasattr(self.loan.customer, "account"):
    #         self.loan.customer.save()
    #     if all([self.loanamount, self.interest]) == 0:
    #         return None, None
    #     amount = Money(self.loanamount, "INR")
    #     interest = Money(self.interest, "INR")
    #     if self.loan.loan_type == self.loan.LoanType.TAKEN:
    #         lt = [
    #             # {"ledgerno": "Loans", "ledgerno_dr": "Cash", "amount": amount},
    #             # {
    #             #     "ledgerno": "Cash",
    #             #     "ledgerno_dr": "Interest Paid",
    #             #     "amount": interest,
    #             # },
    #         ]
    #         at = [
    #             {
    #                 "ledgerno": "Loans",
    #                 "xacttypecode": "Dr",
    #                 "xacttypecode_ext": "LT",
    #                 "account": self.loan.customer.account,
    #                 "amount": amount,
    #             },
    #             # {
    #             #     "ledgerno": "Interest Payable",
    #             #     "xacttypecode": "Cr",
    #             #     "xacttypecode_ext": "IP",
    #             #     "account": self.loan.customer.account,
    #             #     "amount": interest,
    #             # },
    #         ]
    #     else:
    #         lt = [
    #             # {
    #             #     "ledgerno": "Cash",
    #             #     "ledgerno_dr": "Loans & Advances",
    #             #     "amount": amount,
    #             # },
    #             # {
    #             #     "ledgerno": "Interest Received",
    #             #     "ledgerno_dr": "Cash",
    #             #     "amount": interest,
    #             # },
    #         ]
    #         at = [
    #             {
    #                 "ledgerno": "Cash",
    #                 "XactTypeCode": "Cr",
    #                 "XactTypeCode_Ext": "LG",
    #                 "Account": self.loan.customer.account,
    #                 "amount": amount,
    #             },
    #             # {
    #             #     "ledgerno": "Cash",
    #             #     "XactTypeCode": "Dr",
    #             #     "XactTypeCode_Ext": "IR",
    #             #     "Account": self.loan.customer.account,
    #             #     "amount": interest,
    #             # },
    #         ]
    #     return lt, at

    # def get_journal_entry(self, desc=None):
    #     if self.journal_entries.exists():
    #         return self.journal_entries.latest()
    #     else:
    #         return JournalEntry.objects.create(
    #             content_object=self, desc=self.__class__.__name__,parent_object=self.loan
    #         )

    # def delete_journal_entry(self):
    #     for entry in self.journal_entries.all():
    #         entry.delete()

    # def create_transactions(self):
    #     # print("Creating transactions")
    #     lt, at = self.get_transactions()
    #     if lt or at:
    #         journal_entry = self.get_journal_entry()
    #         journal_entry.transact(lt, at)

    # def reverse_transactions(self):
    #     # i.e if je is older than the latest statement then reverse the transactions else do nothing
    #     # print("Reversing transactions")
    #     try:
    #         statement = self.loan.customer.account.accountstatements.latest("created")
    #     except ObjectDoesNotExist:
    #         statement = None
    #     journal_entry = self.get_journal_entry()

    #     if journal_entry and statement and journal_entry.created < statement.created:
    #         lt, at = self.get_transactions()
    #         journal_entry.untransact(lt, at)
    #     else:
    #         self.delete_journal_entry()

    # def is_changed(self, old_instance):
    #     # https://stackoverflow.com/questions/31286330/django-compare-two-objects-using-fields-dynamically
    #     # TODO efficient way to compare old and new instances
    #     # Implement logic to compare old and new instances
    #     # Compare all fields using dictionaries
    #     return model_to_dict(self, fields=["loanamount"]) != model_to_dict(
    #         old_instance, fields=["loanamount"]
    #     )

    def get_item_pic(self):
        return self.pic.url if self.pic and self.pic else None

    @property
    def is_available_for_repledge(self):
        return (
            not self.is_repledged
            and not self.loan.is_released
            and self.loan.loan_type == self.loan.LoanType.GIVEN
        )


class RepledgedLoanItem(models.Model):
    original_loanitem = models.ForeignKey(
        LoanItem, on_delete=models.CASCADE, related_name="repledged_items"
    )
    loan = models.ForeignKey(
        Loan, on_delete=models.CASCADE, related_name="repledgedloanitems"
    )
    repledged_loanamount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    interest = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    repledged_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Repledged {self.original_loanitem} to {self.loan}"

    def get_absolute_url(self):
        # return self.loan.get_absolute_url()
        return reverse("girvi:repledgedloanitem_detail", args=(self.pk,))

    def get_hx_edit_url(self):
        kwargs = {"parent_id": self.loan.id, "id": self.id}
        return reverse("girvi:loanitem_create_update", kwargs=kwargs)

    def get_delete_url(self):
        return reverse(
            "girvi:girvi_loanitem_delete",
            kwargs={"id": self.id, "parent_id": self.loan.id},
        )

    def save(self, *args, **kwargs):
        # if self.loan.is_released:
        #     raise ValidationError(
        #         "Cannot modify LoanItem because related Loan has a Release."
        #     )
        self.interest = (self.interest_rate / 100) * self.repledged_loanamount
        super().save(*args, **kwargs)


class LoanItemPic(models.Model):
    loan = models.ForeignKey(
        "Loan", on_delete=models.CASCADE, related_name="loanitem_pics"
    )
    pic = models.ImageField(upload_to="loan_item_pics/", null=True, blank=True)
    description = models.TextField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Picture for {self.loan.loan_id}"

    def get_absolute_url(self):
        return reverse("loanitempic_detail", args=[str(self.id)])

    def get_update_url(self):
        return reverse("loanitempic_update", args=[str(self.id)])

    def get_delete_url(self):
        return reverse("loanitempic_delete", args=[str(self.id)])


class LoanPayment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="loan_payments_created",
    )
    loan = models.ForeignKey(
        "Loan", on_delete=models.CASCADE, related_name="loan_payments"
    )
    payment_date = models.DateTimeField()
    payment_amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Payment"
    )
    principal_payment = models.DecimalField(max_digits=10, decimal_places=2)
    interest_payment = models.DecimalField(max_digits=10, decimal_places=2)
    journal_entries = GenericRelation(
        JournalEntry, related_query_name="loan_payment_doc"
    )
    with_release = models.BooleanField(default=False)

    class Meta:
        ordering = ("-id",)

    def __str__(self):
        return f"{self.loan.loan_id} - {self.payment_date} - {self.payment_amount}"

    def get_absolute_url(self):
        return self.loan.get_absolute_url()
        # return reverse("girvi:girvi_loanpayment_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("girvi:girvi_loanpayment_update", args=(self.pk,))

    def save(self, *args, **kwargs):
        interest_payment = min(self.payment_amount, self.loan.interestdue())
        principal_payment = self.payment_amount - interest_payment
        self.principal_payment = principal_payment
        self.interest_payment = interest_payment
        super(LoanPayment, self).save(*args, **kwargs)
        self.loan.update()
        if self.with_release and not self.loan.is_released:
            release = self.loan.create_release(
                self.payment_date, self.loan.customer, self.created_by
            )

    def delete(self, *args, **kwargs):
        loan = self.loan
        if self.with_release:
            try:
                self.loan.release.delete()
            except ObjectDoesNotExist:
                pass
        super(LoanPayment, self).delete(*args, **kwargs)

    def get_transactions(self):
        # if (
        #     all([self.payment_amount, self.interest_payment, self.principal_payment])
        #     == 0
        # ):
        #     return None, None
        try:
            if self.loan.customer.account is None:
                self.loan.customer.save()
        except ObjectDoesNotExist:
            self.loan.customer.save()
        amount = Money(self.payment_amount, "INR")
        interest = Money(self.interest_payment, "INR")
        principal = Money(self.principal_payment, "INR")
        if self.loan.loan_type == self.loan.LoanType.TAKEN:
            lt = [
                {"ledgerno": "Cash", "ledgerno_dr": "Loans", "amount": principal},
                {
                    "ledgerno": "Cash",
                    "ledgerno_dr": "Interest Paid",
                    "amount": interest,
                },
            ]
            at = [
                {
                    "ledgerno": "Loans",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "LP",
                    "Account": self.loan.customer.account,
                    "amount": principal,
                },
                {
                    "ledgerno": "Interest Payable",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "IP",
                    "Account": self.loan.customer.account,
                    "amount": interest,
                },
            ]
        else:
            lt = [
                # {
                #     "ledgerno": "Loans & Advances",
                #     "ledgerno_dr": "Cash",
                #     "amount": principal,
                # },
                # {
                #     "ledgerno": "Interest Received",
                #     "ledgerno_dr": "Cash",
                #     "amount": interest,
                # },
            ]
            at = [
                {
                    "ledgerno": "Cash",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_Ext": "PYT",
                    "Account": self.loan.customer.account,
                    "amount": principal,
                },
                {
                    "ledgerno": "Cash",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_Ext": "IR",
                    "Account": self.loan.customer.account,
                    "amount": interest,
                },
            ]
        return lt, at

    def get_journal_entry(self, desc=None):
        if self.loan.journal_entries.filter(desc=self.__class__.__name__).exists():
            return self.loan.journal_entries.filter(
                desc=self.__class__.__name__
            ).latest()
        else:
            return JournalEntry.objects.create(
                content_object=self,
                desc=self.__class__.__name__,
                parent_object=self.loan,
            )

    def delete_journal_entry(self):
        for entry in self.journal_entries.all():
            entry.delete()

    def delete_txns(self):
        je = self.get_journal_entry()
        at = ledger_transactions = AccountTransaction.objects.filter(journal_entry=je)
        lt = ledger_transactions = LedgerTransaction.objects.filter(journal_entry=je)
        at.delete()
        lt.delete()

    def create_transactions(self):
        lt, at = self.get_transactions()
        if lt or at:
            journal_entry = self.get_journal_entry()
            journal_entry.transact(lt, at)

    def reverse_transactions(self):
        # i.e if je is older than the latest statement then reverse the transactions else do nothing

        try:
            statement = self.customer.account.accountstatements.latest("created")
        except AccountStatement.DoesNotExist:
            statement = None
        journal_entry = self.get_journal_entry()

        if journal_entry and statement and journal_entry.created < statement.created:
            lt, at = self.get_transactions()
            if lt or at:
                journal_entry.untransact(lt, at)
        else:
            # self.delete_journal_entry()
            self.delete_txns()

    def is_changed(self, old_instance):
        # https://stackoverflow.com/questions/31286330/django-compare-two-objects-using-fields-dynamically
        # TODO efficient way to compare old and new instances
        # Implement logic to compare old and new instances
        # Compare all fields using dictionaries
        return model_to_dict(self, fields=["payment_amount"]) != model_to_dict(
            old_instance, fields=["payment_amount"]
        )


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
        """
        Returns unreleased loans that were not physically present during verification
        """
        verified_loans = self.statementitem_set.values_list("loan_id", flat=True)
        if self.is_complete:
            return Loan.unreleased.exclude(id__in=verified_loans)
        else:
            return Loan.objects.filter(
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
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
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


class LoanItemStorageBox(models.Model):
    # TODO change start_item_id and end_item_id to ForeignKey to LoanItem
    name = models.CharField(max_length=50)
    location = models.CharField(max_length=50)
    start_item_id = models.CharField(max_length=50)
    end_item_id = models.CharField(max_length=50)
    item_type = models.CharField(
        max_length=6, choices=ItemType.choices, default=ItemType.GOLD
    )

    def __str__(self):
        return f"{self.name} at {self.location} (Items {self.start_item_id} to {self.end_item_id})"

    def clean(self):
        # Check for overlapping ranges
        print("Checking for overlapping ranges")
        print(self.start_item_id, self.end_item_id)
        overlapping_boxes = LoanItemStorageBox.objects.filter(
            item_type=self.item_type,
            start_item_id__lte=self.end_item_id,
            end_item_id__gte=self.start_item_id,
        ).exclude(pk=self.pk)

        if overlapping_boxes.exists():
            raise ValidationError(
                "The item ID range overlaps with another storage box."
            )

    def position_for_item(self, item_id):
        items_in_box = self.items().order_by("loan_id")
        item_ids = list(items_in_box.values_list("loan_id", flat=True))
        try:
            position = item_ids.index(item_id) + 1
        except ValueError:
            position = None
        return position

    def items(self):
        return Loan.unreleased.filter(
            loan_id__gte=self.start_item_id,
            loan_id__lte=self.end_item_id,
            loanitems__itemtype=self.item_type,
        )

    def items_count(self):
        return self.items().count()

    def get_absolute_url(self):
        return reverse("girvi:storagebox_detail", args=(self.pk,))
