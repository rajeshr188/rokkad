# Loan Refactor: Integration Fix Guide

This guide provides concrete code changes to fully integrate the refactored loan models with existing views.

---

## 🔧 Fix 1: Release Model - Update FK to GivenLoan

**File:** `apps/tenant_apps/girvi/models/release.py`

**Current (Broken):**
```python
class Release(models.Model):
    loan = models.OneToOneField(
        'Loan',  # ❌ Points to old model
        on_delete=models.CASCADE,
        related_name='release'
    )
```

**Fixed:**
```python
class Release(models.Model):
    loan = models.OneToOneField(
        'GivenLoan',  # ✓ Points to new model
        on_delete=models.CASCADE,
        related_name='release'
    )
```

**Required Migration:**
```bash
python manage.py makemigrations girvi
python manage.py migrate girvi
```

---

## 🔧 Fix 2: Add Missing Dashboard Stats Methods

**File:** `apps/tenant_apps/girvi/managers_refactored.py`

Add these methods to `GivenLoanManager`:

```python
class GivenLoanManager(models.Manager):
    # ... existing methods ...
    
    def non_performing_loans_stats(self):
        """
        Get statistics for non-performing loans (is_overdue=True).
        
        Returns QuerySet with overdue status annotation.
        
        Usage:
            stats = GivenLoan.objects.non_performing_loans_stats()
            count = stats.count()
            total_due = stats.aggregate(Sum('total_due'))['total_due__sum']
        """
        return self.get_queryset().with_overdue_status().filter(is_overdue=True)
    
    def long_dead_loans_stats(self, threshold_months=12):
        """
        Get statistics for long-dead loans (unreleased for N+ months).
        
        Args:
            threshold_months: Minimum months unreleased (default: 12)
        
        Returns QuerySet of old unreleased loans.
        
        Usage:
            stats = GivenLoan.objects.long_dead_loans_stats(threshold_months=12)
            count = stats.count()
        """
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=threshold_months * 30)
        return self.get_queryset().filter(
            release__isnull=True,
            loan_date__lt=cutoff_date
        )
```

Add same methods to `TakenLoanManager`:

```python
class TakenLoanManager(models.Manager):
    # ... existing methods ...
    
    def non_performing_loans_stats(self):
        """Get statistics for non-performing repledge loans."""
        return self.get_queryset().with_overdue_status().filter(is_overdue=True)
    
    def long_dead_loans_stats(self, threshold_months=12):
        """Get statistics for long-dead repledge loans."""
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=threshold_months * 30)
        return self.get_queryset().filter(
            release__isnull=True,
            loan_date__lt=cutoff_date
        )
```

---

## 🔧 Fix 3: Update LoanForm to Use Correct Fields

**File:** `apps/tenant_apps/girvi/forms.py`

**Current (Broken):**
```python
class LoanForm(forms.ModelForm):
    class Meta:
        model = GivenLoan
        fields = ['loan_amount', 'interest', 'value', 'weight']  # ❌ Not on GivenLoan!
```

**Fixed:**
```python
class LoanForm(forms.ModelForm):
    """
    Form for creating/editing GivenLoans.
    Note: loan_amount, interest are entered via LoanItemFormSet
    """
    class Meta:
        model = GivenLoan
        fields = [
            'borrower',           # Customer receiving the loan
            'series',             # Series for loan ID
            'loan_date',          # When loan was given
            'tenure',             # Loan tenure in months
            'interest_type',      # Simple or Compound
            'status',             # Loan status (Created, Approved, etc)
        ]
        widgets = {
            'loan_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'borrower': forms.Select(),
            'series': forms.Select(),
        }


class LoanItemForm(forms.ModelForm):
    """Form for individual loan items with amount and interest"""
    class Meta:
        model = LoanItem
        fields = [
            'itemdesc',           # Description
            'weight',             # Weight
            'purity',             # Purity percentage
            'loanamount',         # Amount loaned
            'interest',           # Interest rate
            'interest_type',      # Simple or Compound
        ]


class LoanItemFormSet(forms.inlineformset_factory):
    """FormSet for creating multiple items in one loan"""
    pass
```

---

## 🔧 Fix 4: Update LoanFilter to Use Annotations Properly

**File:** `apps/tenant_apps/girvi/filters.py`

**Current (Broken):**
```python
class LoanFilter(django_filters.FilterSet):
    is_overdue = django_filters.BooleanFilter(
        field_name='is_overdue',  # ❌ This is an annotation, not a field!
        label='Show Overdue'
    )
    
    class Meta:
        model = GivenLoan
        fields = ['is_overdue', 'status', 'borrower']
```

**Fixed Option 1: Remove filter, use in view:**
```python
class LoanFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=LoanStatus.choices)
    borrower = django_filters.ModelChoiceFilter(queryset=Customer.objects.all())
    
    class Meta:
        model = GivenLoan
        fields = ['status', 'borrower', 'series']


# In view:
def loan_list(request):
    queryset = GivenLoan.objects.order_by("-id")
    
    # Add annotations if filter needs them
    if request.GET.get('is_overdue'):
        queryset = queryset.with_overdue_status()
        queryset = queryset.filter(is_overdue=request.GET.get('is_overdue'))
    
    filter = LoanFilter(request.GET, queryset=queryset)
    # ... rest of view
```

**Fixed Option 2: Use method filter:**
```python
class LoanFilter(django_filters.FilterSet):
    is_overdue = django_filters.BooleanFilter(
        method='filter_overdue',  # ← Use custom method
        label='Show Overdue'
    )
    
    def filter_overdue(self, queryset, name, value):
        """Custom filter for is_overdue annotation"""
        if value is None:
            return queryset
        
        queryset = queryset.with_overdue_status()
        return queryset.filter(is_overdue=value)
    
    class Meta:
        model = GivenLoan
        fields = ['status', 'borrower']
```

---

## 🔧 Fix 5: Update Dashboard Views for Aggregations

**File:** `apps/tenant_apps/girvi/views/reports.py` (or wherever dashboard views are)

**Current Pattern (Broken):**
```python
def dashboard(request):
    # ❌ These aggregations don't work with GivenLoan
    total_due = GivenLoan.objects.unreleased().aggregate(
        Sum('loan_amount'), 
        Sum('total_due')
    )
```

**Fixed Pattern:**
```python
def dashboard(request):
    from django.db.models import Sum
    from apps.tenant_apps.girvi.models import LoanItem
    
    # Get all unreleased loans
    unreleased = GivenLoan.objects.unreleased()
    
    # Aggregate loan amounts from LoanItems (not Loan itself)
    loan_stats = LoanItem.objects.filter(
        loan__in=unreleased
    ).aggregate(
        total_amount=Sum('loanamount'),
        total_interest=Sum('interest'),
        item_count=Count('id')
    )
    
    # Get overdue status
    non_perf = GivenLoan.objects.non_performing_loans_stats()
    
    # Get long-dead loans
    long_dead = GivenLoan.objects.long_dead_loans_stats(threshold_months=12)
    
    context = {
        'total_amount': loan_stats['total_amount'] or 0,
        'total_interest': loan_stats['total_interest'] or 0,
        'unreleased_count': unreleased.count(),
        'non_performing': {
            'count': non_perf.count(),
            'total_due': non_perf.aggregate(Sum('total_due'))['total_due__sum'] or 0,
        },
        'long_dead': {
            'count': long_dead.count(),
        }
    }
    
    return render(request, 'girvi/dashboard.html', context)
```

---

## 🔧 Fix 6: Remove Old Loan Model from Imports

**File:** `apps/tenant_apps/girvi/models/__init__.py`

**Current (Has Both):**
```python
from .license import *
from .loan import *              # ← Old model
from .release import *
from .template import *
from .loan_refactored import *   # ← New models
from .loan_item import *
from .custody_tracking import *
from .statement import *
```

**After Phase 1 (Remove Old):**
```python
from .license import *
# from .loan import *           # ← REMOVED after migration
from .release import *
from .template import *
from .loan_refactored import *  # ← Keep this
from .loan_item import *
from .custody_tracking import *
from .statement import *

# Keep enums available at package level for backward compatibility
from .loan_refactored import LoanStatus, InterestType
```

---

## 🔧 Fix 7: Update View Imports

**Files:** All views using Loan model

**Before:**
```python
from ..models import Loan, GivenLoan, LoanItem  # ❌ Ambiguous
```

**After:**
```python
from ..models import GivenLoan, TakenLoan, LoanItem  # ✓ Clear
# Remove: from ..models import Loan
```

**Check in:**
- `apps/tenant_apps/girvi/views/loan.py` ✓
- `apps/tenant_apps/girvi/views/release.py` ✓
- `apps/tenant_apps/girvi/views/reports.py` - Check/fix
- `apps/tenant_apps/girvi/views/prints.py` - Check/fix
- `apps/tenant_apps/girvi/views/custody_views.py` ✓

---

## 🔧 Fix 8: Update Services to Use New Models

**File:** `apps/tenant_apps/girvi/services.py`

**Already Fixed? Check:**
```python
# Line 23
from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan  # ✓ Correct

# Make sure no references to old Loan model
# Search for: "from .models import Loan"
# Replace with: "from .models import GivenLoan, TakenLoan"
```

---

## 📋 Step-by-Step Integration Checklist

### Phase 1: Critical (Do First)
- [ ] Update `Release.loan` FK to point to `GivenLoan`
- [ ] Create and run migration
- [ ] Update imports in all views (remove `Loan`)
- [ ] Test `GivenLoan.objects.release_related` access

### Phase 2: High Priority (Do Second)  
- [ ] Add `non_performing_loans_stats()` to GivenLoanManager
- [ ] Add `long_dead_loans_stats()` to GivenLoanManager
- [ ] Update LoanForm to use correct fields
- [ ] Update all view aggregations to query LoanItem

### Phase 3: Medium Priority (Do Third)
- [ ] Fix LoanFilter if used
- [ ] Update dashboard views
- [ ] Update report views  
- [ ] Fix print/batch views

### Phase 4: Consolidation (Do Last)
- [ ] Remove old `Loan` model from imports  
- [ ] Delete old migration files referencing `Loan`
- [ ] Run full test suite
- [ ] Verify no references to old model remain

---

## 🧪 Testing Commands

```bash
# Test imports work
python manage.py shell
>>> from apps.tenant_apps.girvi.models import GivenLoan, TakenLoan
>>> GivenLoan.objects.count()

# Test new methods exist
>>> GivenLoan.objects.non_performing_loans_stats()
>>> GivenLoan.objects.long_dead_loans_stats()

# Test Release access
>>> loan = GivenLoan.objects.first()
>>> loan.release  # Should work if updated

# Test aggregations
>>> from apps.tenant_apps.girvi.models import LoanItem
>>> LoanItem.objects.filter(loan__in=GivenLoan.objects.unreleased()).aggregate(Sum('loanamount'))

# Run migrations
python manage.py check
python manage.py migrate
```

---

## ⚠️ Common Mistakes to Avoid

1. **❌ Don't** use `Loan.objects` - use `GivenLoan.objects` or `TakenLoan.objects`
2. **❌ Don't** aggregate on GivenLoan fields that are on LoanItem - query LoanItem instead
3. **❌ Don't** forget Release FK update - views will break
4. **❌ Don't** leave old model imports - causes confusion
5. **❌ Don't** create forms with non-existent fields - use LoanItemFormSet instead

---

## 🎯 After These Fixes

✓ All views will work with new models  
✓ No more "field doesn't exist" errors  
✓ Release relationships will work properly  
✓ Dashboard stats will calculate correctly  
✓ Forms will save data to right tables  
✓ Clean separation: GivenLoan for given loans, TakenLoan for repledges  

