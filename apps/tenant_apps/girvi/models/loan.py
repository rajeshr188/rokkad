import re
from decimal import Decimal

# import qrcode
# import qrcode.image.svg
from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import (BooleanField, DecimalField, ExpressionWrapper, F,
                              Func, Max, Q, Sum)
from django.db.models.functions import Coalesce
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

# from qrcode.image.pure import PyImagingImage
# from io import BytesIO





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
    lid = models.IntegerField(blank=True, null=True)
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
        return joiner.join(
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

    def get_current_value(self):
        try:
            total_current_value = sum(
                loan_item.current_value()
                for loan_item in self.loanitems.select_related("item").all()
            )
        except Exception as e:
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

    def get_transactions(self):
        if not hasattr(self.customer, "account"):
            self.customer.save()
        if all([self.loan_amount, self.interest]) == 0:
            return None, None
        amount = Money(self.loan_amount, "INR")
        interest = Money(self.interest, "INR")
        document_charge = Money(10, "INR")
        if self.loan_type == self.LoanType.TAKEN:
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
                    "account": self.customer.account,
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
                    "Account": self.customer.account,
                    "amount": amount,
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
        at = ledger_transactions = AccountTransaction.objects.filter(
            journal_entry=je
        ).delete()
        lt = ledger_transactions = LedgerTransaction.objects.filter(
            journal_entry=je
        ).delete()

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
        except Exception as e:
            # Log the exception if needed
            # print(f"An error occurred: {e}")
            return None


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
        # return self.loan.get_absolute_url()
        return reverse("girvi:girvi_loanitem_detail", args=(self.pk,))

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


class StatementItem(models.Model):
    statement = models.ForeignKey(
        Statement,
        on_delete=models.CASCADE,
    )
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    verified_at = models.DateTimeField(default=timezone.now)
    descrepancy_found = models.BooleanField(default=False)
    descrepancy_note = models.TextField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["statement", "loan"], name="unique_loan_per_statement"
            )
        ]

    def __str__(self):
        return f"{self.loan.loan_id} - {self.statement.created} - {self.verified_at} - {self.descrepancy_found} - {self.descrepancy_note}"


class ItemType(models.TextChoices):
    GOLD = "gold", "Gold"
    SILVER = "silver", "Silver"
    BRONZE = "bronze", "Bronze"


class LoanItemStorageBox(models.Model):
    name = models.CharField(max_length=50)
    location = models.CharField(max_length=50)
    start_item_id = models.PositiveIntegerField()
    end_item_id = models.PositiveIntegerField()
    item_type = models.CharField(
        max_length=6, choices=ItemType.choices, default=ItemType.GOLD
    )

    def __str__(self):
        return f"{self.name} at {self.location} (Items {Loan.objects.get(id = self.start_item_id).loan_id} to {Loan.objects.get(id =self.end_item_id).loan_id})"

    def get_start_item_loan_id(self):
        return Loan.objects.get(id=self.start_item_id).loan_id

    def get_end_item_loan_id(self):
        return Loan.objects.get(id=self.end_item_id).loan_id

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
        # naive approach
        # if item_id < self.start_item_id or item_id > self.end_item_id:
        #     return None
        # return item_id - self.start_item_id + 1
        items_in_box = self.items().order_by("id")
        item_ids = list(items_in_box.values_list("id", flat=True))
        try:
            position = item_ids.index(item_id) + 1
        except ValueError:
            position = None
        return position

    def items(self):
        return Loan.objects.filter(id__gte=self.start_item_id, id__lte=self.end_item_id)

    def items_count(self):
        return self.end_item_id - self.start_item_id + 1

    def get_absolute_url(self):
        return reverse("girvi:storagebox_detail", args=(self.pk,))
