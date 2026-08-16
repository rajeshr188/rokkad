"""
Sales Invoice Voucher Model

Records revenue from goods/services sold to customers.
Creates AR (Accounts Receivable) until customer pays.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money
from decimal import Decimal

from .doc import BusinessDoc


class SalesInvoiceVoucher(BusinessDoc):
    """
    Sales Invoice Voucher - Records revenue from sales.

    ACCRUAL-BASED ARCHITECTURE:
    - Created when goods/services are delivered
    - Posts to GL immediately (AR ↔ Revenue)
    - Cash collection handled separately by PaymentVoucher
    - Supports complex tax scenarios (GST, TCS, etc.)

    Example:
    Goods sold to customer → Invoice → SalesInvoiceVoucher → PaymentVoucher (collection)
    """

    # === Core Identity ===
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique invoice reference (auto-generated: INV-YYYY-MM-0001)",
    )

    invoice_date = models.DateField(
        default=timezone.now, db_index=True, help_text="Date of invoice"
    )

    # === Customer Party ===
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        related_name="dea_sales_invoices",
        help_text="Canonical customer Party.",
    )

    # === Reference to Sales Order (optional) ===
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference to sales order or other document",
    )

    # === Amounts ===
    subtotal = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Subtotal before taxes and discounts",
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
        help_text="Amount subject to tax (subtotal - discount)",
    )

    cgst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="CGST (Central GST)",
    )

    sgst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="SGST (State GST)",
    )

    igst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="IGST (Integrated GST) for interstate",
    )

    tcs_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="TCS (Tax Collected at Source)",
    )

    total_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Grand total (taxable + taxes + tcs)",
    )

    # === Payment Tracking ===
    received_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Amount received from customer",
    )

    is_fully_paid = models.BooleanField(
        default=False, help_text="Whether invoice is fully paid"
    )

    # === Terms ===
    payment_terms = models.CharField(
        max_length=100, blank=True, help_text="Payment terms (e.g., Net 30 days)"
    )

    due_date = models.DateField(null=True, blank=True, help_text="Payment due date")

    # === Description ===
    description = models.TextField(help_text="Invoice description")

    notes = models.TextField(blank=True, help_text="Invoice notes/terms")

    memo = models.CharField(max_length=255, blank=True, help_text="Internal memo")

    # === Reverse relation to payments ===
    payments = GenericRelation("PaymentVoucher")

    class Meta:
        ordering = ["-invoice_date", "-created_at"]
        verbose_name = "Sales Invoice Voucher"
        verbose_name_plural = "Sales Invoice Vouchers"
        indexes = [
            models.Index(fields=["invoice_date", "party"]),
            models.Index(fields=["is_fully_paid"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.party} - ₹{self.total_amount.amount}"

    def clean(self):
        """Validate invoice data"""
        super().clean()

        # Calculate taxable amount
        calculated_taxable = self.subtotal.amount - self.discount_amount.amount
        if abs(calculated_taxable - self.taxable_amount.amount) > Decimal("0.01"):
            raise ValidationError(
                f"Taxable amount mismatch: Expected {calculated_taxable}, got {self.taxable_amount.amount}"
            )

        # Calculate total
        total_tax = (
            self.cgst_amount.amount
            + self.sgst_amount.amount
            + self.igst_amount.amount
            + self.tcs_amount.amount
        )
        calculated_total = self.taxable_amount.amount + total_tax

        if abs(calculated_total - self.total_amount.amount) > Decimal("0.01"):
            raise ValidationError(
                f"Total amount mismatch: Expected {calculated_total}, got {self.total_amount.amount}"
            )

        # Validate amounts are positive
        if self.subtotal.amount < 0:
            raise ValidationError("Subtotal cannot be negative")

        # Validate payment tracking
        if self.received_amount.amount > self.total_amount.amount:
            raise ValidationError(f"Received amount cannot exceed total")

    def save(self, *args, **kwargs):
        """Auto-generate invoice number and calculate amounts"""
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()

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
                + self.tcs_amount.amount
            )
            self.total_amount = Money(
                self.taxable_amount.amount + total_tax, self.taxable_amount.currency
            )

        # Update payment status
        self.is_fully_paid = self.received_amount.amount >= self.total_amount.amount

        super().save(*args, **kwargs)

    def _generate_invoice_number(self) -> str:
        """Generate unique invoice number: INV-YYYY-MM-0001"""
        today = timezone.now()
        prefix = f"INV-{today.year}-{today.month:02d}"

        last_invoice = (
            SalesInvoiceVoucher.objects.filter(invoice_number__startswith=prefix)
            .order_by("-invoice_number")
            .first()
        )

        if last_invoice:
            try:
                last_seq = int(last_invoice.invoice_number.split("-")[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1

        return f"{prefix}-{next_seq:04d}"

    def get_voucher_type(self) -> str:
        """Return voucher type for posting rules"""
        return "SALES_INVOICE"

    def get_economic_payload(self) -> dict:
        """Return economic data for fingerprinting"""
        return {
            "invoice_number": self.invoice_number,
            "party_id": self.party_id,
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
        """Amount still due from customer"""
        return Money(
            self.total_amount.amount - self.received_amount.amount,
            self.total_amount.currency,
        )

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is past due date"""
        if not self.due_date or self.is_fully_paid:
            return False
        return timezone.now().date() > self.due_date

    @property
    def payment_percentage(self) -> float:
        """Percentage of invoice paid"""
        if self.total_amount.amount == 0:
            return 100.0
        return float(self.received_amount.amount / self.total_amount.amount * 100)


class SalesInvoiceLineItem(models.Model):
    """Individual line items in sales invoice"""

    invoice = models.ForeignKey(
        SalesInvoiceVoucher,
        on_delete=models.CASCADE,
        related_name="line_items",
        help_text="Parent invoice",
    )

    line_number = models.PositiveIntegerField(default=1, help_text="Line item sequence")

    # === Product/Service ===
    item_code = models.CharField(
        max_length=50, blank=True, help_text="Product/service code"
    )

    description = models.TextField(help_text="Item description")

    # === Quantity & Price ===
    quantity = models.DecimalField(
        max_digits=10, decimal_places=3, default=1, help_text="Quantity sold"
    )

    unit_price = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Price per unit",
    )

    line_total = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Line total (quantity * unit_price)",
    )

    # === Discount ===
    discount_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="Discount percentage"
    )

    discount_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Discount amount",
    )

    # === Tax ===
    hsn_code = models.CharField(
        max_length=20, blank=True, help_text="HSN/SAC code for GST"
    )

    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="GST rate percentage"
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
        verbose_name = "Sales Invoice Line Item"
        verbose_name_plural = "Sales Invoice Line Items"
        unique_together = [["invoice", "line_number"]]

    def __str__(self):
        return f"{self.invoice.invoice_number} - Line {self.line_number}: {self.description}"

    def clean(self):
        """Validate line item"""
        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

        if self.unit_price.amount < 0:
            raise ValidationError("Unit price cannot be negative")

    def save(self, *args, **kwargs):
        """Auto-calculate line totals and set line number"""
        # Auto-assign line number if not set
        if not self.line_number or self.line_number == 1:
            if self.invoice_id:
                max_line = SalesInvoiceLineItem.objects.filter(
                    invoice=self.invoice
                ).aggregate(models.Max("line_number"))["line_number__max"]
                self.line_number = (max_line or 0) + 1

        # Calculate line total
        self.line_total = Money(
            self.quantity * self.unit_price.amount, self.unit_price.currency
        )

        # Calculate discount
        if self.discount_percentage > 0:
            self.discount_amount = Money(
                self.line_total.amount * self.discount_percentage / 100,
                self.line_total.currency,
            )

        super().save(*args, **kwargs)
