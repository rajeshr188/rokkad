# Loan Refactoring - Quick Reference

## 🎯 What Changed?

### Model Structure

| Aspect | OLD | NEW |
|--------|-----|-----|
| **Base Model** | `Loan` (concrete with `loan_type` field) | `BaseLoan` (abstract base) |
| **Given Loans** | `Loan(loan_type="Given")` | `GivenLoan` (dedicated model) |
| **Taken Loans** | `Loan(loan_type="Taken")` | `TakenLoan` (dedicated model) |
| **Customer Field** | `customer` (ambiguous) | `borrower` (Given) / `lender` (Taken) |
| **Redundant Fields** | Stored: `loan_amount`, `interest`, `weight`, `value` | Properties: `get_loan_amount`, `current_value`|

---

## 🔄 Code Migration Quick Guide

### 1. Creating Loans

```python
# ❌ OLD WAY
loan = Loan.objects.create(
    customer=customer,
    loan_type="Given",  # String literal
    series=series
)

# ✅ NEW WAY
given_loan = GivenLoan.objects.create(
    borrower=customer,  # Clear semantics
    series=series
)

taken_loan = TakenLoan.objects.create(
    lender=customer,
    original_loan=some_given_loan,
    series=series
)
```

---

### 2. Querying Loans

```python
# ❌ OLD WAY
given_loans = Loan.objects.filter(loan_type="Given")
taken_loans = Loan.objects.filter(loan_type="Taken").unreleased()
customer_loans = customer.loan_set.all()  # Unclear type

# ✅ NEW WAY
given_loans = GivenLoan.objects.all()
taken_loans = TakenLoan.objects.unreleased()
loans_received = customer.loans_received.all()  # GivenLoans
loans_given = customer.loans_given.all()        # TakenLoans
```

---

### 3. Accessing Loan Amount

```python
# ❌ OLD WAY (stored field - needs manual sync)
loan.update()  # Must call to sync
amount = loan.loan_amount  # Stored value

# ✅ NEW WAY (calculated property - always accurate)
amount = loan.get_loan_amount  # Property automatically calculates
```

---

### 4. Customer Relationships

```python
# ❌ OLD WAY
loan.customer  # Ambiguous: borrower or lender?

# ✅ NEW WAY
given_loan.borrower  # Customer receiving money
taken_loan.lender    # Customer providing money
```

---

### 5. Conditional Logic

```python
# ❌ OLD WAY
if loan.loan_type == Loan.LoanType.GIVEN:
    items = loan.loanitems.all()
else:
    items = loan.repledgedloanitems.all()

# ✅ NEW WAY (type-based dispatch)
if isinstance(loan, GivenLoan):
    items = loan.loanitems.all()
elif isinstance(loan, TakenLoan):
    items = loan.repledgedloanitems.all()

# Or better: separate code paths per type
def handle_given_loan(loan: GivenLoan):
    items = loan.loanitems.all()
    # ...

def handle_taken_loan(loan: TakenLoan):
    items = loan.repledgedloanitems.all()
    # ...
```

---

### 6. Manager Queries

```python
# ❌ OLD WAY
loans = Loan.objects.filter(
    loan_type="Given"
).with_details()  # Complex 150+ line annotation

# ✅ NEW WAY
loans = GivenLoan.objects.for_table_display()  # Clean, focused
```

---

### 7. Loan Operations

```python
# ❌ OLD WAY
if loan.loanitems.count() > 1:
    new_loans = loan.split_loan_items([1, 2, 3])

# ✅ NEW WAY
if given_loan.can_split():
    new_loans = given_loan.split_items([1, 2, 3])
# Method only exists on GivenLoan where it makes sense!
```

---

## 📊 Field Mapping

### GivenLoan (Pawn)
| OLD Field | NEW Field/Property | Type |
|-----------|-------------------|------|
| `customer` | `borrower` | FK to Customer |
| `loan_amount` | `get_loan_amount` | @property |
| `interest` | `get_interest_amount` | @property |
| `weight` | `get_weight_summary` | @property |
| `item_desc` | `get_item_description` | @property |
| `value` | `current_value` | @property |

### TakenLoan (Repledge)
| OLD Field | NEW Field/Property | Type |
|-----------|-------------------|------|
| `customer` | `lender` | FK to Customer |
| *(new)* | `original_loan` | FK to GivenLoan |
| `loan_amount` | `get_loan_amount` | @property |
| `interest` | `get_interest_amount` | @property |
| `weight` | `get_weight_summary` | @property |
| `item_desc` | `get_item_description` | @property |
| `value` | `current_value` | @property |

---

## 🔍 Common Patterns

### Pattern 1: Display Loan Details (Single Record)
```python
# Use properties for single loan display
def loan_detail_view(request, pk):
    loan = GivenLoan.objects.get(pk=pk)
    context = {
        'loan_id': loan.loan_id,
        'borrower': loan.borrower,
        'amount': loan.get_loan_amount,        # Property
        'interest_due': loan.interest_due(),    # Method
        'current_value': loan.current_value,   # Property
        'equity': loan.equity,                 # Property
    }
    return render(request, 'detail.html', context)
```

### Pattern 2: List View with Annotations
```python
# Use manager annotations for efficient list queries
def loan_list_view(request):
    loans = (
        GivenLoan.objects
        .unreleased()
        .for_table_display()  # Adds all annotations in single query
        .select_related('borrower', 'series')
    )
    return render(request, 'list.html', {'loans': loans})
```

### Pattern 3: Dashboard Aggregations
```python
def dashboard_view(request):
    # Lightweight annotations for aggregation
    metrics = (
        GivenLoan.objects
        .unreleased()
        .for_dashboard_metrics()
        .filter(is_overdue=True)
        .aggregate(
            count=Count('id'),
            total_due=Sum('total_due'),
            total_value=Sum('total_current_value')
        )
    )
    return render(request, 'dashboard.html', {'metrics': metrics})
```

### Pattern 4: Customer Reports
```python
def customer_loans_view(request, customer_id):
    customer = Customer.objects.get(pk=customer_id)
    
    # Separate querysets for clarity
    given_loans = customer.loans_received.unreleased()
    taken_loans = customer.loans_given.unreleased()
    
    context = {
        'customer': customer,
        'given_loans': given_loans,  # Customer is borrower
        'taken_loans': taken_loans,  # Customer is lender
    }
    return render(request, 'customer_loans.html', context)
```

---

## ⚙️ Manager Chaining Examples

```python
# Basic filtering
GivenLoan.objects.unreleased()
GivenLoan.objects.by_status('Disbursed')
GivenLoan.objects.by_borrower(customer)
GivenLoan.objects.older_than_months(12)

# Chainable annotations (compose as needed)
loans = (
    GivenLoan.objects
    .unreleased()
    .with_duration_metrics()      # Add: days_since_created, months_since_created
    .with_interest_metrics()      # Add: total_interest, total_due
    .with_metal_weights()         # Add: gold_weight, pure_gold_weight, etc.
    .with_current_value()         # Add: gold_value, total_current_value
    .with_overdue_status()        # Add: is_overdue
)

# Kitchen sink (all annotations)
loans = GivenLoan.objects.for_table_display()

# Lightweight (dashboard)
loans = GivenLoan.objects.for_dashboard_metrics()
```

---

## ✅ Checklist for Migrating Code

Use this when updating views, forms, or other code:

- [ ] Replace `Loan` imports with `GivenLoan` / `TakenLoan`
- [ ] Change `customer` to `borrower` (GivenLoan) or `lender` (TakenLoan)
- [ ] Remove `.filter(loan_type=...)` - use correct model instead
- [ ] Replace `loan.loan_amount` with `loan.get_loan_amount`
- [ ] Replace `loan.update()` calls - no longer needed
- [ ] Update manager queries to use `GivenLoan.objects` / `TakenLoan.objects`
- [ ] Update templates to use `borrower` / `lender` instead of `customer`
- [ ] Update forms to use separate forms for each loan type if needed
- [ ] Update serializers/APIs with new field names
- [ ] Run tests and fix failures
- [ ] Update documentation

---

## 🚨 Gotchas & Troubleshooting

### Issue: `AttributeError: 'GivenLoan' object has no attribute 'customer'`
**Fix**: Change `loan.customer` → `loan.borrower` (GivenLoan) or `loan.lender` (TakenLoan)

### Issue: `Loan has no attribute 'loan_type'`
**Fix**: Remove `loan_type` checks. Use `isinstance()` or separate code paths.

### Issue: Loan amount shows 0
**Cause**: No LoanItem objects exist yet
**Fix**: Check `loan.loanitems.exists()` before accessing amount

### Issue: Performance slow when displaying many loans
**Fix**: Use `.for_table_display()` or targeted annotation chains instead of properties

### Issue: Can't import `GivenLoan`
**Fix**: Update import: `from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan, TakenLoan`

---

## 📁 File Locations

- **Models**: `apps/tenant_apps/girvi/models/loan_refactored.py`
- **Managers**: `apps/tenant_apps/girvi/managers_refactored.py`
- **Migration**: `apps/tenant_apps/girvi/migrations/migrate_to_refactored_loans.py`
- **Guide**: `apps/tenant_apps/girvi/docs/LOAN_REFACTORING_GUIDE.md`
- **Analysis**: `apps/tenant_apps/girvi/docs/GIRVI_MODEL_ANALYSIS.md`

---

## 🎓 Key Benefits Recap

✅ **No more data inconsistency** - Properties always calculate fresh  
✅ **Clear semantics** - `borrower` vs `lender` tells the story  
✅ **Simpler queries** - No `loan_type` filtering needed  
✅ **Type safety** - Can't query wrong loan type  
✅ **Better structure** - Each model handles its own logic  
✅ **Easier testing** - Test each type independently  
✅ **Better performance** - No unnecessary field updates  

---

## 🚀 Next Steps

1. **Review** the full guide: `LOAN_REFACTORING_GUIDE.md`
2. **Test** migration on backup: `python migrate_to_refactored_loans.py test`
3. **Verify** data integrity: `python migrate_to_refactored_loans.py verify`
4. **Execute** migration: `python migrate_to_refactored_loans.py execute`
5. **Update** views/forms/templates gradually
6. **Monitor** for issues
7. **Remove** old code after validation

---

**Questions?** Refer to `LOAN_REFACTORING_GUIDE.md` for detailed explanations.

**Last Updated**: February 22, 2026
