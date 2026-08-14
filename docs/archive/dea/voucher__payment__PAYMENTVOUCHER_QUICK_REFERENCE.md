---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# PaymentVoucher Quick Reference Guide

**Last Updated**: February 26, 2026

---

## Quick Start

### Create a Payment from a Loan
```python
from apps.tenant_apps.girvi.models import GivenLoan
from moneyed import Money

# Get the loan
loan = GivenLoan.objects.get(id=1)

# Create a payment (auto-posts to accounting)
payment = loan.create_payment(
    amount=Money(10000, 'INR'),
    principal=Money(10000, 'INR'),
    payment_method='BANK',
    reference_number='TXN-2026-001',
    description='Partial repayment',
    is_final=False,
    created_by=request.user,
)

# Check if successful
print(f"Payment ID: {payment.payment_id}")
print(f"Posted: {payment.posted}")
```

### Create a Payment Directly
```python
from apps.tenant_apps.dea.models import PaymentVoucher
from django.contrib.contenttypes.models import ContentType
from moneyed import Money

# Create payment
payment = PaymentVoucher.objects.create(
    source_content_type=ContentType.objects.get_for_model(GivenLoan),
    source_object_id=1,
    total_amount=Money(5000, 'INR'),
    direction='RECEIPT',  # Money coming in
    payment_type='RECEIPT',
    payment_method='CASH',
    payment_date=timezone.now(),
    created_by=request.user,
)
```

### Query Payments
```python
from apps.tenant_apps.dea.models import PaymentVoucher

# All receipts
receipts = PaymentVoucher.objects.filter(direction='RECEIPT')

# All payments
payments = PaymentVoucher.objects.filter(direction='PAYMENT')

# For a specific loan
loan = GivenLoan.objects.get(id=1)
loan_payments = loan.payments.all()

# Posted payments only
posted = PaymentVoucher.objects.filter(posted=True)

# By date range
from datetime import date
recent = PaymentVoucher.objects.filter(
    payment_date__gte=date(2026, 1, 1)
)
```

### Check Loan Status with Payments
```python
loan = GivenLoan.objects.get(id=1)

# Total received
print(f"Total Received: {loan.total_received}")

# Outstanding
print(f"Outstanding: {loan.outstanding_principal}")

# All payments
for payment in loan.all_payments():
    print(f"{payment.payment_id}: {payment.total_amount} on {payment.payment_date}")
```

---

## Payment Voucher Fields

### Core Identity
- `payment_id`: Unique payment reference (auto-generated)
- `payment_date`: When cash actually moved
- `created_at/created_by`: Audit trail
- `updated_at/updated_by`: Audit trail

### Direction & Type
- `direction`: RECEIPT (in) or PAYMENT (out)
- `payment_type`: DISBURSAL, RECEIPT, REFUND, OTHER
- `payment_method`: CASH, BANK, CHEQUE, UPI, CARD

### Amounts
- `total_amount`: Total payment amount (Decimal or Money)
- `principal_amount`: Principal portion (optional)
- `interest_amount`: Interest portion (optional)
- `fee_amount`: Other charges (optional)

### Multi-Currency
- `exchange_rate`: Rate used (default 1.0)
- `amount_in_base_currency`: Converted to base currency (INR)
- `is_multicurrency`: Flag if currency != base

### Source Document (Generic FK)
- `source_content_type`: Type of source (GivenLoan, TakenLoan, etc)
- `source_object_id`: ID of the source document
- `source_document`: Convenience property to get the actual object

### Reference & Notes
- `reference_number`: Bank ref, cheque no, transaction ID, etc
- `description`: Additional notes

### Flags
- `is_final_payment`: Marks if payment closes the loan
- `create_release`: Auto-create Release after posting
- `posted`: Has this been posted to accounting?
- `reversal_of`: Links to original if this is a reversal

---

## URL Routes

### List & Detail
- `/dea/payments/` â†’ Payment list with filters
- `/dea/payments/<id>/` â†’ Payment detail view

### Create & Modify
- `/dea/payments/create/` â†’ Create new payment
- `/dea/payments/<id>/edit/` â†’ Edit draft payment
- `/dea/payments/<id>/delete/` â†’ Delete draft payment

### Loan Payment (AJAX)
- `/dea/loans/<type>/<id>/payment/create/` â†’ Quick payment from loan
  - `<type>`: 'givenloan' or 'takenloan'
  - `<id>`: Loan ID

---

## Posting Rules

| Source Type | Direction | Rule Name | Posting |
|------------|-----------|-----------|---------|
| GivenLoan | PAYMENT | GIVENLOAN_PAYMENT | Dr LOAN_RECEIVABLE, Cr CASH |
| GivenLoan | RECEIPT | GIVENLOAN_RECEIPT | Dr CASH, Cr LOAN_RECEIVABLE |
| TakenLoan | RECEIPT | TAKENLOAN_RECEIPT | Dr CASH, Cr LOAN_PAYABLE |
| TakenLoan | PAYMENT | TAKENLOAN_PAYMENT | Dr LOAN_PAYABLE, Cr CASH |

All rules:
- âœ… Automatically triggered on payment creation
- âœ… Create appropriate journal entries
- âœ… Update GL and subledger balances
- âœ… Support idempotent operations

---

## Common Scenarios

### Scenario 1: Customer Pays on Loan
```python
loan = GivenLoan.objects.get(id=123)

# Receipt came in
payment = loan.create_payment(
    amount=5000,
    principal=5000,
    payment_method='BANK',
    reference_number='ACC-567',
)

# Posting rules executed automatically:
# Dr CASH â‚¹5,000
# Cr LOAN_RECEIVABLE â‚¹5,000
# Customer subledger updated (Cr side)

# Check updated balances
print(loan.total_received)  # â‚¹5,000
print(loan.outstanding_principal)  # Initial - â‚¹5,000
```

### Scenario 2: Loan Disbursal
```python
loan = GivenLoan.objects.create(
    borrower=customer,
    loan_amount=100000,
    # ... other fields
)

# When we give the money (not at creation, but at cash transfer)
payment = PaymentVoucher.objects.create(
    source_document=loan,
    total_amount=Money(100000, 'INR'),
    direction='PAYMENT',  # Money going out
    payment_type='DISBURSAL',
    payment_method='BANK',
    created_by=request.user,
)

# GIVENLOAN_PAYMENT rule posts:
# Dr LOAN_RECEIVABLE â‚¹100,000
# Cr CASH â‚¹100,000
# Customer subledger: Dr â‚¹100,000 (they owe us)
```

### Scenario 3: Multi-Currency Payment
```python
from moneyed import Money

# Customer pays in USD
payment = loan.create_payment(
    amount=Money(150, 'USD'),
    exchange_rate=Decimal('83.50'),  # 1 USD = 83.50 INR
    is_multicurrency=True,
    principal=Money(150, 'USD'),
    created_by=user,
)

# Automatically converts
print(payment.total_amount)  # USD 150.00
print(payment.amount_in_base_currency)  # â‚¹12,525.00

# Posts using base currency amount
```

### Scenario 4: Partial Payment with Interest
```python
loan = GivenLoan.objects.get(id=1)

# Customer pays both principal and interest
payment = loan.create_payment(
    amount=5500,  # Total
    principal=5000,  # Principal portion
    interest=500,  # Interest portion
    payment_method='CASH',
    created_by=user,
)

# Posts with both components tracked
print(payment.principal_amount)  # â‚¹5,000
print(payment.interest_amount)  # â‚¹500
```

---

## Tips & Best Practices

### âœ… DO
- âœ… Create payments ONLY when cash actually moves
- âœ… Use meaningful reference numbers for traceability
- âœ… Set `is_final_payment=True` when loan closes
- âœ… Use appropriate payment methods for records
- âœ… Add descriptions for complex payments
- âœ… Create in drafts first if you want to review
- âœ… Use Money objects for amounts (supports currency)
- âœ… Check `payment.posted` before editing

### âŒ DON'T
- âŒ Don't create payments at contract creation (wait for cash)
- âŒ Don't edit payments after they're posted (create reversal instead)
- âŒ Don't mix up principal/interest allocation
- âŒ Don't mix up direction (RECEIPT vs PAYMENT confusing)
- âŒ Don't leave reference_number blank for bank transfers
- âŒ Don't ignore validation errors

### ðŸ“ Notes on Payment Direction
- **RECEIPT** = Money coming IN to you (customer pays, you receive)
- **PAYMENT** = Money going OUT from you (you pay supplier/lender/loan return)

For **GIVENLOAN**:
- Disbursal = PAYMENT direction (money goes out to customer)
- Receipt = RECEIPT direction (money comes back from customer)

For **TAKENLOAN**:
- Receipt = RECEIPT direction (money comes from lender)
- Repayment = PAYMENT direction (money goes to lender)

---

## Troubleshooting

### Payment Not Posted
**Symptom**: `payment.posted == False`

**Cause**: Check for exceptions during auto-posting

**Solution**:
```python
try:
    from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc
    from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
    
    voucher, je = create_and_post_voucher_for_doc(
        doc=payment,
        user=request.user,
        voucher_type_input=payment.get_voucher_type(),
        engine=DjangoPostingEngine()
    )
    payment.posted = True
    payment.save()
except Exception as e:
    print(f"Posting failed: {e}")
```

### Source Document Not Found
**Symptom**: `payment.source_document` returns None

**Cause**: ContentType or ID mismatch

**Solution**:
```python
# Verify content type
from django.contrib.contenttypes.models import ContentType
ct = ContentType.objects.get_for_model(GivenLoan)
print(ct)  # Should match payment.source_content_type

# Verify source object exists
GivenLoan.objects.filter(id=payment.source_object_id).exists()
```

### Validation Error on Create
**Symptom**: `ValidationError: ...`

**Solution**: Always call `payment.full_clean()` first:
```python
payment = PaymentVoucher(...)
try:
    payment.full_clean()  # Run validations
    payment.save()
except ValidationError as e:
    print(f"Validation failed: {e}")
```

---

## Performance Considerations

### Indexes
The PaymentVoucher table has indexes on:
- `payment_id` (unique)
- `payment_date`
- `direction`
- `reference_number`
- `(source_content_type_id, source_object_id)` (compound)

These support common query patterns.

### Aggregations
```python
# Efficient: Uses indexed fields
totals = PaymentVoucher.objects.filter(
    payment_date__gte=date(2026, 1, 1)
).aggregate(
    total=Sum('amount_in_base_currency'),
)
```

### Large Datasets
For reports with many payments, use:
```python
# Better than iterating
from django.db.models import Sum

result = PaymentVoucher.objects.filter(
    source_object_id=loan_id,
    source_content_type=ContentType.objects.get_for_model(GivenLoan),
).aggregate(
    total=Sum('amount_in_base_currency'),
)
```

---

## References

- [PaymentVoucher Model](apps/tenant_apps/dea/models/payment.py)
- [Posting Rules](apps/tenant_apps/dea/posting/rules/)
- [Views](apps/tenant_apps/dea/views/payment.py)
- [URLs](apps/tenant_apps/dea/urls.py)
- [Templates](templates/dea/paymentvoucher*.html)
- [Full Implementation Summary](PAYMENTVOUCHER_IMPLEMENTATION.md)
- [Design Document](apps/tenant_apps/dea/know/voucher/PAYMENT_VOUCHER_DESIGN.md)

---

## Version Info
- **Django Version**: 4.2+
- **Python Version**: 3.10+
- **Database**: PostgreSQL recommended
- **Created**: February 26, 2026
- **Status**: Production Ready âœ…

