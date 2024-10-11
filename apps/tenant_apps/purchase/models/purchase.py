from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import CharField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.forms import model_to_dict
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from djmoney.models.fields import MoneyField
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (AccountStatement,  # , JournalTypes
                                         JournalEntry)
from apps.tenant_apps.dea.models.moneyvalue import MoneyValueField
from apps.tenant_apps.dea.utils.currency import Balance
from apps.tenant_apps.product.attributes import get_product_attributes_data
from apps.tenant_apps.product.models import ProductVariant, Stock
from apps.tenant_apps.terms.models import PaymentTerm

from ..managers import PurchaseQueryset


class Purchase(models.Model):
    # Fields
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    voucher_date = models.DateTimeField(default=timezone.now, db_index=True)
    voucher_no = models.CharField(max_length=20, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,  # cant be null
        blank=True,  # cant be blank
        related_name="purchases_created",
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
    supplier = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="purchases",
        verbose_name=_("Supplier"),
    )
    term = models.ForeignKey(
        PaymentTerm,
        on_delete=models.SET_NULL,
        related_name="purchase_term",
        blank=True,
        null=True,
    )
    journal_entries = GenericRelation(
        JournalEntry,
        related_query_name="purchase_doc",
    )
    objects = PurchaseQueryset.as_manager()

    class Meta:
        ordering = (
            "id",
            "created",
        )

    def __str__(self):
        return f"{self.id}"

    def get_absolute_url(self):
        return reverse("purchase:purchase_invoice_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("purchase:purchase_invoice_update", args=(self.id,))

    def get_next(self):
        return self.__class__.objects.filter(id__gt=self.id).order_by("id").first()

    def get_previous(self):
        return self.__class__.objects.filter(id__lt=self.id).order_by("id").last()

    def get_item_children(self):
        return self.purchase_items.all()

    def get_gross_wt(self):
        # this should return the sum of all purchaseitems weight by metal_balance_currency
        weights = self.purchase_items.values("metal_balance_currency").annotate(
            amount=Sum("weight"), currency=F("metal_balance_currency")
        )
        money_values = [Money(item["amount"], item["currency"]) for item in weights]
        return Balance(money_values)

    def get_net_wt(self):
        weights = self.purchase_items.values("metal_balance_currency").annotate(
            amount=Sum("net_wt"), currency=F("metal_balance_currency")
        )
        money_values = [Money(item["amount"], item["currency"]) for item in weights]
        return Balance(money_values)

    def get_sum_metal_balance(self):
        return self.purchase_items.values("metal_balance_currency").annotate(
            total=Sum("metal_balance")
        )

    def get_sum_gold_balance(self):
        bal = (
            self.purchase_items.aggregate(
                total=Sum("metal_balance", filter=Q(metal_balance_currency="USD"))
            )["total"]
            or 0
        )
        return Money(bal, "USD")

    def get_sum_silver_balance(self):
        bal = (
            self.purchase_items.aggregate(
                total=Sum("metal_balance", filter=Q(metal_balance_currency="EUR"))
            )["total"]
            or 0
        )
        return Money(bal, "EUR")

    def get_sum_cash_balance(self):
        bal = self.purchase_items.aggregate(total=Sum("cash_balance"))["total"] or 0
        return Money(bal, "INR")

    @property
    def overdue_days(self):
        return (timezone.now().date() - self.due_date).days

    def get_gst(self):
        amount = self.purchase_items.aggregate(t=Sum("cash_balance"))["t"] or 0
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

    def save(self, calculate_balances=True, *args, **kwargs):
        if self.pk and calculate_balances:
            self.calculate_balances()
        if not self.due_date:
            if self.term:
                self.due_date = self.voucher_date + timedelta(days=self.term.due_days)
        super(Purchase, self).save(*args, **kwargs)

    # def delete(self, *args, **kwargs):
    #     # add custom logic here
    #     # for example, check if the object can be deleted
    #     if self.can_be_deleted():
    #         # call the parent's delete method to actually delete the object
    #         super(MyModel, self).delete(*args, **kwargs)
    #     else:
    #         # raise an exception or return a message to indicate that deletion is not allowed
    #         raise Exception("Deletion not allowed for this object")

    # @property
    # def outstanding_balance(self):
    #     return self.balance - self.total_allocated_amount

    @classmethod
    def with_outstanding_balance(cls):
        return cls.objects.annotate(
            total_allocated_cash=Coalesce(
                Sum(
                    "paymentallocation__allocated",
                    filter=Q(paymentallocation__allocated_currency="INR"),
                ),
                0,
                output_field=models.DecimalField(),
            ),
            total_allocated_gold=Coalesce(
                Sum(
                    "paymentallocation__allocated",
                    filter=Q(paymentallocation__allocated_currency="USD"),
                ),
                0,
                output_field=models.DecimalField(),
            ),
            total_allocated_silver=Coalesce(
                Sum(
                    "paymentallocation__allocated",
                    filter=Q(paymentallocation__allocated_currency="EUR"),
                ),
                0,
                output_field=models.DecimalField(),
            ),
        ).annotate(
            outstanding_balance_cash=F("purchase_balance__cash_balance")
            - F("total_allocated_cash"),
            outstanding_balance_gold=F("purchase_balance__gold_balance")
            - F("total_allocated_gold"),
            outstanding_balance_silver=F("purchase_balance__silver_balance")
            - F("total_allocated_silver"),
        )

    # overdue_invoices = Invoice.with_outstanding_balance().filter(outstanding_balance_cash__gt=0, due_date__lt=date.today())

    def get_allocations(self):
        if self.paymentallocation_set.exists():
            paid = self.paymentallocation_set.aggregate(
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
        return Balance(
            [
                self.balance_cash or Money(0, "INR"),
                self.balance_gold or Money(0, "USD"),
                self.balance_silver or Money(0, "EUR"),
            ]
        )

    def get_balance_with_allocations(self):
        return self.balance - self.get_allocations()

    def get_transactions(self):
        if not hasattr(self.supplier, "account"):
            # Create the account here
            self.supplier.save()

        inv = "GST INV" if self.is_gst else "Non-GST INV"
        tax = self.get_gst()

        lt, at = [], []

        cash_balance = self.balance_cash  # self.balance["INR"]
        gold_balance = self.balance_gold  # self.balance["USD"]
        silver_balance = self.balance_silver  # self.balance["EUR"]
        if all(v is None for v in [cash_balance, gold_balance, silver_balance]):
            print("No balances to post")
            return None, None
        if cash_balance is not None:
            lt.append(
                {
                    "ledgerno": "Sundry Creditors",
                    "ledgerno_dr": inv,
                    "amount": cash_balance,
                }
            )
            at.append(
                {
                    "ledgerno": "Sundry Creditors",
                    "XactTypeCode": "Dr",
                    "Account": self.supplier.account,
                    "XactTypeCode_Ext": "CRPU",
                    "amount": cash_balance,
                }
            )
            if self.is_gst:
                lt.append(
                    {
                        "ledgerno": "Sundry Creditors",
                        "ledgerno_dr": "Input Igst",
                        "amount": tax,
                    }
                )
                at.append(
                    {
                        "ledgerno": "Sundry Creditors",
                        "XactTypeCode": "Cr",
                        "XactTypeCode_Ext": "CRPU",
                        "Account": self.supplier.account,
                        "amount": tax,
                    }
                )

        if gold_balance is not None:
            lt.append(
                {
                    "ledgerno": "Sundry Creditors",
                    "ledgerno_dr": inv,
                    "amount": gold_balance,
                }
            )
            at.append(
                {
                    "ledgerno": "Sundry Creditors",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_Ext": "CRPU",
                    "Account": self.supplier.account,
                    "amount": gold_balance,
                }
            )

        if silver_balance is not None:
            lt.append(
                {
                    "ledgerno": "Sundry Creditors",
                    "ledgerno_dr": inv,
                    "amount": silver_balance,
                }
            )
            at.append(
                {
                    "ledgerno": "Sundry Creditors",
                    "XactTypeCode": "Dr",
                    "XactTypeCode_Ext": "CRPU",
                    "Account": self.supplier.account,
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
        # if no je or je older than statement create je and txns else update txns
        # if not self.journal_entries.exists() or self.journal_entries.latest().created < self.supplier.account.accountstatements.latest('created').created:

        # je = self.journal_entries.latest('created') or None
        # statement = self.supplier.account.accountstatements.latest('created') or None
        # if je and (statement is None or statement.created < je.created):
        #     self.delete_journal_entry()

        lt, at = self.get_transactions()
        if lt and at:
            journal_entry = self.get_journal_entry()
            journal_entry.transact(lt, at)

    def reverse_transactions(self):
        # i.e if je is older than the latest statement then reverse the transactions else do nothing
        try:
            statement = self.supplier.account.accountstatements.latest("created")
        except AccountStatement.DoesNotExist:
            statement = None
        journal_entry = self.get_journal_entry()

        if journal_entry and statement and journal_entry.created < statement.created:
            lt, at = self.get_transactions()
            if lt and at:
                journal_entry.untransact(lt, at)
        else:
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


class PurchaseItem(models.Model):
    # TODO:if saved and lot has sold items this shouldnt/cant be edited

    # Fields
    huid = models.CharField(max_length=7, blank=True, null=True, unique=True)
    quantity = models.IntegerField()
    weight = models.DecimalField(max_digits=14, decimal_places=3)
    touch = models.DecimalField(max_digits=14, decimal_places=3)
    net_wt = models.DecimalField(max_digits=14, decimal_places=3, default=0, blank=True)
    # normalize charges
    making_charge = models.DecimalField(
        max_digits=14, decimal_places=3, blank=True, null=True, default=0
    )
    hallmark_charge = models.DecimalField(
        max_digits=14, decimal_places=3, blank=True, null=True, default=0
    )
    metal_balance = MoneyField(max_digits=14, decimal_places=3, default_currency="USD")
    cash_balance = MoneyField(max_digits=14, decimal_places=3, default_currency="INR")

    # Relationship Fields
    product = models.ForeignKey(
        ProductVariant, on_delete=models.CASCADE, related_name="products"
    )
    invoice = models.ForeignKey(
        "purchase.Purchase", on_delete=models.CASCADE, related_name="purchase_items"
    )

    class Meta:
        ordering = ("-pk",)

    def __str__(self):
        return "%s" % self.pk

    def get_absolute_url(self):
        return reverse("purchase:purchase_purchaseitem_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("purchase:purchase_purchaseitem_update", args=(self.pk,))

    def get_hx_edit_url(self):
        kwargs = {"parent_id": self.invoice.id, "id": self.id}
        return reverse("purchase:purchase_purchaseitem_detail", kwargs=kwargs)

    def get_delete_url(self):
        return reverse(
            "purchase:purchase_purchaseitem_delete",
            kwargs={"id": self.id, "parent_id": self.invoice.id},
        )

    def get_nettwt(self):
        return self.weight * (self.touch / 100)

    def save(self, *args, **kwargs):
        self.net_wt = self.get_nettwt()
        self.metal_balance_currency = (
            "USD" if self.product.product.category.name == "Gold" else "EUR"
        )
        self.cash_balance = self.making_charge + self.hallmark_charge
        self.metal_balance = self.net_wt
        super(PurchaseItem, self).save(*args, **kwargs)

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
        print("Posting the purchase item")
        stock, created = Stock.objects.get_or_create(
            purchase_item=self,
            variant=self.product,
            weight=self.weight,
            quantity=self.quantity,
            purchase_touch=self.touch,
            purchase_rate=self.invoice.gold_rate
            if self.product.product.category.name == "Gold"
            else self.invoice.silver_rate,
            huid=self.huid,
        )
        je = self.get_journal_entry()
        print(f"je:{je}")
        stock.transact(
            weight=self.weight,
            quantity=self.quantity,
            movement_type="P",
            journal_entry=je,
        )

    @transaction.atomic()
    def unpost(self):
        """
        add lot back to stock lot if item is_return,
        remove lot from stocklot if item is not return item"""
        print("Unposting the purchase item")
        je = self.get_journal_entry()
        print(f"je:{je}")
        try:
            # self.stock_item.delete()
            lot = self.stock_item
            x = lot.transact(
                journal_entry=je,
                weight=lot.weight,
                quantity=lot.quantity,
                movement_type="PR",
            )
            print(x)

        except Stock.DoesNotExist:
            print("Oops!while Unposting there was no said stock.  Try again...")

    def delete(self, delete_stock=False, *args, **kwargs):
        purchase = self.invoice
        if delete_stock and hasattr(self, "stock_item"):
            self.stock_item.delete()
        super().delete(*args, **kwargs)
        purchase.save()


"""
 initial logic for purchase balance
  SELECT purchase_invoice.id AS voucher_id,
    sum(pi.cash_balance) AS cash_balance,
    sum(pi.metal_balance) AS metal_balance
   FROM purchase_invoice
     JOIN purchase_invoiceitem pi ON pi.invoice_id = purchase_invoice.id
  GROUP BY purchase_invoice.id;
    --------------------------------------------
  improved logic:
  SELECT purchase_invoice.id AS voucher_id,
    sum(pi.cash_balance) AS cash_balance,
    sum(pi.metal_balance) FILTER(WHERE pi.metal_balance_currency = 'USD') AS gold_balance,
    sum(pi.metal_balance) FILTER(WHERE pi.metal_balance_currency = 'EUR') AS silver_balance
   FROM purchase_invoice
     JOIN purchase_invoiceitem pi ON pi.invoice_id = purchase_invoice.id
  GROUP BY 
    purchase_invoice.id;
  --------------------------------------------


   SELECT purchase_invoice.id AS voucher_id,
    ROW(COALESCE(sum(pi.cash_balance), 0::numeric)::numeric(14,0), 'INR'::character varying(3))::money_value AS cash_balance,
    ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'USD'::text), 0::numeric)::numeric(14,0), 'USD'::character varying(3))::money_value AS gold_balance,
    ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'EUR'::text), 0::numeric)::numeric(14,0), 'EUR'::character varying(3))::money_value AS silver_balance,
    ARRAY[
		ROW(COALESCE(sum(pi.cash_balance), 0::numeric)::numeric(14,0), 'INR'::character varying(3))::money_value, 
		ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'USD'::text), 0::numeric)::numeric(14,0), 'USD'::character varying(3))::money_value, 
		ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'EUR'::text), 0::numeric)::numeric(14,0), 'EUR'::character varying(3))::money_value] AS balances
   FROM purchase_invoice
     JOIN purchase_invoiceitem pi ON pi.invoice_id = purchase_invoice.id
  GROUP BY purchase_invoice.id;

    --------------------------------------------
  final:
  SELECT purchase_invoice.id AS voucher_id,
    ROW(COALESCE(sum(pi.cash_balance), 0.0), 'INR'::character varying(3))::money_value AS cash_balance,
    ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'USD'::text), 0.0), 'USD'::character varying(3))::money_value AS gold_balance,
    ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'EUR'::text), 0.0), 'EUR'::character varying(3))::money_value AS silver_balance,
    ARRAY[
		ROW(COALESCE(sum(pi.cash_balance), 0.0), 'INR'::character varying(3))::money_value, 
		ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'USD'::text), 0.0), 'USD'::character varying(3))::money_value, 
		ROW(COALESCE(sum(pi.metal_balance) FILTER (WHERE pi.metal_balance_currency::text = 'EUR'::text), 0.0), 'EUR'::character varying(3))::money_value
	] AS balances
   FROM purchase_invoice
     JOIN purchase_invoiceitem pi ON pi.invoice_id = purchase_invoice.id
  GROUP BY purchase_invoice.id;"""


# db view for tracking the balance of a invoice from its invoice items in multicurrency
class PurchaseBalance(models.Model):
    voucher = models.OneToOneField(
        Purchase,
        on_delete=models.DO_NOTHING,
        primary_key=True,
        related_name="purchase_balance",
    )
    cash_balance = MoneyValueField(null=True, blank=True)
    gold_balance = MoneyValueField(null=True, blank=True)
    silver_balance = MoneyValueField(null=True, blank=True)
    balances = ArrayField(MoneyValueField(null=True, blank=True))
    # cash_received = models.DecimalField(max_digits=14, decimal_places=3)
    # gold_received = models.DecimalField(max_digits=14, decimal_places=3)
    # silver_received = models.DecimalField(max_digits=14, decimal_places=3)
    # received = ArrayField(MoneyValueField(null=True, blank=True))

    class Meta:
        managed = False
        db_table = "purchase_balance"

    def __str__(self):
        # return f"Balance:{Balance([self.balances]) - Balance([self.received])}"
        return f"Balance:{Balance([self.balances])}"
