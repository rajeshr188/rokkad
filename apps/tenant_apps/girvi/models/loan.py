import math
from datetime import datetime
from decimal import Decimal
# from qrcode.image.pure import PyImagingImage
from io import BytesIO

# import qrcode
# import qrcode.image.svg
from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import (BooleanField, Case, DecimalField,
                              ExpressionWrapper, F, Func, Q, Sum, Value, When)
from django.db.models.functions import (Coalesce, Concat, ExtractMonth,
                                        ExtractYear)
from django.forms.models import model_to_dict
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (AccountTransaction, JournalEntry,
                                         LedgerTransaction)
from apps.tenant_apps.rates.models import Rate

# from ..models import Release
from ..managers import (LoanManager, LoanQuerySet, ReleasedManager,
                        UnReleasedManager)


class Loan(models.Model):
    # Fields
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    voucher_date = models.DateTimeField(default=timezone.now)
    voucher_no = models.CharField(max_length=50, null=True, blank=True)
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="loans_created",
    )
    loan_date = models.DateTimeField(default=timezone.now, verbose_name=_("Loan Date"))
    lid = models.IntegerField(blank=True, null=True)
    loan_id = models.CharField(max_length=255, unique=True, db_index=True)
    # has_collateral = models.BooleanField(default=False)
    pic = models.ImageField(
        upload_to="loan_pics/", null=True, blank=True, verbose_name=_("Image")
    )

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

    # -----------------------------------
    class InterestType(models.TextChoices):
        SIMPLE = "Simple", "Simple"
        COMPOUND = "Compound", "Compound"

    interest_type = models.CharField(
        max_length=10, choices=InterestType.choices, default=InterestType.SIMPLE
    )
    series = models.ForeignKey(
        "girvi.Series",
        on_delete=models.CASCADE,
        verbose_name="Series",
    )
    tenure = models.PositiveIntegerField(default=0)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    journal_entries = GenericRelation(JournalEntry, related_query_name="loan_doc")
    # notifications = models.ManyToManyField(Notification)
    # Managers
    # objects = LoanManager.from_queryset(LoanQuerySet)()
    objects = LoanManager()
    released = ReleasedManager()
    unreleased = UnReleasedManager()
    lqs = LoanQuerySet.as_manager()

    class Meta:
        ordering = ("series", "lid")
        get_latest_by = "id"

    def __str__(self):
        return f"{self.loan_id} - {self.loan_amount} - {self.loan_date.date()}"

    def get_absolute_url(self):
        return reverse("girvi:girvi_loan_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("girvi:girvi_loan_update", args=(self.pk,))

    # @property
    # def get_qr(self):
    #     factory = qrcode.image.svg.SvgImage
    #     img = qrcode.make(data=self.lid, image_factory=factory, box_size=20)
    #     stream = BytesIO()
    #     img.save(stream)
    #     svg = stream.getvalue().decode()
    #     return svg

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
            [f"{item['itemtype']} {item['total_weight']} " for item in self.get_weight]
        )

    def formatted_pure(self, joiner=", "):
        return ", ".join(
            [f" {item['itemtype']} {item['pure_weight']}" for item in self.get_pure]
        )

    @property
    def get_loanamount(self):
        return self.loanitems.aggregate(Sum("loanamount"))["loanamount__sum"] or 0

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
        # date = date.replace(tzinfo=None)
        nom = relativedelta(date, self.loan_date)
        return nom.years * 12 + nom.months

    def interestdue(self, date=None):
        if date is None:
            date = timezone.now()
        return round(self.interest * self.noofmonths(date))

    def current_value(self):
        total_current_value = sum(
            loan_item.current_value() for loan_item in self.loanitems.all()
        )
        return total_current_value

    def total(self):
        return self.interestdue() + self.get_loanamount

    def due(self):
        total_payments = self.get_total_payments()
        return self.total() - total_payments

    def due_with_currency(self):
        return Money(self.due(), "INR")

    def is_worth(self):
        return self.current_value() < self.due()

    def get_worth(self):
        return self.current_value() - self.due()

    def calculate_months_to_exceed_value(self):
        try:
            if not self.is_released and self.loanitems.exists():
                return round((self.current_value() - self.due()) / self.interest, 1)
        except Exception as e:
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
            Loan.objects.filter(series=self.series, lid__gt=self.lid)
            .order_by("lid")
            .first()
        )

    def get_previous(self):
        return (
            Loan.objects.filter(series=self.series, lid__lt=self.lid)
            .order_by("lid")
            .last()
        )

    def save(self, *args, **kwargs):
        self.loan_id = self.series.name + str(self.lid)
        super(Loan, self).save(*args, **kwargs)

    def update(self):
        item_desc = ", ".join(
            [item.itemdesc for item in LoanItem.objects.filter(loan=self)]
        )
        # Aggregate the loan amounts and interests
        aggregates = self.loanitems.aggregate(
            loan_amount=Coalesce(Sum("loanamount"), 0, output_field=DecimalField()),
            interest=Coalesce(Sum("interest"), 0, output_field=DecimalField()),
        )
        loan_amount = aggregates["loan_amount"]
        interest = aggregates["interest"]

        try:
            # Update the loan object with the aggregated values
            with transaction.atomic():
                # Loan.objects.filter(id=self.id).update(
                self.loan_amount = loan_amount
                self.interest = interest
                self.item_desc = item_desc
                self.save()
                # )

        except Exception as e:
            # Handle or log the error as needed
            print(f"An error occurred while updating the loan: {e}")

    def notify(self, notice_type, medium_type):
        from notify.models import Notification

        notification = Notification(
            loan=self, notice_type=notice_type, medium_type=medium_type
        )
        notification.save()
        return notification

    def get_atxns(self):
        # Retrieve all LoanItems and LoanPayments for the loan
        loan_items = self.loanitems.all()
        loan_payments = self.loan_payments.all()
        # Get the ContentType for LoanItem and LoanPayment
        loan_item_content_type = ContentType.objects.get_for_model(LoanItem)
        loan_payment_content_type = ContentType.objects.get_for_model(LoanPayment)

        # Retrieve JournalEntries related to LoanItems and LoanPayments
        journal_entries = JournalEntry.objects.filter(
            Q(content_type=loan_item_content_type, object_id__in=loan_items)
            | Q(content_type=loan_payment_content_type, object_id__in=loan_payments)
        )

        # Retrieve all AccountTransactions and LedgerTransactions for the filtered JournalEntries
        account_transactions = AccountTransaction.objects.filter(
            journal_entry__in=journal_entries
        )
        # ledger_transactions = LedgerTransaction.objects.filter(journal_entry__in=journal_entries)

        # Combine the transactions into a single list
        # combined_transactions = list(account_transactions) + list(ledger_transactions)

        # return combined_transactions
        return list(account_transactions)

    def get_ltxns(self):
        # Retrieve all LoanItems and LoanPayments for the loan
        loan_items = self.loanitems.all()
        loan_payments = self.loan_payments.all()
        # Get the ContentType for LoanItem and LoanPayment
        loan_item_content_type = ContentType.objects.get_for_model(LoanItem)
        loan_payment_content_type = ContentType.objects.get_for_model(LoanPayment)

        # Retrieve JournalEntries related to LoanItems and LoanPayments
        journal_entries = JournalEntry.objects.filter(
            Q(content_type=loan_item_content_type, object_id__in=loan_items)
            | Q(content_type=loan_payment_content_type, object_id__in=loan_payments)
        )

        # Retrieve all AccountTransactions and LedgerTransactions for the filtered JournalEntries
        # account_transactions = AccountTransaction.objects.filter(journal_entry__in=journal_entries)
        ledger_transactions = LedgerTransaction.objects.filter(
            journal_entry__in=journal_entries
        )

        # Combine the transactions into a single list
        # combined_transactions = list(account_transactions) + list(ledger_transactions)

        # return combined_transactions
        return list(ledger_transactions)


class LoanItem(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="loanitems")
    item = models.ForeignKey(
        "product.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True
    )
    pic = models.ImageField(upload_to="loan_pics/", null=True, blank=True)

    class ItemType(models.TextChoices):
        GOLD = "Gold", "Gold"
        SILVER = "Silver", "Silver"
        BRONZE = "Bronze", "Bronze"

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
    journal_entries = GenericRelation(JournalEntry, related_query_name="loanitem_doc")

    def __str__(self):
        return f"{self.itemdesc} - {self.quantity}"

    def get_absolute_url(self):
        return self.loan.get_absolute_url()
        # return reverse("girvi:girvi_loanitem_detail", args=(self.pk,))

    def get_hx_edit_url(self):
        kwargs = {"parent_id": self.loan.id, "id": self.id}
        return reverse("girvi:hx-loanitem-detail", kwargs=kwargs)

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
        super().delete(*args, **kwargs)

    def get_transactions(self):
        if not hasattr(self.loan.customer, "account"):
            self.loan.customer.save()
        if all([self.loanamount, self.interest]) == 0:
            return None, None
        amount = Money(self.loanamount, "INR")
        interest = Money(self.interest, "INR")
        if self.loan.loan_type == self.loan.LoanType.TAKEN:
            lt = [
                # {"ledgerno": "Loans", "ledgerno_dr": "Cash", "amount": amount},
                # {
                #     "ledgerno": "Cash",
                #     "ledgerno_dr": "Interest Paid",
                #     "amount": interest,
                # },
            ]
            at = [
                {
                    "ledgerno": "Loans",
                    "xacttypecode": "Dr",
                    "xacttypecode_ext": "LT",
                    "account": self.loan.customer.account,
                    "amount": amount,
                },
                # {
                #     "ledgerno": "Interest Payable",
                #     "xacttypecode": "Cr",
                #     "xacttypecode_ext": "IP",
                #     "account": self.loan.customer.account,
                #     "amount": interest,
                # },
            ]
        else:
            lt = [
                # {
                #     "ledgerno": "Cash",
                #     "ledgerno_dr": "Loans & Advances",
                #     "amount": amount,
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
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "LG",
                    "Account": self.loan.customer.account,
                    "amount": amount,
                },
                # {
                #     "ledgerno": "Cash",
                #     "XactTypeCode": "Dr",
                #     "XactTypeCode_Ext": "IR",
                #     "Account": self.loan.customer.account,
                #     "amount": interest,
                # },
            ]
        return lt, at

    def get_journal_entry(self, desc=None):
        if self.journal_entries.exists():
            return self.journal_entries.latest()
        else:
            return JournalEntry.objects.create(
                content_object=self, desc=self.__class__.__name__
            )

    def delete_journal_entry(self):
        for entry in self.journal_entries.all():
            entry.delete()

    def create_transactions(self):
        # print("Creating transactions")
        lt, at = self.get_transactions()
        journal_entry = self.get_journal_entry()
        journal_entry.transact(lt, at)

    def reverse_transactions(self):
        # i.e if je is older than the latest statement then reverse the transactions else do nothing
        # print("Reversing transactions")
        try:
            statement = self.loan.customer.account.accountstatements.latest("created")
        except ObjectDoesNotExist:
            statement = None
        journal_entry = self.get_journal_entry()

        if journal_entry and statement and journal_entry.created < statement.created:
            lt, at = self.get_transactions()
            journal_entry.untransact(lt, at)
        else:
            self.delete_journal_entry()

    def is_changed(self, old_instance):
        # https://stackoverflow.com/questions/31286330/django-compare-two-objects-using-fields-dynamically
        # TODO efficient way to compare old and new instances
        # Implement logic to compare old and new instances
        # Compare all fields using dictionaries
        return model_to_dict(self, fields=["loanamount"]) != model_to_dict(
            old_instance, fields=["loanamount"]
        )


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
                    "XactTypeCode_Ext": "LR",
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
        if self.journal_entries.exists():
            return self.journal_entries.latest()
        else:
            return JournalEntry.objects.create(
                content_object=self, desc=self.__class__.__name__
            )

    def delete_journal_entry(self):
        for entry in self.journal_entries.all():
            entry.delete()

    def create_transactions(self):
        lt, at = self.get_transactions()
        if lt or at:
            journal_entry = self.get_journal_entry()
            journal_entry.transact(lt, at)

    def reverse_transactions(self):
        # i.e if je is older than the latest statement then reverse the transactions else do nothing
        print("Reversing transactions")
        try:
            statement = self.customer.account.accountstatements.latest("created")
        except AccountStatement.DoesNotExist:
            statement = None
        journal_entry = self.get_journal_entry()

        if journal_entry and statement and journal_entry.created < statement.created:
            lt, at = self.get_transactions()
            if lt and at:
                journal_entry.untransact(lt, at)
        else:
            self.delete_journal_entry()

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
    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name="loan_statements_created",
    )
    # loan = models.ForeignKey(Loan, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.created}"

    def get_absolute_url(self):
        return reverse("girvi:girvi_loanstatement_detail", args=(self.pk,))

    @property
    def next(self):
        return Statement.objects.filter(id__gt=self.id).order_by("id").first()

    @property
    def previous(self):
        return Statement.objects.filter(id__lt=self.id).order_by("id").last()


class StatementItem(models.Model):
    statement = models.ForeignKey(Statement, on_delete=models.CASCADE)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.loan.loanid}"
