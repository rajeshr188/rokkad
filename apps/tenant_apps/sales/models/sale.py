from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import F, Func, Q, Sum
from django.forms import model_to_dict
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from moneyed import Money

from apps.tenant_apps.approval.models import ReturnItem
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (AccountStatement,  # , JournalTypes
                                         JournalEntry)
from apps.tenant_apps.dea.models.moneyvalue import MoneyValueField
from apps.tenant_apps.dea.utils.currency import Balance
from apps.tenant_apps.product.models import Stock, StockTransaction
from apps.tenant_apps.terms.models import PaymentTerm

# from sympy import content


class Month(Func):
    function = "EXTRACT"
    template = "%(function)s(MONTH from %(expressions)s)"
    output_field = models.IntegerField()


class Year(Func):
    function = "EXTRACT"
    template = "%(function)s(YEAR from %(expressions)s)"
    output_field = models.IntegerField()


class SalesQueryset(models.QuerySet):
    def is_gst(self, value):
        return self.filter(is_gst=value)

    def is_ratecut(self, value):
        return self.filter(is_ratecut=value)

    def today(self):
        return self.filter(created__date=date.today())

    def cur_month(self):
        return self.filter(
            created__month=date.today().month, created__year=date.today().year
        )

    def total_with_ratecut(self):
        return self.aggregate(
            cash=Sum("balance", filter=Q(balancetype="INR")),
            cash_g=Sum("balance", filter=Q(balancetype="INR", metaltype="Gold")),
            cash_s=Sum("balance", filter=Q(balancetype="INR", metaltype="Silver")),
            cash_g_nwt=Sum("net_wt", filter=Q(balancetype="INR", metaltype="Gold")),
            cash_s_nwt=Sum("net_wt", filter=Q(balancetype="INR", metaltype="Silver")),
            gold=Sum("balance", filter=Q(balancetype="USD")),
            silver=Sum("balance", filter=Q(balancetype="AUD")),
        )

    def with_balance(self):
        return self.annotate(
            gold_balance=Sum(
                "saleitem__metal_balance", filter=Q(metal_balance_currency="USD")
            ),
            silver_balance=Sum(
                "saleitem__metal_balance", filter=Q(metal_balance_currency="EUR")
            ),
            cash_balance=Sum("saleitem__cash_balance"),
        ).select_related("saleitem")

    def with_allocated_payment(self):
        return self.annotate(
            gold_amount=Sum(
                "receiptallocation__allocated",
                filter=Q(receiptallocation__allocated_currency="USD"),
            ),
            silver_amount=Sum(
                "receiptallocation__allocated",
                filter=Q(receiptallocation__allocated_currency="EUR"),
            ),
            cash_amount=Sum(
                "receiptallocation__allocated",
                filter=Q(receiptallocation__allocated_currency="INR"),
            ),
        ).select_related("receiptallocation")

    def with_outstanding_balance(self):
        return self.annotate(
            outstanding_gold_balance=F("gold_amount") - F("sale_balance__gold_balance"),
            outstanding_silver_balance=F("silver_amount")
            - F("sale_balance__silver_balance"),
            outstanding_cash_balance=F("cash_amount") - F("sale_balance__cash_balance"),
        )


class Invoice(models.Model):
    # Fields
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, editable=False)
    voucher_date = models.DateTimeField(default=timezone.now)
    voucher_no = models.CharField(max_length=20, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sold",
    )
    is_ratecut = models.BooleanField(default=False)
    is_gst = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    status_choices = (
        ("Paid", "Paid"),
        ("PartiallyPaid", "PartiallyPaid"),
        ("Unpaid", "Unpaid"),
    )
    status = models.CharField(max_length=15, choices=status_choices, default="Unpaid")
    # make rates auto fill from the latest rates
    gold_rate = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    silver_rate = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    balance_cash = MoneyField(
        max_digits=14, decimal_places=3, default_currency="INR", null=True, blank=True
    )
    balance_gold = MoneyField(
        max_digits=14, decimal_places=3, default_currency="USD", null=True, blank=True
    )
    balance_silver = MoneyField(
        max_digits=14, decimal_places=3, default_currency="EUR", null=True, blank=True
    )
    balance = ArrayField(MoneyValueField(null=True, blank=True), null=True, blank=True)
    # Relationship Fields
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="sales",
        verbose_name="Customer",
    )
    term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sale_term",
    )
    # change to foreign
    approval = models.ForeignKey(
        "approval.Approval",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sales",
    )
    journal_entries = GenericRelation(
        JournalEntry,
        related_query_name="sales_doc",
    )
    objects = SalesQueryset.as_manager()

    class Meta:
        ordering = ("-created",)
        get_latest_by = "id"

    def __str__(self):
        return f"{self.id}"

    def get_absolute_url(self):
        return reverse("sales:sales_invoice_detail", kwargs={"pk": self.pk})

    def get_hx_url(self):
        return reverse("sales:hx-detail", kwargs={"id": self.id})

    def get_update_url(self):
        return reverse("sales:sales_invoice_update", args=(self.pk,))

    def get_delete_url(self):
        return reverse("sales:sales_invoice_delete", kwargs={"id": self.id})

    def get_invoiceitem_children(self):
        return self.sale_items.all()

    def get_next(self):
        return Invoice.objects.filter(id__gt=self.id).order_by("id").first()

    def get_previous(self):
        return Invoice.objects.filter(id__lt=self.id).order_by("id").last()

    def get_gross_wt(self):
        # this should return the sum of all purchaseitems weight by metal_balance_currency
        weights = self.sale_items.values("metal_balance_currency").annotate(
            amount=Sum("weight"), currency=F("metal_balance_currency")
        )
        money_values = [Money(item["amount"], item["currency"]) for item in weights]
        return Balance(money_values)

    def get_net_wt(self):
        weights = self.sale_items.values("metal_balance_currency").annotate(
            amount=Sum("net_wt"), currency=F("metal_balance_currency")
        )
        money_values = [Money(item["amount"], item["currency"]) for item in weights]
        return Balance(money_values)

    def get_sum_metal_balance(self):
        return self.sale_items.values("metal_balance_currency").annotate(
            total=Sum("metal_balance")
        )

    def get_sum_gold_balance(self):
        bal = (
            self.sale_items.aggregate(
                total=Sum("metal_balance", filter=Q(metal_balance_currency="USD"))
            )["total"]
            or 0
        )
        return Money(bal, "USD")

    def get_sum_silver_balance(self):
        bal = (
            self.sale_items.aggregate(
                total=Sum("metal_balance", filter=Q(metal_balance_currency="EUR"))
            )["total"]
            or 0
        )
        return Money(bal, "EUR")

    def get_sum_cash_balance(self):
        bal = self.sale_items.aggregate(total=Sum("cash_balance"))["total"] or 0
        return Money(bal, "INR")

    @property
    def overdue_days(self):
        return (timezone.now().date() - self.date_due).days

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=["self.is_active"])

    def get_gst(self):
        amount = self.sale_items.aggregate(t=Sum("cash_balance"))["t"] or 0
        gst = Money(amount * Decimal(0.03), "INR")
        return gst

    def calculate_balances(self):
        self.balance = Balance().monies()
        if self.is_ratecut:
            self.balance_cash = Money(
                self.get_sum_cash_balance().amount
                + self.get_sum_gold_balance().amount * self.gold_rate
                + self.get_sum_silver_balance().amount * self.silver_rate,
                "INR",
            )
            if self.is_gst:
                self.balance_cash.amount += self.balance_cash.amount * Decimal(0.03)
            self.balance_gold = Money(0, "USD")
            self.balance_silver = Money(0, "EUR")
        else:
            self.balance_cash = self.get_sum_cash_balance()
            self.balance_gold = self.get_sum_gold_balance()
            self.balance_silver = self.get_sum_silver_balance()
        self.balance = Balance(
            [self.balance_cash, self.balance_gold, self.balance_silver]
        ).monies()

    def save(self, *args, **kwargs):
        if self.pk:
            self.calculate_balances()

        if not self.due_date:
            if self.term:
                self.due_date = self.voucher_date + timedelta(days=self.term.due_days)

        super(Invoice, self).save(*args, **kwargs)

    # def delete(self, *args, **kwargs):
    #     if self.approval:
    #         self.approval.is_billed = False
    #     super(Invoice, self).delete(*args, **kwargs)

    @classmethod
    def with_outstanding_balance(cls):
        return cls.objects.annotate(
            total_allocated_cash=Coalesce(
                Sum(
                    "receiptallocation__allocated",
                    filter=Q(receiptallocation__allocated_currency="INR"),
                ),
                0,
                output_field=models.DecimalField(),
            ),
            total_allocated_gold=Coalesce(
                Sum(
                    "receiptallocation__allocated",
                    filter=Q(receiptallocation__allocated_currency="USD"),
                ),
                0,
                output_field=models.DecimalField(),
            ),
            total_allocated_silver=Coalesce(
                Sum(
                    "receiptallocation__allocated",
                    filter=Q(receiptallocation__allocated_currency="EUR"),
                ),
                0,
                output_field=models.DecimalField(),
            ),
        ).annotate(
            outstanding_balance_cash=F("sales_balance__cash_balance")
            - F("total_allocated_cash"),
            outstanding_balance_gold=F("sales_balance__gold_balance")
            - F("total_allocated_gold"),
            outstanding_balance_silver=F("sales_balance__silver_balance")
            - F("total_allocated_silver"),
        )

    def get_allocations(self):
        if self.receiptallocation_set.exists():
            paid = self.receiptallocation_set.aggregate(
                cash=Coalesce(
                    Sum("allocated", filter=Q(allocated_currency="INR")),
                    0,
                    output_field=models.DecimalField(),
                ),
                gold=Coalesce(
                    Sum("allocated", filter=Q(allocated_currency="USD")),
                    0,
                    output_field=models.DecimalField(),
                ),
                silver=Coalesce(
                    Sum("allocated", filter=Q(allocated_currency="EUR")),
                    0,
                    output_field=models.DecimalField(),
                ),
            )
            return Balance(
                [
                    Money(paid["cash"], "INR"),
                    Money(paid["gold"], "USD"),
                    Money(paid["silver"], "EUR"),
                ]
            )
        return Balance(0, "INR")

    def get_balance(self):
        return Balance(self.balance)
        # return self.balance - self.get_allocations()

    def get_transactions(self):
        if not hasattr(self.customer, "account"):
            self.customer.save()
        """
        if self.approval:

            before 16/4/2023 this logic was used to create sale items from approval items
            if any approval, return and bill

            for i in self.approval.items.filter(status="Pending"):
                apr = ReturnItem.objects.create(
                    line=i, quantity=i.quantity, weight=i.weight
                )
                apr.post()
                i.update_status()
            self.approval.is_billed = True
            self.approval.save()
            self.approval.update_status()
        """

        inv = "GST INV" if self.is_gst else "Non-GST INV"
        cogs = "GST COGS" if self.is_gst else "Non-GST COGS"
        tax = self.get_gst()
        lt, at = [], []

        cash_balance = self.balance_cash  # self.balance["INR"]
        gold_balance = self.balance_gold  # self.balance["USD"]
        silver_balance = self.balance_silver  # self.balance["EUR"]
        print(
            f"cash_balance:{cash_balance} gold_balance:{gold_balance} silver_balance:{silver_balance}"
        )

        if all(v is None for v in [cash_balance, gold_balance, silver_balance]):
            print("No balances to post")
            return None, None

        if cash_balance.amount != 0:
            lt.append(
                {
                    "ledgerno": "Sales",
                    "ledgerno_dr": "Sundry Debtors",
                    "amount": cash_balance,
                }
            )
            lt.append({"ledgerno": inv, "ledgerno_dr": cogs, "amount": cash_balance})
            at.append(
                {
                    "ledgerno": "Sales",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "CRSL",
                    "Account": self.customer.account,
                    "amount": cash_balance,
                }
            )
            if self.is_gst:
                lt.append(
                    {
                        "ledgerno": "Output Igst",
                        "ledgerno_dr": "Sundry Debtors",
                        "amount": tax,
                    },
                )
                at.append(
                    {
                        "ledgerno": "Sales",
                        "XactTypeCode": "Cr",
                        "XactTypeCode_Ext": "CRSL",
                        "Account": self.customer.account,
                        "amount": tax,
                    }
                )

        if gold_balance.amount != 0:
            lt.append(
                {
                    "ledgerno": "Sales",
                    "ledgerno_dr": "Sundry Debtors",
                    "amount": gold_balance,
                }
            )
            lt.append({"ledgerno": inv, "ledgerno_dr": cogs, "amount": gold_balance})
            at.append(
                {
                    "ledgerno": "Sales",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "CRSL",
                    "Account": self.customer.account,
                    "amount": gold_balance,
                }
            )

        if silver_balance and silver_balance.amount != 0:
            lt.append(
                {
                    "ledgerno": "Sales",
                    "ledgerno_dr": "Sundry Debtors",
                    "amount": silver_balance,
                }
            )
            lt.append({"ledgerno": inv, "ledgerno_dr": cogs, "amount": silver_balance})
            at.append(
                {
                    "ledgerno": "Sales",
                    "XactTypeCode": "Cr",
                    "XactTypeCode_Ext": "CRSL",
                    "Account": self.customer.account,
                    "amount": silver_balance,
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

    def delete_txns(self):
        je = self.get_journal_entry()
        at = je.atxns.all()
        lt = je.ltxns.all()

        at.delete()
        lt.delete()

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
            # self.delete_journal_entry()
            self.delete_txns()

    def is_changed(self, old_instance):
        # https://stackoverflow.com/questions/31286330/django-compare-two-objects-using-fields-dynamically
        # TODO efficient way to compare old and new instances
        # Implement logic to compare old and new instances
        # Compare all fields using dictionaries
        return model_to_dict(
            self, fields=["balance_cash", "balance_gold", "balance_silver"]
        ) != model_to_dict(
            old_instance, fields=["balance_cash", "balance_gold", "balance_silver"]
        )


class InvoiceItem(models.Model):
    # Fields
    is_return = models.BooleanField(default=False, verbose_name="Return")
    quantity = models.IntegerField()
    weight = models.DecimalField(max_digits=10, decimal_places=3)
    # remove less stone
    less_stone = models.DecimalField(
        max_digits=10, decimal_places=3, default=0, verbose_name="less wt"
    )
    touch = models.DecimalField(max_digits=10, decimal_places=3)
    wastage = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    net_wt = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    making_charge = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    hallmark_charge = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    metal_balance = MoneyField(
        max_digits=14, decimal_places=3, default_currency="USD", default=0
    )
    cash_balance = MoneyField(
        max_digits=14, decimal_places=3, default_currency="INR", default=0
    )

    # Relationship Fields
    product = models.ForeignKey(
        Stock, on_delete=models.CASCADE, related_name="sold_items"
    )
    invoice = models.ForeignKey(
        "sales.Invoice", on_delete=models.CASCADE, related_name="sale_items"
    )
    approval_line = models.ForeignKey(
        "approval.ApprovalLine",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="sold_items",
    )

    class Meta:
        ordering = ("-pk",)

    def __str__(self):
        return "%s" % self.pk

    def get_absolute_url(self):
        return reverse("sales:sales_invoiceitem_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("sales:sales_invoiceitem_update", args=(self.pk,))

    def get_delete_url(self):
        return reverse(
            "sales:sales_invoiceitem_delete",
            kwargs={"id": self.id, "parent_id": self.invoice.id},
        )

    def get_hx_edit_url(self):
        kwargs = {"parent_id": self.invoice.id, "id": self.id}
        return reverse("sales:hx-invoiceitem-detail", kwargs=kwargs)

    def get_nettwt(self):
        return (self.weight * self.touch) / 100

    def save(self, *args, **kwargs):
        self.net_wt = self.get_nettwt()
        self.metal_balance_currency = (
            "USD" if self.product.variant.product.category.name == "Gold" else "EUR"
        )
        self.cash_balance = self.making_charge + self.hallmark_charge
        self.metal_balance = self.net_wt
        return super(InvoiceItem, self).save(*args, **kwargs)

    def delete(self, unpost=False, *args, **kwargs):
        if unpost:
            self.unpost()
        super(InvoiceItem, self).delete(*args, **kwargs)

    def balance(self):
        return Balance([self.metal_balance, self.cash_balance])

    def is_changed(self, old_instance):
        # https://stackoverflow.com/questions/31286330/django-compare-two-objects-using-fields-dynamically
        # TODO efficient way to compare old and new instances
        # Implement logic to compare old and new instances
        # Compare all fields using dictionaries
        from django.forms import model_to_dict

        return model_to_dict(
            self, fields=["product", "quantity", "weight"]
        ) != model_to_dict(old_instance, fields=["product", "quantity", "weight"])

    def get_journal_entry(self, desc=None):
        if self.invoice.journal_entries.exists():
            return self.invoice.journal_entries.latest()
        else:
            return JournalEntry.objects.create(
                content_object=self.invoice,
                desc=self.invoice.__class__.__name__,
            )

    @transaction.atomic()
    def post(self):
        je = self.get_journal_entry()
        print(f"je:{je}")
        if not self.is_return:
            print("not return")
            if self.approval_line:
                # unpost the approval line to return the stocklot from approvalline
                stock_journal_entry = self.approval_line.get_journal_entry()
                self.approval_line.unpost(stock_journal)
                self.approval_line.update_status()
            # post the invoice item to deduct the stock from stocklot
            x = self.product.transact(self.weight, self.quantity, "S", journal_entry=je)
            print(f"posting:{x}")
        else:
            print("return")
            x = self.product.transact(
                self.weight, self.quantity, "SR", journal_entry=je
            )
            print(f"posting:{x}")

    @transaction.atomic()
    def unpost(self):
        je = self.get_journal_entry()
        print(f"je:{je}")
        if self.is_return:
            self.product.transact(self.weight, self.quantity, "S", journal_entry=je)
        else:
            if self.approval_line:
                # post the approval line to deduct the stock from invoiceitem
                stock_journal_entry = self.approval_line.get_journal()
                self.approval_line.post(stock_journal_entry)
                self.approval_line.update_status()
            x = self.product.transact(
                self.weight, self.quantity, "SR", journal_entry=je
            )
            print(f"unposting:{x}")


class SaleBalance(models.Model):
    """
    SELECT sales_invoice.id AS voucher_id,
        COALESCE(sum(pi.cash_balance), 0.0) AS cash_balance,
        COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'USD'::text), 0.0) AS gold_balance,
        COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'EUR'::text), 0.0) AS silver_balance,
        ARRAY[ROW(COALESCE(sum(pi.cash_balance), 0.0)::numeric(14,0), 'INR'::character varying(3))::money_value, ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'USD'::text), 0.0)::numeric(14,0), 'USD'::character varying(3))::money_value, ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'EUR'::text), 0.0)::numeric(14,0), 'EUR'::character varying(3))::money_value] AS balances,
        COALESCE(sum(pa.allocated) FILTER (WHERE pa.allocated_currency::text = 'INR'::text), 0.0) AS cash_received,
        COALESCE(sum(pa.allocated) FILTER (WHERE pa.allocated_currency::text = 'USD'::text), 0.0) AS gold_received,
        COALESCE(sum(pa.allocated) FILTER (WHERE pa.allocated_currency::text = 'EUR'::text), 0.0) AS silver_received,
        ARRAY[ROW(COALESCE(sum(pa.allocated) FILTER (WHERE pa.allocated_currency::text = 'INR'::text), 0.0)::numeric(14,0), 'INR'::character varying(3))::money_value, ROW(COALESCE(sum(pa.allocated) FILTER (WHERE pa.allocated_currency::text = 'USD'::text), 0.0)::numeric(14,0), 'USD'::character varying(3))::money_value, ROW(COALESCE(sum(pa.allocated) FILTER (WHERE pa.allocated_currency::text = 'EUR'::text), 0.0)::numeric(14,0), 'EUR'::character varying(3))::money_value] AS received
    FROM sales_invoice
     JOIN sales_invoiceitem pi ON pi.invoice_id = sales_invoice.id
     LEFT JOIN sales_receiptallocation pa ON pa.invoice_id = sales_invoice.id
    GROUP BY sales_invoice.id;"""

    voucher = models.OneToOneField(
        "sales.Invoice",
        on_delete=models.DO_NOTHING,
        primary_key=True,
        related_name="sale_balance",
    )
    cash_balance = models.DecimalField(max_digits=14, decimal_places=3)
    gold_balance = models.DecimalField(max_digits=14, decimal_places=3)
    silver_balance = models.DecimalField(max_digits=14, decimal_places=3)
    balances = ArrayField(MoneyValueField(null=True, blank=True))
    cash_received = models.DecimalField(max_digits=14, decimal_places=3)
    gold_received = models.DecimalField(max_digits=14, decimal_places=3)
    silver_received = models.DecimalField(max_digits=14, decimal_places=3)
    received = ArrayField(MoneyValueField(null=True, blank=True))

    class Meta:
        managed = False
        db_table = "sales_balance"

    def __str__(self):
        return f"Balance:{Balance([self.balances]) - Balance([self.received])}"

    def balance(self):
        return Balance([self.balances]) - Balance([self.received])
