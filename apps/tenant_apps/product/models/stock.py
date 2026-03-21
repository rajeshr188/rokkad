from datetime import datetime
from decimal import Decimal

from django.db import models, transaction
from django.db.models.functions import Coalesce
from django.shortcuts import reverse

from apps.tenant_apps.dea.models import JournalEntry

from ...utils.friendlyid import encode
from ..managers import StockManager

# double entry accounting applies to stocks too:THINK: how to implement


class Stock(models.Model):

    """
    represents stock for each product variant.this stock is used in sale/purchase purposes
    """

    # should this be mptt?Maybe yes i suppose
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    reorder_level = models.IntegerField(default=1)
    quantity = models.IntegerField(default=0)
    weight = models.DecimalField(max_digits=10, decimal_places=3)
    sku = models.CharField(max_length=20, blank=True, null=True)
    lot_no = models.CharField(max_length=20, blank=True, null=True)
    serial_no = models.CharField(max_length=8, blank=True, null=True, unique=True)
    huid = models.CharField(max_length=7, null=True, blank=True, unique=True)
    purchase_touch = models.DecimalField(max_digits=10, decimal_places=3)
    purchase_rate = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )
    is_unique = models.BooleanField(default=False)

    class StockStatusChoices(models.TextChoices):
        EMPTY = "Empty", "Empty"
        AVAILABLE = "Available", "Available"
        SOLD = "Sold", "Sold"
        APPROVAL = "Approval", "Approval"
        RETURN = "Return", "Return"
        DAMAGED = "Damaged", "Damaged"
        LOST = "Lost", "Lost"
        RESERVED = "Reserved", "Reserved"

    status = models.CharField(
        max_length=10,
        choices=StockStatusChoices.choices,
        default=StockStatusChoices.EMPTY,
    )

    purchase_item = models.OneToOneField(
        "purchase.PurchaseItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_item",
    )
    variant = models.ForeignKey(
        "product.ProductVariant",
        on_delete=models.CASCADE,
        related_name="stocks",
        null=True,
        blank=True,
    )
    parent_stock = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent lot if this was created via merge/split operation"
    )
    objects = StockManager()

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        cb = self.current_balance()
        return f"{self.huid or self.serial_no or ''} | {self.lot_no} |{self.variant} | {cb} | {self.status}"

    def get_absolute_url(self):
        return reverse("product_stock_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("product_stock_update", args=(self.pk,))

    def get_pure_by_cost(self):
        return self.get_weight() * self.purchase_touch

    def get_weight(self):
        return self.stockbalance.get_wt_bal()

    def get_quantity(self):
        return self.stockbalance.get_qty_bal()

    def save(self, *args, **kwargs):
        # Save without lot_no and serial_no
        super().save(*args, **kwargs)

        # Now self.pk is not None
        if self.huid:
            self.is_unique = True
            self.serial_no = self.huid
        if not self.serial_no and self.is_unique:
            self.serial_no = "JE" + encode(self.pk)
        if not self.lot_no:
            if self.purchase_item is not None:
                self.lot_no = "-".join(
                    [
                        self.purchase_item.invoice.supplier.name[:4].upper(),
                        self.purchase_item.invoice.created.strftime("%d%m%y"),
                        str(self.pk),
                    ]
                )
            else:
                self.lot_no = datetime.now().strftime("%d%m%y") + "-" + str(self.pk)

        # Save again with updated lot_no and serial_no
        super().save(update_fields=["lot_no", "serial_no"])

    def audit(self):
        try:
            last_statement = self.stockstatement_set.latest()
        except StockStatement.DoesNotExist:
            last_statement = None

        if last_statement is not None:
            ls_wt = last_statement.Closing_wt
            ls_qty = last_statement.Closing_qty
        else:
            ls_wt = 0
            ls_qty = 0

        stock_in = self.stock_in_txns(last_statement)
        stock_out = self.stock_out_txns(last_statement)
        cb_wt = ls_wt + (stock_in["wt"] - stock_out["wt"])
        cb_qty = ls_qty + (stock_in["qty"] - stock_out["qty"])

        return StockStatement.objects.create(
            stock=self,
            Closing_wt=cb_wt,
            Closing_qty=cb_qty,
            total_wt_in=stock_in["wt"] if stock_in["wt"] else 0.0,
            total_qty_in=stock_in["qty"] if stock_in["qty"] else 0,
            total_wt_out=stock_out["wt"] if stock_out["wt"] else 0.0,
            total_qty_out=stock_out["qty"] if stock_out["qty"] else 0,
        )

    def stock_in_txns(self, ls):
        """
        return all the In transactions since last audit"""
        st = self.stocktransaction_set.all()
        if ls:
            st = st.filter(created__gte=ls.created)
        st = st.filter(movement_type__direction="+")
        # st = st.filter(movement_type__in=["P", "SR", "AR", "AD", "IN","SM"])

        return st.aggregate(
            qty=Coalesce(models.Sum("quantity", output_field=models.IntegerField()), 0),
            wt=Coalesce(
                models.Sum("weight", output_field=models.DecimalField()), Decimal(0.0)
            ),
        )

    def stock_out_txns(self, ls):
        """
        return all Out Transactions since last audit
        """
        st = self.stocktransaction_set.all()
        if ls:
            st = st.filter(created__gte=ls.created)
        st = st.filter(movement_type__direction="-")
        # st = st.filter(movement_type__in=["PR", "S", "A", "RM", "OT","SS"])

        return st.aggregate(
            qty=Coalesce(models.Sum("quantity", output_field=models.IntegerField()), 0),
            wt=Coalesce(
                models.Sum("weight", output_field=models.DecimalField()), Decimal(0.0)
            ),
        )

    def current_balance(self):
        """
        compute balance from last audit and append following
        """
        bal = {}
        Closing_wt: Decimal = 0
        Closing_qty: int = 0

        try:
            ls = self.stockstatement_set.latest()
            Closing_wt = ls.Closing_wt
            Closing_qty = ls.Closing_qty

        except StockStatement.DoesNotExist:
            ls = None

        in_txns = self.stock_in_txns(ls)
        out_txns = self.stock_out_txns(ls)
        bal["wt"] = Closing_wt + (in_txns["wt"] - out_txns["wt"])
        bal["qty"] = Closing_qty + (in_txns["qty"] - out_txns["qty"])
        return bal

    def get_age(self):
        """
        returns age of stock in days
        """
        return (self.created - self.updated).days

    def transact(self, weight, quantity, movement_type, journal_entry):
        """
        Modifies weight and quantity associated with the stock based on movement type
        Returns none
        """
        t = StockTransaction.objects.create(
            stock=self,
            weight=weight,
            quantity=quantity,
            movement_type_id=movement_type,
            journal_entry=journal_entry,
        )
        self.update_status()
        return t

    # @classmethod
    # def with_balance(cls):
    #     balance_subquery = (
    #         StockLotBalance.objects.filter(stocklot_id=OuterRef("pk"))
    #         .values("stocklot_id")
    #         .annotate(total_balance=Coalesce(Sum("balance"), 0))
    #         .values("total_balance")
    #     )
    #     queryset = cls.objects.annotate(balance=Subquery(balance_subquery))
    #     return queryset

    def generate_barcode(self):
        print("generating barcode")
        if not self.serial_no:
            self.serial_no = "JE" + encode(self.pk)
            self.save()

    def update_status(self):
        cb = self.current_balance()
        if cb["wt"] <= 0.0 or cb["qty"] <= 0:
            self.status = "Empty"
        else:
            self.status = "Available"
        self.save()

    def get_total_sold(self):
        return self.sold_items.aggregate(
            qty=Coalesce(models.Sum("quantity", output_field=models.IntegerField()), 0),
            wt=Coalesce(
                models.Sum("weight", output_field=models.DecimalField()), Decimal(0.0)
            ),
        )

    @transaction.atomic
    def merge(self, lot: "Stock"):
        """
        a lots qty and weight remains same throughout its life,
        any add/remove/merge/split on a lot is performed via transactions,
        and current balance of a lot is derived from transaction.

        Return : new_lot:Stock
        """

        if self.variant != lot.variant:
            raise Exception(
                "cannot merge lots from different variant"
            )

        new_lot = Stock(
            variant=self.variant,
            weight=lot.weight + self.weight,
            quantity=lot.quantity + self.quantity,
        )
        new_lot.save()
        
        self.transact(
            self.weight, self.quantity, movement_type="RM", journal_entry=None
        )
        lot.transact(lot.weight, lot.quantity, movement_type="RM", journal_entry=None)
        new_lot.transact(
            self.weight + lot.weight,
            self.quantity + lot.quantity,
            movement_type="AD",
            journal_entry=None,
        )
        return new_lot

    @transaction.atomic
    def split(self, wt: Decimal, qty: int, is_unique: bool = False):
        """
        split a lot by creating a new lot and transfering the wt & qty to new lot
        """
        if not self.is_unique and self.quantity > qty and self.weight > wt:
            new_lot = Stock.objects.create(
                variant=self.variant,
                weight=wt,
                quantity=qty,
                purchase_touch=self.purchase_touch,
                purchase_rate=self.purchase_rate,
                sku=self.sku,
                is_unique=is_unique,
            )
            new_lot.transact(weight=wt, quantity=qty, movement_type="AD", journal_entry=None)

            self.transact(weight=wt, quantity=qty, movement_type="SS", journal_entry=None)

            return new_lot
        raise Exception("Unique lots cant be split")


class Movement(models.Model):

    """represents movement_type with direction of stock/lot transaction
    ex: [('purchase','+'),('purchase return','-'),('sales','-'),('sale return','+'),
        ('split','-'),('merge','+')]
    """

    id = models.CharField(max_length=3, primary_key=True)
    name = models.CharField(max_length=30)
    direction = models.CharField(max_length=1, default="+")

    def __str__(self):
        return self.name


class StockTransaction(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    quantity = models.IntegerField(default=0, blank=True)
    weight = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    description = models.TextField(null=True, blank=True)
    movement_type = models.ForeignKey(Movement, on_delete=models.CASCADE, default="P")
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, null=True, blank=True)
    stock_item = models.ForeignKey(
        'StockItem', on_delete=models.CASCADE, null=True, blank=True,
        related_name='transactions',
        help_text="Union FK: either stock_id or stock_item_id must be set"
    )
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="stxns", null=True, blank=True
    )

    def __str__(self):
        subject = self.stock or self.stock_item
        return f"{subject} {self.movement_type} {self.quantity} {self.weight}"

    def get_update_url(self):
        return reverse("product_stocktransaction_update", args=(self.pk,))


class StockStatement(models.Model):
    ss_method = (
        ("Auto", "Auto"),
        ("Physical", "Physical"),
    )
    method = models.CharField(max_length=20, choices=ss_method, default="Auto")
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, null=True, blank=True)
    stock_item = models.ForeignKey(
        'StockItem', on_delete=models.CASCADE, null=True, blank=True,
        related_name='statements',
        help_text="Union FK: either stock_id or stock_item_id must be set"
    )
    created = models.DateTimeField(auto_now_add=True)
    Closing_wt = models.DecimalField(max_digits=14, decimal_places=3)
    Closing_qty = models.IntegerField()
    total_wt_in = models.DecimalField(max_digits=14, decimal_places=3, default=0.0)
    total_wt_out = models.DecimalField(max_digits=14, decimal_places=3, default=0.0)
    total_qty_in = models.IntegerField(default=0.0)
    total_qty_out = models.IntegerField(default=0.0)

    class Meta:
        ordering = ("created",)
        get_latest_by = ["created"]

    def __str__(self):
        subject = self.stock or self.stock_item
        return f"{subject} - qty:{self.Closing_qty} wt:{self.Closing_wt}"


class StockItem(models.Model):
    """
    Represents a unique/trackable stock unit for high-value items.
    Each StockItem is a single unit with its own lineage and transaction history.
    """
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    quantity = models.IntegerField(default=1)  # Always 1 for unique units
    weight = models.DecimalField(max_digits=10, decimal_places=3)
    
    # Identification
    serial_no = models.CharField(max_length=8, blank=True, null=True, unique=True)
    huid = models.CharField(max_length=7, null=True, blank=True, unique=True)
    
    # Sourcing
    purchase_touch = models.DecimalField(max_digits=10, decimal_places=3)
    purchase_rate = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )
    purchase_item = models.ForeignKey(
        "purchase.PurchaseItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_items",
        help_text="Original purchase source if applicable"
    )
    
    # Variant and lineage
    variant = models.ForeignKey(
        "product.ProductVariant",
        on_delete=models.CASCADE,
        related_name="stock_items",
        null=True,
        blank=True,
    )
    parent_stock = models.ForeignKey(
        Stock,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="split_items",
        help_text="Parent lot if created via split operation"
    )
    
    # Status
    class StockItemStatusChoices(models.TextChoices):
        AVAILABLE = "Available", "Available"
        SOLD = "Sold", "Sold"
        DAMAGED = "Damaged", "Damaged"
        LOST = "Lost", "Lost"
        RESERVED = "Reserved", "Reserved"

    status = models.CharField(
        max_length=10,
        choices=StockItemStatusChoices.choices,
        default=StockItemStatusChoices.AVAILABLE,
    )
    
    class Meta:
        ordering = ("-created",)

    def __str__(self):
        cb = self.current_balance()
        return f"{self.huid or self.serial_no or f'Item#{self.pk}'} | {self.variant} | qty:{cb['qty']} wt:{cb['wt']} | {self.status}"

    def get_absolute_url(self):
        return reverse("product_stockitem_detail", args=(self.pk,))

    def current_balance(self):
        """
        Compute balance from transactions for unique item.
        """
        try:
            ls = self.statements.latest()
            Closing_wt = ls.Closing_wt
            Closing_qty = ls.Closing_qty
        except StockStatement.DoesNotExist:
            Closing_wt = 0
            Closing_qty = 0

        in_txns = self.stock_in_txns(ls if 'ls' in locals() else None)
        out_txns = self.stock_out_txns(ls if 'ls' in locals() else None)
        return {
            'wt': Closing_wt + (in_txns['wt'] - out_txns['wt']),
            'qty': Closing_qty + (in_txns['qty'] - out_txns['qty'])
        }

    def stock_in_txns(self, ls=None):
        """Return all in transactions since last audit."""
        st = self.transactions.all()
        if ls:
            st = st.filter(created__gte=ls.created)
        st = st.filter(movement_type__direction="+")
        return st.aggregate(
            qty=Coalesce(models.Sum("quantity", output_field=models.IntegerField()), 0),
            wt=Coalesce(
                models.Sum("weight", output_field=models.DecimalField()), Decimal(0.0)
            ),
        )

    def stock_out_txns(self, ls=None):
        """Return all out transactions since last audit."""
        st = self.transactions.all()
        if ls:
            st = st.filter(created__gte=ls.created)
        st = st.filter(movement_type__direction="-")
        return st.aggregate(
            qty=Coalesce(models.Sum("quantity", output_field=models.IntegerField()), 0),
            wt=Coalesce(
                models.Sum("weight", output_field=models.DecimalField()), Decimal(0.0)
            ),
        )

    def transact(self, weight, quantity, movement_type, journal_entry=None):
        """
        Record movement for this unique item.
        """
        t = StockTransaction.objects.create(
            stock_item=self,
            weight=weight,
            quantity=quantity,
            movement_type_id=movement_type,
            journal_entry=journal_entry,
        )
        self.update_status()
        return t

    def update_status(self):
        """Update status based on current balance."""
        cb = self.current_balance()
        if cb['wt'] <= 0.0 or cb['qty'] <= 0:
            self.status = 'Sold'
        else:
            self.status = 'Available'
        self.save(update_fields=['status'])


class StockBalance(models.Model):
    stock = models.OneToOneField(Stock, on_delete=models.DO_NOTHING, primary_key=True)
    closing_wt = models.DecimalField(max_digits=14, decimal_places=3)
    closing_qty = models.IntegerField()
    in_wt = models.DecimalField(max_digits=14, decimal_places=3)
    in_qty = models.IntegerField()
    out_wt = models.DecimalField(max_digits=14, decimal_places=3)
    out_qty = models.IntegerField()

    class Meta:
        managed = False
        db_table = "stock_balance"

    def get_qty_bal(self):
        return self.closing_qty + self.in_qty - self.out_qty

    def get_wt_bal(self):
        return self.closing_wt + self.in_wt - self.out_wt
