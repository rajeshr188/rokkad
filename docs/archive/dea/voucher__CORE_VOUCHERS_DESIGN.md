---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Complete ERP Vouchers Design Document

**Date**: February 26-27, 2026  
**Status**: Complete Design Phase  
**Goal**: Comprehensive design for all 6 essential voucher types for minimal viable ERP system

---

## Table of Contents

### Priority 1: Foundation (Week 1-2)
1. [Payment Voucher Design](#payment-voucher-design)
2. [Expense Voucher Design](#expense-voucher-design)
3. [Journal Entry Voucher Design](#journal-entry-voucher-design)

### Priority 2: Business Operations (Week 3-4)
4. [Sales Invoice Voucher Design](#sales-invoice-voucher-design)
5. [Purchase Invoice Voucher Design](#purchase-invoice-voucher-design)

### Priority 3: Advanced (Later)
6. [Stock Movement Voucher Design](#stock-movement-voucher-design)
7. [Depreciation Voucher Design](#depreciation-voucher-design)

### Support Sections
8. [Architecture Overview](#architecture-overview)
9. [Integration & Workflows](#integration--workflows)
10. [Complete Implementation Roadmap](#implementation-roadmap)

---

## Architecture Overview

### The Six Essential Voucher Types

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                  SIX ESSENTIAL VOUCHERS (MVP ERP)                â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚     PRIORITY 1       â”‚     PRIORITY 2       â”‚    PRIORITY 3     â”‚
â”‚    (Week 1-2)        â”‚    (Week 3-4)        â”‚     (Later)       â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                                  â”‚
â”‚ 1. PAYMENT VOUCHER   â”‚ 4. SALES INVOICE     â”‚ 6. STOCK MOVEMENT â”‚
â”‚    âœ“ Cash flows      â”‚    â–¡ Revenue         â”‚    â–¡ Inventory    â”‚
â”‚    âœ“ Receipts/       â”‚    â–¡ AR tracking     â”‚    â–¡ Movement     â”‚
â”‚      Payments        â”‚                      â”‚      tracking      â”‚
â”‚                      â”‚ 5. PURCHASE INVOICE  â”‚                    â”‚
â”‚ 2. EXPENSE VOUCHER   â”‚    â–¡ Inventory/      â”‚ 7. DEPRECIATION   â”‚
â”‚    âœ“ Company costs   â”‚      Expense         â”‚    â–¡ Period-end   â”‚
â”‚    âœ“ Accruals        â”‚    â–¡ AP tracking     â”‚      adjustment    â”‚
â”‚    âœ“ Tax handling    â”‚                      â”‚    â–¡ Asset value   â”‚
â”‚                      â”‚                      â”‚                    â”‚
â”‚ 3. JOURNAL ENTRY     â”‚                      â”‚                    â”‚
â”‚    âœ“ Manual GL       â”‚                      â”‚                    â”‚
â”‚      adjustments     â”‚                      â”‚                    â”‚
â”‚    âœ“ Corrections     â”‚                      â”‚                    â”‚
â”‚                                                                  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Key Principle: Accrual + Payment Separation

```
ACCRUAL EVENT (Business Transaction)
â”œâ”€ Creates SOURCE DOCUMENT (Invoice, Expense Claim, etc.)
â”œâ”€ Source Doc approved â†’ Creates VOUCHER
â”œâ”€ Voucher posted â†’ Creates JOURNAL ENTRY #1
â”‚  â””â”€ Records: Asset/Expense â†” Liability/Revenue
â”‚
â””â”€ Creates PAYABLE/RECEIVABLE (not yet settled)

         â†“ TIME PASSES (days/weeks)

CASH EVENT (Economic Transaction)
â”œâ”€ Creates PAYMENT VOUCHER
â”œâ”€ Payment Voucher posted â†’ Creates JOURNAL ENTRY #2
â”‚  â””â”€ Records: Cash â†” Payable/Receivable
â”‚
â””â”€ Settles the outstanding balance
```

**Example Timeline:**
```
Day 1: Purchase goods â†’ PurchaseInvoice â†’ Voucher â†’ JE (DR Inventory, CR AP)
Day 15: Pay supplier â†’ PaymentVoucher â†’ JE (DR AP, CR Cash)

Result:
- Day 1-14: AP shows liability, Cash unchanged âœ… Accurate
- Day 15: AP reduced, Cash decreased âœ… Accurate
```

---

## Expense Voucher Design

### Overview

**Purpose**: Track company expenses for services, utilities, employee reimbursements, and operating costs.

**Key Characteristics:**
- Accrual-based (expense recognized when incurred, not when paid)
- Can have multiple expense categories in one voucher
- Supports tax handling (GST, TDS, etc.)
- Creates liability until payment is made

### Model Design

**File**: `apps/tenant_apps/dea/models/expense.py`

```python
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money
from decimal import Decimal

from .doc import BusinessDoc
from ..posting.types import PostingBundle, DualLedgerLine, AccountLine


class ExpenseCategory(models.TextChoices):
    """Standard expense categories"""
    RENT = "RENT", "Rent/Lease"
    UTILITIES = "UTILITIES", "Utilities"
    REPAIRS = "REPAIRS", "Repairs & Maintenance"
    TRAVEL = "TRAVEL", "Travel & Conveyance"
    FOOD = "FOOD", "Food & Entertainment"
    SUPPLIES = "SUPPLIES", "Office Supplies"
    PROFESSIONAL = "PROFESSIONAL", "Professional Services"
    CONSULTING = "CONSULTING", "Consulting Fees"
    INSURANCE = "INSURANCE", "Insurance Premiums"
    ADVERTISING = "ADVERTISING", "Advertising & Marketing"
    COMMUNICATION = "COMMUNICATION", "Communication (Phone, Internet)"
    EMPLOYEE_BENEFIT = "EMP_BENEFIT", "Employee Benefits"
    DEPRECIATION = "DEPRECIATION", "Depreciation"
    INTEREST = "INTEREST", "Interest Expense"
    OTHER = "OTHER", "Other Expenses"


class ExpenseSource(models.TextChoices):
    """How the expense originated"""
    EMPLOYEE_CLAIM = "EMP_CLAIM", "Employee Expense Claim"
    VENDOR_BILL = "VENDOR_BILL", "Vendor Bill/Invoice"
    DIRECT_PAYMENT = "DIRECT_PAYMENT", "Direct Company Payment"
    PETTY_CASH = "PETTY_CASH", "Petty Cash"
    ACCRUAL = "ACCRUAL", "Accrual/Adjustment"


class ExpenseVoucher(BusinessDoc):
    """
    Expense Voucher - Records company expenses.
    
    ACCRUAL-BASED ARCHITECTURE:
    - Created when expense is incurred/approved
    - Posts to GL immediately (Expense â†” Payable)
    - Cash settlement handled separately by PaymentVoucher
    - Supports complex tax scenarios (GST, TDS)
    
    Examples:
    - Employee expense claim â†’ Approved â†’ ExpenseVoucher â†’ PaymentVoucher (reimbursement)
    - Vendor bill for services â†’ Received â†’ ExpenseVoucher â†’ PaymentVoucher (payment)
    - Rent accrual â†’ Month-end â†’ ExpenseVoucher (no payment yet)
    """
    
    # === Core Identity ===
    expense_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique expense voucher reference (auto-generated)"
    )
    
    expense_date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Date when expense was incurred"
    )
    
    # === Classification ===
    category = models.CharField(
        max_length=50,
        choices=ExpenseCategory.choices,
        help_text="Primary expense category"
    )
    
    source_type = models.CharField(
        max_length=50,
        choices=ExpenseSource.choices,
        default=ExpenseSource.DIRECT_PAYMENT,
        help_text="How this expense originated"
    )
    
    # === Reference to Source Document ===
    # Links to ExpenseClaim, VendorBill, or other source
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Type of source document"
    )
    source_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID of source document"
    )
    source_document = GenericForeignKey('source_content_type', 'source_object_id')
    
    # === Party Information ===
    # For employee claims: employee
    # For vendor bills: vendor
    # For direct: None
    party_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name='expense_party_ct',
        null=True,
        blank=True,
        help_text="Type of party (Employee, Vendor, etc.)"
    )
    party_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID of party"
    )
    party = GenericForeignKey('party_content_type', 'party_object_id')
    
    # === Amounts ===
    gross_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Total expense amount before taxes"
    )
    
    tax_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Total tax amount (GST, etc.)"
    )
    
    tds_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="TDS withheld (if applicable)"
    )
    
    net_payable = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Net amount payable (gross + tax - tds)"
    )
    
    # === Description ===
    description = models.TextField(
        help_text="Detailed description of expense"
    )
    
    memo = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short memo/reference"
    )
    
    # === Approval ===
    approved_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expenses',
        help_text="User who approved this expense"
    )
    
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When expense was approved"
    )
    
    # === Settlement ===
    is_paid = models.BooleanField(
        default=False,
        help_text="Whether expense has been paid"
    )
    
    paid_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Amount already paid"
    )
    
    # === Reverse relation to payments ===
    # payments = GenericRelation('PaymentVoucher')  # Added in PaymentVoucher
    
    class Meta:
        ordering = ['-expense_date', '-created_at']
        verbose_name = "Expense Voucher"
        verbose_name_plural = "Expense Vouchers"
        indexes = [
            models.Index(fields=['expense_date', 'category']),
            models.Index(fields=['source_type', 'is_paid']),
        ]
    
    def __str__(self):
        return f"{self.expense_number} - {self.get_category_display()} - {self.net_payable}"
    
    def clean(self):
        """Validate expense voucher data"""
        super().clean()
        
        # Calculate net payable
        calculated_net = (
            self.gross_amount.amount + 
            self.tax_amount.amount - 
            self.tds_amount.amount
        )
        
        if abs(calculated_net - self.net_payable.amount) > Decimal('0.01'):
            raise ValidationError(
                f"Net payable mismatch: Expected {calculated_net}, got {self.net_payable.amount}"
            )
        
        # Validate amounts are positive
        if self.gross_amount.amount < 0:
            raise ValidationError("Gross amount cannot be negative")
        
        if self.tax_amount.amount < 0:
            raise ValidationError("Tax amount cannot be negative")
        
        if self.tds_amount.amount < 0:
            raise ValidationError("TDS amount cannot be negative")
        
        # Validate payment doesn't exceed net payable
        if self.paid_amount.amount > self.net_payable.amount:
            raise ValidationError(
                f"Paid amount ({self.paid_amount}) cannot exceed net payable ({self.net_payable})"
            )
    
    def save(self, *args, **kwargs):
        """Auto-generate expense number if not set"""
        if not self.expense_number:
            self.expense_number = self._generate_expense_number()
        
        # Auto-calculate net payable if not set
        if not self.net_payable or self.net_payable.amount == 0:
            self.net_payable = Money(
                self.gross_amount.amount + self.tax_amount.amount - self.tds_amount.amount,
                self.gross_amount.currency
            )
        
        # Update is_paid status
        self.is_paid = (self.paid_amount.amount >= self.net_payable.amount)
        
        super().save(*args, **kwargs)
    
    def _generate_expense_number(self) -> str:
        """Generate unique expense number"""
        from django.utils import timezone
        today = timezone.now()
        prefix = f"EXP-{today.year}-{today.month:02d}"
        
        # Get last expense number for this month
        last_expense = ExpenseVoucher.objects.filter(
            expense_number__startswith=prefix
        ).order_by('-expense_number').first()
        
        if last_expense:
            # Extract sequence number and increment
            try:
                last_seq = int(last_expense.expense_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}-{next_seq:04d}"
    
    def get_voucher_type(self) -> str:
        """Return voucher type for posting rules"""
        return f"EXPENSE_{self.source_type}"
    
    @property
    def outstanding_balance(self) -> Money:
        """Amount still unpaid"""
        return Money(
            self.net_payable.amount - self.paid_amount.amount,
            self.net_payable.currency
        )
    
    @property
    def is_fully_paid(self) -> bool:
        """Check if expense is fully settled"""
        return self.paid_amount.amount >= self.net_payable.amount
    
    @property
    def payment_percentage(self) -> float:
        """Percentage of expense paid"""
        if self.net_payable.amount == 0:
            return 100.0
        return float(self.paid_amount.amount / self.net_payable.amount * 100)


class ExpenseLineItem(models.Model):
    """
    Individual line items in an expense voucher.
    Allows multi-category expenses in single voucher.
    """
    
    expense_voucher = models.ForeignKey(
        ExpenseVoucher,
        on_delete=models.CASCADE,
        related_name='line_items',
        help_text="Parent expense voucher"
    )
    
    line_number = models.PositiveIntegerField(
        default=1,
        help_text="Line item sequence number"
    )
    
    category = models.CharField(
        max_length=50,
        choices=ExpenseCategory.choices,
        help_text="Expense category for this line"
    )
    
    description = models.TextField(
        help_text="Description of this expense line"
    )
    
    amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Amount for this line item"
    )
    
    # Optional: Link to specific GL account
    expense_ledger = models.ForeignKey(
        'dea.Ledger',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Specific GL expense account (optional override)"
    )
    
    # Optional: Tax details per line
    is_taxable = models.BooleanField(
        default=False,
        help_text="Is this line item subject to tax?"
    )
    
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Tax rate percentage (e.g., 18 for 18%)"
    )
    
    tax_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Calculated tax for this line"
    )
    
    class Meta:
        ordering = ['expense_voucher', 'line_number']
        verbose_name = "Expense Line Item"
        verbose_name_plural = "Expense Line Items"
        unique_together = [['expense_voucher', 'line_number']]
    
    def __str__(self):
        return f"{self.expense_voucher.expense_number} - Line {self.line_number}: {self.get_category_display()}"
    
    def clean(self):
        """Validate line item"""
        if self.amount.amount < 0:
            raise ValidationError("Line item amount cannot be negative")
        
        if self.is_taxable and self.tax_rate < 0:
            raise ValidationError("Tax rate cannot be negative")
        
        # Auto-calculate tax if taxable
        if self.is_taxable and self.tax_rate > 0:
            calculated_tax = self.amount.amount * self.tax_rate / 100
            if self.tax_amount.amount != calculated_tax:
                self.tax_amount = Money(calculated_tax, self.amount.currency)
    
    def save(self, *args, **kwargs):
        """Auto-calculate line number if not set"""
        if not self.line_number or self.line_number == 0:
            # Get max line number for this voucher
            max_line = ExpenseLineItem.objects.filter(
                expense_voucher=self.expense_voucher
            ).aggregate(models.Max('line_number'))['line_number__max']
            
            self.line_number = (max_line or 0) + 1
        
        # Calculate tax if taxable
        if self.is_taxable and self.tax_rate > 0:
            self.tax_amount = Money(
                self.amount.amount * self.tax_rate / 100,
                self.amount.currency
            )
        
        super().save(*args, **kwargs)
```

### Posting Rules for Expense Voucher

**File**: `apps/tenant_apps/dea/posting/rules/expense_voucher.py`

```python
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("EXPENSE_EMP_CLAIM")
class EmployeeExpenseClaimRule(BasePostingRule):
    """
    Posting rule for employee expense claims.
    
    ACCOUNTING ENTRIES:
    When expense approved (NOT when paid):
    DR: Various Expense Accounts (based on categories)
    DR: GST Input Credit (if applicable)
    CR: Employee Payable
    CR: TDS Payable (if withheld)
    
    Example:
    Employee submits â‚¹10,000 claim (Travel â‚¹6,000 + Food â‚¹4,000)
    DR: Travel Expense â‚¹6,000
    DR: Food Expense â‚¹4,000
    CR: Employee Payable â‚¹10,000
    """
    
    def should_run(self, doc) -> bool:
        """Only run for employee expense claims"""
        from apps.tenant_apps.dea.models import ExpenseVoucher
        return (
            isinstance(doc, ExpenseVoucher) and 
            doc.source_type == 'EMP_CLAIM'
        )
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for employee expense claim"""
        from apps.tenant_apps.dea.models import ExpenseVoucher
        
        if not isinstance(doc, ExpenseVoucher):
            raise ValidationError("Document must be ExpenseVoucher")
        
        # Get account IDs
        expense_accounts = self._get_expense_accounts_for_categories(doc)
        gst_input_ledger = get_ledger_id_by_key("GST_INPUT_CREDIT")
        employee_payable_ledger = get_ledger_id_by_key("EMPLOYEE_PAYABLE")
        tds_payable_ledger = get_ledger_id_by_key("TDS_PAYABLE")
        
        lines = []
        total_dr = Decimal('0')
        total_cr = Decimal('0')
        
        # DR: Expense accounts (from line items or single category)
        if doc.line_items.exists():
            # Multi-line expense
            for line_item in doc.line_items.all():
                expense_ledger = (
                    line_item.expense_ledger.id 
                    if line_item.expense_ledger 
                    else self._get_ledger_for_category(line_item.category)
                )
                
                lines.append(DualLedgerLine(
                    ledger_dr=expense_ledger,
                    ledger_cr=None,
                    amount=line_item.amount.amount,
                    memo=f"{line_item.get_category_display()}: {line_item.description}"
                ))
                total_dr += line_item.amount.amount
                
                # Add tax line if applicable
                if line_item.is_taxable and line_item.tax_amount.amount > 0:
                    lines.append(DualLedgerLine(
                        ledger_dr=gst_input_ledger,
                        ledger_cr=None,
                        amount=line_item.tax_amount.amount,
                        memo=f"GST Input on {line_item.get_category_display()}"
                    ))
                    total_dr += line_item.tax_amount.amount
        else:
            # Single category expense
            expense_ledger = self._get_ledger_for_category(doc.category)
            lines.append(DualLedgerLine(
                ledger_dr=expense_ledger,
                ledger_cr=None,
                amount=doc.gross_amount.amount,
                memo=f"{doc.get_category_display()}: {doc.description}"
            ))
            total_dr += doc.gross_amount.amount
            
            # Add GST if applicable
            if doc.tax_amount.amount > 0:
                lines.append(DualLedgerLine(
                    ledger_dr=gst_input_ledger,
                    ledger_cr=None,
                    amount=doc.tax_amount.amount,
                    memo=f"GST Input on {doc.get_category_display()}"
                ))
                total_dr += doc.tax_amount.amount
        
        # CR: TDS Payable (if withheld)
        if doc.tds_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=tds_payable_ledger,
                amount=doc.tds_amount.amount,
                memo=f"TDS withheld @ source"
            ))
            total_cr += doc.tds_amount.amount
        
        # CR: Employee Payable (net amount after TDS)
        payable_amount = doc.net_payable.amount
        lines.append(DualLedgerLine(
            ledger_dr=None,
            ledger_cr=employee_payable_ledger,
            amount=payable_amount,
            memo=f"Payable to {doc.party} for expense claim"
        ))
        total_cr += payable_amount
        
        # Add subledger entry for employee
        account_lines = []
        if doc.party:
            account_lines.append(AccountLine(
                account_dr=None,
                account_cr=doc.party.id,  # Employee account
                amount=payable_amount,
                memo=f"Expense claim {doc.expense_number}"
            ))
        
        # Validate balanced
        if abs(total_dr - total_cr) > Decimal('0.01'):
            raise ValidationError(
                f"Unbalanced entry: DR {total_dr} != CR {total_cr}"
            )
        
        return PostingBundle(
            voucher_type="EXPENSE_EMP_CLAIM",
            voucher_number=doc.expense_number,
            voucher_date=doc.expense_date,
            description=f"Employee expense claim: {doc.description}",
            lines=lines,
            account_lines=account_lines,
        )
    
    def _get_ledger_for_category(self, category: str) -> int:
        """Map expense category to GL account"""
        category_mapping = {
            'RENT': 'RENT_EXPENSE',
            'UTILITIES': 'UTILITIES_EXPENSE',
            'REPAIRS': 'REPAIRS_MAINTENANCE_EXPENSE',
            'TRAVEL': 'TRAVEL_EXPENSE',
            'FOOD': 'FOOD_ENTERTAINMENT_EXPENSE',
            'SUPPLIES': 'OFFICE_SUPPLIES_EXPENSE',
            'PROFESSIONAL': 'PROFESSIONAL_SERVICES_EXPENSE',
            'CONSULTING': 'CONSULTING_EXPENSE',
            'COMMUNICATION': 'COMMUNICATION_EXPENSE',
            'OTHER': 'MISCELLANEOUS_EXPENSE',
        }
        
        ledger_key = category_mapping.get(category, 'MISCELLANEOUS_EXPENSE')
        return get_ledger_id_by_key(ledger_key)


@register_rule("EXPENSE_VENDOR_BILL")
class VendorBillExpenseRule(BasePostingRule):
    """
    Posting rule for vendor bills (services).
    
    ACCOUNTING ENTRIES:
    DR: Expense Account
    DR: GST Input Credit
    CR: Vendor Payable (AP)
    CR: TDS Payable
    
    Example:
    Professional service bill for â‚¹50,000 + GST â‚¹9,000 - TDS â‚¹5,000
    DR: Professional Services Expense â‚¹50,000
    DR: GST Input Credit â‚¹9,000
    CR: TDS Payable â‚¹5,000
    CR: Vendor Payable â‚¹54,000
    """
    
    def should_run(self, doc) -> bool:
        """Only run for vendor bills"""
        from apps.tenant_apps.dea.models import ExpenseVoucher
        return (
            isinstance(doc, ExpenseVoucher) and 
            doc.source_type == 'VENDOR_BILL'
        )
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for vendor bill"""
        from apps.tenant_apps.dea.models import ExpenseVoucher
        
        if not isinstance(doc, ExpenseVoucher):
            raise ValidationError("Document must be ExpenseVoucher")
        
        # Get account IDs
        expense_ledger = self._get_ledger_for_category(doc.category)
        gst_input_ledger = get_ledger_id_by_key("GST_INPUT_CREDIT")
        vendor_payable_ledger = get_ledger_id_by_key("ACCOUNTS_PAYABLE")
        tds_payable_ledger = get_ledger_id_by_key("TDS_PAYABLE")
        
        lines = []
        
        # DR: Expense
        lines.append(DualLedgerLine(
            ledger_dr=expense_ledger,
            ledger_cr=None,
            amount=doc.gross_amount.amount,
            memo=f"{doc.get_category_display()}: {doc.description}"
        ))
        
        # DR: GST Input Credit
        if doc.tax_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=gst_input_ledger,
                ledger_cr=None,
                amount=doc.tax_amount.amount,
                memo="GST Input Credit"
            ))
        
        # CR: TDS Payable
        if doc.tds_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=tds_payable_ledger,
                amount=doc.tds_amount.amount,
                memo="TDS withheld"
            ))
        
        # CR: Vendor Payable
        lines.append(DualLedgerLine(
            ledger_dr=None,
            ledger_cr=vendor_payable_ledger,
            amount=doc.net_payable.amount,
            memo=f"Payable to vendor for {doc.description}"
        ))
        
        # Subledger: Vendor account
        account_lines = []
        if doc.party:
            account_lines.append(AccountLine(
                account_dr=None,
                account_cr=doc.party.id,
                amount=doc.net_payable.amount,
                memo=f"Vendor bill {doc.expense_number}"
            ))
        
        return PostingBundle(
            voucher_type="EXPENSE_VENDOR_BILL",
            voucher_number=doc.expense_number,
            voucher_date=doc.expense_date,
            description=f"Vendor bill: {doc.description}",
            lines=lines,
            account_lines=account_lines,
        )
    
    def _get_ledger_for_category(self, category: str) -> int:
        """Same mapping as employee claim"""
        # Reuse from EmployeeExpenseClaimRule
        return EmployeeExpenseClaimRule()._get_ledger_for_category(category)


@register_rule("EXPENSE_DIRECT_PAYMENT")
class DirectExpenseRule(BasePostingRule):
    """
    Posting rule for direct expenses (already paid, no payable).
    
    ACCOUNTING ENTRIES:
    DR: Expense Account
    CR: Cash/Bank (immediately)
    
    Example:
    Rent paid directly â‚¹20,000
    DR: Rent Expense â‚¹20,000
    CR: Cash â‚¹20,000
    
    Note: This is unusual - typically expenses create payables.
    Use PaymentVoucher with source=ExpenseVoucher for normal flow.
    """
    
    def should_run(self, doc) -> bool:
        """Only run for direct payment expenses"""
        from apps.tenant_apps.dea.models import ExpenseVoucher
        return (
            isinstance(doc, ExpenseVoucher) and 
            doc.source_type == 'DIRECT_PAYMENT' and
            doc.is_paid  # Only if marked as paid
        )
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for direct expense payment"""
        from apps.tenant_apps.dea.models import ExpenseVoucher
        
        if not isinstance(doc, ExpenseVoucher):
            raise ValidationError("Document must be ExpenseVoucher")
        
        expense_ledger = self._get_ledger_for_category(doc.category)
        cash_ledger = get_ledger_id_by_key("CASH")
        
        lines = [
            DualLedgerLine(
                ledger_dr=expense_ledger,
                ledger_cr=None,
                amount=doc.gross_amount.amount,
                memo=f"{doc.get_category_display()}: {doc.description}"
            ),
            DualLedgerLine(
                ledger_dr=None,
                ledger_cr=cash_ledger,
                amount=doc.gross_amount.amount,
                memo=f"Cash paid for {doc.description}"
            ),
        ]
        
        return PostingBundle(
            voucher_type="EXPENSE_DIRECT_PAYMENT",
            voucher_number=doc.expense_number,
            voucher_date=doc.expense_date,
            description=f"Direct expense payment: {doc.description}",
            lines=lines,
            account_lines=[],
        )
    
    def _get_ledger_for_category(self, category: str) -> int:
        return EmployeeExpenseClaimRule()._get_ledger_for_category(category)
```

### Expense Voucher Workflow

```
EMPLOYEE EXPENSE CLAIM WORKFLOW:
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. Employee submits expense claim
   â”œâ”€ ExpenseClaim created
   â”œâ”€ Status: SUBMITTED
   â”œâ”€ Line items: Travel, Food, etc.
   â””â”€ Receipts attached

2. Manager reviews & approves
   â”œâ”€ ExpenseClaim.status = APPROVED
   â””â”€ Triggers: Create ExpenseVoucher
      â”œâ”€ source_document = ExpenseClaim
      â”œâ”€ source_type = EMP_CLAIM
      â”œâ”€ party = Employee
      â””â”€ net_payable = calculated

3. ExpenseVoucher auto-posts
   â”œâ”€ Status: POSTED
   â”œâ”€ JournalEntry created
   â”‚  â”œâ”€ DR: Expense accounts
   â”‚  â”œâ”€ DR: GST Input (if any)
   â”‚  â””â”€ CR: Employee Payable
   â””â”€ GL balances updated

4. Accountant creates payment
   â”œâ”€ PaymentVoucher created
   â”œâ”€ source_document = ExpenseVoucher
   â”œâ”€ direction = PAYMENT
   â”œâ”€ amount = net_payable
   â””â”€ Posts:
      â”œâ”€ DR: Employee Payable
      â””â”€ CR: Cash/Bank

5. Employee receives money
   â”œâ”€ ExpenseVoucher.paid_amount updated
   â”œâ”€ ExpenseVoucher.is_paid = True
   â””â”€ Workflow complete


VENDOR BILL WORKFLOW:
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. Vendor sends bill
   â”œâ”€ VendorBill created
   â”œâ”€ Amount: â‚¹50,000 + GST
   â””â”€ Status: RECEIVED

2. Bill verified & approved
   â”œâ”€ VendorBill.status = APPROVED
   â””â”€ Triggers: Create ExpenseVoucher
      â”œâ”€ source_document = VendorBill
      â”œâ”€ source_type = VENDOR_BILL
      â”œâ”€ party = Vendor
      â””â”€ net_payable = calculated

3. ExpenseVoucher auto-posts
   â”œâ”€ JournalEntry created
   â”‚  â”œâ”€ DR: Expense account
   â”‚  â”œâ”€ DR: GST Input
   â”‚  â”œâ”€ CR: TDS Payable (if withheld)
   â”‚  â””â”€ CR: Vendor Payable (AP)
   â””â”€ Creates AP liability

4. Pay vendor (later)
   â”œâ”€ PaymentVoucher created
   â”œâ”€ source_document = ExpenseVoucher
   â”œâ”€ direction = PAYMENT
   â””â”€ Posts:
      â”œâ”€ DR: Vendor Payable
      â””â”€ CR: Cash/Bank

5. Vendor receives payment
   â”œâ”€ ExpenseVoucher.paid_amount updated
   â”œâ”€ ExpenseVoucher.is_paid = True
   â””â”€ AP liability cleared
```

---

## Sales Invoice Voucher Design

### Overview

**Purpose**: Record revenue from goods/services sold to customers.

**Key Characteristics:**
- Accrual-based (revenue recognized when delivered, not when paid)
- Creates AR (Accounts Receivable) until customer pays
- Supports multiple items, taxes, discounts
- Can have partial payments

### Model Design

**File**: `apps/tenant_apps/dea/models/sales.py`

```python
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
    - Posts to GL immediately (AR â†” Revenue)
    - Cash collection handled separately by PaymentVoucher
    - Supports complex tax scenarios (GST, TCS, etc.)
    
    Example:
    Goods sold to customer â†’ Invoice â†’ SalesInvoiceVoucher â†’ PaymentVoucher (collection)
    """
    
    # === Core Identity ===
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique invoice reference (auto-generated)"
    )
    
    invoice_date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Date of invoice"
    )
    
    # === Customer ===
    customer = models.ForeignKey(
        'contact.Contact',  # Or your Customer model
        on_delete=models.PROTECT,
        related_name='sales_invoices',
        help_text="Customer who purchased"
    )
    
    # === Reference to Sales Order (if exists) ===
    sales_order = models.ForeignKey(
        'SalesOrder',  # If you have sales order model
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        help_text="Reference to sales order"
    )
    
    # === Amounts ===
    subtotal = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Subtotal before taxes and discounts"
    )
    
    discount_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Total discount amount"
    )
    
    taxable_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Amount subject to tax (subtotal - discount)"
    )
    
    cgst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="CGST (Central GST)"
    )
    
    sgst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="SGST (State GST)"
    )
    
    igst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="IGST (Integrated GST) for interstate"
    )
    
    tcs_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="TCS (Tax Collected at Source)"
    )
    
    total_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Grand total (taxable + taxes + tcs)"
    )
    
    # === Payment Tracking ===
    received_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Amount received from customer"
    )
    
    is_fully_paid = models.BooleanField(
        default=False,
        help_text="Whether invoice is fully paid"
    )
    
    # === Terms ===
    payment_terms = models.CharField(
        max_length=100,
        blank=True,
        help_text="Payment terms (e.g., Net 30 days)"
    )
    
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Payment due date"
    )
    
    # === Description ===
    notes = models.TextField(
        blank=True,
        help_text="Invoice notes/terms"
    )
    
    # === Reverse relation to payments ===
    payments = GenericRelation('PaymentVoucher')
    
    class Meta:
        ordering = ['-invoice_date', '-created_at']
        verbose_name = "Sales Invoice Voucher"
        verbose_name_plural = "Sales Invoice Vouchers"
        indexes = [
            models.Index(fields=['invoice_date', 'customer']),
            models.Index(fields=['is_fully_paid']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number} - {self.customer} - {self.total_amount}"
    
    def clean(self):
        """Validate invoice data"""
        super().clean()
        
        # Calculate taxable amount
        calculated_taxable = self.subtotal.amount - self.discount_amount.amount
        if abs(calculated_taxable - self.taxable_amount.amount) > Decimal('0.01'):
            raise ValidationError(
                f"Taxable amount mismatch: Expected {calculated_taxable}, got {self.taxable_amount.amount}"
            )
        
        # Calculate total
        total_tax = (
            self.cgst_amount.amount + 
            self.sgst_amount.amount + 
            self.igst_amount.amount + 
            self.tcs_amount.amount
        )
        calculated_total = self.taxable_amount.amount + total_tax
        
        if abs(calculated_total - self.total_amount.amount) > Decimal('0.01'):
            raise ValidationError(
                f"Total amount mismatch: Expected {calculated_total}, got {self.total_amount.amount}"
            )
        
        # Validate amounts are positive
        if self.subtotal.amount < 0:
            raise ValidationError("Subtotal cannot be negative")
        
        # Validate payment tracking
        if self.received_amount.amount > self.total_amount.amount:
            raise ValidationError(
                f"Received amount ({self.received_amount}) cannot exceed total ({self.total_amount})"
            )
    
    def save(self, *args, **kwargs):
        """Auto-generate invoice number if not set"""
        if not self.invoice_number:
            self.invoice_number = self._generate_invoice_number()
        
        # Auto-calculate taxable amount
        if not self.taxable_amount or self.taxable_amount.amount == 0:
            self.taxable_amount = Money(
                self.subtotal.amount - self.discount_amount.amount,
                self.subtotal.currency
            )
        
        # Auto-calculate total
        if not self.total_amount or self.total_amount.amount == 0:
            total_tax = (
                self.cgst_amount.amount + 
                self.sgst_amount.amount + 
                self.igst_amount.amount + 
                self.tcs_amount.amount
            )
            self.total_amount = Money(
                self.taxable_amount.amount + total_tax,
                self.taxable_amount.currency
            )
        
        # Update payment status
        self.is_fully_paid = (self.received_amount.amount >= self.total_amount.amount)
        
        super().save(*args, **kwargs)
    
    def _generate_invoice_number(self) -> str:
        """Generate unique invoice number"""
        from django.utils import timezone
        today = timezone.now()
        prefix = f"INV-{today.year}-{today.month:02d}"
        
        last_invoice = SalesInvoiceVoucher.objects.filter(
            invoice_number__startswith=prefix
        ).order_by('-invoice_number').first()
        
        if last_invoice:
            try:
                last_seq = int(last_invoice.invoice_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}-{next_seq:04d}"
    
    def get_voucher_type(self) -> str:
        """Return voucher type for posting rules"""
        return "SALES_INVOICE"
    
    @property
    def outstanding_balance(self) -> Money:
        """Amount still due from customer"""
        return Money(
            self.total_amount.amount - self.received_amount.amount,
            self.total_amount.currency
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
        related_name='line_items',
        help_text="Parent invoice"
    )
    
    line_number = models.PositiveIntegerField(
        default=1,
        help_text="Line item sequence"
    )
    
    # === Product/Service ===
    product = models.ForeignKey(
        'product.Product',  # Your product model
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Product sold (if applicable)"
    )
    
    description = models.TextField(
        help_text="Item description"
    )
    
    # === Quantity & Price ===
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=1,
        help_text="Quantity sold"
    )
    
    unit_price = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Price per unit"
    )
    
    line_total = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Line total (quantity * unit_price)"
    )
    
    # === Discount ===
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Discount percentage"
    )
    
    discount_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Discount amount"
    )
    
    # === Tax ===
    hsn_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="HSN/SAC code for GST"
    )
    
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="GST rate percentage"
    )
    
    cgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="CGST rate"
    )
    
    sgst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="SGST rate"
    )
    
    igst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="IGST rate"
    )
    
    class Meta:
        ordering = ['invoice', 'line_number']
        verbose_name = "Sales Invoice Line Item"
        verbose_name_plural = "Sales Invoice Line Items"
        unique_together = [['invoice', 'line_number']]
    
    def __str__(self):
        return f"{self.invoice.invoice_number} - Line {self.line_number}: {self.description}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate line totals"""
        # Calculate line total
        self.line_total = Money(
            self.quantity * self.unit_price.amount,
            self.unit_price.currency
        )
        
        # Calculate discount
        if self.discount_percentage > 0:
            self.discount_amount = Money(
                self.line_total.amount * self.discount_percentage / 100,
                self.line_total.currency
            )
        
        super().save(*args, **kwargs)
```

### Posting Rule for Sales Invoice

**File**: `apps/tenant_apps/dea/posting/rules/sales_invoice.py`

```python
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("SALES_INVOICE")
class SalesInvoiceRule(BasePostingRule):
    """
    Posting rule for sales invoices.
    
    ACCOUNTING ENTRIES:
    DR: Accounts Receivable (Customer)
    CR: Sales Revenue
    CR: CGST Output
    CR: SGST Output
    CR: IGST Output
    CR: TCS Payable
    
    Example:
    Sold goods for â‚¹100,000 + GST â‚¹18,000
    DR: AR â‚¹118,000
    CR: Sales Revenue â‚¹100,000
    CR: GST Output â‚¹18,000
    """
    
    def should_run(self, doc) -> bool:
        """Only run for sales invoices"""
        from apps.tenant_apps.dea.models import SalesInvoiceVoucher
        return isinstance(doc, SalesInvoiceVoucher)
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for sales invoice"""
        from apps.tenant_apps.dea.models import SalesInvoiceVoucher
        
        if not isinstance(doc, SalesInvoiceVoucher):
            raise ValidationError("Document must be SalesInvoiceVoucher")
        
        # Get account IDs
        ar_ledger = get_ledger_id_by_key("ACCOUNTS_RECEIVABLE")
        sales_ledger = get_ledger_id_by_key("SALES_REVENUE")
        cgst_output_ledger = get_ledger_id_by_key("CGST_OUTPUT" )
        sgst_output_ledger = get_ledger_id_by_key("SGST_OUTPUT")
        igst_output_ledger = get_ledger_id_by_key("IGST_OUTPUT")
        tcs_payable_ledger = get_ledger_id_by_key("TCS_PAYABLE")
        
        lines = []
        
        # DR: Accounts Receivable (total invoice amount)
        lines.append(DualLedgerLine(
            ledger_dr=ar_ledger,
            ledger_cr=None,
            amount=doc.total_amount.amount,
            memo=f"Sale to {doc.customer.name} - Invoice {doc.invoice_number}"
        ))
        
        # CR: Sales Revenue (taxable amount - use subtotal - discount)
        lines.append(DualLedgerLine(
            ledger_dr=None,
            ledger_cr=sales_ledger,
            amount=doc.taxable_amount.amount,
            memo=f"Sales revenue - Invoice {doc.invoice_number}"
        ))
        
        # CR: CGST Output
        if doc.cgst_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=cgst_output_ledger,
                amount=doc.cgst_amount.amount,
                memo="CGST collected"
            ))
        
        # CR: SGST Output
        if doc.sgst_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=sgst_output_ledger,
                amount=doc.sgst_amount.amount,
                memo="SGST collected"
            ))
        
        # CR: IGST Output
        if doc.igst_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=igst_output_ledger,
                amount=doc.igst_amount.amount,
                memo="IGST collected"
            ))
        
        # CR: TCS Payable
        if doc.tcs_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=tcs_payable_ledger,
                amount=doc.tcs_amount.amount,
                memo="TCS collected"
            ))
        
        # Subledger: Customer account
        account_lines = [
            AccountLine(
                account_dr=doc.customer.id,
                account_cr=None,
                amount=doc.total_amount.amount,
                memo=f"Invoice {doc.invoice_number}"
            )
        ]
        
        return PostingBundle(
            voucher_type="SALES_INVOICE",
            voucher_number=doc.invoice_number,
            voucher_date=doc.invoice_date,
            description=f"Sales to {doc.customer.name}",
            lines=lines,
            account_lines=account_lines,
        )
```

### Sales Invoice Workflow

```
SALES INVOICE WORKFLOW:
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. Customer places order (optional)
   â”œâ”€ SalesOrder created
   â”œâ”€ Status: PENDING
   â””â”€ Items: Product A x 10, Product B x 5

2. Goods delivered to customer
   â”œâ”€ Delivery Note created
   â””â”€ Triggers: Create SalesInvoiceVoucher
      â”œâ”€ reference: SalesOrder
      â”œâ”€ customer: XYZ Corp
      â”œâ”€ line_items: from order
      â””â”€ Status: DRAFT

3. Invoice reviewed & finalized
   â”œâ”€ Line items confirmed
   â”œâ”€ Taxes calculated
   â”œâ”€ Status: APPROVED
   â””â”€ Triggers: Auto-post voucher

4. SalesInvoiceVoucher posts
   â”œâ”€ JournalEntry created
   â”‚  â”œâ”€ DR: AR â‚¹118,000
   â”‚  â”œâ”€ CR: Sales Revenue â‚¹100,000
   â”‚  â””â”€ CR: GST Output â‚¹18,000
   â””â”€ Creates AR (receivable from customer)

5. Customer pays (later)
   â”œâ”€ PaymentVoucher created
   â”œâ”€ source_document = SalesInvoiceVoucher
   â”œâ”€ direction = RECEIPT
   â”œâ”€ amount = â‚¹118,000
   â””â”€ Posts:
      â”œâ”€ DR: Cash â‚¹118,000
      â””â”€ CR: AR â‚¹118,000

6. Payment received
   â”œâ”€ SalesInvoiceVoucher.received_amount updated
   â”œâ”€ SalesInvoiceVoucher.is_fully_paid = True
   â””â”€ AR cleared
```

---

## Purchase Invoice Voucher Design

### Overview

**Purpose**: Record costs of goods/services purchased from vendors.

**Key Characteristics:**
- Accrual-based (liability recognized when received, not when paid)
- Creates AP (Accounts Payable) until vendor is paid
- Can update inventory (if goods) or expense (if services)
- Supports GRN (Goods Receipt Note) matching

### Model Design

**File**: `apps/tenant_apps/dea/models/purchase.py`

```python
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
    - Posts to GL immediately (Inventory/Expense â†” AP)
    - Cash payment handled separately by PaymentVoucher
    - Supports GRN matching for goods
    
    Example:
    Goods purchased from vendor â†’ GRN â†’ PurchaseInvoiceVoucher â†’ PaymentVoucher (payment)
    """
    
    # === Core Identity ===
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Vendor's invoice number"
    )
    
    internal_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        blank=True,
        help_text="Our internal reference number (auto-generated)"
    )
    
    invoice_date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Date on vendor's invoice"
    )
    
    received_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date when goods/services received"
    )
    
    # === Vendor ===
    vendor = models.ForeignKey(
        'contact.Contact',  # Or your Vendor model
        on_delete=models.PROTECT,
        related_name='purchase_invoices',
        help_text="Vendor who supplied"
    )
    
    # === Purchase Type ===
    purchase_type = models.CharField(
        max_length=20,
        choices=PurchaseType.choices,
        default=PurchaseType.GOODS,
        help_text="Type of purchase"
    )
    
    # === Reference to Purchase Order/GRN ===
    purchase_order = models.ForeignKey(
        'PurchaseOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        help_text="Reference to purchase order"
    )
    
    grn = models.ForeignKey(
        'GoodsReceiptNote',  # If you have GRN model
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        help_text="Reference to GRN (Goods Receipt Note)"
    )
    
    # === Amounts ===
    subtotal = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Subtotal before taxes"
    )
    
    discount_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Total discount amount"
    )
    
    taxable_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Amount subject to tax"
    )
    
    cgst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="CGST amount"
    )
    
    sgst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="SGST amount"
    )
    
    igst_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="IGST amount"
    )
    
    tds_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="TDS withheld (if applicable)"
    )
    
    total_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Grand total (taxable + taxes)"
    )
    
    net_payable = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Net payable to vendor (total - tds)"
    )
    
    # === Payment Tracking ===
    paid_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Amount paid to vendor"
    )
    
    is_fully_paid = models.BooleanField(
        default=False,
        help_text="Whether invoice is fully paid"
    )
    
    # === Terms ===
    payment_terms = models.CharField(
        max_length=100,
        blank=True,
        help_text="Payment terms from vendor"
    )
    
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Payment due date"
    )
    
    # === Description ===
    notes = models.TextField(
        blank=True,
        help_text="Invoice notes"
    )
    
    # === Reverse relation to payments ===
    payments = GenericRelation('PaymentVoucher')
    
    class Meta:
        ordering = ['-invoice_date', '-created_at']
        verbose_name = "Purchase Invoice Voucher"
        verbose_name_plural = "Purchase Invoice Vouchers"
        indexes = [
            models.Index(fields=['invoice_date', 'vendor']),
            models.Index(fields=['purchase_type', 'is_fully_paid']),
        ]
    
    def __str__(self):
        return f"{self.internal_number} - {self.vendor} - {self.total_amount}"
    
    def clean(self):
        """Validate invoice data"""
        super().clean()
        
        # Calculate taxable amount
        calculated_taxable = self.subtotal.amount - self.discount_amount.amount
        if abs(calculated_taxable - self.taxable_amount.amount) > Decimal('0.01'):
            raise ValidationError(
                f"Taxable amount mismatch"
            )
        
        # Calculate total
        total_tax = (
            self.cgst_amount.amount + 
            self.sgst_amount.amount + 
            self.igst_amount.amount
        )
        calculated_total = self.taxable_amount.amount + total_tax
        
        if abs(calculated_total - self.total_amount.amount) > Decimal('0.01'):
            raise ValidationError(
                f"Total amount mismatch"
            )
        
        # Calculate net payable
        calculated_net = self.total_amount.amount - self.tds_amount.amount
        if abs(calculated_net - self.net_payable.amount) > Decimal('0.01'):
            raise ValidationError(
                f"Net payable mismatch"
            )
    
    def save(self, *args, **kwargs):
        """Auto-generate internal number if not set"""
        if not self.internal_number:
            self.internal_number = self._generate_internal_number()
        
        # Auto-calculate amounts
        if not self.taxable_amount or self.taxable_amount.amount == 0:
            self.taxable_amount = Money(
                self.subtotal.amount - self.discount_amount.amount,
                self.subtotal.currency
            )
        
        if not self.total_amount or self.total_amount.amount == 0:
            total_tax = (
                self.cgst_amount.amount + 
                self.sgst_amount.amount + 
                self.igst_amount.amount
            )
            self.total_amount = Money(
                self.taxable_amount.amount + total_tax,
                self.taxable_amount.currency
            )
        
        if not self.net_payable or self.net_payable.amount == 0:
            self.net_payable = Money(
                self.total_amount.amount - self.tds_amount.amount,
                self.total_amount.currency
            )
        
        # Update payment status
        self.is_fully_paid = (self.paid_amount.amount >= self.net_payable.amount)
        
        super().save(*args, **kwargs)
    
    def _generate_internal_number(self) -> str:
        """Generate unique internal reference number"""
        from django.utils import timezone
        today = timezone.now()
        prefix = f"PI-{today.year}-{today.month:02d}"
        
        last_invoice = PurchaseInvoiceVoucher.objects.filter(
            internal_number__startswith=prefix
        ).order_by('-internal_number').first()
        
        if last_invoice:
            try:
                last_seq = int(last_invoice.internal_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}-{next_seq:04d}"
    
    def get_voucher_type(self) -> str:
        """Return voucher type for posting rules"""
        return f"PURCHASE_{self.purchase_type}"
    
    @property
    def outstanding_balance(self) -> Money:
        """Amount still owed to vendor"""
        return Money(
            self.net_payable.amount - self.paid_amount.amount,
            self.net_payable.currency
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
        related_name='line_items',
        help_text="Parent invoice"
    )
    
    line_number = models.PositiveIntegerField(
        default=1,
        help_text="Line item sequence"
    )
    
    # === Product/Item ===
    product = models.ForeignKey(
        'product.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Product purchased"
    )
    
    description = models.TextField(
        help_text="Item description"
    )
    
    # === Quantity & Price ===
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=1,
        help_text="Quantity purchased"
    )
    
    unit_price = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Price per unit"
    )
    
    line_total = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Line total"
    )
    
    # === Tax ===
    hsn_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="HSN code"
    )
    
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="GST rate"
    )
    
    class Meta:
        ordering = ['invoice', 'line_number']
        verbose_name = "Purchase Invoice Line Item"
        verbose_name_plural = "Purchase Invoice Line Items"
        unique_together = [['invoice', 'line_number']]
    
    def save(self, *args, **kwargs):
        """Auto-calculate line total"""
        self.line_total = Money(
            self.quantity * self.unit_price.amount,
            self.unit_price.currency
        )
        super().save(*args, **kwargs)
```

### Posting Rule for Purchase Invoice

**File**: `apps/tenant_apps/dea/posting/rules/purchase_invoice.py`

```python
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("PURCHASE_GOODS")
class PurchaseGoodsRule(BasePostingRule):
    """
    Posting rule for purchase of goods (inventory).
    
    ACCOUNTING ENTRIES:
    DR: Inventory/Stock
    DR: GST Input Credit
    CR: Accounts Payable (Vendor)
    CR: TDS Payable (if withheld)
    
    Example:
    Purchased goods for â‚¹100,000 + GST â‚¹18,000
    DR: Inventory â‚¹100,000
    DR: GST Input â‚¹18,000
    CR: AP â‚¹118,000
    """
    
    def should_run(self, doc) -> bool:
        """Only run for goods purchases"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher
        return (
            isinstance(doc, PurchaseInvoiceVoucher) and 
            doc.purchase_type == 'GOODS'
        )
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for purchase of goods"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher
        
        if not isinstance(doc, PurchaseInvoiceVoucher):
            raise ValidationError("Document must be PurchaseInvoiceVoucher")
        
        # Get account IDs
        inventory_ledger = get_ledger_id_by_key("INVENTORY")
        gst_input_ledger = get_ledger_id_by_key("GST_INPUT_CREDIT")
        ap_ledger = get_ledger_id_by_key("ACCOUNTS_PAYABLE")
        tds_payable_ledger = get_ledger_id_by_key("TDS_PAYABLE")
        
        lines = []
        
        # DR: Inventory
        lines.append(DualLedgerLine(
            ledger_dr=inventory_ledger,
            ledger_cr=None,
            amount=doc.taxable_amount.amount,
            memo=f"Purchase from {doc.vendor.name} - {doc.internal_number}"
        ))
        
        # DR: GST Input Credit
        total_gst = (
            doc.cgst_amount.amount + 
            doc.sgst_amount.amount + 
            doc.igst_amount.amount
        )
        if total_gst > 0:
            lines.append(DualLedgerLine(
                ledger_dr=gst_input_ledger,
                ledger_cr=None,
                amount=total_gst,
                memo="GST Input Credit"
            ))
        
        # CR: TDS Payable (if withheld)
        if doc.tds_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=tds_payable_ledger,
                amount=doc.tds_amount.amount,
                memo="TDS withheld"
            ))
        
        # CR: Accounts Payable
        lines.append(DualLedgerLine(
            ledger_dr=None,
            ledger_cr=ap_ledger,
            amount=doc.net_payable.amount,
            memo=f"Payable to {doc.vendor.name}"
        ))
        
        # Subledger: Vendor account
        account_lines = [
            AccountLine(
                account_dr=None,
                account_cr=doc.vendor.id,
                amount=doc.net_payable.amount,
                memo=f"Purchase {doc.internal_number}"
            )
        ]
        
        return PostingBundle(
            voucher_type="PURCHASE_GOODS",
            voucher_number=doc.internal_number,
            voucher_date=doc.invoice_date,
            description=f"Purchase from {doc.vendor.name}",
            lines=lines,
            account_lines=account_lines,
        )


@register_rule("PURCHASE_SERVICES")
class PurchaseServicesRule(BasePostingRule):
    """
    Posting rule for purchase of services (expense).
    
    ACCOUNTING ENTRIES:
    DR: Expense Account
    DR: GST Input Credit
    CR: Accounts Payable (Vendor)
    CR: TDS Payable (if withheld)
    
    Example:
    Consulting services â‚¹50,000 + GST â‚¹9,000 - TDS â‚¹5,000
    DR: Professional Services Expense â‚¹50,000
    DR: GST Input â‚¹9,000
    CR: TDS Payable â‚¹5,000
    CR: AP â‚¹54,000
    """
    
    def should_run(self, doc) -> bool:
        """Only run for services purchases"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher
        return (
            isinstance(doc, PurchaseInvoiceVoucher) and 
            doc.purchase_type == 'SERVICES'
        )
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for purchase of services"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher
        
        if not isinstance(doc, PurchaseInvoiceVoucher):
            raise ValidationError("Document must be PurchaseInvoiceVoucher")
        
        # Get account IDs (similar to PURCHASE_GOODS but use expense account)
        expense_ledger = get_ledger_id_by_key("PROFESSIONAL_SERVICES_EXPENSE")
        gst_input_ledger = get_ledger_id_by_key("GST_INPUT_CREDIT")
        ap_ledger = get_ledger_id_by_key("ACCOUNTS_PAYABLE")
        tds_payable_ledger = get_ledger_id_by_key("TDS_PAYABLE")
        
        lines = []
        
        # DR: Expense
        lines.append(DualLedgerLine(
            ledger_dr=expense_ledger,
            ledger_cr=None,
            amount=doc.taxable_amount.amount,
            memo=f"Service from {doc.vendor.name}"
        ))
        
        # DR: GST Input
        total_gst = (
            doc.cgst_amount.amount + 
            doc.sgst_amount.amount + 
            doc.igst_amount.amount
        )
        if total_gst > 0:
            lines.append(DualLedgerLine(
                ledger_dr=gst_input_ledger,
                ledger_cr=None,
                amount=total_gst,
                memo="GST Input Credit"
            ))
        
        # CR: TDS Payable
        if doc.tds_amount.amount > 0:
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=tds_payable_ledger,
                amount=doc.tds_amount.amount,
                memo="TDS withheld"
            ))
        
        # CR: Accounts Payable
        lines.append(DualLedgerLine(
            ledger_dr=None,
            ledger_cr=ap_ledger,
            amount=doc.net_payable.amount,
            memo=f"Payable to {doc.vendor.name}"
        ))
        
        # Subledger
        account_lines = [
            AccountLine(
                account_dr=None,
                account_cr=doc.vendor.id,
                amount=doc.net_payable.amount,
                memo=f"Purchase {doc.internal_number}"
            )
        ]
        
        return PostingBundle(
            voucher_type="PURCHASE_SERVICES",
            voucher_number=doc.internal_number,
            voucher_date=doc.invoice_date,
            description=f"Purchase services from {doc.vendor.name}",
            lines=lines,
            account_lines=account_lines,
        )
```

### Purchase Invoice Workflow

```
PURCHASE INVOICE WORKFLOW:
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. Purchase order placed (optional)
   â”œâ”€ PurchaseOrder created
   â”œâ”€ Vendor: ABC Supplies
   â””â”€ Status: APPROVED

2. Goods received
   â”œâ”€ GoodsReceiptNote created
   â”œâ”€ Quantity verified
   â”œâ”€ Quality checked
   â””â”€ Status: RECEIVED

3. Vendor invoice received
   â”œâ”€ PurchaseInvoiceVoucher created
   â”œâ”€ invoice_number: From vendor
   â”œâ”€ internal_number: Auto-generated
   â”œâ”€ Match with GRN
   â””â”€ Status: DRAFT

4. Invoice verified & approved
   â”œâ”€ 3-way match: PO â†” GRN â†” Invoice
   â”œâ”€ Amounts reconciled
   â”œâ”€ Status: APPROVED
   â””â”€ Triggers: Auto-post voucher

5. PurchaseInvoiceVoucher posts
   â”œâ”€ JournalEntry created
   â”‚  â”œâ”€ DR: Inventory â‚¹100,000
   â”‚  â”œâ”€ DR: GST Input â‚¹18,000
   â”‚  â””â”€ CR: AP â‚¹118,000
   â””â”€ Creates AP (payable to vendor)

6. Pay vendor (later)
   â”œâ”€ PaymentVoucher created
   â”œâ”€ source_document = PurchaseInvoiceVoucher
   â”œâ”€ direction = PAYMENT
   â”œâ”€ amount = â‚¹118,000
   â””â”€ Posts:
      â”œâ”€ DR: AP â‚¹118,000
      â””â”€ CR: Cash â‚¹118,000

7. Vendor receives payment
   â”œâ”€ PurchaseInvoiceVoucher.paid_amount updated
   â”œâ”€ PurchaseInvoiceVoucher.is_fully_paid = True
   â””â”€ AP cleared
```

---

## Journal Entry Voucher Design

### Overview

**Purpose**: Record manual accounting adjustments, corrections, and period-end entries.

**Key Characteristics:**
- Completely manual (user enters DR/CR lines)
- No automatic posting from business documents
- Used for closing entries, accruals, corrections
- Requires approval before posting
- Most flexible voucher type

### Model Design

**File**: `apps/tenant_apps/dea/models/journal.py`

```python
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money
from decimal import Decimal

from .doc import BusinessDoc


class JournalEntryVoucher(BusinessDoc):
    """
    Journal Entry Voucher - Manual GL adjustments.
    
    CHARACTERISTICS:
    - Completely manual data entry
    - No automatic posting from source documents
    - Used for corrections, period-end adjustments
    - Can be multi-currency
    - Requires review and approval
    
    Examples:
    - Depreciation accrual at month-end
    - Inter-company adjustments
    - Reversal of incorrect entries
    - Exchange rate adjustments
    - Manual corrections
    """
    
    # === Core Identity ===
    je_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique journal entry reference (auto-generated)"
    )
    
    je_date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Journal entry date (may differ from posting date)"
    )
    
    # === Classification ===
    ENTRY_TYPES = [
        ('CLOSING', 'Closing Entry'),
        ('ACCRUAL', 'Accrual'),
        ('CORRECTION', 'Correction/Reversal'),
        ('ADJUSTMENT', 'Period-End Adjustment'),
        ('INTERCORP', 'Inter-Company'),
        ('EXCHANGE', 'Exchange Rate Adjustment'),
        ('OTHER', 'Other'),
    ]
    
    entry_type = models.CharField(
        max_length=50,
        choices=ENTRY_TYPES,
        default='OTHER',
        help_text="Type of journal entry"
    )
    
    # === Description ===
    description = models.TextField(
        help_text="Detailed description of the journal entry"
    )
    
    memo = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short memo/reference"
    )
    
    # === Reference (Optional) ===
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference to source document (if applicable)"
    )
    
    # === Amounts ===
    total_debit = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Total of all debit lines"
    )
    
    total_credit = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Total of all credit lines"
    )
    
    # === Approval ===
    reviewed_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_journal_entries',
        help_text="User who reviewed and approved"
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When journal entry was reviewed"
    )
    
    class Meta:
        ordering = ['-je_date', '-created_at']
        verbose_name = "Journal Entry Voucher"
        verbose_name_plural = "Journal Entry Vouchers"
        indexes = [
            models.Index(fields=['je_date', 'entry_type']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.je_number} - {self.get_entry_type_display()} - DR: {self.total_debit} CR: {self.total_credit}"
    
    def clean(self):
        """Validate journal entry"""
        super().clean()
        
        # Check if balanced
        if abs(self.total_debit.amount - self.total_credit.amount) > Decimal('0.01'):
            raise ValidationError(
                f"Journal entry not balanced: DR {self.total_debit} â‰  CR {self.total_credit}"
            )
        
        # Check if has line items
        line_count = self.line_items.count()
        if line_count < 2:
            raise ValidationError("Journal entry must have at least 2 line items (1 DR and 1 CR)")
    
    def save(self, *args, **kwargs):
        """Auto-generate JE number if not set"""
        if not self.je_number:
            self.je_number = self._generate_je_number()
        
        super().save(*args, **kwargs)
    
    def _generate_je_number(self) -> str:
        """Generate unique journal entry number"""
        from django.utils import timezone
        today = timezone.now()
        prefix = f"JE-{today.year}-{today.month:02d}"
        
        last_je = JournalEntryVoucher.objects.filter(
            je_number__startswith=prefix
        ).order_by('-je_number').first()
        
        if last_je:
            try:
                last_seq = int(last_je.je_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}-{next_seq:04d}"
    
    def get_voucher_type(self) -> str:
        """Return voucher type"""
        return f"JOURNAL_ENTRY_{self.entry_type}"
    
    @property
    def is_balanced(self) -> bool:
        """Check if journal entry is balanced"""
        return abs(self.total_debit.amount - self.total_credit.amount) <= Decimal('0.01')
    
    @property
    def balance_difference(self) -> Money:
        """Return the balance difference (should be 0)"""
        return Money(
            self.total_debit.amount - self.total_credit.amount,
            self.total_debit.currency
        )


class JournalEntryLineItem(models.Model):
    """Line items in a journal entry (DR/CR transactions)"""
    
    journal_entry = models.ForeignKey(
        JournalEntryVoucher,
        on_delete=models.CASCADE,
        related_name='line_items',
        help_text="Parent journal entry"
    )
    
    line_number = models.PositiveIntegerField(
        default=1,
        help_text="Line sequence number"
    )
    
    # === Account ===
    ledger = models.ForeignKey(
        'dea.Ledger',
        on_delete=models.PROTECT,
        help_text="GL account (Ledger)"
    )
    
    # === DR/CR ===
    SIDE_CHOICES = [('DR', 'Debit'), ('CR', 'Credit')]
    side = models.CharField(
        max_length=2,
        choices=SIDE_CHOICES,
        help_text="Debit or Credit side"
    )
    
    amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Amount (always positive, side determines direction)"
    )
    
    # === Description ===
    description = models.TextField(
        help_text="Line description"
    )
    
    class Meta:
        ordering = ['journal_entry', 'line_number']
        verbose_name = "Journal Entry Line Item"
        verbose_name_plural = "Journal Entry Line Items"
        unique_together = [['journal_entry', 'line_number']]
    
    def __str__(self):
        return f"{self.journal_entry.je_number} - Line {self.line_number}: {self.side} {self.amount}"
    
    def clean(self):
        """Validate line item"""
        if self.amount.amount < 0:
            raise ValidationError("Amount must be positive (side determines DR/CR)")
        
        if self.amount.amount == 0:
            raise ValidationError("Amount cannot be zero")
    
    def save(self, *args, **kwargs):
        """Auto-calculate line number if not set"""
        if not self.line_number or self.line_number == 0:
            max_line = JournalEntryLineItem.objects.filter(
                journal_entry=self.journal_entry
            ).aggregate(models.Max('line_number'))['line_number__max']
            
            self.line_number = (max_line or 0) + 1
        
        super().save(*args, **kwargs)
```

### Posting Rule for Journal Entry

**File**: `apps/tenant_apps/dea/posting/rules/journal_entry.py`

```python
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine
from .base import BasePostingRule
from ..registry import register_rule


@register_rule("JOURNAL_ENTRY_CLOSING")
@register_rule("JOURNAL_ENTRY_ACCRUAL")
@register_rule("JOURNAL_ENTRY_CORRECTION")
@register_rule("JOURNAL_ENTRY_ADJUSTMENT")
@register_rule("JOURNAL_ENTRY_INTERCORP")
@register_rule("JOURNAL_ENTRY_EXCHANGE")
@register_rule("JOURNAL_ENTRY_OTHER")
class JournalEntryRule(BasePostingRule):
    """
    Posting rule for manual journal entries.
    
    Simply posts the lines as entered by user.
    All validation is done at data entry time.
    """
    
    def should_run(self, doc) -> bool:
        """Only run for journal entries"""
        from apps.tenant_apps.dea.models import JournalEntryVoucher
        return isinstance(doc, JournalEntryVoucher)
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting from journal entry lines"""
        from apps.tenant_apps.dea.models import JournalEntryVoucher
        
        if not isinstance(doc, JournalEntryVoucher):
            raise ValidationError("Document must be JournalEntryVoucher")
        
        # Validate balanced
        if not doc.is_balanced:
            raise ValidationError(f"Entry not balanced: Difference = {doc.balance_difference}")
        
        lines = []
        
        # Add each line from journal entry
        for je_line in doc.line_items.all():
            if je_line.side == 'DR':
                lines.append(DualLedgerLine(
                    ledger_dr=je_line.ledger.id,
                    ledger_cr=None,
                    amount=je_line.amount.amount,
                    memo=je_line.description
                ))
            else:  # CR
                lines.append(DualLedgerLine(
                    ledger_dr=None,
                    ledger_cr=je_line.ledger.id,
                    amount=je_line.amount.amount,
                    memo=je_line.description
                ))
        
        return PostingBundle(
            voucher_type=doc.get_voucher_type(),
            voucher_number=doc.je_number,
            voucher_date=doc.je_date,
            description=f"{doc.get_entry_type_display()}: {doc.description}",
            lines=lines,
            account_lines=[],
        )
```

### Journal Entry Workflow

```
JOURNAL ENTRY WORKFLOW:
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. Accountant creates manual journal entry
   â”œâ”€ JournalEntryVoucher created
   â”œâ”€ entry_type: CLOSING, ACCRUAL, CORRECTION, etc.
   â”œâ”€ description: Detailed explanation
   â””â”€ Status: DRAFT

2. Add line items
   â”œâ”€ For each debit and credit:
   â”‚  â”œâ”€ Select GL account (Ledger)
   â”‚  â”œâ”€ Enter amount (always positive)
   â”‚  â”œâ”€ Select side (DR or CR)
   â”‚  â””â”€ Add description/memo
   â”‚
   â””â”€ System validates:
      â”œâ”€ Total DR = Total CR âœ“
      â””â”€ At least 2 lines âœ“

3. Save journal entry
   â”œâ”€ JournalEntryVoucher.total_debit calculated
   â”œâ”€ JournalEntryVoucher.total_credit calculated
   â””â”€ Status: DRAFT

4. Manager reviews and approves
   â”œâ”€ JournalEntryVoucher.reviewed_by = Manager
   â”œâ”€ JournalEntryVoucher.reviewed_at = now
   â”œâ”€ Status: APPROVED
   â””â”€ Triggers: Post to GL

5. Auto-post on approval
   â”œâ”€ JournalEntry created
   â”‚  â”œâ”€ Posted by: Posting Engine
   â”‚  â”œâ”€ Posted at: now
   â”‚  â””â”€ Period: Auto-detected from date
   â”‚
   â”œâ”€ Ledger entries created (per line item)
   â”‚  â”œâ”€ DR entries â†’ Ledger balances â†‘
   â”‚  â””â”€ CR entries â†’ Ledger balances â†“
   â”‚
   â””â”€ GL immediately updated

Example: Depreciation Accrual
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ JournalEntryVoucher                  â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚ JE Number: JE-2024-02-0001           â”‚
â”‚ Entry Type: ACCRUAL                  â”‚
â”‚ Total DR: â‚¹5,000 = Total CR: â‚¹5,000 â”‚
â”‚                                      â”‚
â”‚ Line Items:                          â”‚
â”‚ 1. DR: Depreciation Exp. â‚¹5,000     â”‚
â”‚ 2. CR: Accumulated Depreciation     â”‚
â”‚        â‚¹5,000                        â”‚
â”‚                                      â”‚
â”‚ Status: POSTED                       â”‚
â”‚ GL Impact:                           â”‚
â”‚ â”œâ”€ Depreciation Expense â†‘ â‚¹5,000    â”‚
â”‚ â””â”€ Acc. Depreciation â†‘ â‚¹5,000       â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Stock Movement Voucher Design

### Overview

**Purpose**: Track inventory movements between locations, bins, or departments.

**Key Characteristics:**
- Links inventory to locations/bins
- Tracks movement reasons (transfer, damage, usage)
- Updates stock balances in real-time
- Optional GL posting for cost adjustments
- Supports batch/serial tracking

### Model Design

**File**: `apps/tenant_apps/dea/models/stock.py`

```python
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money
from decimal import Decimal

from .doc import BusinessDoc


class StockMovementReason(models.TextChoices):
    """Reasons for stock movement"""
    TRANSFER = "TRANSFER", "Transfer Between Locations"
    DAMAGED = "DAMAGED", "Damaged/Defective"
    LOSS = "LOSS", "Loss/Discrepancy"
    ISSUANCE = "ISSUANCE", "Issued to Production/Sales"
    RECEIPT = "RECEIPT", "Received into Store"
    ADJUSTMENT = "ADJUSTMENT", "Stock Adjustment"
    SAMPLE = "SAMPLE", "Sample/Testing"
    RETURN = "RETURN", "Return from Usage"
    SCRAP = "SCRAP", "Scrapped/Waste"
    OTHER = "OTHER", "Other"


class StockMovementVoucher(BusinessDoc):
    """
    Stock Movement Voucher - Track inventory movements.
    
    CHARACTERISTICS:
    - Records movement of goods between locations/bins
    - Updates quantity in locations
    - Posts GL entries if there's value change
    - Tracks reason for movement
    - Supports batch/serial tracking
    
    Examples:
    - Transfer of raw material between warehouses
    - Receipt of goods from purchase
    - Issuance to production
    - Stock adjustment (loss/damage)
    - Return from usage
    """
    
    # === Core Identity ===
    movement_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique movement reference (auto-generated)"
    )
    
    movement_date = models.DateField(
        default=timezone.now,
        db_index=True,
        help_text="Date of movement"
    )
    
    # === Movement Classification ===
    reason = models.CharField(
        max_length=50,
        choices=StockMovementReason.choices,
        default=StockMovementReason.TRANSFER,
        help_text="Reason for movement"
    )
    
    # === Locations ===
    from_location = models.ForeignKey(
        'Location',  # Your location model
        on_delete=models.PROTECT,
        related_name='movements_out',
        null=True,
        blank=True,
        help_text="Source location"
    )
    
    to_location = models.ForeignKey(
        'Location',
        on_delete=models.PROTECT,
        related_name='movements_in',
        null=True,
        blank=True,
        help_text="Destination location"
    )
    
    # === Reference ===
    reference_doc = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference to source (PO, WO, etc.)"
    )
    
    # === Description ===
    description = models.TextField(
        help_text="Details of movement"
    )
    
    memo = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short memo"
    )
    
    # === Totals ===
    total_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=0,
        help_text="Total quantity moved"
    )
    
    total_value = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Total value at movement"
    )
    
    class Meta:
        ordering = ['-movement_date', '-created_at']
        verbose_name = "Stock Movement Voucher"
        verbose_name_plural = "Stock Movement Vouchers"
        indexes = [
            models.Index(fields=['movement_date', 'reason']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.movement_number} - {self.get_reason_display()} - {self.total_quantity} units"
    
    def clean(self):
        """Validate movement"""
        super().clean()
        
        if self.total_quantity <= 0:
            raise ValidationError("Quantity must be positive")
        
        # For transfers, require both locations
        if self.reason == StockMovementReason.TRANSFER:
            if not self.from_location or not self.to_location:
                raise ValidationError("Transfer requires both source and destination locations")
            
            if self.from_location == self.to_location:
                raise ValidationError("Source and destination must be different for transfers")
    
    def save(self, *args, **kwargs):
        """Auto-generate movement number if not set"""
        if not self.movement_number:
            self.movement_number = self._generate_movement_number()
        
        super().save(*args, **kwargs)
    
    def _generate_movement_number(self) -> str:
        """Generate unique movement number"""
        from django.utils import timezone
        today = timezone.now()
        prefix = f"SM-{today.year}-{today.month:02d}"
        
        last_movement = StockMovementVoucher.objects.filter(
            movement_number__startswith=prefix
        ).order_by('-movement_number').first()
        
        if last_movement:
            try:
                last_seq = int(last_movement.movement_number.split('-')[-1])
                next_seq = last_seq + 1
            except (ValueError, IndexError):
                next_seq = 1
        else:
            next_seq = 1
        
        return f"{prefix}-{next_seq:04d}"
    
    def get_voucher_type(self) -> str:
        """Return voucher type"""
        return f"STOCK_MOVEMENT_{self.reason}"


class StockMovementLineItem(models.Model):
    """Individual product movements"""
    
    movement = models.ForeignKey(
        StockMovementVoucher,
        on_delete=models.CASCADE,
        related_name='line_items',
        help_text="Parent movement"
    )
    
    line_number = models.PositiveIntegerField(
        default=1,
        help_text="Line sequence"
    )
    
    # === Product ===
    product = models.ForeignKey(
        'product.Product',
        on_delete=models.PROTECT,
        help_text="Product moved"
    )
    
    # === Quantity ===
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        help_text="Quantity moved"
    )
    
    unit = models.CharField(
        max_length=20,
        help_text="Unit of measurement"
    )
    
    # === Valuation ===
    unit_cost = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Unit cost for valuation"
    )
    
    line_value = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Total value of this line"
    )
    
    # === Batch/Serial ===
    batch_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Batch/Lot number (if applicable)"
    )
    
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Serial number (if applicable)"
    )
    
    class Meta:
        ordering = ['movement', 'line_number']
        verbose_name = "Stock Movement Line Item"
        verbose_name_plural = "Stock Movement Line Items"
        unique_together = [['movement', 'line_number']]
    
    def save(self, *args, **kwargs):
        """Auto-calculate line value"""
        self.line_value = Money(
            self.quantity * self.unit_cost.amount,
            self.unit_cost.currency
        )
        super().save(*args, **kwargs)
```

### Posting Rule for Stock Movement

**File**: `apps/tenant_apps/dea/posting/rules/stock_movement.py`

```python
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("STOCK_MOVEMENT_DAMAGED")
class DamagedStockRule(BasePostingRule):
    """
    Posts loss on damaged goods.
    
    DR: Loss/Damage Expense
    CR: Inventory
    """
    
    def should_run(self, doc) -> bool:
        from apps.tenant_apps.dea.models import StockMovementVoucher, StockMovementReason
        return (
            isinstance(doc, StockMovementVoucher) and 
            doc.reason == StockMovementReason.DAMAGED
        )
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        inventory_ledger = get_ledger_id_by_key("INVENTORY")
        loss_ledger = get_ledger_id_by_key("LOSS_DAMAGE_EXPENSE")
        
        lines = [
            DualLedgerLine(
                ledger_dr=loss_ledger,
                ledger_cr=None,
                amount=doc.total_value.amount,
                memo=f"Loss on damaged goods: {doc.description}"
            ),
            DualLedgerLine(
                ledger_dr=None,
                ledger_cr=inventory_ledger,
                amount=doc.total_value.amount,
                memo=f"Removal from inventory: {doc.total_quantity} units"
            ),
        ]
        
        return PostingBundle(
            voucher_type="STOCK_MOVEMENT_DAMAGED",
            voucher_number=doc.movement_number,
            voucher_date=doc.movement_date,
            description=f"Stock damage: {doc.description}",
            lines=lines,
            account_lines=[],
        )


@register_rule("STOCK_MOVEMENT_LOSS")
class StockLossRule(BasePostingRule):
    """
    Posts loss on stock discrepancy.
    
    DR: Loss/Shortage Expense
    CR: Inventory
    """
    
    def should_run(self, doc) -> bool:
        from apps.tenant_apps.dea.models import StockMovementVoucher, StockMovementReason
        return (
            isinstance(doc, StockMovementVoucher) and 
            doc.reason == StockMovementReason.LOSS
        )
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        inventory_ledger = get_ledger_id_by_key("INVENTORY")
        loss_ledger = get_ledger_id_by_key("LOSS_SHORTAGE_EXPENSE")
        
        lines = [
            DualLedgerLine(
                ledger_dr=loss_ledger,
                ledger_cr=None,
                amount=doc.total_value.amount,
                memo=f"Loss/shortage: {doc.description}"
            ),
            DualLedgerLine(
                ledger_dr=None,
                ledger_cr=inventory_ledger,
                amount=doc.total_value.amount,
                memo=f"Inventory adjustment: {doc.total_quantity} units"
            ),
        ]
        
        return PostingBundle(
            voucher_type="STOCK_MOVEMENT_LOSS",
            voucher_number=doc.movement_number,
            voucher_date=doc.movement_date,
            description=f"Stock loss/shortage: {doc.description}",
            lines=lines,
            account_lines=[],
        )


@register_rule("STOCK_MOVEMENT_TRANSFER")
class StockTransferRule(BasePostingRule):
    """
    Stock transfers don't post to GL.
    They just update location balances.
    """
    
    def should_run(self, doc) -> bool:
        # Transfers don't need GL posting
        return False
```

### Stock Movement Workflow

```
STOCK MOVEMENT WORKFLOW:
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. Goods received into warehouse
   â”œâ”€ Vendor sends goods
   â””â”€ Triggers: Create StockMovementVoucher
      â”œâ”€ reason: RECEIPT
      â”œâ”€ to_location: Warehouse A
      â”œâ”€ reference: PO-xxxxx
      â””â”€ line_items: Product A x 100 @ â‚¹100

2. Record movement
   â”œâ”€ StockMovementVoucher created
   â”œâ”€ Status: DRAFT
   â””â”€ Validate:
      â”œâ”€ Product exists âœ“
      â”œâ”€ Location exists âœ“
      â””â”€ Quantity > 0 âœ“

3. Approve movement
   â”œâ”€ Status: APPROVED
   â””â”€ System updates:
      â”œâ”€ Inventory balance â†‘ in Warehouse A
      â””â”€ (No GL posting for receipts)

4. Transfer goods between locations
   â”œâ”€ StockMovementVoucher created
   â”œâ”€ reason: TRANSFER
   â”œâ”€ from_location: Warehouse A
   â”œâ”€ to_location: Production Floor
   â””â”€ line_items: Product A x 50

5. Approve transfer
   â”œâ”€ Status: APPROVED
   â””â”€ System updates:
      â”œâ”€ Warehouse A balance â†“ 50 units
      â”œâ”€ Production Floor balance â†‘ 50 units
      â””â”€ (No GL posting for transfers)

6. Stock damage/loss
   â”œâ”€ StockMovementVoucher created
   â”œâ”€ reason: DAMAGED (or LOSS)
   â”œâ”€ from_location: Warehouse A
   â””â”€ line_items: Product B x 10 @ loss value

7. Approve damage
   â”œâ”€ Status: APPROVED
   â””â”€ Auto-post to GL:
      â”œâ”€ JournalEntry created
      â”œâ”€ DR: Loss/Damage Expense
      â””â”€ CR: Inventory
```

---

## Depreciation Voucher Design

### Overview

**Purpose**: Record periodic depreciation of fixed assets.

**Key Characteristics:**
- Typically created monthly or annually (scheduled)
- Calculates depreciation per asset
- Updates accumulated depreciation and P&L
- Supports multiple depreciation methods
- Handles asset retirement

### Model Design

**File**: `apps/tenant_apps/dea/models/depreciation.py`

```python
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money
from decimal import Decimal

from .doc import BusinessDoc


class DepreciationMethod(models.TextChoices):
    """Depreciation calculation methods"""
    STRAIGHT_LINE = "STRAIGHT_LINE", "Straight Line"
    DECLINING_BALANCE = "DECLINING_BALANCE", "Declining Balance"
    SUM_OF_YEARS = "SUM_OF_YEARS", "Sum of Years Digits"
    UNITS_OF_PRODUCTION = "UNITS_PROD", "Units of Production"
    OTHER = "OTHER", "Other"


class DepreciationVoucher(BusinessDoc):
    """
    Depreciation Voucher - Record asset depreciation.
    
    CHARACTERISTICS:
    - Calculated depreciation for multiple assets
    - Posts to GL with journal entries
    - Updates accumulated depreciation
    - Can be scheduled for periods
    - Supports reversal of previous depreciation
    
    Calculation:
    Depreciation Expense = (Cost - Salvage Value) / Useful Life
    
    Posting:
    DR: Depreciation Expense (P&L)
    CR: Accumulated Depreciation (Balance Sheet)
    """
    
    # === Core Identity ===
    dep_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique depreciation reference (auto-generated)"
    )
    
    period_start = models.DateField(
        help_text="Start date of depreciation period"
    )
    
    period_end = models.DateField(
        help_text="End date of depreciation period"
    )
    
    # === Period ===
    year = models.IntegerField(
        db_index=True,
        help_text="Depreciation year"
    )
    
    month = models.IntegerField(
        db_index=True,
        help_text="Depreciation month (1-12)"
    )
    
    # === Description ===
    description = models.TextField(
        default="Monthly Depreciation",
        help_text="Description of depreciation calculation"
    )
    
    # === Totals ===
    total_depreciation = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Total depreciation amount"
    )
    
    # === Approval ===
    calculated_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calculated_depreciation',
        help_text="User who calculated depreciation"
    )
    
    calculated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When depreciation was calculated"
    )
    
    class Meta:
        ordering = ['-period_end', '-created_at']
        verbose_name = "Depreciation Voucher"
        verbose_name_plural = "Depreciation Vouchers"
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['period_end']),
        ]
        unique_together = [['year', 'month']]  # One depreciation per period
    
    def __str__(self):
        return f"{self.dep_number} - {self.period_start.strftime('%b %Y')} - {self.total_depreciation}"
    
    def clean(self):
        """Validate depreciation voucher"""
        super().clean()
        
        if self.total_depreciation.amount < 0:
            raise ValidationError("Depreciation amount cannot be negative")
        
        if self.period_start >= self.period_end:
            raise ValidationError("Period start must be before period end")
    
    def save(self, *args, **kwargs):
        """Auto-generate depreciation number if not set"""
        if not self.dep_number:
            self.dep_number = self._generate_dep_number()
        
        # Auto-calculate year and month from period_end
        if self.period_end:
            self.year = self.period_end.year
            self.month = self.period_end.month
        
        super().save(*args, **kwargs)
    
    def _generate_dep_number(self) -> str:
        """Generate unique depreciation number"""
        prefix = f"DEP-{self.year}-{self.month:02d}"
        
        return f"{prefix}-{1:04d}"
    
    def get_voucher_type(self) -> str:
        """Return voucher type"""
        return "DEPRECIATION"


class DepreciationLineItem(models.Model):
    """Individual asset depreciation"""
    
    depreciation = models.ForeignKey(
        DepreciationVoucher,
        on_delete=models.CASCADE,
        related_name='line_items',
        help_text="Parent depreciation"
    )
    
    line_number = models.PositiveIntegerField(
        default=1,
        help_text="Line sequence"
    )
    
    # === Asset ===
    asset = models.ForeignKey(
        'fixed_assets.FixedAsset',  # Your fixed asset model
        on_delete=models.PROTECT,
        help_text="Asset being depreciated"
    )
    
    # === Depreciation Details ===
    method = models.CharField(
        max_length=50,
        choices=DepreciationMethod.choices,
        help_text="Depreciation method used"
    )
    
    original_cost = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Original asset cost"
    )
    
    useful_life = models.IntegerField(
        help_text="Useful life in years"
    )
    
    salvage_value = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=0,
        help_text="Salvage value at end of life"
    )
    
    # === Calculated Depreciation ===
    monthly_depreciation = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Calculated monthly depreciation"
    )
    
    accumulated_before = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Accumulated depreciation before this period"
    )
    
    accumulated_after = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Accumulated depreciation after this period"
    )
    
    remaining_value = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Book value after depreciation"
    )
    
    class Meta:
        ordering = ['depreciation', 'line_number']
        verbose_name = "Depreciation Line Item"
        verbose_name_plural = "Depreciation Line Items"
        unique_together = [['depreciation', 'line_number']]
    
    def __str__(self):
        return f"{self.depreciation.dep_number} - {self.asset.name}: {self.monthly_depreciation}"
    
    def calculate_monthly_depreciation(self) -> Money:
        """Calculate monthly depreciation using the specified method"""
        remaining_cost = self.original_cost.amount - self.salvage_value.amount
        
        if self.method == DepreciationMethod.STRAIGHT_LINE:
            # Cost / Useful life / 12 months
            return Money(
                remaining_cost / (self.useful_life * 12),
                self.original_cost.currency
            )
        
        elif self.method == DepreciationMethod.DECLINING_BALANCE:
            # More complex: uses rate on declining balance
            # Simplified: 2x straight-line rate
            annual_rate = Decimal('2') / Decimal(str(self.useful_life))
            current_book_value = self.original_cost.amount - self.accumulated_before.amount
            return Money(
                current_book_value * annual_rate / 12,
                self.original_cost.currency
            )
        
        else:
            # Straight-line as default
            return Money(
                remaining_cost / (self.useful_life * 12),
                self.original_cost.currency
            )
    
    def save(self, *args, **kwargs):
        """Auto-calculate accumulated depreciation"""
        # Calculate monthly depreciation if not set
        if not self.monthly_depreciation or self.monthly_depreciation.amount == 0:
            self.monthly_depreciation = self.calculate_monthly_depreciation()
        
        # Calculate accumulated after
        if self.accumulated_before:
            self.accumulated_after = Money(
                self.accumulated_before.amount + self.monthly_depreciation.amount,
                self.original_cost.currency
            )
        else:
            self.accumulated_after = Money(
                self.monthly_depreciation.amount,
                self.original_cost.currency
            )
        
        # Calculate remaining value
        self.remaining_value = Money(
            self.original_cost.amount - self.accumulated_after.amount,
            self.original_cost.currency
        )
        
        super().save(*args, **kwargs)
```

### Posting Rule for Depreciation

**File**: `apps/tenant_apps/dea/posting/rules/depreciation.py`

```python
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("DEPRECIATION")
class DepreciationRule(BasePostingRule):
    """
    Posting rule for depreciation.
    
    ACCOUNTING ENTRIES:
    For each asset:
    DR: Depreciation Expense (P&L)
    CR: Accumulated Depreciation (Balance Sheet)
    
    Example:
    Asset: Equipment @ â‚¹100,000, 5-year life
    Monthly depreciation: â‚¹1,667
    
    DR: Depreciation Expense â‚¹1,667
    CR: Accumulated Depreciation â‚¹1,667
    """
    
    def should_run(self, doc) -> bool:
        """Only run for depreciation vouchers"""
        from apps.tenant_apps.dea.models import DepreciationVoucher
        return isinstance(doc, DepreciationVoucher)
    
    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for depreciation"""
        from apps.tenant_apps.dea.models import DepreciationVoucher
        
        if not isinstance(doc, DepreciationVoucher):
            raise ValidationError("Document must be DepreciationVoucher")
        
        dep_expense_ledger = get_ledger_id_by_key("DEPRECIATION_EXPENSE")
        
        lines = []
        
        # For each asset, create two lines (DR Expense, CR Accumulated)
        for dep_line in doc.line_items.all():
            # DR: Depreciation Expense
            lines.append(DualLedgerLine(
                ledger_dr=dep_expense_ledger,
                ledger_cr=None,
                amount=dep_line.monthly_depreciation.amount,
                memo=f"{dep_line.asset.name}: Monthly depreciation"
            ))
            
            # CR: Accumulated Depreciation (get from asset)
            # Note: This would need to reference asset's accumulated depr account
            accumulated_ledger = self._get_accumulated_depr_ledger(dep_line.asset)
            lines.append(DualLedgerLine(
                ledger_dr=None,
                ledger_cr=accumulated_ledger,
                amount=dep_line.monthly_depreciation.amount,
                memo=f"Accumulated depreciation for {dep_line.asset.name}"
            ))
        
        return PostingBundle(
            voucher_type="DEPRECIATION",
            voucher_number=doc.dep_number,
            voucher_date=doc.period_end,
            description=f"Depreciation for {doc.period_start.strftime('%b %Y')}",
            lines=lines,
            account_lines=[],
        )
    
    def _get_accumulated_depr_ledger(self, asset) -> int:
        """Get accumulated depreciation ledger for asset"""
        # This would need to be configured per asset or asset category
        return get_ledger_id_by_key("ACCUMULATED_DEPRECIATION")
```

### Depreciation Workflow

```
DEPRECIATION WORKFLOW:
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

1. Month-end approaching
   â”œâ”€ Accountant prepares depreciation
   â””â”€ Trigger: Create DepreciationVoucher
      â”œâ”€ period_start: Feb 1, 2024
      â”œâ”€ period_end: Feb 29, 2024
      â””â”€ description: "February 2024 Depreciation"

2. Calculate asset depreciation
   â”œâ”€ For each fixed asset:
   â”‚  â”œâ”€ Get: Original Cost, Useful Life, Salvage Value
   â”‚  â”œâ”€ Calculate: Monthly Depreciation
   â”‚  â”œâ”€ Get: Accumulated Before
   â”‚  â””â”€ Create DepreciationLineItem
   â”‚
   â””â”€ Add all lines to voucher

Example: Equipment
â”œâ”€ Original Cost: â‚¹100,000
â”œâ”€ Useful Life: 5 years (60 months)
â”œâ”€ Salvage: â‚¹10,000
â”œâ”€ Depreciable Amount: â‚¹90,000
â”œâ”€ Monthly: â‚¹1,500
â”œâ”€ Accumulated Before: â‚¹7,500 (5 months)
â”œâ”€ This Month: â‚¹1,500
â”œâ”€ Accumulated After: â‚¹9,000
â””â”€ Remaining Value: â‚¹91,000

3. Voucher created
   â”œâ”€ Total Depreciation: â‚¹1,500 Ã— N assets
   â”œâ”€ Status: DRAFT
   â””â”€ Lines: One per asset

4. Review and approve
   â”œâ”€ Accountant reviews calculations
   â”œâ”€ Status: APPROVED
   â””â”€ Triggers: Post to GL

5. Auto-post to GL
   â”œâ”€ JournalEntry created
   â”œâ”€ Posted by: Posting Engine
   â”œâ”€ Posted at: Feb 29, 2024
   â”‚
   â””â”€ For each asset:
      â”œâ”€ DR: Depreciation Expense â‚¹1,500
      â””â”€ CR: Accumulated Depreciation â‚¹1,500

6. GL Updated
   â”œâ”€ Depreciation Expense â†‘ â‚¹1,500 (P&L)
   â”œâ”€ Equipment value on BS:
   â”‚  â”œâ”€ Original: â‚¹100,000
   â”‚  â”œâ”€ Less: Accumulated Dep â‚¹9,000
   â”‚  â””â”€ Net Book: â‚¹91,000
   â””â”€ Monthly workflow complete
```

---

## Integration & Workflows

### Complete Flow: Expense â†’ Payment

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ EMPLOYEE EXPENSE CLAIM â†’ PAYMENT COMPLETE FLOW           â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                           â”‚
â”‚ DAY 1: Employee submits claim                            â”‚
â”‚ â”œâ”€ ExpenseClaim created (source document)               â”‚
â”‚ â”œâ”€ Line items: Travel, Food, Professional               â”‚
â”‚ â”œâ”€ Total: â‚¹15,500                                        â”‚
â”‚ â””â”€ Status: SUBMITTED                                     â”‚
â”‚                                                           â”‚
â”‚ DAY 2: Manager approves                                  â”‚
â”‚ â”œâ”€ ExpenseClaim.status = APPROVED                        â”‚
â”‚ â””â”€ Signal triggers: Create ExpenseVoucher               â”‚
â”‚    â”œâ”€ source_document = ExpenseClaim                     â”‚
â”‚    â”œâ”€ source_type = EMP_CLAIM                           â”‚
â”‚    â”œâ”€ party = Employee                                   â”‚
â”‚    â”œâ”€ gross_amount = â‚¹15,500                            â”‚
â”‚    â”œâ”€ tax_amount = â‚¹900 (GST on professional)          â”‚
â”‚    â”œâ”€ tds_amount = â‚¹500 (TDS on professional)          â”‚
â”‚    â”œâ”€ net_payable = â‚¹15,900                            â”‚
â”‚    â””â”€ Status: DRAFT                                      â”‚
â”‚                                                           â”‚
â”‚ DAY 2: ExpenseVoucher auto-posts                         â”‚
â”‚ â”œâ”€ Status: DRAFT â†’ POSTED                               â”‚
â”‚ â”œâ”€ Posting engine creates JournalEntry #1:              â”‚
â”‚ â”‚  â”œâ”€ DR: Travel Expense â‚¹2,500                         â”‚
â”‚ â”‚  â”œâ”€ DR: Food Expense â‚¹1,200                           â”‚
â”‚ â”‚  â”œâ”€ DR: Professional Services â‚¹5,000                  â”‚
â”‚ â”‚  â”œâ”€ DR: GST Input Credit â‚¹900                         â”‚
â”‚ â”‚  â”œâ”€ DR: Office Supplies â‚¹3,800                        â”‚
â”‚ â”‚  â”œâ”€ DR: Employee Reimb. â‚¹3,000                        â”‚
â”‚ â”‚  â”œâ”€ CR: TDS Payable â‚¹500                              â”‚
â”‚ â”‚  â””â”€ CR: Employee Payable â‚¹15,900                      â”‚
â”‚ â”‚                                                         â”‚
â”‚ â””â”€ GL balances updated:                                  â”‚
â”‚    â”œâ”€ Expense accounts â†‘                                 â”‚
â”‚    â””â”€ Employee Payable â†‘ (liability created)             â”‚
â”‚                                                           â”‚
â”‚ DAY 3: Accountant creates payment                        â”‚
â”‚ â”œâ”€ PaymentVoucher created                                â”‚
â”‚ â”‚  â”œâ”€ source_document = ExpenseVoucher                   â”‚
â”‚ â”‚  â”œâ”€ direction = PAYMENT (cash OUT)                     â”‚
â”‚ â”‚  â”œâ”€ payment_type = REIMBURSEMENT                       â”‚
â”‚ â”‚  â”œâ”€ total_amount = â‚¹15,400 (net of TDS)              â”‚
â”‚ â”‚  â””â”€ payment_method = BANK                              â”‚
â”‚ â”‚                                                         â”‚
â”‚ â”œâ”€ PaymentVoucher auto-posts                             â”‚
â”‚ â”œâ”€ Creates JournalEntry #2:                              â”‚
â”‚ â”‚  â”œâ”€ DR: Employee Payable â‚¹15,900                      â”‚
â”‚ â”‚  â”œâ”€ CR: TDS Payable â‚¹500 (reversed from accrual)     â”‚
â”‚ â”‚  â””â”€ CR: Cash/Bank â‚¹15,400                             â”‚
â”‚ â”‚                                                         â”‚
â”‚ â””â”€ GL balances updated:                                  â”‚
â”‚    â”œâ”€ Employee Payable â†“ (liability cleared)             â”‚
â”‚    â””â”€ Cash â†“ (money went out)                            â”‚
â”‚                                                           â”‚
â”‚ DAY 3: ExpenseVoucher updated                            â”‚
â”‚ â”œâ”€ paid_amount = â‚¹15,400                                â”‚
â”‚ â”œâ”€ is_paid = True                                        â”‚
â”‚ â””â”€ Workflow complete âœ…                                  â”‚
â”‚                                                           â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Complete Flow: Sales â†’ Collection

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ SALES INVOICE â†’ PAYMENT COLLECTION COMPLETE FLOW         â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                           â”‚
â”‚ DAY 1: Customer places order                             â”‚
â”‚ â”œâ”€ SalesOrder created                                    â”‚
â”‚ â”œâ”€ Customer: XYZ Corp                                    â”‚
â”‚ â”œâ”€ Items: Product A x 10                                 â”‚
â”‚ â””â”€ Status: CONFIRMED                                     â”‚
â”‚                                                           â”‚
â”‚ DAY 2: Goods delivered                                   â”‚
â”‚ â”œâ”€ Delivery Note created                                 â”‚
â”‚ â”œâ”€ Goods dispatched                                      â”‚
â”‚ â””â”€ Triggers: Create SalesInvoiceVoucher                  â”‚
â”‚    â”œâ”€ reference: SalesOrder                              â”‚
â”‚    â”œâ”€ customer: XYZ Corp                                 â”‚
â”‚    â”œâ”€ subtotal: â‚¹100,000                                â”‚
â”‚    â”œâ”€ cgst: â‚¹9,000                                       â”‚
â”‚    â”œâ”€ sgst: â‚¹9,000                                       â”‚
â”‚    â”œâ”€ total: â‚¹118,000                                   â”‚
â”‚    â””â”€ Status: DRAFT                                      â”‚
â”‚                                                           â”‚
â”‚ DAY 2: SalesInvoiceVoucher approved & posted             â”‚
â”‚ â”œâ”€ Status: DRAFT â†’ POSTED                               â”‚
â”‚ â”œâ”€ Creates JournalEntry #1:                              â”‚
â”‚ â”‚  â”œâ”€ DR: Accounts Receivable â‚¹118,000                  â”‚
â”‚ â”‚  â”œâ”€ CR: Sales Revenue â‚¹100,000                        â”‚
â”‚ â”‚  â”œâ”€ CR: CGST Output â‚¹9,000                            â”‚
â”‚ â”‚  â””â”€ CR: SGST Output â‚¹9,000                            â”‚
â”‚ â”‚                                                         â”‚
â”‚ â””â”€ GL balances updated:                                  â”‚
â”‚    â”œâ”€ AR (asset) â†‘ â‚¹118,000                             â”‚
â”‚    â”œâ”€ Sales Revenue â†‘ â‚¹100,000                          â”‚
â”‚    â””â”€ GST Output (liability) â†‘ â‚¹18,000                  â”‚
â”‚                                                           â”‚
â”‚ DAY 15: Customer pays                                    â”‚
â”‚ â”œâ”€ PaymentVoucher created                                â”‚
â”‚ â”‚  â”œâ”€ source_document = SalesInvoiceVoucher              â”‚
â”‚ â”‚  â”œâ”€ direction = RECEIPT (cash IN)                      â”‚
â”‚ â”‚  â”œâ”€ payment_type = RECEIPT                             â”‚
â”‚ â”‚  â”œâ”€ total_amount = â‚¹118,000                           â”‚
â”‚ â”‚  â””â”€ payment_method = BANK                              â”‚
â”‚ â”‚                                                         â”‚
â”‚ â”œâ”€ PaymentVoucher auto-posts                             â”‚
â”‚ â”œâ”€ Creates JournalEntry #2:                              â”‚
â”‚ â”‚  â”œâ”€ DR: Cash/Bank â‚¹118,000                            â”‚
â”‚ â”‚  â””â”€ CR: Accounts Receivable â‚¹118,000                  â”‚
â”‚ â”‚                                                         â”‚
â”‚ â””â”€ GL balances updated:                                  â”‚
â”‚    â”œâ”€ Cash â†‘ â‚¹118,000 (money received)                  â”‚
â”‚    â””â”€ AR â†“ â‚¹118,000 (receivable cleared)                â”‚
â”‚                                                           â”‚
â”‚ DAY 15: SalesInvoiceVoucher updated                      â”‚
â”‚ â”œâ”€ received_amount = â‚¹118,000                           â”‚
â”‚ â”œâ”€ is_fully_paid = True                                 â”‚
â”‚ â””â”€ Workflow complete âœ…                                  â”‚
â”‚                                                           â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Complete Flow: Purchase â†’ Payment

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ PURCHASE INVOICE â†’ VENDOR PAYMENT COMPLETE FLOW          â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                                                           â”‚
â”‚ DAY 1: Purchase order placed                             â”‚
â”‚ â”œâ”€ PurchaseOrder created                                 â”‚
â”‚ â”œâ”€ Vendor: ABC Supplies                                  â”‚
â”‚ â”œâ”€ Items: Raw material x 100                             â”‚
â”‚ â””â”€ Status: APPROVED                                      â”‚
â”‚                                                           â”‚
â”‚ DAY 5: Goods received                                    â”‚
â”‚ â”œâ”€ GoodsReceiptNote created                              â”‚
â”‚ â”œâ”€ Quantity verified: 100 units âœ“                        â”‚
â”‚ â”œâ”€ Quality checked âœ“                                     â”‚
â”‚ â””â”€ Status: RECEIVED                                      â”‚
â”‚                                                           â”‚
â”‚ DAY 6: Vendor invoice received                           â”‚
â”‚ â”œâ”€ PurchaseInvoiceVoucher created                        â”‚
â”‚ â”‚  â”œâ”€ invoice_number: VENDOR-INV-001                     â”‚
â”‚ â”‚  â”œâ”€ internal_number: PI-2024-02-0001                   â”‚
â”‚ â”‚  â”œâ”€ vendor: ABC Supplies                               â”‚
â”‚ â”‚  â”œâ”€ subtotal: â‚¹100,000                                â”‚
â”‚ â”‚  â”œâ”€ gst: â‚¹18,000                                       â”‚
â”‚ â”‚  â”œâ”€ total: â‚¹118,000                                   â”‚
â”‚ â”‚  â”œâ”€ grn: linked                                        â”‚
â”‚ â”‚  â””â”€ Status: DRAFT                                      â”‚
â”‚ â”‚                                                         â”‚
â”‚ â””â”€ 3-way match performed:                                â”‚
â”‚    â”œâ”€ PO quantity = GRN quantity = Invoice quantity âœ“    â”‚
â”‚    â””â”€ PO price = Invoice price âœ“                         â”‚
â”‚                                                           â”‚
â”‚ DAY 6: PurchaseInvoiceVoucher approved & posted          â”‚
â”‚ â”œâ”€ Status: DRAFT â†’ POSTED                               â”‚
â”‚ â”œâ”€ Creates JournalEntry #1:                              â”‚
â”‚ â”‚  â”œâ”€ DR: Inventory â‚¹100,000                            â”‚
â”‚ â”‚  â”œâ”€ DR: GST Input Credit â‚¹18,000                      â”‚
â”‚ â”‚  â””â”€ CR: Accounts Payable â‚¹118,000                     â”‚
â”‚ â”‚                                                         â”‚
â”‚ â””â”€ GL balances updated:                                  â”‚
â”‚    â”œâ”€ Inventory (asset) â†‘ â‚¹100,000                      â”‚
â”‚    â”œâ”€ GST Input (asset) â†‘ â‚¹18,000                       â”‚
â”‚    â””â”€ AP (liability) â†‘ â‚¹118,000                         â”‚
â”‚                                                           â”‚
â”‚ DAY 20: Pay vendor (as per credit terms)                 â”‚
â”‚ â”œâ”€ PaymentVoucher created                                â”‚
â”‚ â”‚  â”œâ”€ source_document = PurchaseInvoiceVoucher           â”‚
â”‚ â”‚  â”œâ”€ direction = PAYMENT (cash OUT)                     â”‚
â”‚ â”‚  â”œâ”€ payment_type = VENDOR_PAYMENT                      â”‚
â”‚ â”‚  â”œâ”€ total_amount = â‚¹118,000                           â”‚
â”‚ â”‚  â””â”€ payment_method = BANK                              â”‚
â”‚ â”‚                                                         â”‚
â”‚ â”œâ”€ PaymentVoucher auto-posts                             â”‚
â”‚ â”œâ”€ Creates JournalEntry #2:                              â”‚
â”‚ â”‚  â”œâ”€ DR: Accounts Payable â‚¹118,000                     â”‚
â”‚ â”‚  â””â”€ CR: Cash/Bank â‚¹118,000                            â”‚
â”‚ â”‚                                                         â”‚
â”‚ â””â”€ GL balances updated:                                  â”‚
â”‚    â”œâ”€ AP â†“ â‚¹118,000 (liability cleared)                 â”‚
â”‚    â””â”€ Cash â†“ â‚¹118,000 (money paid)                      â”‚
â”‚                                                           â”‚
â”‚ DAY 20: PurchaseInvoiceVoucher updated                   â”‚
â”‚ â”œâ”€ paid_amount = â‚¹118,000                               â”‚
â”‚ â”œâ”€ is_fully_paid = True                                 â”‚
â”‚ â””â”€ Workflow complete âœ…                                  â”‚
â”‚                                                           â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

---

## Implementation Roadmap

### Priority 1: Core Transactional Vouchers (Week 1-4)

#### Week 1-2: Payment, Expense, Journal Entry Models

**Models:**
- [x] PaymentVoucher model (existing)
- [x] Expense Voucher model
- [x] ExpenseLineItem model
- [ ] Journal Entry Voucher model
- [ ] JournalEntryLineItem model

**Posting Rules:**
- [ ] Payment posting rules (5 types) - existing
- [ ] Expense posting rules (3 types) - ready
- [ ] Journal Entry posting rules (all types)

**Migrations & Testing:**
- [ ] Create model migrations
- [ ] Unit tests for models
- [ ] Unit tests for posting rules
- [ ] Database schema validation

#### Week 2-3: Posting Engine & Basic Workflows

**Posting Engine:**
- [ ] Register all Priority 1 rules
- [ ] Test posting for each rule
- [ ] Validate GL postings
- [ ] Error handling & rollback

**Signals & Auto-Creation:**
- [ ] Expense auto-creation from ExpenseClaim
- [ ] Payment auto-creation from Expense
- [ ] Journal Entry direct creation
- [ ] Status change triggers

**Testing:**
- [ ] Complete expense workflow test
- [ ] Complete journal entry workflow test
- [ ] GL reconciliation tests

#### Week 3-4: Views, Forms & UI (Priority 1)

**Views:**
- [ ] ExpenseVoucher CRUD views
- [ ] JournalEntryVoucher CRUD views
- [ ] PaymentVoucher matching views
- [ ] Approval workflow views
- [ ] List views with filters & pagination

**Forms:**
- [ ] ExpenseVoucher form with validation
- [ ] ExpenseLineItem formset
- [ ] JournalEntryVoucher form
- [ ] JournalEntryLineItem formset
- [ ] Custom field renderers (MoneyField, etc.)

**Templates:**
- [ ] Expense voucher list/detail/form
- [ ] Journal entry list/detail/form
- [ ] Approval UI with status workflow
- [ ] GL posting preview before approval

---

### Priority 2: Sales & Purchase Vouchers (Week 4-6)

#### Week 4: Sales Invoice Models & Rules

**Models:**
- [ ] Sales Invoice Voucher model
- [ ] SalesInvoiceLineItem model
- [ ] Auto-link to delivery notes/sales orders

**Posting Rules:**
- [ ] SalesInvoiceRule (AR + Revenue)
- [ ] Test with different scenarios

**Views & Forms:**
- [ ] SalesInvoiceVoucher CRUD views
- [ ] SalesInvoiceLineItem formset
- [ ] Customer selection & history
- [ ] Invoice duplicate checking

**Testing:**
- [ ] Create invoice from delivery
- [ ] Verify GL postings (AR + Tax)
- [ ] Test different GST scenarios

#### Week 5: Purchase Invoice Models & Rules

**Models:**
- [ ] Purchase Invoice Voucher model
- [ ] PurchaseInvoiceLineItem model
- [ ] Auto-link to GRN/purchase orders

**Posting Rules:**
- [ ] PurchaseInvoiceRule for goods (Inventory)
- [ ] PurchaseInvoiceRule for services (Expense)
- [ ] TDS calculation & posting
- [ ] Test three-way match logic

**Views & Forms:**
- [ ] PurchaseInvoiceVoucher CRUD views
- [ ] PurchaseInvoiceLineItem formset
- [ ] Vendor selection & payment terms
- [ ] GRN matching UI

**Testing:**
- [ ] Create invoice from GRN
- [ ] Verify GL postings (Inventory + Tax)
- [ ] Test TDS scenarios

#### Week 5-6: Payment Integration & Reports

**Payment Integration:**
- [ ] Link SalesInvoiceVoucher to PaymentVoucher
- [ ] Link PurchaseInvoiceVoucher to PaymentVoucher
- [ ] Track payment status
- [ ] Partial payment handling

**Reports:**
- [ ] Expense report by category
- [ ] Sales by customer/period
- [ ] Purchase by vendor/period
- [ ] Outstanding AR aging
- [ ] Outstanding AP aging

---

### Priority 3: Inventory & Fixed Assets (Week 6-8)

#### Week 6-7: Stock Movement Voucher

**Models:**
- [ ] Stock Movement Voucher model
- [ ] StockMovementLineItem model
- [ ] Location & inventory integration

**Posting Rules:**
- [ ] Transfer rule (no GL posting)
- [ ] Damage loss rule (Expense posting)
- [ ] Stock loss rule (Shortage posting)

**Views & Forms:**
- [ ] Stock Movement CRUD views
- [ ] Location selection
- [ ] Product/batch/serial tracking

**Testing:**
- [ ] Warehouse transfers
- [ ] Stock damage scenarios
- [ ] Inventory balance updates

#### Week 7-8: Depreciation Voucher

**Models:**
- [ ] Depreciation Voucher model
- [ ] DepreciationLineItem model
- [ ] FixedAsset integration

**Posting Rules:**
- [ ] DepreciationRule for all methods
- [ ] Accumulated depreciation tracking

**Views & Forms:**
- [ ] Depreciation CRUD views
- [ ] Period-end processing
- [ ] Asset depreciation schedule

**Testing:**
- [ ] Monthly depreciation calculation
- [ ] Accumulated depreciation tracking
- [ ] P&L impact verification

---

### Summary Timeline

```
WEEK 1-2:  âœ“ Payment + Expense + Journal Entry models & rules
WEEK 2-3:  âœ“ Posting engine & auto-creation signals
WEEK 3-4:  âœ“ Priority 1 views, forms, templates
WEEK 4:    âœ“ Sales Invoice Voucher complete
WEEK 5:    âœ“ Purchase Invoice Voucher complete
WEEK 5-6:  âœ“ Payment integration & reports
WEEK 6-7:  âœ“ Stock Movement Voucher complete
WEEK 7-8:  âœ“ Depreciation Voucher complete
WEEK 8:    âœ“ Testing, documentation, deployment
```

### Skill Dependencies

| Task | Skills Needed | Estimated Hours |
|------|---------------|-----------------|
| Models & Migrations | Django ORM, database design | 20 |
| Posting Rules | Accounting logic, custom rules | 25 |
| Views & Forms | Django views, form handling | 30 |
| Templates & UI | HTML/CSS, HTMX | 20 |
| Testing | Unit tests, integration tests | 25 |
| Integration | Signals, auto-creation | 15 |
| Reports | QuerySets, aggregations | 20 |
| **Total** | | **155 hours (~4 weeks at 40hrs/week)** |

### Success Criteria

- âœ… All 6 voucher types fully implemented
- âœ… Django models with complete field coverage
- âœ… All posting rules working correctly
- âœ… GL balances reconcile with source documents
- âœ… Complete workflows tested end-to-end
- âœ… No orphaned transactions
- âœ… User acceptance testing passed
- âœ… Production deployment successful

---

## Voucher Comparison Matrix

| Characteristic | Payment | Expense | Journal Entry | Sales Invoice | Purchase Invoice | Stock Movement | Depreciation |
|---|---|---|---|---|---|---|---|
| **Purpose** | Record cash inflows/outflows | Employee/vendor expenses | Manual GL adjustments | Customer invoices | Vendor invoices | Inventory transfers | Asset depreciation |
| **Source Document** | Accrual doc (Expense, Invoice, etc.) | ExpenseClaim | None (manual entry) | SalesOrder + Delivery | PurchaseOrder + GRN | None (manual) | FixedAsset schedule |
| **Data Entry** | References existing doc | Creates new expense | Completely manual (DR/CR lines) | Auto from delivery | Auto from GRN | Manual by warehouse | Auto calculated |
| **GL Impact** | Clears liabilities/receivables | Posts expenses & liabilities | Posts any GL accounts | Posts AR & revenue | Posts inventory & AP | No GL (transfers) or GL (damage) | Posts depreciation |
| **Posting Rules** | 5 rules (varies by type) | 3 rules (EMP/VENDOR/DIRECT) | 1 rule (all types) | 1 rule (AR + Revenue) | 2 rules (goods/services) | 2-3 rules (transfer/damage/loss) | 1 rule (depreciation) |
| **Multi-currency** | Yes | Yes | Yes | Yes | Yes | Optional | Optional |
| **Tax Handling** | GST reversal | GST input + TDS | Manual | CGST/SGST/IGST output | GST input + TDS | N/A | N/A |
| **Approval Workflow** | Auto on creation | Manager review | Accountant review | Auto | Auto | Manager review | Accountant review |
| **Line Items** | N/A (single amount) | Yes (multiple categories) | Yes (DR/CR entries) | Yes (multiple products) | Yes (multi-product) | Yes (per-product) | Yes (per-asset) |
| **Frequency** | Ongoing (as payments occur) | Ongoing (as claims submitted) | Periodic (month-end) | Ongoing (as orders delivered) | Ongoing (as GRNs received) | Ongoing (as needed) | Periodic (monthly) |
| **Posting Timing** | Immediate on approval | Immediate on approval | Immediate on approval | Immediate on approval | Immediate on approval | Immediate (damage) or no GL (transfer) | Immediate on approval |
| **Reversal Support** | Yes (reverse payment) | Yes (negative entries) | Yes (reverse entries) | Yes | Yes (debit note) | Yes | Yes (depreciation reversal) |
| **Implementation Priority** | Week 1-2 | Week 1-2 | Week 2-3 | Week 4 | Week 5 | Week 6-7 | Week 7-8 |
| **Complexity** | Medium | Medium-High | Low | Medium | High | Medium | Medium |
| **Critical for MVP** | âœ… Yes | âœ… Yes | âœ… Yes | âœ… Yes | âœ… Yes | â³ Phase 2 | â³ Phase 2 |

## GL Account Mapping by Voucher

```
EXPENSE VOUCHER:
â”œâ”€ Debit Accounts:
â”‚  â”œâ”€ Travel Expense
â”‚  â”œâ”€ Food Expense
â”‚  â”œâ”€ Professional Services
â”‚  â”œâ”€ Office Supplies
â”‚  â”œâ”€ GST Input Credit
â”‚  â””â”€ (Custom by category)
â”œâ”€ Credit Accounts:
â”‚  â”œâ”€ Employee Payable
â”‚  â”œâ”€ TDS Payable
â”‚  â””â”€ Vendor Payable

SALES INVOICE VOUCHER:
â”œâ”€ Debit Accounts:
â”‚  â””â”€ Accounts Receivable
â”œâ”€ Credit Accounts:
â”‚  â”œâ”€ Sales Revenue
â”‚  â”œâ”€ CGST Output
â”‚  â””â”€ SGST Output

PURCHASE INVOICE VOUCHER:
â”œâ”€ Debit Accounts:
â”‚  â”œâ”€ Inventory (for goods)
â”‚  â”œâ”€ Expense account (for services)
â”‚  â””â”€ GST Input Credit
â”œâ”€ Credit Accounts:
â”‚  â”œâ”€ Accounts Payable
â”‚  â””â”€ TDS Payable

JOURNAL ENTRY VOUCHER:
â”œâ”€ Debit Accounts: User selects (any GL account)
â”œâ”€ Credit Accounts: User selects (any GL account)

STOCK MOVEMENT VOUCHER:
â”œâ”€ Debit Accounts:
â”‚  â”œâ”€ Loss/Damage Expense (if damage/loss)
â”‚  â””â”€ N/A (if transfer)
â”œâ”€ Credit Accounts:
â”‚  â”œâ”€ Inventory (if damage/loss)
â”‚  â””â”€ N/A (if transfer)

DEPRECIATION VOUCHER:
â”œâ”€ Debit Accounts:
â”‚  â””â”€ Depreciation Expense
â”œâ”€ Credit Accounts:
â”‚  â””â”€ Accumulated Depreciation
```

---

## Summary

This complete design document now covers all 6 essential voucher types:

**âœ… PRIORITY 1 - Core Transactional (Week 1-4):**
- Payment Voucher - Handles cash inflows/outflows, clears accruals
- Expense Voucher - Employee & vendor expenses with tax handling
- Journal Entry Voucher - Manual GL adjustments and period-end entries

**âœ… PRIORITY 2 - Sales & Purchase (Week 4-6):**
- Sales Invoice Voucher - Customer invoices with AR & tax posting
- Purchase Invoice Voucher - Vendor invoices with GRN matching & TDS

**âœ… PRIORITY 3 - Inventory & Assets (Week 6-8):**
- Stock Movement Voucher - Inventory transfers & adjustments
- Depreciation Voucher - Fixed asset depreciation scheduling

**Included in This Document:**
- âœ… Complete Django models (all 7 voucher types)
- âœ… Posting rules for all scenarios (15+ rule implementations)
- âœ… Line item models with tax & cost handling
- âœ… Complete end-to-end workflows (3 detailed examples)
- âœ… GL account mapping and posting logic
- âœ… Validation rules and business constraints
- âœ… Auto-numbering and sequence generation
- âœ… Multi-currency and tax compliance support
- âœ… Detailed 8-week implementation roadmap
- âœ… Comparison matrix for all voucher types
- âœ… Success criteria and testing strategy

**Architecture Highlights:**
- **Payment-Centric Design**: Separates accrual (GL posting) from settlement (payment)
- **Posting Rule Registry**: Extensible pattern for business rule execution
- **Generic Relations**: Flexible source document linking
- **Multi-Currency Support**: django-money integration throughout
- **Tax Compliance**: CGST/SGST/IGST/TCS/TDS handling per region
- **Auto-Numbering**: Monthly sequence generation per voucher type
- **IFRS 9 Compliant**: Asset recognition at cash transfer point

**Next Steps:**
1. âœ… Review and approve design
2. â³ Create models and migrations (Week 1)
3. â³ Implement posting rules (Week 2-3)
4. â³ Build views and forms (Week 3-4)
5. â³ Create templates and workflows (Week 4-5)
6. â³ Test end-to-end scenarios (Week 6)
7. â³ Deploy to production (Week 7-8)

---

**Document Version**: 1.0  
**Last Updated**: February 26, 2024  
**Status**: âœ… Complete - All 6 Voucher Types Fully Designed  
**Ready for Development**: Yes

