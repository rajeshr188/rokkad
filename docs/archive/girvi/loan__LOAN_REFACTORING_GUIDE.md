---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Loan Model Refactoring Guide

## ðŸŽ¯ Executive Summary

This refactoring addresses the critical design issues identified in the Girvi model analysis:

### Problems Solved:
1. **âœ… Eliminated dual loan type complexity** - Separate `GivenLoan` and `TakenLoan` models instead of `loan_type` field
2. **âœ… Removed data redundancy** - `loan_amount`, `interest`, `weight`, `value` are now calculated `@property` methods
3. **âœ… Fixed semantic confusion** - `borrower` vs `lender` fields with clear meanings
4. **âœ… Cleaner architecture** - No more conditional logic based on `loan_type`
5. **âœ… Better maintainability** - Each loan type handles its own business logic

---

## ðŸ“Š Before vs After Comparison

### Before (Old Structure)
```python
# Single Loan model with dual personality
class Loan(BusinessDoc):
    loan_type = models.CharField(...)  # "Given" or "Taken"
    customer = models.ForeignKey(Customer)  # Ambiguous meaning
    
    # Redundant denormalized fields
    loan_amount = models.PositiveIntegerField()
    interest = models.DecimalField()
    weight = models.CharField()
    item_desc = models.TextField()
    value = models.DecimalField()
    
    # Conditional logic everywhere
    def get_loanamount(self):
        if self.loan_type == self.LoanType.GIVEN:
            return self.loanitems.aggregate(...)
        elif self.loan_type == self.LoanType.TAKEN:
            return self.repledgedloanitems.aggregate(...)
```

### After (New Structure)
```python
# Abstract base with shared fields
class BaseLoan(BusinessDoc):
    loan_id = models.CharField(...)
    series = models.ForeignKey(...)
    # ... common fields only
    
    # Abstract properties that subclasses must implement
    @property
    def get_loan_amount(self) -> Decimal:
        raise NotImplementedError

# Given Loan - Clear semantics
class GivenLoan(BaseLoan):
    borrower = models.ForeignKey(Customer, related_name="loans_received")
    
    @property
    def get_loan_amount(self) -> Decimal:
        return self.loanitems.aggregate(Sum("loanamount"))["loanamount__sum"] or 0

# Taken Loan - Clear semantics  
class TakenLoan(BaseLoan):
    lender = models.ForeignKey(Customer, related_name="loans_given")
    original_loan = models.ForeignKey(GivenLoan, null=True)
    
    @property
    def get_loan_amount(self) -> Decimal:
        return self.repledgedloanitems.aggregate(
            Sum("repledged_loanamount")
        )["repledged_loanamount__sum"] or 0
```

---

## ðŸ—ï¸ Architecture Overview

```
BaseLoan (abstract)
â”œâ”€â”€ Common fields (loan_id, series, loan_date, etc.)
â”œâ”€â”€ Abstract properties (@property methods)
â””â”€â”€ Shared business logic

GivenLoan (concrete)
â”œâ”€â”€ Specific field: borrower
â”œâ”€â”€ Related: loanitems (LoanItem)
â”œâ”€â”€ Implements: get_loan_amount, current_value, etc.
â””â”€â”€ Methods: split_items(), can_split()

TakenLoan (concrete)
â”œâ”€â”€ Specific fields: lender, original_loan
â”œâ”€â”€ Related: repledgedloanitems (RepledgedLoanItem)
â”œâ”€â”€ Implements: get_loan_amount, current_value, etc.
â””â”€â”€ Methods: (repledge-specific logic)
```

---

## ðŸ”‘ Key Changes in Detail

### 1. Semantic Clarity with Distinct Fields

**Given Loan (Pawn):**
- **Who**: We give money TO the customer
- **Field**: `borrower` - The customer receiving the loan
- **Collateral**: Customer pledges items (tracked in `LoanItem`)
- **Related name**: `customer.loans_received`

**Taken Loan (Repledge):**
- **Who**: We take money FROM the customer
- **Field**: `lender` - The customer providing us the loan
- **Collateral**: Customer holds our repledged items (tracked in `RepledgedLoanItem`)
- **Related name**: `customer.loans_given`

### 2. Redundancy Elimination

All calculated fields are now `@property` methods:

| Old (Stored Field) | New (Calculated Property) | Why |
|-------------------|---------------------------|-----|
| `loan_amount` | `@property get_loan_amount` | Always derived from items |
| `interest` | `@property get_interest_amount` | Always derived from items |
| `weight` | `@property get_weight_summary` | Always derived from items |
| `item_desc` | `@property get_item_description` | Always derived from items |
| `value` | `@property current_value` | Always derived from market rates |

**Benefits:**
- âœ… Single source of truth
- âœ… No `update()` method needed
- âœ… No sync issues
- âœ… Always accurate

### 3. Cleaner Method Organization

**Common Base Methods** (in `BaseLoan`):
- `interest_due(as_of_date)` - Calculate interest
- `total_due` - Principal + interest
- `outstanding_balance` - After payments
- `is_underwater` - Value < due amount
- `equity` - Value - due amount
- `get_status_history()` - Audit trail

**GivenLoan-Specific Methods:**
- `can_split()` - Check if splittable
- `split_items(item_ids)` - Split into multiple loans
- `merge_loans(source_loans)` - Merge multiple loans

**TakenLoan-Specific Methods:**
- (Future: repledge management methods)

---

## ðŸ“‹ Manager Changes

### Old Manager Pattern
```python
# Had to filter by loan_type constantly
loans = Loan.objects.filter(loan_type="Given").unreleased()

# Complex conditionals in annotations
Loan.objects.annotate(
    loan_amount=Case(
        When(loan_type="Given", then=Sum("loanitems__loanamount")),
        When(loan_type="Taken", then=Sum("repledgedloanitems__repledged_loanamount")),
    )
)
```

### New Manager Pattern
```python
# Direct model queries - no loan_type filtering
given_loans = GivenLoan.objects.unreleased()
taken_loans = TakenLoan.objects.unreleased()

# Simpler annotations - no conditionals needed
GivenLoan.objects.annotate(
    loan_amount=Sum("loanitems__loanamount")
)
```

### Manager Features

Both `GivenLoanManager` and `TakenLoanManager` provide:

**Filtering Methods:**
```python
.released()          # Has release document
.unreleased()        # No release yet
.active()            # Currently active
.overdue()           # Collateral value < due amount
.by_status(status)   # Filter by specific status
```

**Annotation Chains:**
```python
.with_duration_metrics()    # days_since_created, months_since_created
.with_interest_metrics()    # total_interest, total_due
.with_metal_weights()       # gold_weight, pure_gold_weight, etc.
.with_itemwise_amounts()    # gold_loanamount, silver_loanamount, etc.
.with_current_value()       # gold_value, total_current_value
.with_overdue_status()      # is_overdue boolean
.with_payment_metrics()     # total_payments, outstanding_balance

# Convenience method - all annotations
.for_table_display()        # Everything for table views
.for_dashboard_metrics()    # Lightweight for dashboards
```

**GivenLoan-Specific:**
```python
.by_borrower(customer)      # Filter by borrower
.splittable()               # Loans with multiple items
.available_for_repledge()   # Items not yet repledged
```

**TakenLoan-Specific:**
```python
.by_lender(customer)        # Filter by lender
.from_original_loan(loan)   # Repledges of specific loan
```

---

## ðŸ”„ Migration Strategy

### Phase 1: Parallel Implementation (Safe)

1. **Keep existing `loan.py` intact**
2. **Test new models** using `loan_refactored.py`
3. **Update views gradually** to use new models
4. **Create data migration script**

### Phase 2: Data Migration

```python
# Example migration pseudocode
from girvi.models.loan import Loan as OldLoan
from girvi.models.loan_refactored import GivenLoan, TakenLoan

def migrate_loans():
    for old_loan in OldLoan.objects.all():
        if old_loan.loan_type == "Given":
            new_loan = GivenLoan.objects.create(
                borrower=old_loan.customer,
                loan_id=old_loan.loan_id,
                series=old_loan.series,
                # ... other fields
            )
            # LoanItems automatically link via FK
        
        elif old_loan.loan_type == "Taken":
            new_loan = TakenLoan.objects.create(
                lender=old_loan.customer,
                loan_id=old_loan.loan_id,
                series=old_loan.series,
                # ... other fields
            )
            # RepledgedLoanItems automatically link
```

### Phase 3: Cutover

1. **Update all imports** from `loan.py` to `loan_refactored.py`
2. **Update forms, serializers, templates**
3. **Rename** `loan_refactored.py` â†’ `loan.py`
4. **Remove old model** after verification

---

## ðŸ’¡ Usage Examples

### Creating Loans

**Before:**
```python
# Ambiguous - what does customer mean here?
loan = Loan.objects.create(
    customer=customer,
    loan_type="Given",
    series=series,
)
```

**After:**
```python
# Crystal clear semantics
given_loan = GivenLoan.objects.create(
    borrower=customer,  # Customer is receiving the loan
    series=series,
)

taken_loan = TakenLoan.objects.create(
    lender=customer,  # Customer is providing the loan
    original_loan=some_given_loan,  # Optional reference
    series=series,
)
```

### Accessing Loan Amount

**Before:**
```python
# Manual update required to sync denormalized field
loan.update()  # Recalculates loan_amount from items
amount = loan.loan_amount
```

**After:**
```python
# Always accurate, no sync needed
amount = loan.get_loan_amount  # Calculated on-the-fly
```

### Querying Loans

**Before:**
```python
# Filter by loan_type everywhere
given_loans = Loan.objects.filter(loan_type="Given", status="Disbursed")
taken_loans = Loan.objects.filter(loan_type="Taken").unreleased()
```

**After:**
```python
# Direct model queries
given_loans = GivenLoan.objects.by_status("Disbursed")
taken_loans = TakenLoan.objects.unreleased()
```

### Customer's Loans

**Before:**
```python
# Confusing - which type?
customer_loans = customer.loan_set.all()
```

**After:**
```python
# Clear separation
loans_received = customer.loans_received.all()  # GivenLoans
loans_given = customer.loans_given.all()        # TakenLoans
```

### Table Display with Annotations

**Before:**
```python
loans = Loan.objects.filter(loan_type="Given").with_details()  # 150+ line annotation
for loan in loans:
    print(loan.gold_weight, loan.total_interest, loan.is_overdue)
```

**After:**
```python
loans = GivenLoan.objects.for_table_display()
for loan in loans:
    print(loan.gold_weight, loan.total_interest, loan.is_overdue)
# Same result, but cleaner implementation
```

### Splitting Loans

**Before:**
```python
# Method mixed with other loan logic
new_loans = loan.split_loan_items(item_ids=[1, 2, 3])
```

**After:**
```python
# Only available on GivenLoan (makes sense!)
if given_loan.can_split():
    new_loans = given_loan.split_items(item_ids=[1, 2, 3])
```

---

## ðŸ§ª Testing Checklist

### Unit Tests

- [ ] Test `GivenLoan.get_loan_amount` calculates correctly
- [ ] Test `TakenLoan.get_loan_amount` calculates correctly
- [ ] Test `interest_due()` calculations
- [ ] Test `current_value` property
- [ ] Test `outstanding_balance` after payments
- [ ] Test `can_split()` logic
- [ ] Test `split_items()` functionality
- [ ] Test `merge_loans()` functionality

### Manager Tests

- [ ] Test `.released()` and `.unreleased()` filters
- [ ] Test `.with_duration_metrics()` annotations
- [ ] Test `.with_interest_metrics()` calculations
- [ ] Test `.with_metal_weights()` for both loan types
- [ ] Test `.with_current_value()` uses correct rates
- [ ] Test `.for_table_display()` complete chain
- [ ] Test GivenLoan-specific queries
- [ ] Test TakenLoan-specific queries

### Integration Tests

- [ ] Test loan creation workflow
- [ ] Test payment application
- [ ] Test release creation
- [ ] Test loan splitting
- [ ] Test loan merging
- [ ] Test status transitions
- [ ] Test related models (LoanItem, Release, etc.)

---

## ðŸ“Š Performance Considerations

### Calculated Properties

**Concern**: "Won't calculating `loan_amount` on-the-fly be slow?"

**Answer**: Not significantly, and benefits outweigh costs:

1. **Database-level aggregation** - Uses `Sum()` with index
2. **Rarely accessed in bulk** - Most views show list of loans, not individual amounts repeatedly
3. **Can add `select_related` prefetch** if needed
4. **Caching at view level** if performance critical

### When Properties Might Be Slow

```python
# âŒ BAD: N+1 queries
for loan in GivenLoan.objects.all():
    print(loan.get_loan_amount)  # Separate query each time

# âœ… GOOD: Use annotations
loans = GivenLoan.objects.with_itemwise_amounts()
for loan in loans:
    print(loan.gold_loanamount + loan.silver_loanamount + loan.bronze_loanamount)
```

### Manager Annotations Are Efficient

```python
# Single query with all calculations at database level
loans = GivenLoan.objects.for_table_display()
# â†’ Executes ONE SQL query with joins and aggregations
```

---

## ðŸš§ Removed/Deprecated Methods

### Removed from Base Loan

Methods that no longer make sense:

| Old Method | Status | Replacement |
|-----------|--------|-------------|
| `update()` | âŒ Removed | Properties calculate automatically |
| `get_loanamount()` (method) | âœ… Now property | `get_loan_amount` property |
| Loan type conditionals | âŒ Removed | Subclass implements directly |

### Cleaned Up Methods

Removed debug code:
- `print()` statements in `update()`
- `print()` statements in ID generation
- Unused commented code blocks

---

## ðŸŽ“ Best Practices

### 1. Use Properties for Display

```python
# âœ… GOOD: For displaying single loan details
def loan_detail_view(request, pk):
    loan = GivenLoan.objects.get(pk=pk)
    context = {
        'loan': loan,
        'amount': loan.get_loan_amount,  # Property
        'interest': loan.interest_due(),  # Method
        'value': loan.current_value,  # Property
    }
    return render(request, 'detail.html', context)
```

### 2. Use Annotations for Lists

```python
# âœ… GOOD: For displaying lists of loans
def loan_list_view(request):
    loans = GivenLoan.objects.unreleased().for_table_display()
    # All calculations done in single query
    return render(request, 'list.html', {'loans': loans})
```

### 3. Type Hints for Clarity

```python
from typing import List
from decimal import Decimal

def calculate_portfolio_value(loans: List[GivenLoan]) -> Decimal:
    """Type hints make code self-documenting."""
    return sum(loan.current_value for loan in loans)
```

### 4. Use Correct Model

```python
# âŒ BAD: Don't query wrong model
given_loans = TakenLoan.objects.filter(lender=customer)  # Wrong!

# âœ… GOOD: Use correct model
given_loans = GivenLoan.objects.filter(borrower=customer)
taken_loans = TakenLoan.objects.filter(lender=customer)
```

---

## ðŸ” Troubleshooting

### Issue: "Can't access old `customer` field"

**Solution**: Update to use `borrower` or `lender`:
```python
# Before
loan.customer

# After
given_loan.borrower
taken_loan.lender
```

### Issue: "Loan amount is 0"

**Cause**: No related items yet

**Solution**: Check that LoanItems or RepledgedLoanItems exist:
```python
if given_loan.loanitems.exists():
    amount = given_loan.get_loan_amount
```

### Issue: "AttributeError: 'GivenLoan' object has no attribute 'loan_type'"

**Cause**: Code still referencing old field

**Solution**: Remove `loan_type` checks:
```python
# Before
if loan.loan_type == "Given":
    ...

# After
if isinstance(loan, GivenLoan):
    ...
# Or better: make separate views/logic for each type
```

---

## ðŸ“š Additional Resources

### Related Files

- `loan_refactored.py` - New loan models
- `managers_refactored.py` - New QuerySet/Manager classes
- `services.py` - Calculation services (InterestCalculationService, RateCacheService)
- `GIRVI_MODEL_ANALYSIS.md` - Original analysis document

### Documentation

- BaseLoan API reference (see docstrings)
- GivenLoan API reference (see docstrings)
- TakenLoan API reference (see docstrings)
- Manager method reference (see managers_refactored.py)

---

## âœ… Summary: Why This Refactoring Matters

### Problems Solved

1. **âœ… No more data consistency issues** - Calculated fields always accurate
2. **âœ… Clearer code intent** - `borrower` vs `lender` tells the story
3. **âœ… Simpler queries** - No `loan_type` filtering everywhere
4. **âœ… Type safety** - Can't accidentally query wrong loan type
5. **âœ… Better maintenance** - Each model handles its own logic
6. **âœ… Easier testing** - Test each type independently
7. **âœ… Better performance** - No unnecessary field updates

### Trade-offs

- **Migration effort** - Need to migrate existing data
- **Property overhead** - Slight performance cost (negligible in practice)
- **Learning curve** - Team needs to understand new structure

### Long-term Benefits

- ðŸš€ **Scalability** - Easy to add loan type-specific features
- ðŸ”§ **Maintainability** - Dedicated code paths per type
- ðŸ› **Fewer bugs** - No sync issues, clear semantics
- ðŸ“ˆ **Growth** - Foundation for future enhancements

---

## ðŸŽ¯ Next Steps

1. **Review** this refactoring with the team
2. **Test** the new models thoroughly
3. **Create** data migration script
4. **Update** views, forms, templates incrementally
5. **Deploy** with feature flag for gradual rollout
6. **Monitor** performance and accuracy
7. **Remove** old code after successful migration

---

**Questions? Issues?**  
Document any problems or questions during implementation to refine this guide.

---

**Last Updated**: February 22, 2026  
**Version**: 1.0  
**Status**: Ready for Review

