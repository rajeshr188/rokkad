# Migration Guide: Old Loan Model → GivenLoan/TakenLoan

## ✅ MIGRATION COMPLETE (as of Feb 24, 2026)

**Status**: All database migrations applied successfully. All views updated. Ready for production deployment.

See [MIGRATION_COMPLETION_REPORT_FINAL.md](../MIGRATION_COMPLETION_REPORT_FINAL.md) for detailed completion report.

---

## Overview
Transitioning from single `Loan` model with `loan_type` to separate `GivenLoan` and `TakenLoan` models.

---

## Views Requiring Updates

### Priority 1: Core Loan Views (CRITICAL)

| File | Current | Issue | Fix |
|------|---------|-------|-----|
| `views/loan.py` | `Loan.objects` | Dual-personality queries | Split into `GivenLoan.objects` + `TakenLoan.objects` |
| `views/release.py` | `Loan.objects.for_table_display()` | Old manager | Use `GivenLoan.objects.for_table_display()` |
| `views/loanpayment.py` | `Loan.objects.get()` | Generic lookup | Need loan_type context to route correctly |

### Priority 2: Reporting & Statements (HIGH)

| File | Current | Issue | Fix |
|------|---------|-------|-----|
| `views/reports.py` | `Loan.objects.unreleased()` | Generic filter | Use `GivenLoan.objects.unreleased()` for given loans |
| `views/statement.py` | `Loan.objects.unreleased()` | Generic filter | Filter by loan_type OR combine both querysets |
| `views/prints.py` | `Loan.objects.unreleased()` | Generic filter | Filter by context (given/taken) |

### Priority 3: Notices & Utilities (MEDIUM)

| File | Current | Issue | Fix |
|------|---------|-------|-----|
| `views/notice.py` | `Loan.objects.unreleased()` | Generic filter | Context-dependent |
| `views/custody_views.py` | `Loan.objects.create()` | Should be TakenLoan | Use `TakenLoan.objects.create()` |

---

## Migration Pattern: Before & After

### Pattern 1: Simple Filter to GivenLoan

**Before:**
```python
loans = Loan.objects.filter(release__isnull=True).for_table_display()
# Returns both GivenLoan and TakenLoan
```

**After:**
```python
loans = GivenLoan.objects.unreleased().for_table_display()
# Clear intent: pawns only
```

### Pattern 2: Dual Query (Given + Taken)

**Before:**
```python
loans = Loan.objects.filter(loan_type__in=['Given', 'Taken']).unreleased()
# Mixes both types
```

**After:**
```python
given_loans = GivenLoan.objects.unreleased()
taken_loans = TakenLoan.objects.unreleased()

# In template: loop both separately
```

### Pattern 3: Conditional on Model Type

**Before:**
```python
def loan_detail(request, pk):
    loan = Loan.objects.get(id=pk)
    if loan.loan_type == 'Given':
        return render(request, 'given_detail.html', {'loan': loan})
    else:
        return render(request, 'taken_detail.html', {'loan': loan})
```

**After:**
```python
def given_loan_detail(request, pk):
    loan = GivenLoan.objects.get(id=pk)
    return render(request, 'given_detail.html', {'loan': loan})

def taken_loan_detail(request, pk):
    loan = TakenLoan.objects.get(id=pk)
    return render(request, 'taken_detail.html', {'loan': loan})
```

---

## Query Method Mapping

| Old Method | New Method (GivenLoan) | New Method (TakenLoan) |
|-----------|--------|-------|
| `Loan.objects.unreleased()` | `GivenLoan.objects.unreleased()` | `TakenLoan.objects.unreleased()` |
| `Loan.objects.released()` | `GivenLoan.objects.released()` | `TakenLoan.objects.released()` |
| `Loan.objects.active()` | `GivenLoan.objects.active()` | `TakenLoan.objects.active()` |
| `Loan.objects.overdue()` | `GivenLoan.objects.overdue()` | `TakenLoan.objects.overdue()` |
| `Loan.objects.for_table_display()` | `GivenLoan.objects.for_table_display()` | `TakenLoan.objects.for_table_display()` |
| `Loan.objects.by_borrower(c)` | `GivenLoan.objects.by_borrower(c)` | N/A |
| `Loan.objects.by_lender(c)` | N/A | `TakenLoan.objects.by_lender(c)` |

---

## Import Updates

### File: `views/__init__.py`

**Before:**
```python
from .models import Loan, LoanItem
```

**After:**
```python
from .models import GivenLoan, TakenLoan, LoanItem
```

### Individual View Files

**Before:**
```python
from apps.tenant_apps.girvi.models import Loan
```

**After:**
```python
from apps.tenant_apps.girvi.models import GivenLoan, TakenLoan
```

---

## Templates Change Log

### Identifying Templates Using `loan.loan_type`

Search for these patterns and update:

```django
{% if loan.loan_type == 'Given' %}
    <!-- Update: loan is always GivenLoan in given_detail.html -->
    <!-- Remove if/else, use direct template -->
{% endif %}
```

### Template Imports

**Before:**
```django
<!-- Used both types -->
<div class="loan-type">{{ loan.loan_type }}</div>
```

**After:**
```django
<!-- Template knows the type from URL routing -->
<!-- Use semantic template names: given_loan_list.html, taken_loan_list.html -->
```

---

## Staged Migration Plan

### Phase 1: Foundation (Week 1)
- [ ] Update `views/__init__.py` imports
- [ ] Update model imports in each view file
- [ ] Keep old `Loan` model for data access only (read-only)

### Phase 2: Core Views (Week 2)
- [ ] Refactor `views/loan.py` - split into CreateGivenLoan, CreateTakenLoan views
- [ ] Refactor `views/release.py` - use GivenLoan only
- [ ] Refactor `views/loanpayment.py` - context-aware routing

### Phase 3: Reporting (Week 3)
- [ ] Update `views/reports.py` - separate given/taken reports
- [ ] Update `views/statement.py` - combine queries
- [ ] Update `views/prints.py` - print separate documents

### Phase 4: Polish (Week 4)
- [ ] Update URLs to separate given_loan/ and taken_loan/ paths
- [ ] Update templates with new structure
- [ ] Remove old Loan references from codebase

---

## Testing Checklist

For each view update:

- [ ] GivenLoan.objects.* queries work (test with data)
- [ ] TakenLoan.objects.* queries work (test with data)
- [ ] `.for_table_display()` returns correct annotations
- [ ] `.unreleased()`, `.released()` filter correctly
- [ ] URLs route to correct view
- [ ] Templates render without loan_type conditionals

---

## Files to Update (Detailed)

### `views/loan.py` (HIGH PRIORITY)
- Line 104, 121: Change `Loan.objects` → `GivenLoan.objects` or route context
- Line 243, 263: QuerySet for given loans only
- Line 441, 490, 630, 672, 708: Context-dependent updates

### `views/release.py` (HIGH PRIORITY)
- Line 245: Change to `GivenLoan.objects.for_table_display()`

### `views/loanpayment.py` (HIGH PRIORITY)
- Line 47: Add context check before `.get()`

### `views/reports.py` (MEDIUM PRIORITY)
- Lines 12, 86, 104: Use appropriate manager

### `views/custody_views.py` (MEDIUM PRIORITY)
- Line 359: `Loan.objects.create()` → `TakenLoan.objects.create()`

---

## Reference Implementation

See `managers_refactored.py` for complete QuerySet methods:
- `GivenLoanManager`, `GivenLoanQuerySet`
- `TakenLoanManager`, `TakenLoanQuerySet`

All chainable methods available:
- `.for_table_display()`
- `.for_dashboard_metrics()`
- `.with_duration_metrics()`
- `.with_interest_metrics()`
- `.with_current_value()`
- `.overdue()`
