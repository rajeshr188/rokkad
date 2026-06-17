---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Quick Reference: After Loan Model Refactoring

## âœ… Migration Complete

All migrations have been successfully applied. Database is ready for development.

---

## Using the New Models

### For Given Loans (Pawn/Loan TO a customer):
```python
from apps.tenant_apps.girvi.models import GivenLoan

# Query given loans
given_loans = GivenLoan.objects.all()
unreleased = GivenLoan.objects.unreleased()
for_borrower = GivenLoan.objects.by_borrower(customer)

# Access borrower (customer receiving the loan)
loan.borrower
```

### For Taken Loans (Repledge/Loan FROM a customer):
```python
from apps.tenant_apps.girvi.models import TakenLoan

# Query taken loans
taken_loans = TakenLoan.objects.all()
unreleased = TakenLoan.objects.unreleased()
for_lender = TakenLoan.objects.by_lender(customer)

# Access lender (customer providing the loan)
loan.lender
```

### DO NOT USE (Deprecated):
```python
# âŒ OLD - Don't use
from girvi.models import Loan
Loan.objects.all()  # Will include all loans mixed together

# Use specific model instead:
# âœ… NEW
GivenLoan.objects.all()  # Only pawn loans
TakenLoan.objects.all()  # Only repledge loans
```

---

## Key Differences from Old Model

| Aspect | Old `Loan` | New `GivenLoan` | New `TakenLoan` |
|--------|-----------|----------------|----|
| **Related Model** | `customer` (ambiguous) | `borrower` (clear) | `lender` (clear) |
| **Semantics** | Dual-personality | Pawn loan to customer | Repledge loan from customer |
| **Items** | `loanitems` (via FK) | `loanitems` (via FK) | `repledgedloanitems` (via FK) |
| **Release** | `.release` (OneToOne) | `.release` (OneToOne) | N/A |

---

## Common Operations

### Create a Given Loan:
```python
from apps.tenant_apps.girvi.models import GivenLoan

loan = GivenLoan.objects.create(
    loan_id="A00001",
    series=series,
    borrower=customer,
    tenure=3,
    interest_type='Simple',
    created_by=user
)
```

### Create a Taken Loan:
```python
from apps.tenant_apps.girvi.models import TakenLoan

loan = TakenLoan.objects.create(
    loan_id="R00001",
    series=series,
    lender=customer,
    tenure=3,
    interest_type='Simple',
    created_by=user
)
```

### Query Unreleased Loans:
```python
# Given loans not yet released
unreleased_given = GivenLoan.objects.unreleased()

# Taken loans not yet repledged
unreleased_taken = TakenLoan.objects.unreleased()
```

### Get Loan Details:
```python
# These work for both models (inherited from BaseLoan)
loan.get_loan_amount  # Total amount from items
loan.get_interest_amount  # Base interest rate
loan.total_due  # Principal + interest
loan.outstanding_balance  # Total due - payments made
loan.is_released  # Check if loan released/repledged
```

---

## Database Schema Changes

### New Tables Created:
- `girvi_givenloan` - All pawn loans
- `girvi_takenloan` - All repledge loans

### Fields That Changed:
- **LoanItem.loan** - Now FK to `GivenLoan` (was `Loan`)
- **LoanItemPic.loan** - Now FK to `GivenLoan` (was `Loan`)
- **Release.loan** - Now OneToOne to `GivenLoan` (was `Loan`)
- **RepledgedLoanItem.loan** - Now FK to `TakenLoan` (was `Loan`)
- **StatementItem.loan** - Now FK to `GivenLoan` (was `Loan`)

### Preserved Data:
- All existing loans migrated to appropriate new model
- Original loan IDs preserved for consistency
- All related items/payments/releases migrated

---

## Related Documentation

See these files for more information:

1. **MIGRATION_TO_GIVENLOAN_TAKENLOAN.md** - Full migration guide with before/after examples
2. **MIGRATION_COMPLETION_REPORT_FINAL.md** - Detailed completion report with all changes
3. **loan_refactored.py** - New model definitions with full docstrings
4. **managers_refactored.py** - Custom QuerySet methods (unreleased, released, etc.)

---

## Troubleshooting

### Import Error: "cannot import name 'Loan'"
```python
# âŒ Wrong
from girvi.models import Loan

# âœ… Correct
from girvi.models import GivenLoan, TakenLoan
```

### AttributeError: "GivenLoan" has no attribute "customer"
```python
# âŒ Wrong - old Loan model field
loan.customer

# âœ… Correct - new model uses specific field names
loan.borrower  # For GivenLoan
loan.lender    # For TakenLoan
```

### QuerySet filter not working
```python
# âŒ Wrong - assuming combined queryset
Loan.objects.filter(loan_type='Given')

# âœ… Correct - use specific model
GivenLoan.objects.filter(...)
TakenLoan.objects.filter(...)
```

---

## Migration Timeline

- **Feb 24, 2026**: âœ… Complete (you are here)
  - Database schema migrated
  - All data migrated
  - Views updated
  - Ready for production

- **Q2 2026**: Planned
  - Mark old Loan model as read-only
  - Remove from views if any remain

- **Q3 2026**: Planned  
  - Delete old Loan model entirely
  - Final cleanup

---

## Contact & Support

For issues or questions about the migration, refer to the
migration completion report or check the model docstrings in loan_refactored.py.

