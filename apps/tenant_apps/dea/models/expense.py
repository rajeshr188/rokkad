"""
ExpenseVoucher Model - Track employee & vendor expenses with tax handling

EXPENSE WORKFLOW:
1. Employee submits ExpenseClaim (source document)
2. Manager approves claim
3. ExpenseVoucher auto-created from approved claim
4. Accounts posts to GL immediately
5. Payment created later to clear the payable

Supports:
- Employee reimbursements, vendor bills, direct expenses
- Multi-category line items
- GST input credit calculation
- TDS withholding
- Multi-currency
"""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money
from decimal import Decimal

from .doc import BusinessDoc


class ExpenseSource(models.TextChoices):
    """Source of expense"""

    EMP_CLAIM = "EMP_CLAIM", "Employee Expense Claim"
    VENDOR_BILL = "VENDOR_BILL", "Vendor Bill"
    DIRECT_PAYMENT = "DIRECT_PAYMENT", "Direct Payment/Cash"
    REIMBURSEMENT = "REIMBURSEMENT", "Reimbursement Request"
    OTHER = "OTHER", "Other"


class ExpenseCategory(models.TextChoices):
    """Expense categories"""

    TRAVEL = "TRAVEL", "Travel & Transportation"
    FOOD = "FOOD", "Food & Meals"
    ACCOMMODATION = "ACCOMMODATION", "Accommodation"
    PROFESSIONAL = "PROFESSIONAL", "Professional Services"
    OFFICE = "OFFICE", "Office & Supplies"
    UTILITIES = "UTILITIES", "Utilities & Communications"
    MAINTENANCE = "MAINTENANCE", "Maintenance & Repair"
    MARKETING = "MARKETING", "Marketing & Advertising"
    OTHER = "OTHER", "Other"


class ExpenseVoucher(BusinessDoc):
    """
    Expense Voucher - Record employee & vendor expenses.

    CHARACTERISTICS:
    - Created for approved expense claims
    - Multi-category line items (each with own GL account)
    - Calculates tax (GST input, TDS withholding)
    - Auto-posts to GL immediately
    - Tracks payment status separately via PaymentVoucher

    ACCOUNTING ENTRY:
    DR: Expense accounts (by category)
    DR: GST Input Credit (if applicable)
    CR: TDS Payable (if applicable)
    CR: Employee Payable / Vendor Payable / Cash

    Examples:
    - Employee travel claim: Travel Exp + GST Input → Employee Payable
    - Vendor professional service: Professional Exp + GST Input + TDS → Vendor Payable
    - Office supplies purchase: Office Exp + GST Input → AP
    """

    # === Core Identity ===
    expense_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique expense reference (auto-generated)",
    )

    expense_date = models.DateField(
        default=timezone.now, db_index=True, help_text="Date of expense"
    )

    # === Classification ===
    source_type = models.CharField(
        max_length=50,
        choices=ExpenseSource.choices,
        default=ExpenseSource.EMP_CLAIM,
        help_text="Source of expense",
    )

    # === Generic reference to source document ===
    # Links to ExpenseClaim, VendorBill, or other source
    source_doc_id = models.CharField(
        max_length=100, blank=True, help_text="Reference to source document ID"
    )

    # === Party (Employee/Vendor) ===
    party_name = models.CharField(
        max_length=255, help_text="Name of employee or vendor"
    )

    party_email = models.EmailField(
        blank=True, help_text="Email of party (for employee/vendor)"
    )

    # === Amounts ===
    gross_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Total before tax (sum of line items)",
    )

    tax_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Total GST (CGST + SGST + IGST)",
    )

    taxable_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Total of taxable items",
    )

    tds_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="TDS withholding (if applicable)",
    )

    net_payable = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Amount payable (gross + tax - tds)",
    )

    # === Description ===
    description = models.TextField(help_text="Description of expenses")

    memo = models.CharField(
        max_length=255, blank=True, help_text="Short memo or reference"
    )

    # === Payment Tracking ===
    is_paid = models.BooleanField(
        default=False, help_text="Whether expense has been paid"
    )

    paid_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        null=True,
        blank=True,
        help_text="Amount actually paid (if partially paid)",
    )

    paid_date = models.DateField(
        null=True, blank=True, help_text="When payment was made"
    )

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        verbose_name = "Expense Voucher"
        verbose_name_plural = "Expense Vouchers"
        indexes = [
            models.Index(fields=["expense_date", "source_type"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["is_paid"]),
        ]

    def __str__(self):
        return f"{self.expense_number} - {self.party_name} - {self.net_payable}"

    def clean(self):
        """Validate expense voucher"""
        super().clean()

        if self.gross_amount.amount < 0:
            raise ValidationError("Gross amount cannot be negative")

        if self.tax_amount.amount < 0:
            raise ValidationError("Tax amount cannot be negative")

        if self.tds_amount.amount < 0:
            raise ValidationError("TDS amount cannot be negative")

    def save(self, *args, **kwargs):
        """Auto-generate expense number and calculate amounts"""
        if not self.expense_number:
            self.expense_number = self._generate_expense_number()

        # Calculate net payable
        self.net_payable = Money(
            self.gross_amount.amount + self.tax_amount.amount - self.tds_amount.amount,
            self.gross_amount.currency,
        )

        super().save(*args, **kwargs)

    def _generate_expense_number(self) -> str:
        """Generate unique expense number"""
        today = timezone.now()
        prefix = f"EXP-{today.year}-{today.month:02d}"

        last_expense = (
            ExpenseVoucher.objects.filter(expense_number__startswith=prefix)
            .order_by("-expense_number")
            .first()
        )

        if last_expense:
            try:
                last_seq = int(last_expense.expense_number.split("-")[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1

        return f"{prefix}-{next_seq:04d}"

    def get_voucher_type(self) -> str:
        """Return voucher type for posting"""
        return f"EXPENSE_{self.source_type}"

    @property
    def is_pending_approval(self) -> bool:
        """Check if expense is pending approval"""
        return not self.is_paid

    def get_economic_payload(self) -> dict:
        """Return economic fields for posting fingerprint"""
        return {
            "expense_number": self.expense_number,
            "gross_amount": float(self.gross_amount.amount),
            "tax_amount": float(self.tax_amount.amount),
            "tds_amount": float(self.tds_amount.amount),
            "net_payable": float(self.net_payable.amount),
            "source_type": self.source_type,
            "currency": str(self.gross_amount.currency),
        }


class ExpenseLineItem(models.Model):
    """Individual line items in an expense"""

    expense_voucher = models.ForeignKey(
        ExpenseVoucher,
        on_delete=models.CASCADE,
        related_name="line_items",
        help_text="Parent expense voucher",
    )

    line_number = models.PositiveIntegerField(
        default=1, help_text="Line sequence number"
    )

    # === Category ===
    category = models.CharField(
        max_length=50, choices=ExpenseCategory.choices, help_text="Expense category"
    )

    # === Description ===
    description = models.TextField(help_text="Description of this line item")

    # === Amounts ===
    amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Amount before tax",
    )

    # === Tax ===
    is_taxable = models.BooleanField(
        default=True, help_text="Whether this item is subject to GST"
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Tax rate as percentage (e.g., 5, 12, 18)",
    )

    tax_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Calculated tax amount",
    )

    # === TDS ===
    tds_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="TDS rate as percentage (e.g., 5, 10)",
    )

    tds_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        default=0,
        help_text="Calculated TDS amount",
    )

    # === Total ===
    line_total = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Total (amount + tax - tds)",
    )

    class Meta:
        ordering = ["expense_voucher", "line_number"]
        verbose_name = "Expense Line Item"
        verbose_name_plural = "Expense Line Items"
        unique_together = [["expense_voucher", "line_number"]]

    def __str__(self):
        return f"{self.expense_voucher.expense_number} - Line {self.line_number}: {self.category} {self.amount}"

    def clean(self):
        """Validate line item"""
        if self.amount is None:
            raise ValidationError("Amount is required for each expense line item.")
        if self.amount.amount < 0:
            raise ValidationError("Amount must be positive")

        if self.tax_rate is not None and self.tax_rate < 0:
            raise ValidationError("Tax rate cannot be negative")

        if self.tds_rate is not None and self.tds_rate < 0:
            raise ValidationError("TDS rate cannot be negative")

    def save(self, *args, **kwargs):
        """Auto-calculate line totals and tax"""
        # Auto-calculate line number if not set
        if not self.line_number or self.line_number == 0:
            max_line = ExpenseLineItem.objects.filter(
                expense_voucher=self.expense_voucher
            ).aggregate(models.Max("line_number"))["line_number__max"]

            self.line_number = (max_line or 0) + 1

        # Calculate tax if item is taxable
        if self.is_taxable:
            self.tax_amount = Money(
                (self.amount.amount * self.tax_rate) / 100, self.amount.currency
            )
        else:
            self.tax_amount = Money(0, self.amount.currency)

        # Calculate TDS
        self.tds_amount = Money(
            (self.amount.amount * self.tds_rate) / 100, self.amount.currency
        )

        # Calculate line total
        self.line_total = Money(
            self.amount.amount + self.tax_amount.amount - self.tds_amount.amount,
            self.amount.currency,
        )

        super().save(*args, **kwargs)
