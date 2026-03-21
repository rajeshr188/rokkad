from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from django.db.models import F, Func, Q, Sum, Count
from django.db.models.functions import Coalesce
from django.forms import model_to_dict
from django.urls import reverse
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import AccountStatement  # , JournalTypes
from apps.tenant_apps.dea.models import JournalEntry
from apps.tenant_apps.dea.models import Voucher, VoucherStatus
from apps.tenant_apps.dea.utils.currency import Balance
from apps.tenant_apps.product.models import Stock, StockItem
from apps.tenant_apps.terms.models import PaymentTerm


def _resolve_posted_journal_entry(doc):
    if not getattr(doc, "pk", None):
        return None

    content_type = ContentType.objects.get_for_model(doc, for_concrete_model=False)
    voucher = (
        Voucher.objects.filter(
            doc_content_type=content_type,
            doc_object_id=doc.pk,
            status=VoucherStatus.POSTED,
        )
        .order_by("-last_posted_at", "-id")
        .first()
    )
    if not voucher:
        return None

    return voucher.journal_entries.order_by("-id").first()


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

    def with_balances(self):
        return self.prefetch_related("balances", "receiptallocation_set").annotate(
            total_cash=Coalesce(
                Sum("balances__amount", filter=Q(balances__amount_currency="INR")), 0
            ),
            total_gold=Coalesce(
                Sum("balances__amount", filter=Q(balances__amount_currency="USD")), 0
            ),
            total_silver=Coalesce(
                Sum("balances__amount", filter=Q(balances__amount_currency="EUR")), 0
            ),
            allocated_cash=Coalesce(
                Sum(
                    "receiptallocation__allocated",
                    filter=Q(receiptallocation__allocated_currency="INR"),
                ),
                0,
            ),
            allocated_gold=Coalesce(
                Sum(
                    "receiptallocation__allocated",
                    filter=Q(receiptallocation__allocated_currency="USD"),
                ),
                0,
            ),
            allocated_silver=Coalesce(
                Sum(
                    "receiptallocation__allocated",
                    filter=Q(receiptallocation__allocated_currency="EUR"),
                ),
                0,
            ),
        )

    def for_list_view(self):
        return (
            self.select_related("customer", "term", "approval", "created_by")
            .prefetch_related("balances", "journal_entries")
            .with_balances()
        )

    def get_status_counts(self):
        return self.values("status").annotate(count=Count("id"))


class Invoice(models.Model):
    # Fields
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True, editable=False)
    voucher_date = models.DateTimeField(default=timezone.now, db_index=True)
    voucher_no = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)
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
    status = models.CharField(
        max_length=15, choices=status_choices, default="Unpaid", db_index=True
    )
    # make rates auto fill from the latest rates
    gold_rate = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    silver_rate = models.DecimalField(max_digits=14, decimal_places=3, default=0)
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
        indexes = [
            models.Index(fields=["status", "-created"]),
            models.Index(fields=["customer", "-created"]),
            models.Index(fields=["due_date", "status"]),
        ]

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
    def is_overdue(self):
        if self.due_date:
            return timezone.now().date() > self.due_date
        return False

    @property
    def overdue_days(self):
        if self.is_overdue:
            return (timezone.now().date() - self.due_date).days
        return 0

    def deactivate(self):
        self.is_active = False
        self.save(update_fields=["self.is_active"])

    def get_gst(self):
        amount = self.sale_items.aggregate(t=Sum("cash_balance"))["t"] or 0
        return Money(amount * Decimal(0.03), "INR")

    def get_balance(self):
        """Returns the pre-calculated balance from balances table"""
        if not hasattr(self, "_balance"):
            self._balance = Balance([b.amount for b in self.balances.all()])
        return self._balance

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if self.term and not self.due_date:
            # Calculate due date based on payment term
            self.due_date = self.voucher_date.date() + timedelta(
                days=self.term.due_days
            )

        super().save(*args, **kwargs)

        if not is_new:
            self.calculate_balances()

    @transaction.atomic
    def calculate_balances(self):
        """Calculate and store balances in Balance table"""
        self.balances.all().delete()

        if self.is_ratecut:
            total = self._calculate_ratecut_total()
            Balance.objects.create(invoice=self, amount=Money(total, "INR"))
        else:
            self._create_currency_balances()

    def _calculate_ratecut_total(self):
        cash_balance = sum(
            (item.cash_balance for item in self.sale_items.all()),
            Money(0, "INR"),
        )
        gold_balance = sum(
            (
                item.metal_balance
                for item in self.sale_items.filter(metal_balance_currency="USD")
            ),
            Money(0, "USD"),
        )
        silver_balance = sum(
            (
                item.metal_balance
                for item in self.sale_items.filter(metal_balance_currency="EUR")
            ),
            Money(0, "EUR"),
        )

        cash = cash_balance.amount
        gold = gold_balance.amount * self.gold_rate
        silver = silver_balance.amount * self.silver_rate

        total = cash + gold + silver
        if self.is_gst:
            total += total * Decimal("0.03")
        return total

    def _create_currency_balances(self):
        cash_total = sum(
            (item.cash_balance for item in self.sale_items.all()),
            Money(0, "INR"),
        )
        gold_total = sum(
            (
                item.metal_balance
                for item in self.sale_items.filter(metal_balance_currency="USD")
            ),
            Money(0, "USD"),
        )
        silver_total = sum(
            (
                item.metal_balance
                for item in self.sale_items.filter(metal_balance_currency="EUR")
            ),
            Money(0, "EUR"),
        )

        if cash_total.amount:
            Balance.objects.create(invoice=self, amount=cash_total)
        if gold_total.amount:
            Balance.objects.create(invoice=self, amount=gold_total)
        if silver_total.amount:
            Balance.objects.create(invoice=self, amount=silver_total)

    def update_status(self):
        """Update payment status based on outstanding balance"""
        outstanding = self.get_outstanding_balance()
        if outstanding.is_zero():
            self.status = "Paid"
        elif outstanding < self.get_balance():
            self.status = "PartiallyPaid"
        else:
            self.status = "Unpaid"
        self.save(update_fields=["status"])

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

    def get_allocated_payments(self):
        """Returns total allocated payments per currency"""
        allocations = self.receiptallocation_set.values("allocated_currency").annotate(
            total=Coalesce(Sum("allocated"), 0)
        )
        return Balance(
            [Money(item["total"], item["allocated_currency"]) for item in allocations]
        )

    def get_outstanding_balance(self):
        """Returns true outstanding balance after subtracting allocations"""
        total_balance = self.get_balance()
        allocated = self.get_allocated_payments()
        return total_balance - allocated

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
        return _resolve_posted_journal_entry(self)

    def delete_journal_entry(self):
        return None

    def delete_txns(self):
        je = self.get_journal_entry()
        if je is None:
            return
        at = je.atxns.all()
        lt = je.ltxns.all()

        at.delete()
        lt.delete()

    def create_transactions(self):
        return self.get_journal_entry()

    def reverse_transactions(self):
        return self.get_journal_entry()

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
        Stock, on_delete=models.CASCADE, related_name="sold_items", null=True, blank=True
    )
    stock_item = models.ForeignKey(
        StockItem,
        on_delete=models.CASCADE,
        related_name="sold_items",
        null=True,
        blank=True,
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

    def get_inventory_subject(self):
        return self.stock_item or self.product

    def get_inventory_variant(self):
        subject = self.get_inventory_subject()
        return subject.variant if subject else None

    def get_inventory_quantity(self):
        return 1 if self.stock_item_id else self.quantity

    def clean(self):
        has_stock = bool(self.product_id)
        has_stock_item = bool(self.stock_item_id)

        if has_stock == has_stock_item:
            raise ValidationError("InvoiceItem must reference exactly one of product or stock_item")

        if has_stock_item and self.quantity != 1:
            raise ValidationError("InvoiceItem using stock_item must have quantity 1")

    def save(self, *args, **kwargs):
        subject_variant = self.get_inventory_variant()
        if subject_variant is None:
            raise ValueError("InvoiceItem requires a stock or stock_item subject")

        self.net_wt = self.get_nettwt()
        self.metal_balance_currency = (
            "USD" if subject_variant.product.category.name == "Gold" else "EUR"
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
        return self.invoice.get_journal_entry(desc=desc)

    @transaction.atomic()
    def post(self):
        from apps.tenant_apps.product.inventory.services import InventoryMovementService

        subject = self.get_inventory_subject()
        je = self.get_journal_entry()
        if not self.is_return:
            if self.approval_line:
                self.approval_line.unpost(None)
                self.approval_line.update_status()
            return InventoryMovementService.record_movement(
                subject=subject,
                movement_type_id="S",
                quantity=self.get_inventory_quantity(),
                weight=self.weight,
                journal_entry=je,
                description=f"Invoice item {self.pk}",
            )
        else:
            return InventoryMovementService.record_movement(
                subject=subject,
                movement_type_id="SR",
                quantity=self.get_inventory_quantity(),
                weight=self.weight,
                journal_entry=je,
                description=f"Invoice return item {self.pk}",
            )

    @transaction.atomic()
    def unpost(self):
        from apps.tenant_apps.product.inventory.services import InventoryMovementService

        subject = self.get_inventory_subject()
        je = self.get_journal_entry()
        if self.is_return:
            return InventoryMovementService.record_movement(
                subject=subject,
                movement_type_id="S",
                quantity=self.get_inventory_quantity(),
                weight=self.weight,
                journal_entry=je,
                description=f"Invoice return reversal {self.pk}",
            )
        else:
            if self.approval_line:
                self.approval_line.post(None)
                self.approval_line.update_status()
            return InventoryMovementService.record_movement(
                subject=subject,
                movement_type_id="SR",
                quantity=self.get_inventory_quantity(),
                weight=self.weight,
                journal_entry=je,
                description=f"Invoice item reversal {self.pk}",
            )


class Balance(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    invoice = models.ForeignKey(
        "Invoice", on_delete=models.CASCADE, related_name="balances"
    )
    amount = MoneyField(max_digits=14, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return f"{self.amount}"
