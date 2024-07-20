from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import Func, Q, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from moneyed import Money

from apps.tenant_apps.approval.models import ReturnItem
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import JournalEntry  # , JournalTypes
from apps.tenant_apps.dea.models.moneyvalue import MoneyValueField
from apps.tenant_apps.product.models import Stock, StockTransaction
from apps.tenant_apps.terms.models import PaymentTerm


class Receipt(models.Model):
    # Fields
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    voucher_date = models.DateTimeField(default=timezone.now)
    voucher_no = models.CharField(max_length=20, null=True, blank=True)
    created_by = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, null=True, blank=True
    )
    weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    touch = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    convert = models.BooleanField(default=False)
    rate = models.IntegerField(default=0)
    total = MoneyField(max_digits=10, decimal_places=3, default_currency="INR")
    amount = MoneyField(
        max_digits=10, decimal_places=3, default_currency="INR", null=True, blank=True
    )
    description = models.TextField(max_length=50, default="describe here")
    status_choices = (
        ("Allotted", "Allotted"),
        ("Partially Allotted", "PartiallyAllotted"),
        ("Unallotted", "Unallotted"),
    )
    status = models.CharField(
        max_length=18, choices=status_choices, default="Unallotted"
    )
    is_active = models.BooleanField(default=True)
    journal_entries = GenericRelation(JournalEntry, related_query_name="receipt_doc")
    # Relationship Fields
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name="Customer",
    )
    invoices = models.ManyToManyField("sales.Invoice", through="ReceiptAllocation")

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return "%s" % self.id

    def get_absolute_url(self):
        return reverse("sales:sales_receipt_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("sales:sales_receipt_update", args=(self.pk,))

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=["is_active"])

    def get_line_totals(self):
        return self.receiptallocation_set.aggregate(t=Sum("allocated_amount"))["t"]

    def update_status(self):
        total_allotted = self.get_line_totals()
        if total_allotted is not None:
            if total_allotted == self.total:
                self.status = "Allotted"
            else:
                self.status = "Unallotted"
        self.save()

    def deallot(self):
        self.receiptline_set.all().delete()
        self.update_status()

    # def allot(self):
    #     print(f"allotting receipt {self.id} amount: {self.total}")

    #     invpaid = 0 if self.get_line_totals() is None else self.get_line_totals()

    #     remaining_amount = self.total - invpaid

    #     try:
    #         invtopay = (
    #             Invoice.objects.filter(
    #                 customer=self.customer,
    #                 # balancetype=self.type, posted=True
    #             )
    #             .exclude(status="Paid")
    #             .order_by("created")
    #         )
    #         print(f"invtopay:{invtopay}")
    #     except IndexError:
    #         invtopay = None

    #     for i in invtopay:
    #         print(f"i:{i} bal:{i.get_balance()}")
    #         if remaining_amount <= 0:
    #             break
    #         bal = i.get_balance()
    #         if remaining_amount >= bal:
    #             remaining_amount -= bal
    #             ReceiptLine.objects.create(receipt=self, invoice=i, amount=bal)
    #             i.status = "Paid"
    #         else:
    #             ReceiptAllocation.objects.create(
    #                 receipt=self, invoice=i, allocated_amount=remaining_amount
    #             )
    #             i.status = "PartiallyPaid"
    #             remaining_amount = 0
    #         i.save()

    #     self.update_status()

    def allot(self):
        print(f"allotting receipt {self.id} amount: {self.total}")

        invpaid = 0 if self.get_line_totals() is None else self.get_line_totals()
        remaining_amount = self.total - invpaid
        invoices_to_update = []

        try:
            invtopay = (
                Invoice.objects.filter(
                    customer=self.customer,
                    # balancetype=self.type, posted=True
                )
                .exclude(status="Paid")
                .order_by("created")
            )
            print(f"invtopay:{invtopay}")
        except IndexError:
            invtopay = None

        if invtopay is None:
            print("No invoices to pay.")
            return

        for i in invtopay:
            print(f"i:{i} bal:{i.get_balance()}")
            if remaining_amount <= 0:
                break
            bal = i.get_balance()
            if remaining_amount >= bal:
                remaining_amount -= bal
                ReceiptLine.objects.create(receipt=self, invoice=i, amount=bal)
                i.status = "Paid"
            else:
                ReceiptAllocation.objects.create(
                    receipt=self, invoice=i, allocated_amount=remaining_amount
                )
                i.status = "PartiallyPaid"
                remaining_amount = 0
            invoices_to_update.append(i)

        Invoice.objects.bulk_update(invoices_to_update, ["status"])
        self.update_status()

    def amount_allotted(self):
        if self.receiptallocation_set.exists():
            amount_allotted = self.receiptallocation_set.aggregate(
                amount=Sum("allocated"),
            )
            return Money(amount_allotted["amount"], self.total_currency)
        else:
            return Money(0, self.total_currency)

    def get_allocated_total(self):
        return (
            self.receiptallocation_set.aggregate(t=Sum("allocated"))["t"]
            if self.receiptallocation_set.exists()
            else None
        )

    def allocate(self):
        # get all unpaid invoices associated with this payment's customer and this payments currency type
        filters = {}
        filters["customer"] = self.customer
        print(f"total:{self.total_currency}")
        if self.total_currency == "INR":
            filters["outstanding_balance_cash__gt"] = 0
        elif self.total_currency == "USD":
            filters["outstanding_balance_gold__gt"] = 0
        elif self.total_currency == "AUD":
            filters["outstanding_balance_silver__gt"] = 0
        filter_q = Q(**filters)
        print(f"filter_q:{filter_q}")
        unpaid_invoices = (
            Invoice.with_outstanding_balance().filter(filter_q).order_by("created")
        )
        print(f"unpaid_invoices:{unpaid_invoices}")
        # iterate over the unpaid invoices and allocate payment in order
        amount_remaining = (
            self.total.amount
            if self.get_allocated_total() is None
            else self.total.amount - self.get_allocated_total()
        )
        for invoice in unpaid_invoices:
            if amount_remaining <= 0:
                break

            # calculate the amount to allocate to this invoice
            if self.total_currency == "INR":
                amount_due = invoice.outstanding_balance_cash
            elif self.total_currency == "USD":
                amount_due = invoice.outstanding_balance_gold
            elif self.total_currency == "AUD":
                amount_due = invoice.outstanding_balance_silver
            # amount_due = invoice.outstanding_balance
            print(f"amount_due:{amount_due}")
            print(f"amount_remaining:{amount_remaining}")
            amount_to_allocate = min(amount_due, amount_remaining)

            # create a PaymentAllocation object for this invoice and payment
            allocation = ReceiptAllocation.objects.create(
                receipt=self,
                invoice=invoice,
                allocated=Money(amount_to_allocate, self.total_currency),
            )

            # update the amount remaining to allocate
            amount_remaining -= amount_to_allocate

        # mark the payment as fully allocated if there is no amount remaining
        # if amount_remaining <= 0:
        #     self.status = "Allotted"
        #     self.save()
        self.update_status()

    def get_transactions(self):
        lt = []
        at = []
        if self.total.amount == 0:
            return None, None

        if self.convert:
            pure_gold = self.weight * self.touch * 0.01
            rate = self.rate
            at.append(
                {
                    "ledgerno": "Trading",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_ext": "CXC",
                    "Account": self.customer.account,
                    "amount": Money(pure_gold * rate, "INR"),
                }
            )
            at.append(
                {
                    "ledgerno": "Trading",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_ext": "CXC",
                    "Account": self.customer.account,
                    "amount": Money(pure_gold, "USD"),
                }
            )
            at.append(
                {
                    "ledgerno": "Sundry Debtors",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_ext": "RCT",
                    "Account": self.customer.account,
                    "amount": self.amount,
                }
            )
            # if self.amount_currency == "INR":
            #    pure_gold = self.weight * self.touch *0.01
            #    rate = self.rate
            #             #  customer balance is converted from gold to cash
            #    lt.append({ "ledgerno": "Sundry Debtors", "ledgerno_dr": "Trading", "amount": Money(pure_gold,"USD") })
            #    lt.append({ "ledgerno": "Trading", "ledgerno_dr": "Sundry Debtors", "amount": Money(pure_gold * rate,"INR") })
            #    at.append({ "ledgerno": "Trading", "XactTypeCode": "Dr", "XactTypeCode_ext": "CXC","Account": self.customer.account, "amount": Money(pure_gold*rate,"INR")})
            #    at.append({ "ledgerno": "Trading", "XactTypeCode": "Cr", "XactTypeCode_ext": "CXC","Account": self.customer.account, "amount": Money(pure_gold,"USD") })
            # elif self.total_currency == "USD":
            #     pure_gold = self.weight * self.touch *0.1
            #     rate = self.rate
            #     # customer balance is converted from cash to gold
            #     lt.append({ "ledgerno": "Sundry Debtors", "ledgerno_dr": "Trading", "amount": Money(pure_gold * rate,"INR") })
            #     lt.append({ "ledgerno": "Trading", "ledgerno_dr": "Sundry Debtors", "amount": Money(pure_gold,"USD")})
            #     at.append({ "ledgerno": "Trading", "XactTypeCode": "Dr", "XactTypeCode_ext": "CXC","Account": self.customer.account, "amount": Money(pure_gold,"USD") })
            #     at.append({ "ledgerno": "Trading", "XactTypeCode": "Cr", "XactTypeCode_ext": "CXC","Account": self.customer.account, "amount": Money(pure_gold * rate,"INR") })
        else:
            lt.append(
                {
                    "ledgerno": "Sundry Debtors",
                    "ledgerno_dr": "Cash",
                    "amount": self.total,
                }
            )
            at.append(
                {
                    "ledgerno": "Sundry Debtors",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_ext": "RCT",
                    "Account": self.customer.account,
                    "amount": self.total,
                }
            )
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
        print("Creating transactions")
        lt, at = self.get_transactions()
        if lt and at:
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
        return model_to_dict(self, fields=["total"]) != model_to_dict(
            old_instance, fields=["total"]
        )


class ReceiptAllocation(models.Model):
    created = models.DateTimeField(default=timezone.now)
    last_updated = models.DateTimeField(default=timezone.now)
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE)
    invoice = models.ForeignKey("sales.Invoice", on_delete=models.CASCADE)
    # allocated_amount = models.DecimalField(max_digits=10, decimal_places=2)
    allocated = MoneyField(
        max_digits=19,
        decimal_places=4,
        default_currency="INR",
        default=0,  # default value
    )

    def __str__(self):
        return "%s" % self.id

    def get_absolute_url(self):
        return reverse("sales_receiptallocation_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("sales_receiptallocation_update", args=(self.pk,))


"""
    This is a view that is used to get the outstanding balance of an invoice.
    SQL:
        CREATE VIEW invoice_receipt_view AS 
        SELECT invoice.id, invoice.invoice_number, invoice.total_amount, 
            COALESCE(SUM(receipt_allocation.allocated_amount), 0) AS amount_allocated, 
            COALESCE(SUM(receipt.amount), 0) AS amount_paid 
        FROM invoice 
        LEFT JOIN receipt_allocation ON invoice.id = receipt_allocation.invoice_id 
        LEFT JOIN receipt ON receipt_allocation.receipt_id = receipt.id 
        GROUP BY invoice.id;

    invoice_receipts = InvoiceReceiptView.objects.all()
    for invoice in invoice_receipts:
        print(f"Invoice #{invoice.invoice_number}: Total amount: {invoice.total_amount}, Amount paid: {invoice.amount_paid}, Amount allocated: {invoice.amount_allocated}, Outstanding balance: {invoice.outstanding_balance}")

"""


class InvoiceReceiptView(models.Model):
    invoice_number = models.CharField(max_length=50)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_allocated = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def outstanding_balance(self):
        return self.total_amount - self.amount_paid

    @classmethod
    def get_queryset(cls):
        return cls.objects.annotate(
            amount_allocated=Sum("invoice_receipts__allocated_amount")
        )

    class Meta:
        managed = False
        db_table = "sales_receipt_view"
