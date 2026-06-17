---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Loan Model Refactor - Integration Analysis & Compatibility Report

**Date:** February 25, 2026  
**Current Status:** âš ï¸ PARTIAL INTEGRATION - Old views will NOT work with new models

---

## Executive Summary

The refactor from single `Loan` model â†’ `GivenLoan`/`TakenLoan` models is **incomplete**. While views have been partially updated to use `GivenLoan`, there are **critical integration gaps**:

1. **Schema/Field Mismatches** - Views expect fields that don't exist on new models
2. **Manager Method Gaps** - Methods from old `Loan` manager not available on new managers  
3. **Old Model Still in Use** - Original `Loan` model still loaded (circular dependencies)
4. **Manager Chain Breaking** - Custom querysets don't compose with new model structure
5. **Aggregation Issues** - Old aggregations don't work with LoanItem relationships

---

## ðŸ“‹ Part 1: Model Structure Comparison

### Old Loan Model (Still Active)
```python
from .loan import Loan  # â† Still imported in models/__init__.py

# Fields stored directly on Loan
Loan.fields: loan_amount, interest, value, weight, item_desc

# Managers available
Loan.objects.LoanManager()
Loan.release_related.ReleasedManager()
Loan.unreleased.UnReleasedManager()
```

### New Models (Loan_refactored.py)
```python
# Fields stored on LoanItem (not Loan itself!)
GivenLoan.fields: borrower, series, loan_date, tenure, status
LoanItem.fields: loanamount, interest, itemdesc, weight, purity

# Managers available
GivenLoan.objects.GivenLoanManager()
TakenLoan.objects.TakenLoanManager()
# NO ReleasedManager/UnReleasedManager!
```

### âŒ CRITICAL MISMATCH
Managers expose `released()` / `unreleased()` but base queryset calls them on **Manager** class:
```python
# Old way (works on Loan)
Loan.objects.released()  # â† Uses ReleasedManager

# New way (should work on GivenLoan)
GivenLoan.objects.released()  # â† GivenLoanManager.released() exists âœ“
GivenLoan.objects.unreleased()  # â† GivenLoanManager.unreleased() exists âœ“
```

**Status:** âœ“ PARTIALLY FIXED (managers_refactored.py has these methods)

---

## ðŸ“‹ Part 2: View Integration Issues

### Issue A: Dual Model Setup Confusion

**File:** `models/__init__.py`
```python
from .loan import *              # Imports old Loan model
from .loan_refactored import *   # Imports new GivenLoan/TakenLoan
```

**Problem:** Both models coexist, creating ambiguity:
- Views import `GivenLoan` from `models`
- But old code can still use `Loan`
- Django ORM sees both tables in database

**Impact:** Database has TWO separate loan tables:
- `girvi_loan` (old model)
- `girvi_givenloan` (new model)

**Current State:**
- âŒ Data NOT migrated from old to new
- âŒ New views write to `girvi_givenloan` 
- âŒ Old code reads from `girvi_loan`
- âŒ Data out of sync

---

### Issue B: Views Using Non-Existent Fields

**File:** `pages/views.py` (company_dashboard)
```python
# Line 163
loan = GivenLoan.objects.for_table_display()

# Line 177-184  
context["due_amount"] = LoanItem.objects.filter(loan__in=unreleased).aggregate(...)
# âœ“ FIXED - Now correctly queries LoanItem instead of Loan.loan_amount
```

**Problem Areas Still Remaining:**

1. **Release view still references old Loan:**
   ```python
   # apps/tenant_apps/girvi/views/release.py
   Release.objects.order_by("-id").select_related("loan")
   # "loan" FK references OLD Loan model, not GivenLoan!
   ```

2. **Forms expecting wrong fields:**
   ```python
   # apps/tenant_apps/girvi/forms.py
   class LoanForm(forms.ModelForm):
       class Meta:
           model = GivenLoan  # â† New model
           fields = ['loan_amount', 'interest']  # â† But these fields on LoanItem!
   ```

3. **Filters using non-existent annotations:**
   ```python
   # apps/tenant_apps/girvi/filters.py
   class LoanFilter:
       is_overdue = django_filters.BooleanFilter(
           field_name='is_overdue',  # â† Not a field, only annotation
           widget=...
       )
   ```

---

## ðŸ“‹ Part 3: Manager Method Availability Matrix

| Method | Old Loan.objects | New GivenLoan.objects | New Manager | Status |
|--------|------------------|----------------------|-------------|--------|
| `released()` | âœ“ (DirectoryManager) | âœ“ | GivenLoanManager | âœ“ WORKS |
| `unreleased()` | âœ“ (UnReleasedManager) | âœ“ | GivenLoanManager | âœ“ WORKS |
| `active()` | âœ“ | âœ“ | BaseLoanQuerySet | âœ“ WORKS |
| `overdue()` | âœ“ | âœ“ | BaseLoanQuerySet | âœ“ WORKS |
| `for_table_display()` | âœ“ | âœ“ | BaseLoanQuerySet | âš ï¸ WORKS (limited) |
| `for_dashboard_metrics()` | âœ“ | âœ“ | BaseLoanQuerySet | âš ï¸ WORKS (limited) |
| `non_performing_loans_stats()` | âœ“ | âœ— | Missing | âŒ BROKEN |
| `long_dead_loans_stats()` | âœ“ | âœ— | Missing | âŒ BROKEN |
| `total_weight()` | âœ“ | âœ“ | GivenLoanQuerySet | âœ“ ADDED |
| `total_loanamount()` | âœ“ | âœ“ | GivenLoanQuerySet | âœ“ ADDED |
| `total_current_value()` | âœ“ | âœ“ | GivenLoanQuerySet | âœ“ ADDED |

**Missing Dashboard Methods:**
- `non_performing_loans_stats()` 
- `long_dead_loans_stats()`
- These are used in dashboard views but NOT implemented!

---

## ðŸ“‹ Part 4: Aggregation Query Issues

### Old Loan Aggregations (Direct Fields)
```python
Loan.objects.aggregate(
    Sum('loan_amount'),      # â† Direct field on Loan
    Sum('interest'),          # â† Direct field on Loan
    Sum('total_due')          # â† Annotation on Loan
)
```

### New GivenLoan Aggregations (Related LoanItem)
```python
# âœ— BROKEN - These fields don't exist
GivenLoan.objects.aggregate(Sum('loan_amount'))

# âœ“ FIXED - Must query through LoanItem
LoanItem.objects.filter(loan__in=unreleased).aggregate(
    Sum('loanamount'),       # Correct field name
    Sum('interest')          # Correct field name  
)
```

**Files with Old Aggregations:**
1. âŒ `apps/tenant_apps/girvi/filters.py` - LoanFilter aggregations
2. âŒ `apps/tenant_apps/girvi/views/reports.py` - Dashboard stats
3. âŒ `apps/tenant_apps/girvi/views/prints.py` - Print aggregations

---

## ðŸ“‹ Part 5: Relationship/FK Issues

### Release Model
```python
# apps/tenant_apps/girvi/models/release.py
class Release(models.Model):
    loan = models.OneToOneField(
        'Loan',              # â† STILL REFERENCES OLD Loan MODEL!
        on_delete=models.CASCADE,
        related_name='release'
    )
```

**Problem:** Release is bound to old `Loan`, not `GivenLoan`

**Impact:**
- Releases from `GivenLoan` won't work
- `GivenLoan.release` won't exist
- New views breaking when accessing `loan.release`

---

## ðŸ“‹ Part 6: Import Chain Dependencies

### Current Import Structure
```
models/__init__.py
â”œâ”€â”€ from .loan import *           # Old Loan
â”œâ”€â”€ from .loan_refactored import * # New GivenLoan/TakenLoan
â”œâ”€â”€ from .release import *         # References old Loan!
â”œâ”€â”€ from .loan_item import *       # Added FK to new GivenLoan
â””â”€â”€ ... etc

girvi/models/__init__.py
â”œâ”€â”€ from .girvi.models import GivenLoan  # â† Used by views
â”œâ”€â”€ from .girvi.models import Loan        # â† Still available!
â””â”€â”€ Creates ambiguity
```

### Circular Dependency Risk
1. `Loan` imports from `loan_refactored.py` for enums: `LoanStatus`, `InterestType`
2. `loan_refactored.py` imports managers from `managers_refactored.py`
3. `managers_refactored.py` imports services
4. `services.py` may import models (circular!)

---

## âœ“ What's Working

1. âœ“ **Basic queries work:**
   ```python
   GivenLoan.objects.filter(release__isnull=True)  # Works
   GivenLoan.objects.unreleased()  # Works
   ```

2. âœ“ **Most views have been updated** to use `GivenLoan`  
   - `loan.py` 
   - `reports.py` 
   - `prints.py`
   - `release.py` (mostly)
   - `custody_views.py`

3. âœ“ **New aggregate methods added** to GivenLoanQuerySet:
   - `total_weight()`
   - `total_loanamount()`  
   - `total_itemwise_loanamount()`
   - `total_current_value()`

4. âœ“ **Company dashboard mostly fixed:**
   - Now correctly queries `LoanItem` for loan amounts
   - Uses `unreleased` filter properly

---

## âŒ What's Broken

### Critical Issues

1. **Release Model Still Uses Old Loan FK**
   ```python
   # âŒ BROKEN
   Release.loan -> Loan (old model)
   
   # Need
   Release.loan -> GivenLoan (new model)
   ```

2. **Missing Dashboard Stats Methods**
   ```python
   # âŒ NOT IMPLEMENTED
   GivenLoan.objects.non_performing_loans_stats()
   GivenLoan.objects.long_dead_loans_stats()
   ```

3. **Forms Still Reference Loan Fields**
   ```python
   # âŒ Fields don't exist
   class LoanForm(forms.ModelForm):
       class Meta:
           model = GivenLoan
           fields = ['loan_amount', 'interest']  # Not on GivenLoan!
   ```

4. **Filters Reference Non-Existent Annotations**
   ```python
   # âŒ No 'is_overdue' field without annotation
   class LoanFilter(django_filters.FilterSet):
       is_overdue = filters.BooleanFilter('is_overdue')
   ```

5. **Old Loan Model Still Active**  
   - Data not migrated
   - Two separate tables
   - Confusion about which model to use

---

## ðŸ“Š Integration Status by Component

| Component | Status | Issues | Fix Priority |
|-----------|--------|--------|--------------|
| **Models** | âš ï¸ Partial | Old + New coexist | ðŸ”´ HIGH |
| **Managers** | âœ“ Good | Missing dashboard methods | ðŸŸ¡ MEDIUM |
| **Views** | âš ï¸ Partial | Release references old Loan | ðŸ”´ HIGH |
| **Forms** | âŒ Broken | Fields don't exist | ðŸ”´ HIGH |
| **Filters** | âŒ Broken | Annotations missing | ðŸ”´ HIGH |
| **Templates** | âœ“ Good | No issues identified | ðŸŸ¢ LOW |
| **Aggregations** | âš ï¸ Partial | Query paths wrong | ðŸŸ¡ MEDIUM |

---

## ðŸ”§ Recommended Fix Sequence

### Phase 1: Fix Critical Model Issues (Required)

1. **Migrate Release FK to GivenLoan**
   ```python
   # models/release.py
   class Release(models.Model):
       loan = models.OneToOneField(
           'GivenLoan',  # â† Change from Loan
           on_delete=models.CASCADE,
           related_name='release'
       )
   ```
   - Create data migration
   - Delete old Release records pointing to old Loan

2. **Remove Old Loan Model**
   - Create migration to drop old table
   - Remove `from .loan import *` from models/__init__.py
   - BUT: Keep `LoanStatus`, `InterestType` enums available

### Phase 2: Fix Forms & Filters (High Priority)

1. **Update LoanForm**
   - Remove `loan_amount`, `interest` fields
   - Add only GivenLoan fields: `borrower`, `series`, `tenure`, `interest_type`
   - Create separate `LoanItemFormSet` for items

2. **Update LoanFilter**
   - Remove filters on non-existent fields
   - Use `.with_overdue_status()` in queryset instead of filter

### Phase 3: Add Missing Manager Methods (Medium Priority)

1. **Implement dashboard stats methods:**
   ```python
   def non_performing_loans_stats(self):
       """Loans with is_overdue=True"""
       return self.with_overdue_status().filter(is_overdue=True)
   
   def long_dead_loans_stats(self, threshold_months=12):
       """Loans unreleased for 12+ months"""
       return self.filter(
           release__isnull=True,
           created_at__lt=timezone.now() - timedelta(days=threshold_months*30)
       )
   ```

### Phase 4: Update Views (Medium Priority)

1. Fix Release-related views to use GivenLoan
2. Update aggregation queries where needed
3. Test all dashboard metrics

---

## ðŸ“ Data Migration Requirements

**Current State:**
- Old `girvi_loan` table: ~100+ existing loans
- New `girvi_givenloan` table: 0 records
- New `girvi_takenloan` table: 0 records

**Required Steps:**

```sql
-- 1. Identify loan types (all existing are GIVEN type)
SELECT COUNT(*) FROM girvi_loan WHERE loan_type = 'Given';

-- 2. Create GivenLoan records
INSERT INTO girvi_givenloan (...)
SELECT ... FROM girvi_loan WHERE loan_type = 'Given';

-- 3. Create TakenLoan records  
INSERT INTO girvi_takenloan (...)
SELECT ... FROM girvi_loan WHERE loan_type = 'Taken';

-- 4. Update Release FKs
UPDATE girvi_release SET loan_id = girvi_givenloan.id ...;

-- 5. Copy LoanItem records
UPDATE girvi_loanitem SET loan_id = girvi_givenloan.id ...;

-- 6. Drop old table
DROP TABLE girvi_loan;
```

---

## ðŸ§ª Testing Checklist

- [ ] `GivenLoan.objects.unreleased()` returns correct records
- [ ] `GivenLoan.objects.released()` returns correct records  
- [ ] `GivenLoan.objects.for_table_display()` works without errors
- [ ] Release creation/update works with GivenLoan FK
- [ ] Loan list view shows all loans
- [ ] Dashboard metrics calculate correctly
- [ ] Filters work (after fixing)
- [ ] Forms save loans correctly
- [ ] All aggregations return expected values

---

## âš ï¸ Current View Status

### Views That Work âœ“
- `loan_list()` - Shows GivenLoans
- `loan_table_partial()` - Table display
- `release_list()` - Shows releases (but needs FK fix)
- `custody_views.py` - Custody tracking

### Views That Need Fixes âŒ
- Dashboard views using old aggregations
- Forms with wrong field references
- Filters with broken annotations

---

## Summary: Why Old Views Won't Work

1. **Schema Mismatch** - QuerySets expect fields on wrong models
2. **Broken FK Chains** - Release -> Loan instead of Release -> GivenLoan
3. **Missing Methods** - Dashboard stats not implemented
4. **Coexisting Models** - Ambiguity causes data to split across tables

**To make old views work:** Complete the refactor following the Phase 1-4 sequence above.


