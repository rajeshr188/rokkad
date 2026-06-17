---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Unified PaymentVoucher Design Document

**Date**: February 25, 2026  
**Status**: Design Phase  
**Goal**: Replace separate payment models with single unified PaymentVoucher supporting multi-currency

---

## Executive Summary

This document outlines the design for a unified `PaymentVoucher` model that:
- Tracks all cash receipts and payments in one place (PAYMENT-CENTRIC architecture)
- Posts to accounting **only when cash actually moves**, not when contracts are created
- Supports multiple currencies for international transactions with exchange rate tracking
- Works with any source document (GivenLoan, TakenLoan, Sales, Purchase, etc.)
- Routes to appropriate posting rules based on source type and direction
- Maintains backward compatibility during migration
- Achieves IFRS 9 compliance by recognizing financial assets at cash transfer time, not contract creation

---

## Core Architecture

### Conceptual Model: Business Events vs Economic Events

**KEY INSIGHT**: Separate contract/agreement events from cash movement events.

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ BUSINESS EVENTS (Contracts/Agreements)                           â”‚
â”‚ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚
â”‚                                                                   â”‚
â”‚  GivenLoan created â†’ Records agreement to lend                   â”‚
â”‚  Status: CREATED â†’ APPROVED â†’ DISBURSED (just milestones)       â”‚
â”‚  NO ACCOUNTING POSTING at creation!                              â”‚
â”‚                                                                   â”‚
â”‚  TakenLoan created â†’ Records agreement to borrow                 â”‚
â”‚  NO ACCOUNTING POSTING at creation!                              â”‚
â”‚                                                                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
                    [SCHEDULING POINT]
                 When does cash actually move?
                              â†“
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚ ECONOMIC EVENTS (Cash Movements)                                 â”‚
â”‚ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”‚
â”‚                                                                   â”‚
â”‚  PaymentVoucher created â†’ Records ACTUAL cash movement           â”‚
â”‚  payment_type: DISBURSAL | RECEIPT | OTHER                      â”‚
â”‚  direction: PAYMENT (cash out) | RECEIPT (cash in)              â”‚
â”‚  payment_date: When cash actually moves (not contract date)      â”‚
â”‚                                                                   â”‚
â”‚  AUTO POSTING ON SAVE â†’ Creates Voucher + JournalEntries       â”‚
â”‚  Each PaymentVoucher = ONE economic event = ONE accounting entry â”‚
â”‚                                                                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
                    Posting Rule Registry
                              â†“
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚ GIVENLOAN_DISBURSAL                       â”‚
        â”‚ GIVENLOAN_RECEIPT                        â”‚
        â”‚ TAKENLOAN_RECEIPT (we receive)           â”‚
        â”‚ TAKENLOAN_PAYMENT (we pay back)          â”‚
        â”‚ SALES_RECEIPT                            â”‚
        â”‚ PURCHASE_PAYMENT                         â”‚
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                              â†“
                    PostingBundle â†’ JournalEntry
```

### IFRS 9 Compliance

**Previous (Loan-Centric) Approach - NON-COMPLIANT:**
```
GivenLoan creation â†’ Immediate posting
                  â†’ Dr LOAN_RECEIVABLE â‚¹20,000
                  â†’ Cr CASH â‚¹20,000

Problem: IFRS 9 requires "Financial assets recognized when 
         CASH IS TRANSFERRED, not when contract is created"
         
Also: Overstates cash outflow (money hasn't actually left yet!)
```

**New (Payment-Centric) Approach - IFRS 9 COMPLIANT:**
```
GivenLoan creation â†’ No posting (just business record)

Day 1: PaymentVoucher (DISBURSAL) â†’ Posting at actual cash transfer
       Dr LOAN_RECEIVABLE â‚¹20,000
       Cr CASH â‚¹20,000  â† Cash actually decreases here

Day 15: PaymentVoucher (RECEIPT) â†’ Posting at actual cash receipt
        Dr CASH â‚¹10,000  â† Cash actually increases here
        Cr LOAN_RECEIVABLE â‚¹10,000
```

---

## Architectural Decision: Payment-Centric vs Loan-Centric

### Key Insight

**Business Events** (contracts) are NOT the same as **Economic Events** (cash movements).

| Aspect | Business Event (Loan Model) | Economic Event (Payment) |
|--------|---------------------------|------------------------|
| **When it happens** | When contract is created | When cash actually moves |
| **Example** | Loan agreement signed | Money handed to customer |
| **Accounting** | No posting | MUST post for accurate reporting |
| **IFRS 9** | Non-compliant | Compliant |
| **Exchange rates** | Fixed at creation | At payment date |
| **Partial payments** | Hard to handle | Natural/easy |
| **Reversals** | Complex | Clean |

### Why Payment-Centric is Better

**PREVIOUS (Loan-Centric - PROBLEMS)**
```
Loan creation â†’ Immediate accounting posting
              â†’ Overstates cash outflow  
              â†’ Posts before cash moves
              â†’ Exchange rate locks at creation
              â†’ Violates IFRS 9
              â†’ Hard to handle partial payments
```

**NEW (Payment-Centric - CORRECT)**
```
Loan creation â†’ Just business record (NO posting)
              
PaymentVoucher â†’ ONLY created when cash moves
              â†’ Accurate cash flow reporting
              â†’ Exchange rate at actual payment
              â†’ IFRS 9 compliant
              â†’ Natural handling of partial/multiple payments
```

### Benefits of This Architecture

1. **Semantic Correctness**: Clear separation of concerns
2. **Accounting Standards**: IFRS 9 compliance
3. **Flexibility**: Handles partial payments, rescheduling, delays
4. **Accuracy**: Exchange rates captured at cash transfer, not contract time
5. **Audit Trail**: Each payment has its own timestamp
6. **Data Integrity**: Errors caught before posting
7. **Extensibility**: Works for any source document type

---

## Model Design

### PaymentVoucher Model

**Location**: `apps/tenant_apps/dea/models/payment.py`

```python
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money

from .doc import BusinessDoc


class CashFlowDirection(models.TextChoices):
    """Direction of cash movement"""
    RECEIPT = "RECEIPT", "Receipt (Cash In)"
    PAYMENT = "PAYMENT", "Payment (Cash Out)"


class PaymentType(models.TextChoices):
    """Type of payment - distinguishes different payment scenarios"""
    DISBURSAL = "DISBURSAL", "Loan Disbursal/Advance"
    RECEIPT = "RECEIPT", "Payment Receipt/Repayment"
    REFUND = "REFUND", "Refund/Reversal"
    OTHER = "OTHER", "Other Payment"


class PaymentMethod(models.TextChoices):
    """Payment instrument type"""
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank Transfer"
    CHEQUE = "CHEQUE", "Cheque"
    UPI = "UPI", "UPI"
    CARD = "CARD", "Card"
    OTHER = "OTHER", "Other"


class PaymentVoucher(BusinessDoc):
    """
    Unified payment/receipt tracking for all source documents.
    
    PAYMENT-CENTRIC ARCHITECTURE:
    - Created only when CASH ACTUALLY MOVES (not at contract creation)
    - Separate from GivenLoan/TakenLoan which are just business agreements
    - Each PaymentVoucher = ONE economic event = ONE accounting entry
    - IFRS 9 compliant (recognizes assets at cash transfer, not contract time)
    
    Supports multi-currency transactions for international operations.
    Routes to appropriate posting rules based on source type + direction.
    
    Examples:
    - GivenLoan disbursal â†’ DISBURSAL + PAYMENT (money goes out)
    - GivenLoan repayment â†’ RECEIPT + RECEIPT (money comes in)
    - TakenLoan receipt â†’ DISBURSAL + RECEIPT (we receive money)
    - TakenLoan repayment â†’ RECEIPT + PAYMENT (we pay back)
    - Sales payment â†’ RECEIPT + RECEIPT (customer pays)
    - Purchase payment â†’ RECEIPT + PAYMENT (we pay supplier)
    """
    
    # === Core Identity ===
    payment_id = models.CharField(
        max_length=50, 
        unique=True, 
        db_index=True,
        help_text="Unique payment reference (auto-generated)"
    )
    
    payment_date = models.DateTimeField(
        default=timezone.now, 
        db_index=True,
        verbose_name="Payment Date",
        help_text="When cash actually moved (not contract date)"
    )
    
    # === Payment Type (NEW!) ===
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.RECEIPT,
        help_text="Type of payment: DISBURSAL (outflow/advance), RECEIPT (inflow/repayment)"
    )
    
    # === Direction (Cash Flow) ===
    direction = models.CharField(
        max_length=10,
        choices=CashFlowDirection.choices,
        help_text="RECEIPT=money coming in, PAYMENT=money going out"
    )
    
    # === Source Document (Generic Relation) ===
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={
            'model__in': ['givenloan', 'takenloan', 'sales', 'purchase']
        },
        help_text="Type of document this payment is for"
    )
    source_object_id = models.PositiveIntegerField()
    source_document = GenericForeignKey('source_content_type', 'source_object_id')
    
    # === Amount Breakdown (Multi-Currency Support) ===
    total_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Total payment amount in transaction currency"
    )
    
    # Components (use same currency as total_amount)
    principal_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=Money(0, 'INR'),
        help_text="Principal component (loans)"
    )
    
    interest_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=Money(0, 'INR'),
        help_text="Interest component (loans)"
    )
    
    charges_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        default=Money(0, 'INR'),
        help_text="Additional charges/fees"
    )
    
    # Exchange rate tracking for multi-currency
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1.0000,
        help_text="Exchange rate to base currency (INR)"
    )
    
    amount_in_base_currency = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency='INR',
        help_text="Converted amount in base currency (INR)"
    )
    
    # === Payment Method ===
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH
    )
    
    # === Reference Information ===
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cheque no, transaction ID, UTR, etc."
    )
    
    notes = models.TextField(
        blank=True,
        verbose_name="Payment Notes"
    )
    
    # === Special Flags ===
    is_final_payment = models.BooleanField(
        default=False,
        help_text="This payment closes the source document"
    )
    
    triggers_release = models.BooleanField(
        default=False,
        help_text="For GivenLoan: create Release after this payment"
    )
    
    # === Accounting Link ===
    journal_entries = GenericRelation(
        'dea.JournalEntry',
        related_query_name='payment_voucher'
    )
    
    class Meta:
        ordering = ('-payment_date',)
        verbose_name = "Payment Voucher"
        verbose_name_plural = "Payment Vouchers"
        indexes = [
            models.Index(fields=['source_content_type', 'source_object_id']),
            models.Index(fields=['payment_date', 'direction']),
            models.Index(fields=['direction', 'payment_method']),
            models.Index(fields=['payment_id']),
        ]
    
    def __str__(self):
        direction_symbol = "â†" if self.direction == CashFlowDirection.RECEIPT else "â†’"
        return f"{self.payment_id} {direction_symbol} {self.total_amount}"
    
    def clean(self):
        """Validate payment components and currency consistency"""
        super().clean()
        
        # Ensure all components use same currency
        if (self.principal_amount.currency != self.total_amount.currency or
            self.interest_amount.currency != self.total_amount.currency or
            self.charges_amount.currency != self.total_amount.currency):
            raise ValidationError(
                "All amount components must use the same currency"
            )
        
        # Validate components sum to total
        calculated_total = (
            self.principal_amount.amount +
            self.interest_amount.amount +
            self.charges_amount.amount
        )
        
        if abs(calculated_total - self.total_amount.amount) > 0.01:  # Allow 1 paisa rounding
            raise ValidationError(
                f"Components don't sum to total: "
                f"{self.principal_amount} + {self.interest_amount} + {self.charges_amount} "
                f"= {Money(calculated_total, self.total_amount.currency)} "
                f"!= {self.total_amount}"
            )
    
    def save(self, *args, **kwargs):
        """Auto-generate fields and validate before save"""
        
        # Auto-determine direction from source document type
        if not self.direction and self.source_document:
            self.direction = self._infer_direction()
        
        # Generate payment_id if not exists
        if not self.payment_id:
            self.payment_id = self._generate_payment_id()
        
        # Calculate base currency amount if needed
        if self.total_amount.currency != 'INR':
            self.amount_in_base_currency = Money(
                self.total_amount.amount * self.exchange_rate,
                'INR'
            )
        else:
            self.amount_in_base_currency = self.total_amount
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def _infer_direction(self) -> str:
        """Auto-determine cash flow direction from source document"""
        model_name = self.source_content_type.model
        
        # Receipt scenarios (cash coming IN to company)
        if model_name in ['givenloan', 'sales']:
            return CashFlowDirection.RECEIPT
        
        # Payment scenarios (cash going OUT of company)
        elif model_name in ['takenloan', 'purchase']:
            return CashFlowDirection.PAYMENT
        
        else:
            raise ValidationError(f"Unknown source document type: {model_name}")
    
    def _generate_payment_id(self) -> str:
        """Generate unique payment ID with prefix based on direction"""
        prefix = "RCP" if self.direction == CashFlowDirection.RECEIPT else "PAY"
        date_str = self.payment_date.strftime("%Y%m%d")
        
        # Get next sequence number for this date + direction
        count = PaymentVoucher.objects.filter(
            payment_date__date=self.payment_date.date(),
            direction=self.direction
        ).count() + 1
        
        return f"{prefix}-{date_str}-{count:04d}"
    
    def get_voucher_type(self) -> str:
        """
        Return voucher type based on source document + direction.
        This determines which posting rule to use.
        
        Returns:
            str: Voucher type for posting rule registry
        """
        model_name = self.source_content_type.model
        
        # Map source + direction to voucher type
        voucher_type_map = {
            ('givenloan', CashFlowDirection.RECEIPT): 'GIVENLOAN_RECEIPT',
            ('takenloan', CashFlowDirection.PAYMENT): 'TAKENLOAN_PAYMENT',
            ('sales', CashFlowDirection.RECEIPT): 'SALES_RECEIPT',
            ('purchase', CashFlowDirection.PAYMENT): 'PURCHASE_PAYMENT',
        }
        
        key = (model_name, self.direction)
        voucher_type = voucher_type_map.get(key)
        
        if not voucher_type:
            raise ValueError(
                f"No voucher type mapping for source={model_name}, direction={self.direction}"
            )
        
        return voucher_type
    
    def get_economic_payload(self) -> dict:
        """Payload for accounting posting"""
        return {
            "payment_id": self.payment_id,
            "payment_date": str(self.payment_date),
            "direction": self.direction,
            "total_amount": float(self.total_amount.amount),
            "total_currency": str(self.total_amount.currency),
            "principal_amount": float(self.principal_amount.amount),
            "interest_amount": float(self.interest_amount.amount),
            "charges_amount": float(self.charges_amount.amount),
            "payment_method": self.payment_method,
            "source_type": self.source_content_type.model,
            "source_id": self.source_object_id,
            "exchange_rate": float(self.exchange_rate),
            "amount_base_currency": float(self.amount_in_base_currency.amount),
        }
    
    def get_absolute_url(self):
        """URL for payment detail view"""
        return f"/dea/payments/{self.pk}/"
    
    # === Convenience Properties ===
    
    @property
    def is_receipt(self) -> bool:
        """Check if this is a receipt (cash in)"""
        return self.direction == CashFlowDirection.RECEIPT
    
    @property
    def is_payment(self) -> bool:
        """Check if this is a payment (cash out)"""
        return self.direction == CashFlowDirection.PAYMENT
    
    @property
    def is_multicurrency(self) -> bool:
        """Check if this uses non-base currency"""
        return self.total_amount.currency != 'INR'
```

---

## Posting Rules Design

### Important: When Posting Happens

**PAYMENT-CENTRIC**: Posting happens ONLY when PaymentVoucher is created

```python
# Timeline:
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# Day 1: User creates GivenLoan
given_loan = GivenLoan.objects.create(
    borrower=customer,
    loan_id='A00123',
    series=series,
    status='APPROVED',
)
# âœ… IMPORTANT: NO automatic posting here!
# Just a business agreement record


# Day 1 (when cash actually disbursed): Create PaymentVoucher
disbursal = PaymentVoucher.objects.create(
    source_document=given_loan,
    payment_type='DISBURSAL',
    payment_date=timezone.now(),
    direction='PAYMENT',  # Money going OUT
    total_amount=Money(20000, 'INR'),
    payment_method='CASH',
)
# âœ… NOW posting happens automatically!
# Voucher: GIVENLOAN_DISBURSAL
# Entry: Dr LOAN_RECEIVABLE â‚¹20,000, Cr CASH â‚¹20,000


# Day 15: Customer pays â‚¹10,000
receipt = PaymentVoucher.objects.create(
    source_document=given_loan,
    payment_type='RECEIPT',
    payment_date=timezone.now(),
    direction='RECEIPT',  # Money coming IN
    total_amount=Money(10000, 'INR'),
    principal_amount=Money(8000, 'INR'),
    interest_amount=Money(2000, 'INR'),
    payment_method='BANK',
)
# âœ… Posting happens
# Voucher: GIVENLOAN_RECEIPT
# Entry: Dr CASH â‚¹10,000, Cr LOAN_RECEIVABLE â‚¹10,000
```

### 1. GivenLoan Disbursal Rule (NEW!)

**File**: `apps/tenant_apps/dea/posting/rules/givenloan_disbursal.py`

```python
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("GIVENLOAN_DISBURSAL")
class GivenLoanDisbursalRule(BasePostingRule):
    """
    When we disburse a GivenLoan (money actually given to customer).
    
    Accounting Treatment:
      Dr LOAN_RECEIVABLE (we will receive this money back)
      Cr CASH (money leaves our account)
    
    This replaces the old auto-posting on GivenLoan.save()
    Now we only post when PaymentVoucher.save() is called with DISBURSAL type
    """
    voucher_type = "GIVENLOAN_DISBURSAL"
    rule_version = "1"
    
    def build_posting(self, ctx) -> PostingBundle:
        payment = ctx.doc  # PaymentVoucher instance
        tenant_id = getattr(ctx, "tenant_id", None)
        
        # Get the source GivenLoan
        given_loan = payment.source_document
        if not given_loan:
            raise ValidationError("Payment must be linked to a GivenLoan")
        
        customer = given_loan.borrower
        if not customer or not getattr(customer, 'account', None):
            raise ValidationError(f"No account found for customer {customer}")
        
        # Disbursal amount (in base currency)
        amount = Decimal(str(payment.amount_in_base_currency.amount))
        
        # Get ledgers
        cash_id = get_ledger_id_by_key("CASH", tenant_id)
        receivable_id = get_ledger_id_by_key("LOAN_RECEIVABLE", tenant_id)
        
        # Dr LOAN_RECEIVABLE, Cr CASH
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=receivable_id,
                credit_ledger_id=cash_id,
                currency="INR",
                amount=amount,
                amount_base=amount,
            )
        ]
        
        # Account line (book customer as receiving the loan)
        account_lines = [
            AccountLine(
                ledger_id=receivable_id,
                account_id=customer.account.id,
                side="Dr",  # Customer owes us (debit the receivable)
                currency="INR",
                amount=amount,
                amount_base=amount,
                xact_type_ext="LGD",  # Loan Given Disbursal
            )
        ]
        
        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)
    
    def fingerprint_payload(self, ctx):
        """Fingerprint for idempotency"""
        payment = ctx.doc
        return {
            "payment_id": payment.payment_id,
            "given_loan_id": payment.source_object_id,
            "total_amount": str(payment.amount_in_base_currency.amount),
            "payment_date": str(payment.payment_date),
        }
```

### 2. GivenLoan Receipt Rule

**File**: `apps/tenant_apps/dea/posting/rules/givenloan_receipt.py`

```python
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("GIVENLOAN_RECEIPT")
class GivenLoanReceiptRule(BasePostingRule):
    """
    Customer pays back GivenLoan (cash coming in).
    
    Accounting Treatment:
      Principal: Dr CASH, Cr LOAN_RECEIVABLE
      Interest:  Dr CASH, Cr INTEREST_INCOME
    
    Multi-currency: Convert to base currency (INR) for posting.
    """
    voucher_type = "GIVENLOAN_RECEIPT"
    rule_version = "1"
    
    def build_posting(self, ctx) -> PostingBundle:
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)
        
        # Get the source GivenLoan
        given_loan = payment.source_document
        if not given_loan:
            raise ValidationError("Payment must be linked to a GivenLoan")
        
        customer = given_loan.borrower
        if not customer or not getattr(customer, 'account', None):
            raise ValidationError(f"No account found for customer {customer}")
        
        # Use base currency amounts (already converted in PaymentVoucher.save())
        principal = Decimal(str(payment.principal_amount.amount))
        interest = Decimal(str(payment.interest_amount.amount))
        charges = Decimal(str(payment.charges_amount.amount))
        
        # For multi-currency, use converted base amount
        if payment.is_multicurrency:
            principal = Decimal(str(payment.amount_in_base_currency.amount * 
                               (payment.principal_amount.amount / payment.total_amount.amount)))
            interest = Decimal(str(payment.amount_in_base_currency.amount * 
                              (payment.interest_amount.amount / payment.total_amount.amount)))
            charges = Decimal(str(payment.amount_in_base_currency.amount * 
                             (payment.charges_amount.amount / payment.total_amount.amount)))
        
        # Get ledgers
        cash_id = get_ledger_id_by_key("CASH", tenant_id)
        receivable_id = get_ledger_id_by_key("LOAN_RECEIVABLE", tenant_id)
        interest_income_id = get_ledger_id_by_key("INTEREST_INCOME", tenant_id)
        charges_income_id = get_ledger_id_by_key("OTHER_CHARGES_INCOME", tenant_id)
        
        ledger_lines = []
        
        # Principal repayment: Dr CASH, Cr LOAN_RECEIVABLE
        if principal > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=cash_id,
                    credit_ledger_id=receivable_id,
                    currency="INR",
                    amount=principal,
                    amount_base=principal,
                )
            )
        
        # Interest payment: Dr CASH, Cr INTEREST_INCOME
        if interest > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=cash_id,
                    credit_ledger_id=interest_income_id,
                    currency="INR",
                    amount=interest,
                    amount_base=interest,
                )
            )
        
        # Charges: Dr CASH, Cr OTHER_CHARGES_INCOME
        if charges > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=cash_id,
                    credit_ledger_id=charges_income_id,
                    currency="INR",
                    amount=charges,
                    amount_base=charges,
                )
            )
        
        # Account lines (reduce customer's receivable balance)
        total = principal + interest + charges
        account_lines = [
            AccountLine(
                ledger_id=receivable_id,
                account_id=customer.account.id,
                side="Cr",  # Reduce receivable (credit the Dr account)
                currency="INR",
                amount=total,
                amount_base=total,
                xact_type_ext="LGR",  # Loan Given Receipt
            )
        ]
        
        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)
    
    def fingerprint_payload(self, ctx):
        """Fingerprint for idempotency"""
        payment = ctx.doc
        return {
            "payment_id": payment.payment_id,
            "given_loan_id": payment.source_object_id,
            "total_amount": str(payment.amount_in_base_currency.amount),
            "payment_date": str(payment.payment_date),
        }
```

### 2. TakenLoan Payment Rule

**File**: `apps/tenant_apps/dea/posting/rules/takenloan_payment.py`

```python
@register_rule("TAKENLOAN_PAYMENT")
class TakenLoanPaymentRule(BasePostingRule):
    """
    We pay back TakenLoan to lender (cash going out).
    
    Accounting Treatment:
      Principal: Dr LOAN_PAYABLE, Cr CASH
      Interest:  Dr INTEREST_EXPENSE, Cr CASH
    """
    voucher_type = "TAKENLOAN_PAYMENT"
    rule_version = "1"
    
    def build_posting(self, ctx) -> PostingBundle:
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)
        
        # Get the source TakenLoan
        taken_loan = payment.source_document
        if not taken_loan:
            raise ValidationError("Payment must be linked to a TakenLoan")
        
        lender = taken_loan.lender
        if not lender or not getattr(lender, 'account', None):
            raise ValidationError(f"No account found for lender {lender}")
        
        # Use base currency amounts
        principal = Decimal(str(payment.principal_amount.amount))
        interest = Decimal(str(payment.interest_amount.amount))
        
        # Multi-currency conversion
        if payment.is_multicurrency:
            principal = Decimal(str(payment.amount_in_base_currency.amount * 
                               (payment.principal_amount.amount / payment.total_amount.amount)))
            interest = Decimal(str(payment.amount_in_base_currency.amount * 
                              (payment.interest_amount.amount / payment.total_amount.amount)))
        
        # Get ledgers
        cash_id = get_ledger_id_by_key("CASH", tenant_id)
        payable_id = get_ledger_id_by_key("LOAN_PAYABLE", tenant_id)
        interest_expense_id = get_ledger_id_by_key("INTEREST_EXPENSE", tenant_id)
        
        ledger_lines = []
        
        # Principal payment: Dr LOAN_PAYABLE, Cr CASH
        if principal > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=payable_id,
                    credit_ledger_id=cash_id,
                    currency="INR",
                    amount=principal,
                    amount_base=principal,
                )
            )
        
        # Interest payment: Dr INTEREST_EXPENSE, Cr CASH
        if interest > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=interest_expense_id,
                    credit_ledger_id=cash_id,
                    currency="INR",
                    amount=interest,
                    amount_base=interest,
                )
            )
        
        # Account lines (reduce our payable to lender)
        total = principal + interest
        account_lines = [
            AccountLine(
                ledger_id=payable_id,
                account_id=lender.account.id,
                side="Dr",  # Reduce payable (debit the Cr account)
                currency="INR",
                amount=total,
                amount_base=total,
                xact_type_ext="LTP",  # Loan Taken Payment
            )
        ]
        
        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)
```

### 4. Purchase Payment Rule

**File**: `apps/tenant_apps/dea/posting/rules/purchase_payment.py`

```python
@register_rule("PURCHASE_PAYMENT")
class PurchasePaymentRule(BasePostingRule):
    """
    We pay supplier for purchase (cash going out).
    
    Accounting Treatment:
      Dr PURCHASE_PAYABLE, Cr CASH
    """
    voucher_type = "PURCHASE_PAYMENT"
    rule_version = "1"
    
    def build_posting(self, ctx) -> PostingBundle:
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)
        
        # Get the source Purchase
        purchase = payment.source_document
        if not purchase:
            raise ValidationError("Payment must be linked to a Purchase")
        
        supplier = purchase.supplier
        if not supplier or not getattr(supplier, 'account', None):
            raise ValidationError(f"No account found for supplier {supplier}")
        
        # Use total amount
        amount = Decimal(str(payment.amount_in_base_currency.amount))
        
        # Get ledgers
        cash_id = get_ledger_id_by_key("CASH", tenant_id)
        payable_id = get_ledger_id_by_key("PURCHASE_PAYABLE", tenant_id)
        
        # Dr PURCHASE_PAYABLE, Cr CASH
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=payable_id,
                credit_ledger_id=cash_id,
                currency="INR",
                amount=amount,
                amount_base=amount,
            )
        ]
        
        # Account line
        account_lines = [
            AccountLine(
                ledger_id=payable_id,
                account_id=supplier.account.id,
                side="Dr",  # Reduce payable
                currency="INR",
                amount=amount,
                amount_base=amount,
                xact_type_ext="PP",  # Purchase Payment
            )
        ]
        
        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)
```

### 5. TakenLoan Receipt Rule (NEW!) - When we receive borrowed money

**File**: `apps/tenant_apps/dea/posting/rules/takenloan_receipt.py`

```python
@register_rule("TAKENLOAN_RECEIPT")
class TakenLoanReceiptRule(BasePostingRule):
    """
    When we receive (receipt) money from lender for TakenLoan.
    From lender's perspective: they disburse
    From our perspective: we receive money (RECEIPT direction)
    
    Accounting Treatment:
      Dr CASH (we receive money)
      Cr LOAN_PAYABLE (we owe it back)
    """
    voucher_type = "TAKENLOAN_RECEIPT"
    rule_version = "1"
    
    def build_posting(self, ctx) -> PostingBundle:
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)
        
        taken_loan = payment.source_document
        lender = taken_loan.lender
        if not lender or not getattr(lender, 'account', None):
            raise ValidationError(f"No account found for lender {lender}")
        
        amount = Decimal(str(payment.amount_in_base_currency.amount))
        
        cash_id = get_ledger_id_by_key("CASH", tenant_id)
        payable_id = get_ledger_id_by_key("LOAN_PAYABLE", tenant_id)
        
        # Dr CASH, Cr LOAN_PAYABLE
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=cash_id,
                credit_ledger_id=payable_id,
                currency="INR",
                amount=amount,
                amount_base=amount,
            )
        ]
        
        account_lines = [
            AccountLine(
                ledger_id=payable_id,
                account_id=lender.account.id,
                side="Cr",  # We owe lender (credit the account)
                currency="INR",
                amount=amount,
                amount_base=amount,
                xact_type_ext="LTR",  # Loan Taken Receipt
            )
        ]
        
        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)
```

### 6. TakenLoan Payment Rule - When we pay back the lender

**File**: `apps/tenant_apps/dea/posting/rules/takenloan_payment.py`

```python
@register_rule("TAKENLOAN_PAYMENT")
class TakenLoanPaymentRule(BasePostingRule):
    """
    We pay back TakenLoan to lender (cash going out).
    
    Accounting Treatment:
      Principal: Dr LOAN_PAYABLE, Cr CASH
      Interest:  Dr INTEREST_EXPENSE, Cr CASH
    """
    # ... (keep existing implementation from before)
```

---

## Impact Analysis on Current Implementation

### Critical Change: Remove Auto-Posting from Loan Models

**BREAKING CHANGE**: The current auto-posting in GivenLoan and TakenLoan.save() must be REMOVED

**Current (Loan-Centric - Problem):**
```python
class GivenLoan(BaseLoan, ...):
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # âŒ REMOVE THIS - posts too early!
        if self.auto_post_to_accounting:
            self._auto_post_to_accounting()  # Posts when contract created, not when cash moves
```

**New (Payment-Centric - Solution):**
```python
class GivenLoan(BaseLoan, ...):
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # âœ… NO POSTING HERE - Leave it to PaymentVoucher
        # GivenLoan is just a business record, not an economic event
```

**Why:**
- GivenLoan creation â‰  cash outflow
- Cash flows when PaymentVoucher is created
- Separates business events from economic events
- Achieves IFRS 9 compliance

### Files That Need Changes

#### 1. GivenLoan Model (`apps/tenant_apps/girvi/models/loan_refactored.py`)

**Current State:**
- Auto-posts to accounting on save
- No payment relationship defined

**Changes Required:**

**PART A: Remove auto-posting (CRITICAL)**
```python
class GivenLoan(BaseLoan, GivenLoanReleaseMixin):
    # ... existing fields ...
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # âŒ REMOVE automatic posting
        # if self.auto_post_to_accounting:
        #     self._auto_post_to_accounting()
        
        # âœ… Posting now happens in PaymentVoucher.save() instead
```

**PART B: Add payment relationship and properties**
```python
class GivenLoan(BaseLoan, GivenLoanReleaseMixin):
    # ... existing fields ...
    
    # ADD: Generic relation to payments
    payments = GenericRelation(
        'dea.PaymentVoucher',
        content_type_field='source_content_type',
        object_id_field='source_object_id',
        related_query_name='givenloan_payments'
    )
    
    # ADD: Payment-related properties
    @property
    def total_paid(self) -> Decimal:
        """Total amount paid towards this loan"""
        from django.db.models import Sum
        result = self.payments.aggregate(
            total=Sum('amount_in_base_currency')
        )['total']
        return Decimal(str(result)) if result else Decimal(0)
    
    @property
    def outstanding_balance(self) -> Decimal:
        """Remaining balance after payments"""
        return self.get_loan_amount + self.interest_due() - self.total_paid
    
    @property
    def is_fully_paid(self) -> bool:
        """Check if loan is fully paid"""
        return self.outstanding_balance <= 0
    
    def create_disbursal_payment(self, payment_date, payment_method='CASH', **kwargs):
        """
        Create payment voucher for loan disbursal.
        Called when we actually give the money to customer.
        
        Args:
            payment_date: When money was disbursed
            payment_method: How money was given (CASH, BANK, etc.)
            **kwargs: Additional fields
        
        Returns:
            PaymentVoucher instance
        """
        from apps.tenant_apps.dea.models import PaymentVoucher
        from moneyed import Money
        
        return PaymentVoucher.objects.create(
            source_document=self,
            payment_type='DISBURSAL',  # Loan disbursal
            direction='PAYMENT',  # Money goes OUT
            payment_date=payment_date,
            total_amount=Money(self.get_loan_amount, 'IN R'),
            payment_method=payment_method,
            auto_post_to_accounting=True,
            **kwargs
        )
    
    def create_repayment_payment(self, amount, principal, interest, payment_date, payment_method='CASH', **kwargs):
        """
        Create payment voucher for loan repayment.
        Called when customer pays back.
        
        Args:
            amount: Total amount paid
            principal: Principal component
            interest: Interest component
            payment_date: When payment was received
            payment_method: How payment was received
            **kwargs: Additional fields
        
        Returns:
            PaymentVoucher instance
        """
        from apps.tenant_apps.dea.models import PaymentVoucher
        from moneyed import Money
        
        if not isinstance(amount, Money):
            amount = Money(amount, 'INR')
        if not isinstance(principal, Money):
            principal = Money(principal, 'INR')
        if not isinstance(interest, Money):
            interest = Money(interest, 'INR')
        
        return PaymentVoucher.objects.create(
            source_document=self,
            payment_type='RECEIPT',  # Loan repayment
            direction='RECEIPT',  # Money comes IN
            payment_date=payment_date,
            total_amount=amount,
            principal_amount=principal,
            interest_amount=interest,
            payment_method=payment_method,
            auto_post_to_accounting=True,
            **kwargs
        )
```

**Impact**: High
- BREAKING: Removes auto-posting behavior
- Need to create PaymentVoucher for each cash flow
- Views must be updated to create payments
- Data migration needed for existing loans

---

#### 2. TakenLoan Model (`apps/tenant_apps/girvi/models/loan_refactored.py`)

**Current State:**
- Auto-posts to accounting on save
- No payment relationship defined

**Changes Required:**

**PART A: Remove auto-posting (CRITICAL)**
```python
class TakenLoan(BaseLoan, TakenLoanCollateralMixin):
    # ... existing fields ...
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # âŒ REMOVE automatic posting
        # if self.auto_post_to_accounting:
        #     self._auto_post_to_accounting()
        
        # âœ… Posting now happens in PaymentVoucher.save() instead
```

**PART B: Add payment relationship and properties**
```python
class TakenLoan(BaseLoan, TakenLoanCollateralMixin):
    # ... existing fields ...
    
    # ADD: Generic relation to payments
    payments = GenericRelation(
        'dea.PaymentVoucher',
        content_type_field='source_content_type',
        object_id_field='source_object_id',
        related_query_name='takenloan_payments'
    )
    
    # ADD: Payment-related properties
    @property
    def total_paid(self) -> Decimal:
        """Total amount paid towards this loan"""
        from django.db.models import Sum
        result = self.payments.aggregate(
            total=Sum('amount_in_base_currency')
        )['total']
        return Decimal(str(result)) if result else Decimal(0)
    
    @property
    def outstanding_balance(self) -> Decimal:
        """Remaining balance after payments"""
        return self.get_loan_amount + self.interest_due() - self.total_paid
    
    @property
    def is_fully_paid(self) -> bool:
        """Check if loan is fully paid and can be closed"""
        return self.outstanding_balance <= 0
    
    def create_receipt_payment(self, payment_date, payment_method='CASH', **kwargs):
        """
        Create payment voucher for receiving loan (when lender gives us money).
        Called when we actually receive the borrowed amount.
        
        Args:
            payment_date: When money was received
            payment_method: How money was received (CASH, BANK, etc.)
            **kwargs: Additional fields
        
        Returns:
            PaymentVoucher instance
        """
        from apps.tenant_apps.dea.models import PaymentVoucher
        from moneyed import Money
        
        return PaymentVoucher.objects.create(
            source_document=self,
            payment_type='DISBURSAL',  # From lender's perspective
            direction='RECEIPT',  # Money c omes IN to us
            payment_date=payment_date,
            total_amount=Money(self.get_loan_amount, 'INR'),
            payment_method=payment_method,
            auto_post_to_accounting=True,
            **kwargs
        )
    
    def create_repayment_payment(self, amount, principal, interest, payment_date, payment_method='CASH', **kwargs):
        """
        Create payment voucher for loan repayment (when we pay lender back).
        
        Args:
            amount: Total amount paid
            principal: Principal component
            interest: Interest component
            payment_date: When payment was made
            payment_method: How payment was made
            **kwargs: Additional fields
        
        Returns:
            PaymentVoucher instance
        """
        from apps.tenant_apps.dea.models import PaymentVoucher
        from moneyed import Money
        
        if not isinstance(amount, Money):
            amount = Money(amount, 'INR')
        if not isinstance(principal, Money):
            principal = Money(principal, 'INR')
        if not isinstance(interest, Money):
            interest = Money(interest, 'INR')
        
        return PaymentVoucher.objects.create(
            source_document=self,
            payment_type='RECEIPT',  # We pay
            direction='PAYMENT',  # Money goes OUT
            payment_date=payment_date,
            total_amount=amount,
            principal_amount=principal,
            interest_amount=interest,
            payment_method=payment_method,
            auto_post_to_accounting=True,
            **kwargs
        )
```

**Impact**: High
- BREAKING: Removes auto-posting behavior
- Need to create PaymentVoucher for each cash flow
- Views must be updated to create payments
- Data migration needed for existing loans

---

#### 3. LoanPayment Model (`apps/tenant_apps/girvi/models/loan.py`)

**Current State:**
- LoanPayment model with FK to GivenLoan only
- Used throughout views/forms

**Required Changes:**

**Phase 1: Add deprecation warnings**
```python
class LoanPayment(BusinessDoc):
    """
    DEPRECATED: Use PaymentVoucher instead.
    
    This model is kept for backward compatibility during migration.
    Will be removed in future version.
    """
    loan = models.ForeignKey(
        "girvi.GivenLoan", 
        on_delete=models.CASCADE, 
        related_name="loan_payments"  # Keep old name for compatibility
    )
    # ... existing fields ...
    
    def save(self, *args, **kwargs):
        import warnings
        warnings.warn(
            "LoanPayment is deprecated. Use PaymentVoucher instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().save(*args, **kwargs)
```

**Phase 2: Create bridge property**
```python
class GivenLoan(BaseLoan, GivenLoanReleaseMixin):
    # ... existing code ...
    
    @property
    def all_payments(self):
        """
        Get all payments including old LoanPayment and new PaymentVoucher.
        Returns unified queryset.
        """
        from itertools import chain
        old_payments = self.loan_payments.all()
        new_payments = self.payments.all()
        return list(chain(old_payments, new_payments))
```

**Impact**: High
- Need data migration from LoanPayment â†’ PaymentVoucher
- Need to update all views/forms using LoanPayment
- Multi-phase deprecation strategy

---

#### 4. Views Using LoanPayment

**Files to Update:**
- `apps/tenant_apps/girvi/views/loan.py` - loan payment views
- `apps/tenant_apps/girvi/views/loanpayment.py` - if exists
- Any view creating/updating loan payments

**Current Pattern:**
```python
# OLD
payment = LoanPayment.objects.create(
    loan=given_loan,
    payment_date=date,
    payment_amount=amount,
    principal_payment=principal,
    interest_payment=interest,
)
```

**New Pattern:**
```python
# NEW
from moneyed import Money
payment = PaymentVoucher.objects.create(
    source_document=given_loan,  # Generic FK
    payment_date=date,
    total_amount=Money(amount, 'INR'),
    principal_amount=Money(principal, 'INR'),
    interest_amount=Money(interest, 'INR'),
    payment_method='CASH',
)

# Or use convenience method
payment = given_loan.create_payment(
    amount=amount,
    principal=principal,
    interest=interest,
    payment_method='CASH',
)
```

**Impact**: Medium-High
- Pattern change in all payment creation code
- Need to import Money class
- MoneyField uses different API than DecimalField

---

#### 5. Forms Using LoanPayment

**Files to Update:**
- `apps/tenant_apps/girvi/forms.py` - LoanPaymentForm

**Current:**
```python
class LoanPaymentForm(forms.ModelForm):
    class Meta:
        model = LoanPayment
        fields = ['loan', 'payment_date', 'payment_amount', 'with_release']
```

**New:**
```python
class PaymentVoucherForm(forms.ModelForm):
    class Meta:
        model = PaymentVoucher
        fields = [
            'source_document',  # Or hide and set in view
            'payment_date',
            'total_amount',
            'principal_amount',
            'interest_amount',
            'payment_method',
            'reference_number',
            'notes',
            'triggers_release',
        ]
    
    # Custom widget for MoneyField if needed
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add currency selector if multi-currency needed
        # Or hide currency field if INR-only
```

**Impact**: Medium
- Need new form class
- MoneyField widgets different from DecimalField
- May need custom widgets for currency selection

---

#### 6. Templates Displaying Payments

**Files to Update:**
- `templates/girvi/loan_detail.html` - payment history
- `templates/girvi/loanpayment_*.html` - payment CRUD templates

**Current:**
```html
{% for payment in loan.loan_payments.all %}
    {{ payment.payment_amount }}
    {{ payment.principal_payment }} / {{ payment.interest_payment }}
{% endfor %}
```

**New:**
```html
{% for payment in loan.payments.all %}
    {{ payment.total_amount }}  {# Already formatted with currency #}
    {{ payment.principal_amount }} / {{ payment.interest_amount }}
    <span class="badge">{{ payment.get_direction_display }}</span>
{% endfor %}

{# For backward compatibility during migration #}
{% for payment in loan.all_payments %}
    {# Works with both old and new #}
{% endfor %}
```

**Impact**: Low-Medium
- MoneyField renders nicely by default
- Need to update field names
- Add direction indicator

---

#### 7. Reports/Dashboards Using Payment Data

**Files to Update:**
- `pages/views.py` - company dashboard
- Any report aggregating loan payments

**Current:**
```python
total_collected = LoanPayment.objects.aggregate(
    total=Sum('payment_amount')
)['total']
```

**New:**
```python
from django.db.models import Q

# All receipts (money coming in)
total_receipts = PaymentVoucher.objects.filter(
    direction='RECEIPT'
).aggregate(
    total=Sum('amount_in_base_currency')  # Use base currency for consistency
)['total']

# Loan-specific receipts
loan_receipts = PaymentVoucher.objects.filter(
    source_content_type=ContentType.objects.get_for_model(GivenLoan),
    direction='RECEIPT'
).aggregate(
    total=Sum('amount_in_base_currency')
)['total']
```

**Impact**: Medium
- Need to use amount_in_base_currency for aggregations
- Add direction filter
- Can now aggregate across all payment types

---

### Database Migration Changes

**Migration File**: `apps/tenant_apps/dea/migrations/0xxx_create_paymentvoucher.py`

```python
from django.db import migrations, models
import django.db.models.deletion
import djmoney.models.fields


class Migration(migrations.Migration):
    dependencies = [
        ('dea', '0xxx_previous_migration'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]
    
    operations = [
        # Create PaymentVoucher model
        migrations.CreateModel(
            name='PaymentVoucher',
            fields=[
                ('id', models.BigAutoField(...)),
                ('payment_id', models.CharField(max_length=50, unique=True)),
                ('payment_date', models.DateTimeField()),
                ('direction', models.CharField(max_length=10, choices=[...])),
                
                # MoneyField creates two columns: amount + currency
                ('total_amount', djmoney.models.fields.MoneyField(...)),
                ('principal_amount', djmoney.models.fields.MoneyField(...)),
                ('interest_amount', djmoney.models.fields.MoneyField(...)),
                ('charges_amount', djmoney.models.fields.MoneyField(...)),
                ('amount_in_base_currency', djmoney.models.fields.MoneyField(...)),
                
                ('exchange_rate', models.DecimalField(...)),
                ('payment_method', models.CharField(...)),
                ('reference_number', models.CharField(...)),
                ('notes', models.TextField(...)),
                ('is_final_payment', models.BooleanField(...)),
                ('triggers_release', models.BooleanField(...)),
                
                # Generic FK
                ('source_content_type', models.ForeignKey(...)),
                ('source_object_id', models.PositiveIntegerField()),
                
                # Timestamps
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                
                # Users
                ('created_by', models.ForeignKey(...)),
                ('updated_by', models.ForeignKey(...)),
            ],
            options={
                'ordering': ('-payment_date',),
            },
        ),
        
        # Add indexes
        migrations.AddIndex(...),
        migrations.AddIndex(...),
    ]
```

**Data Migration**: `0xxx_migrate_loanpayment_to_paymentvoucher.py`

```python
from django.db import migrations
from django.contrib.contenttypes.models import ContentType


def migrate_loan_payments(apps, schema_editor):
    """Migrate LoanPayment records to PaymentVoucher"""
    LoanPayment = apps.get_model('girvi', 'LoanPayment')
    PaymentVoucher = apps.get_model('dea', 'PaymentVoucher')
    GivenLoan = apps.get_model('girvi', 'GivenLoan')
    
    givenloan_ct = ContentType.objects.get_for_model(GivenLoan)
    
    count = 0
    for old_payment in LoanPayment.objects.all():
        # Create new PaymentVoucher
        new_payment = PaymentVoucher.objects.create(
            payment_id=f"RCP-MIGR-{old_payment.id:06d}",
            payment_date=old_payment.payment_date,
            direction='RECEIPT',
            source_content_type=givenloan_ct,
            source_object_id=old_payment.loan_id,
            
            # MoneyField: set both amount and currency
            total_amount=old_payment.payment_amount,
            total_amount_currency='INR',
            principal_amount=old_payment.principal_payment,
            principal_amount_currency='INR',
            interest_amount=old_payment.interest_payment,
            interest_amount_currency='INR',
            charges_amount=0,
            charges_amount_currency='INR',
            amount_in_base_currency=old_payment.payment_amount,
            amount_in_base_currency_currency='INR',
            
            exchange_rate=1.0,
            payment_method='CASH',  # Default assumption
            triggers_release=old_payment.with_release,
            
            created_by=old_payment.created_by,
            updated_by=old_payment.created_by,
            created_at=old_payment.created_at if hasattr(old_payment, 'created_at') else old_payment.payment_date,
        )
        count += 1
    
    print(f"Migrated {count} LoanPayment records to PaymentVoucher")


class Migration(migrations.Migration):
    dependencies = [
        ('dea', '0xxx_create_paymentvoucher'),
        ('girvi', '0xxx_some_migration'),
    ]
    
    operations = [
        migrations.RunPython(
            migrate_loan_payments,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
```

---

## MoneyField Integration Details

### Key Differences from DecimalField

**DecimalField (Old):**
```python
payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
# Database: Single column 'payment_amount'
# Python: Decimal('100.00')
# Template: 100.00
```

**MoneyField (New):**
```python
total_amount = MoneyField(max_digits=14, decimal_places=2, default_currency='INR')
# Database: Two columns 'total_amount' and 'total_amount_currency'
# Python: Money(100, 'INR')
# Template: â‚¹100.00
```

### Usage Patterns

**Creation:**
```python
from moneyed import Money

# Explicit Money object
payment = PaymentVoucher.objects.create(
    total_amount=Money(100, 'INR'),
    # ...
)

# Automatic conversion from number (uses default_currency)
payment = PaymentVoucher.objects.create(
    total_amount=100,  # Becomes Money(100, 'INR')
    # ...
)

# Multi-currency
payment = PaymentVoucher.objects.create(
    total_amount=Money(100, 'USD'),
    exchange_rate=83.5,  # 1 USD = 83.5 INR
    # amount_in_base_currency auto-calculated as Money(8350, 'INR')
)
```

**Access:**
```python
payment = PaymentVoucher.objects.get(id=1)

# Money object
print(payment.total_amount)  # â‚¹100.00

# Access components
print(payment.total_amount.amount)    # Decimal('100.00')
print(payment.total_amount.currency)  # INR

# Arithmetic
new_total = payment.total_amount + Money(50, 'INR')  # â‚¹150.00

# Currency mismatch raises exception
payment.total_amount + Money(50, 'USD')  # Error!
```

**Queries:**
```python
# Filter by amount (automatic conversion)
payments = PaymentVoucher.objects.filter(total_amount__gte=1000)

# Filter by currency
payments = PaymentVoucher.objects.filter(total_amount_currency='USD')

# Aggregation (use amount field explicitly)
from django.db.models import Sum
total = PaymentVoucher.objects.aggregate(
    total=Sum('total_amount')  # Works, but loses currency info
)

# Better: Use base currency for aggregation
total = PaymentVoucher.objects.aggregate(
    total=Sum('amount_in_base_currency')  # All in INR
)
```

**Forms:**
```python
from djmoney.forms.fields import MoneyField as MoneyFormField

class PaymentVoucherForm(forms.ModelForm):
    class Meta:
        model = PaymentVoucher
        fields = ['total_amount', ...]
    
    # For single currency (INR only), hide currency selector
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['total_amount'].default_currency = 'INR'
        # To hide currency selector:
        # self.fields['total_amount'].disabled_currencies = True
```

**Templates:**
```html
{# MoneyField auto-formats with currency symbol #}
{{ payment.total_amount }}  <!-- â‚¹100.00 -->

{# Access components #}
{{ payment.total_amount.amount }} {{ payment.total_amount.currency }}

{# For multi-currency display #}
{% if payment.is_multicurrency %}
    <span class="foreign-amount">{{ payment.total_amount }}</span>
    <span class="base-amount">â‰ˆ {{ payment.amount_in_base_currency }}</span>
{% else %}
    {{ payment.total_amount }}
{% endif %}
```

---

## Implementation Phases

### Phase 1: Model Creation (Week 1)

**Tasks:**
- [ ] Create PaymentVoucher model in `dea/models/payment.py`
- [ ] Create migration for PaymentVoucher
- [ ] Add to `dea/models/__init__.py`
- [ ] Run migration in dev environment
- [ ] Test model methods (clean, save, get_voucher_type)

**Validation:**
```python
# Test basic creation
from apps.tenant_apps.dea.models import PaymentVoucher
from apps.tenant_apps.girvi.models import GivenLoan
from moneyed import Money

loan = GivenLoan.objects.first()
payment = PaymentVoucher.objects.create(
    source_document=loan,
    total_amount=Money(1000, 'INR'),
    principal_amount=Money(800, 'INR'),
    interest_amount=Money(200, 'INR'),
    payment_method='CASH',
)

assert payment.direction == 'RECEIPT'
assert payment.get_voucher_type() == 'GIVENLOAN_RECEIPT'
assert payment.payment_id.startswith('RCP-')
```

---

### Phase 2: Posting Rules (Week 1-2)

**Tasks:**
- [ ] Create GivenLoanReceiptRule
- [ ] Create TakenLoanPaymentRule
- [ ] Create SalesReceiptRule (if applicable)
- [ ] Create PurchasePaymentRule (if applicable)
- [ ] Register rules in posting registry
- [ ] Test posting for each rule

**Validation:**
```python
# Test posting
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc

payment = PaymentVoucher.objects.get(id=1)
voucher, je = create_and_post_voucher_for_doc(
    doc=payment,
    user=payment.created_by,
    voucher_type_input=payment.get_voucher_type(),
    engine=DjangoPostingEngine()
)

# Check journal entries created
assert je.entries.count() >= 2  # At least Dr CASH, Cr RECEIVABLE
```

---

### Phase 3: Loan Model Integration (Week 2)

**Tasks:**
- [ ] Add GenericRelation to GivenLoan
- [ ] Add GenericRelation to TakenLoan
- [ ] Add payment properties (total_paid, outstanding_balance)
- [ ] Add create_payment() method
- [ ] Update loan managers if needed
- [ ] Test bidirectional access

**Validation:**
```python
# Test bidirectional access
loan = GivenLoan.objects.get(id=1)
payment = loan.create_payment(
    amount=1000,
    principal=800,
    interest=200,
)

# Forward: payment â†’ loan
assert payment.source_document == loan

# Reverse: loan â†’ payments
assert payment in loan.payments.all()
assert loan.total_paid == 1000
```

---

### Phase 4: View Updates (Week 2-3)

**Tasks:**
- [ ] Create PaymentVoucherCreateView
- [ ] Create PaymentVoucherUpdateView
- [ ] Create PaymentVoucherListView
- [ ] Create PaymentVoucherDetailView
- [ ] Update loan detail view to show new payments
- [ ] Create payment form
- [ ] Add URL routes

**Files to Create/Update:**
- `apps/tenant_apps/dea/views/payment.py`
- `apps/tenant_apps/dea/forms.py`
- `apps/tenant_apps/dea/urls.py`
- `templates/dea/payment_*.html`

---

### Phase 5: Template Updates (Week 3)

**Tasks:**
- [ ] Update loan_detail.html payment section
- [ ] Create payment list template
- [ ] Create payment form template
- [ ] Create payment detail template
- [ ] Update dashboard widgets for payments
- [ ] Test responsive design

---

### Phase 6: Data Migration (Week 3-4)

**Tasks:**
- [ ] Create data migration script
- [ ] Test migration on copy of production data
- [ ] Verify data integrity
- [ ] Create rollback plan
- [ ] Execute migration in production
- [ ] Deprecate LoanPayment model (add warnings)

**Migration Checklist:**
- [ ] Backup database
- [ ] Run migration on staging
- [ ] Verify payment counts match
- [ ] Verify totals match
- [ ] Test payment creation in UI
- [ ] Test posting to accounting
- [ ] Check reports still work

---

### Phase 7: Cleanup (Week 4)

**Tasks:**
- [ ] Monitor for issues in production
- [ ] Remove LoanPayment references from code
- [ ] Update documentation
- [ ] Archive old LoanPayment model (don't delete yet)
- [ ] Performance optimization if needed

---

## Testing Checklist

### Unit Tests

- [ ] PaymentVoucher model validation
- [ ] Direction inference from source type
- [ ] Payment ID generation
- [ ] Multi-currency conversion
- [ ] Component sum validation
- [ ] get_voucher_type() for each source type
- [ ] Each posting rule (GivenLoanReceipt, etc.)
- [ ] Loan payment properties (total_paid, etc.)

### Integration Tests

- [ ] Create payment â†’ auto-posts to accounting
- [ ] Payment affects loan outstanding balance
- [ ] Multi-currency payment converts correctly
- [ ] Payment with release flag creates Release
- [ ] Final payment closes loan
- [ ] Bidirectional access (loanâ†’payments, paymentâ†’loan)

### UI Tests

- [ ] Create payment for GivenLoan
- [ ] Create payment for TakenLoan
- [ ] View payment list filtered by direction
- [ ] View payment detail with source document link
- [ ] Edit payment (if allowed)
- [ ] Delete payment reverses accounting entry
- [ ] Multi-currency payment UI (if enabled)

---

## Risk Assessment

### High Risk Areas

1. **Data Migration**
   - Risk: Data loss or corruption during LoanPayment â†’ PaymentVoucher migration
   - Mitigation: 
     - Test on copy of production data
     - Keep LoanPayment table intact
     - Phased rollout with rollback plan

2. **MoneyField Integration**
   - Risk: Existing decimal arithmetic breaks with Money objects
   - Mitigation:
     - Use .amount to extract Decimal where needed
     - Test all aggregation queries
     - Use amount_in_base_currency for consistency

3. **Posting Rule Changes**
   - Risk: Different accounting treatment breaks financial reports
   - Mitigation:
     - Verify posting rules match existing LoanPayment logic
     - Compare journal entries before/after
     - Get accounting approval

### Medium Risk Areas

1. **View/Form Updates**
   - Risk: UI breaks with new model
   - Mitigation: Comprehensive UI testing

2. **Multi-Currency Support**
   - Risk: Exchange rate calculations wrong
   - Mitigation: Extensive testing with multiple currencies

3. **Performance**
   - Risk: Generic FK slower than direct FK
   - Mitigation: Add proper indexes, monitor query performance

---

## Benefits of This Design

1. **Unified Cash Tracking**: All receipts and payments in one place
2. **Multi-Currency Ready**: Built-in support for international transactions
3. **Extensible**: Easy to add new source types without code changes
4. **Clear Direction**: Explicit RECEIPT vs PAYMENT
5. **Rich Reporting**: Can aggregate across all payment types
6. **Type-Safe Posting**: Each source type routes to correct posting rule
7. **Audit Trail**: Single place to track all cash movements
8. **Future-Proof**: Generic design accommodates new business requirements

---

## Open Questions

1. **Currency Policy**: 
   - Should we support multi-currency loans, or only INR?
   - If multi-currency, should loan amounts also be MoneyField?

2. **Payment Editing**:
   - Should payments be editable after posting?
   - Or should we use correction vouchers?

3. **Partial Payments**:
   - How to handle split principal/interest allocation?
   - Auto-calculate like current LoanPayment.save()?

4. **Payment Methods**:
   - Do we need more payment methods (NEFT, RTGS, etc.)?
   - Track bank account for bank transfers?

5. **Receipt Generation**:
   - Should PaymentVoucher auto-generate receipt PDF?
   - Where to store receipt documents?

6. **Reconciliation**:
   - How to match bank statements to payments?
   - Build reconciliation UI?

---

## Next Steps

1. **Review this document** with team and stakeholders
2. **Answer open questions** above
3. **Get approval** for design changes
4. **Assign tasks** from implementation phases
5. **Set timeline** for each phase
6. **Start Phase 1**: Create PaymentVoucher model

---

## References

- Current LoanPayment implementation: `apps/tenant_apps/girvi/models/loan.py:690-767`
- Posting engine: `apps/tenant_apps/dea/posting/engine.py`
- Posting rules: `apps/tenant_apps/dea/posting/rules/`
- BusinessDoc base: `apps/tenant_apps/dea/models/doc.py`
- django-money docs: https://github.com/django-money/django-money

---

**Document Version**: 1.0  
**Last Updated**: February 25, 2026  
**Status**: Ready for Review

