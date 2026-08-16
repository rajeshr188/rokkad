"""
Purchase Invoice Voucher Model

Records costs of goods/services purchased from vendors.
Creates AP (Accounts Payable) until vendor is paid.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money
from decimal import Decimal

from .doc import BusinessDoc


class PurchaseType(models.TextChoices):
    """Type of purchase"""

    GOODS = "GOODS", "Goods (Inventory)"
    SERVICES = "SERVICES", "Services (Expense)"
    ASSETS = "ASSETS", "Fixed Assets"
    OTHER = "OTHER", "Other"


class PurchaseInvoiceVoucher(BusinessDoc):
    """
    Purchase Invoice Voucher - Records purchases from vendors.

    ACCRUAL-BASED ARCHITECTURE:
    - Created when goods/services are received
    - Posts to GL immediately (Inventory/Expense ↔ AP)
    - Cash payment handled separately by PaymentVoucher
    - Supports GRN matching for goods

    Example:
    Goods purchased from vendor → GRN → PurchaseInvoiceVoucher → PaymentVoucher (payment)
    """

    # === Core Identity ===
    invoice_number = models.CharField(
        max_length=50, blank=True, help_text="Vendor's invoice number"
    )

    internal_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Our internal reference number (auto-generated: PI-YYYY-MM-0001)",
    )

    invoice_date = models.DateField(
        default=timezone.now, db_index=True, help_text="Date on vendor's invoice"
    )

    received_date = models.DateField(
        null=True, blank=True, help_text="Date when goods/services received"
    )

    # === Supplier Party ===
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="dea_purchase_invoices",
        help_text="Canonical supplier Party.",
    )

    # === Purchase Type ===
    purchase_type = models.CharField(
        max_length=20,
        choices=PurchaseType.choices,
        default=PurchaseType.GOODS,
        help_text="Type of purchase",
    )

    # === Reference ===
    reference = models.CharField(
        max_length=100, blank=True, help_text="Reference to PO, GRN, or other document"
    )

    # === Amounts ===
    subtotal = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Subtotal before taxes",
    )

    discount_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Total discount amount",
    )

    taxable_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Amount subject to tax",
    )

    cgst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="CGST amount",
    )

    sgst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="SGST amount",
    )

    igst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="IGST amount",
    )

    tds_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="TDS withheld (if applicable)",
    )

    total_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Grand total (taxable + taxes)",
    )

    net_payable = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Net payable to vendor (total - tds)",
    )

    # === Payment Tracking ===
    paid_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Amount paid to vendor",
    )

    is_fully_paid = models.BooleanField(
        default=False, help_text="Whether invoice is fully paid"
    )

    # === Terms ===
    payment_terms = models.CharField(
        max_length=100, blank=True, help_text="Payment terms from vendor"
    )

    due_date = models.DateField(null=True, blank=True, help_text="Payment due date")

    # === Description ===
    description = models.TextField(help_text="Invoice description")

    notes = models.TextField(blank=True, help_text="Invoice notes")

    memo = models.CharField(max_length=255, blank=True, help_text="Internal memo")

    # === Reverse relation to payments ===
    payments = GenericRelation("PaymentVoucher")

    class Meta:
        ordering = ["-invoice_date", "-created_at"]
        verbose_name = "Purchase Invoice Voucher"
        verbose_name_plural = "Purchase Invoice Vouchers"
        indexes = [
            models.Index(fields=["invoice_date", "party"]),
            models.Index(fields=["purchase_type", "is_fully_paid"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.internal_number} - {self.party} - ₹{self.net_payable.amount}"

    def clean(self):
        """Validate invoice data"""
        super().clean()

        # Calculate taxable amount
        calculated_taxable = self.subtotal.amount - self.discount_amount.amount
        if abs(calculated_taxable - self.taxable_amount.amount) > Decimal("0.01"):
            raise ValidationError(f"Taxable amount mismatch")

        # Calculate total
        total_tax = (
            self.cgst_amount.amount + self.sgst_amount.amount + self.igst_amount.amount
        )
        calculated_total = self.taxable_amount.amount + total_tax

        if abs(calculated_total - self.total_amount.amount) > Decimal("0.01"):
            raise ValidationError(f"Total amount mismatch")

        # Calculate net payable
        calculated_net = self.total_amount.amount - self.tds_amount.amount
        if abs(calculated_net - self.net_payable.amount) > Decimal("0.01"):
            raise ValidationError(f"Net payable mismatch")

        # Validate positive amounts
        if self.subtotal.amount < 0:
            raise ValidationError("Subtotal cannot be negative")

    def save(self, *args, **kwargs):
        """Auto-generate internal number and calculate amounts"""
        if not self.internal_number:
            self.internal_number = self._generate_internal_number()

        # Auto-calculate taxable amount from line items if not set
        if not self.taxable_amount or self.taxable_amount.amount == 0:
            subtotal = (
                sum(item.line_total.amount for item in self.line_items.all())
                if self.pk
                else self.subtotal.amount
            )

            self.taxable_amount = Money(
                subtotal - self.discount_amount.amount, self.subtotal.currency
            )

        # Auto-calculate total
        if not self.total_amount or self.total_amount.amount == 0:
            total_tax = (
                self.cgst_amount.amount
                + self.sgst_amount.amount
                + self.igst_amount.amount
            )
            self.total_amount = Money(
                self.taxable_amount.amount + total_tax, self.taxable_amount.currency
            )

        # Auto-calculate net payable
        if not self.net_payable or self.net_payable.amount == 0:
            self.net_payable = Money(
                self.total_amount.amount - self.tds_amount.amount,
                self.total_amount.currency,
            )

        # Update payment status
        self.is_fully_paid = self.paid_amount.amount >= self.net_payable.amount

        super().save(*args, **kwargs)

    def _generate_internal_number(self) -> str:
        """Generate unique internal reference number: PI-YYYY-MM-0001"""
        today = timezone.now()
        prefix = f"PI-{today.year}-{today.month:02d}"

        last_invoice = (
            PurchaseInvoiceVoucher.objects.filter(internal_number__startswith=prefix)
            .order_by("-internal_number")
            .first()
        )

        if last_invoice:
            try:
                last_seq = int(last_invoice.internal_number.split("-")[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1

        return f"{prefix}-{next_seq:04d}"

    def get_voucher_type(self) -> str:
        """Return voucher type for posting rules"""
        return f"PURCHASE_{self.purchase_type}"

    def get_economic_payload(self) -> dict:
        """Return economic data for fingerprinting"""
        return {
            "internal_number": self.internal_number,
            "party_id": self.party_id,
            "purchase_type": self.purchase_type,
            "total_amount": float(self.total_amount.amount),
            "line_items": [
                {
                    "description": item.description,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price.amount),
                }
                for item in self.line_items.all()
            ],
        }

    @property
    def outstanding_balance(self) -> Money:
        """Amount still owed to vendor"""
        return Money(
            self.net_payable.amount - self.paid_amount.amount, self.net_payable.currency
        )

    @property
    def is_overdue(self) -> bool:
        """Check if payment is overdue"""
        if not self.due_date or self.is_fully_paid:
            return False
        return timezone.now().date() > self.due_date


class PurchaseInvoiceLineItem(models.Model):
    """Individual line items in purchase invoice"""

    invoice = models.ForeignKey(
        PurchaseInvoiceVoucher,
        on_delete=models.CASCADE,
        related_name="line_items",
        help_text="Parent invoice",
    )

    line_number = models.PositiveIntegerField(default=1, help_text="Line item sequence")

    # === Product/Item ===
    item_code = models.CharField(
        max_length=50, blank=True, help_text="Product/item code"
    )

    description = models.TextField(help_text="Item description")

    # === Quantity & Price ===
    quantity = models.DecimalField(
        max_digits=10, decimal_places=3, default=1, help_text="Quantity purchased"
    )

    unit_price = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Price per unit",
    )

    line_total = MoneyField(
        max_digits=14, decimal_places=2, default_currency="INR", help_text="Line total"
    )

    # === Tax ===
    hsn_code = models.CharField(max_length=20, blank=True, help_text="HSN code")

    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="GST rate"
    )

    cgst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="CGST rate"
    )

    sgst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="SGST rate"
    )

    igst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="IGST rate"
    )

    class Meta:
        ordering = ["invoice", "line_number"]
        verbose_name = "Purchase Invoice Line Item"
        verbose_name_plural = "Purchase Invoice Line Items"
        unique_together = [["invoice", "line_number"]]

    def __str__(self):
        return f"{self.invoice.internal_number} - Line {self.line_number}: {self.description}"

    def clean(self):
        """Validate line item"""
        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

        if self.unit_price.amount < 0:
            raise ValidationError("Unit price cannot be negative")

    def save(self, *args, **kwargs):
        """Auto-calculate line total and set line number"""
        # Auto-assign line number if not set
        if not self.line_number or self.line_number == 1:
            if self.invoice_id:
                max_line = PurchaseInvoiceLineItem.objects.filter(
                    invoice=self.invoice
                ).aggregate(models.Max("line_number"))["line_number__max"]
                self.line_number = (max_line or 0) + 1

        # Calculate line total
        self.line_total = Money(
            self.quantity * self.unit_price.amount, self.unit_price.currency
        )

        super().save(*args, **kwargs)
