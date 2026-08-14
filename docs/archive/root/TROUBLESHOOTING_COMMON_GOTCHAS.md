---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Troubleshooting & Common Gotchas

Everything that can go wrong and how to fix it.

---

## Installation & Setup Issues

### Issue 1: "ModuleNotFoundError: No module named 'girvi.manager_improved'"

**Cause:** Module not found or not yet created

**Fixes:**
```python
# Check 1: File exists?
# Should be: apps/tenant_apps/girvi/manager_improved.py
import os
path = "apps/tenant_apps/girvi/manager_improved.py"
print(f"File exists: {os.path.exists(path)}")

# Check 2: __init__.py exists in girvi?
path2 = "apps/tenant_apps/girvi/__init__.py"
print(f"__init__.py exists: {os.path.exists(path2)}")

# Check 3: Try importing
try:
    from apps.tenant_apps.girvi.manager_improved import ImprovedLoanManager
    print("âœ“ Import successful")
except ImportError as e:
    print(f"âœ— Import failed: {e}")
```

---

### Issue 2: "ImprovedLoanManager is not defined"

**Cause:** Import syntax wrong

**Wrong:**
```python
from girvi import ImprovedLoanManager  # Wrong path
from girvi.managers import ImprovedLoanManager  # Wrong file
```

**Right:**
```python
from apps.tenant_apps.girvi.manager_improved import ImprovedLoanManager
```

---

### Issue 3: "services.py not found"

**Cause:** services.py file missing

**Fix:**
```bash
# Check file exists
ls apps/tenant_apps/girvi/services.py

# If missing, create it with all service classes
# See: LOAN_QUERY_ANNOTATIONS_GUIDE.md
```

---

## QuerySet/Annotation Issues

### Issue 4: "Cannot resolve keyword 'gold_weight'"

**Cause:** Forgot to add annotation

**Wrong:**
```python
loans = Loan.objects.filter(gold_weight__gt=100)
# ERROR: Field 'gold_weight' doesn't exist on model
```

**Right:**
```python
loans = Loan.objects.with_metal_weights().filter(gold_weight__gt=100)
# Now it works!
```

**Tip:** Always check which annotations you need:
- `with_duration_metrics()` - gives `days_since_created`, `months_since_created`, etc.
- `with_metal_weights()` - gives `gold_weight`, `silver_weight`, etc.
- `with_interest_metrics()` - gives `total_interest`, `total_due`, etc.
- `with_itemwise_amounts()` - gives `gold_loanamount`, `silver_loanamount`, etc.
- `with_current_value()` - gives `gold_value`, `total_current_value`, etc.
- `with_overdue_status()` - gives `is_overdue` boolean

---

### Issue 5: "Cannot resolve keyword 'is_overdue'" in filter

**Cause:** Same as above - forgot annotation

**Wrong:**
```python
loans = Loan.objects.unreleased().filter(is_overdue=True)
# ERROR: is_overdue doesn't exist
```

**Right:**
```python
# Option 1: Use convenience method
loans = Loan.objects.overdue()

# Option 2: Add annotation explicitly
loans = Loan.objects.unreleased().with_overdue_status().filter(is_overdue=True)

# Option 3: Use for_table_display which includes it
loans = Loan.objects.unreleased().for_table_display().filter(is_overdue=True)
```

---

### Issue 6: "Loan matching query does not exist" on single object

**Cause:** The query has no results

**Debug steps:**
```python
# Check 1: Does the loan exist?
from girvi.models import Loan
print(f"Total loans: {Loan.objects.count()}")

# Check 2: Are there unreleased loans?
print(f"Unreleased: {Loan.objects.unreleased().count()}")

# Check 3: Get the loan with debug
try:
    loan = Loan.objects.unreleased().get(id=123)
except Loan.DoesNotExist:
    print("âœ— Loan not found")
    # Show what does exist
    print(f"Available IDs: {list(Loan.objects.values_list('id', flat=True)[:10])}")
```

---

## Rate Issues

### Issue 7: "Rates showing as 0 or None"

**Cause:** Rate model has no entries

**Debug:**
```python
from apps.tenant_apps.rates.models import Rate

# Check 1: Do Rate entries exist?
rates = Rate.objects.all()
print(f"Rate count: {rates.count()}")

# Check 2: Required rates
required = ['Gold', 'Silver', 'Bronze']
for metal in required:
    rate = Rate.objects.filter(metal_type=metal).first()
    if rate:
        print(f"  {metal}: {rate.rate}")
    else:
        print(f"  {metal}: âœ— MISSING")

# Check 3: Create missing rates
if not Rate.objects.filter(metal_type='Gold').exists():
    Rate.objects.create(
        metal_type='Gold',
        rate=5666.25,  # Current market rate
        last_updated=timezone.now()
    )
    print("âœ“ Created Gold rate")
```

---

### Issue 8: "RateCacheService returns stale rates"

**Cause:** Cache not invalidated

**Debug:**
```python
from girvi.services import RateCacheService

# Check 1: What's currently cached?
gold_rate = RateCacheService.get_rate('Gold')
print(f"Cached Gold rate: {gold_rate}")

# Check 2: Is it up to date?
from apps.tenant_apps.rates.models import Rate
db_rate = Rate.objects.get(metal_type='Gold').rate
print(f"DB Gold rate: {db_rate}")

if gold_rate != db_rate:
    print("âœ— Cache is stale!")
    
# Check 3: Invalidate cache manually
RateCacheService.invalidate()
print("âœ“ Cache cleared")

# Check 4: Verify it's fresh now
gold_rate_fresh = RateCacheService.get_rate('Gold')
print(f"Fresh Gold rate: {gold_rate_fresh}")
```

---

### Issue 9: "RateCacheService.get_all_rates() returns empty dict"

**Cause:** Rates not cached or all metal rates missing

**Debug:**
```python
from girvi.services import RateCacheService

# Check 1: Get all rates
all_rates = RateCacheService.get_all_rates()
print(f"Cached rates: {all_rates}")

# Check 2: Check database
from apps.tenant_apps.rates.models import Rate
db_rates = Rate.objects.all().values_list('metal_type', 'rate')
print(f"DB rates: {dict(db_rates)}")

# Check 3: Ensure all required metals exist
required = ['Gold', 'Silver', 'Bronze']
for metal in required:
    if not Rate.objects.filter(metal_type=metal).exists():
        print(f"âœ— {metal} rate missing in DB!")
```

---

## Annotation Field Name Issues

### Issue 10: Spelling/Capitalization Issues

**Wrong field names:**
```python
# Wrong capitalization
gold_Weight  # âœ—
goldweight   # âœ—
Gold_weight  # âœ—

# Wrong words
gold_wt      # âœ—
precious_metal_gold  # âœ—
```

**Right field names:**
```python
gold_weight           # âœ“
pure_gold_weight      # âœ“
silver_weight         # âœ“
bronze_weight         # âœ“
gold_loanamount       # âœ“
gold_value            # âœ“
total_loanamount      # âœ“
total_current_value   # âœ“
total_interest        # âœ“
total_due             # âœ“
is_overdue            # âœ“
months_since_created  # âœ“
```

**Debug:**
```python
# Print all available annotations
loan = Loan.objects.unreleased().for_table_display().first()
annotations = vars(loan)
for key in sorted(annotations.keys()):
    print(f"  {key}")
```

---

## Dashboard Stats Issues

### Issue 11: "Dashboard methods return empty/None"

**Cause:** No loans matching the criteria

**Debug:**
```python
# Check 1: Any unreleased loans?
from girvi.models import Loan
print(f"Unreleased count: {Loan.objects.unreleased().count()}")

# Check 2: Any overdue loans?
print(f"Overdue count: {Loan.objects.overdue().count()}")

# Check 3: Check dashboard stats manually
unreleased = Loan.objects.unreleased()
if unreleased.exists():
    stats = Loan.objects.non_performing_loans_stats()
    print(f"Stats: {stats}")
else:
    print("âœ— No unreleased loans to analyze")

# Check 4: Try with explicit queryset
from girvi.services import DashboardMetricsService
custom_qs = Loan.objects.unreleased().for_table_display()
stats = DashboardMetricsService.get_non_performing_loans_stats(custom_qs)
print(f"Manual stats: {stats}")
```

---

### Issue 12: "Dashboard stats shows incorrect totals"

**Cause:** Wrong aggregation or double-counting

**Debug:**
```python
from girvi.models import Loan

# Method 1: What dashboard returns
stats = Loan.objects.non_performing_loans_stats()
dashboard_count = stats['count']
dashboard_total = stats['total_due']

# Method 2: Manual calculation
loans = Loan.objects.unreleased().for_table_display()
manual_count = loans.count()
from django.db.models import Sum
manual_total = loans.aggregate(total=Sum('total_due'))['total'] or 0

# Compare
print(f"Dashboard count: {dashboard_count}")
print(f"Manual count: {manual_count}")
print(f"Match: {dashboard_count == manual_count}")

print(f"Dashboard total_due: {dashboard_total}")
print(f"Manual total_due: {manual_total}")
print(f"Match: {dashboard_total == manual_total}")
```

---

## Performance Issues

### Issue 13: "Queries are too slow"

**Cause:** No pagination or fetching too much data

**Debug & Fix:**
```python
from django.db import connection
from django.test.utils import override_settings

@override_settings(DEBUG=True)
def debug_performance():
    connection.queries_log.clear()
    
    # Slow query
    loans = list(Loan.objects.unreleased().for_table_display())
    
    print(f"Query count: {len(connection.queries)}")
    for q in connection.queries:
        print(f"  Time: {q['time']:.3f}s")
        print(f"  Query: {q['sql'][:100]}...")

debug_performance()
```

**Solutions:**
```python
# Solution 1: Use pagination
from django.core.paginator import Paginator

loans = Loan.objects.unreleased().for_table_display()
paginator = Paginator(loans, 50)
page = paginator.get_page(1)
# Only fetches 50, not all

# Solution 2: Use .values() for read-only
loans = (Loan.objects
    .unreleased()
    .for_table_display()
    .values('id', 'loan_id', 'gold_weight', 'total_interest')
)

# Solution 3: Add select_related
loans = (Loan.objects
    .unreleased()
    .select_related('customer', 'series')
    .for_table_display()
)

# Solution 4: Limit fields with .only()
loans = (Loan.objects
    .unreleased()
    .only('id', 'loan_id', 'customer')
    .for_table_display()
)
```

---

### Issue 14: "MemoryError when exporting large dataset"

**Cause:** Loading all rows into memory at once

**Wrong:**
```python
# This loads EVERYTHING into memory
loans = list(Loan.objects.unreleased().for_table_display())
```

**Right:**
```python
# Option 1: Use .iterator() for large sets
loans = Loan.objects.unreleased().for_table_display().iterator(chunk_size=1000)
for chunk in loans:
    process(chunk)

# Option 2: Use values() without model instances
loans = (Loan.objects
    .unreleased()
    .for_table_display()
    .values('id', 'gold_weight', 'total_interest')
)

# Option 3: Stream to file
import csv
response = HttpResponse(content_type='text/csv')
writer = csv.DictWriter(response, fieldnames=[...])
writer.writeheader()
for loan in loans.iterator():
    writer.writerow({...})
```

---

## Chaining Issues

### Issue 15: "Got FieldError after chaining methods"

**Cause:** Methods called in wrong order

**Debug:**
```python
# What's the exact error?
try:
    loans = Loan.objects.for_table_display().filter(gold_weight__gt=100)
except Exception as e:
    print(f"Error type: {type(e).__name__}")
    print(f"Error: {e}")
```

**Solutions:**
```python
# If annotation not found: annotation before filter
loans = (Loan.objects
    .with_metal_weights()  # Annotation first
    .filter(gold_weight__gt=100)  # Then use it
)

# If method not on QuerySet: check import
from girvi.manager_improved import ImprovedLoanManager  # Correct import
```

---

### Issue 16: "Chaining methods returns empty QuerySet"

**Cause:** Conflicting filters

**Wrong:**
```python
# These contradict each other!
loans = Loan.objects.overdue().good_standing()
# Result: Empty (loan can't be both overdue AND good standing)
```

**Debug:**
```python
# Check each part separately
overdue = Loan.objects.overdue()
print(f"Overdue count: {overdue.count()}")

good = Loan.objects.good_standing()
print(f"Good standing count: {good.count()}")

# Then check combined
both = Loan.objects.overdue().good_standing()
print(f"Both: {both.count()}")  # Probably 0
```

**Right:**
```python
# Use either/or, not and
loans = Loan.objects.overdue()
# OR
loans = Loan.objects.good_standing()
```

---

## Template Issues

### Issue 17: "Template shows blank/missing values"

**Cause:** Annotation not added

**Wrong template:**
```html
<!-- gold_weight not in annotations -->
{{ loan.gold_weight }} <!-- Shows nothing -->
```

**Debug in view:**
```python
def view(request):
    loans = Loan.objects.unreleased().for_table_display()
    if loans.exists():
        loan = loans.first()
        print(f"Loan fields: {vars(loan).keys()}")
```

**Right template:**
```html
<!-- Make sure to_table_display() was called -->
{{ loan.gold_weight }}
```

**Right view:**
```python
def view(request):
    loans = Loan.objects.unreleased().for_table_display()  # Add annotations
    return render(request, 'template.html', {'loans': loans})
```

---

### Issue 18: "Template shows 'None' for all values"

**Cause:** Loans don't have the collateral data

**Debug:**
```python
# Check the loans have collateral
loan = Loan.objects.first()
items = loan.loanitem_set.all()  # Check related items
print(f"Items: {items.count()}")

for item in items:
    print(f"  {item.metal_type}: {item.weight}")
```

**If no items:**
```python
# Create test data
from girvi.models import Loan, LoanItem

loan = Loan.objects.first()
LoanItem.objects.create(
    loan=loan,
    metal_type='Gold',
    weight=50,
    purity=91.5,
)
```

---

## Import Issues

### Issue 19: "Circular import error"

**Cause:** models.py imports from manager_improved.py which imports from services.py which imports from models.py

**Debug:**
```python
# Try importing each piece
try:
    from girvi.services import RateCacheService
    print("âœ“ services imports OK")
except ImportError as e:
    print(f"âœ— services import failed: {e}")

try:
    from girvi.manager_improved import ImprovedLoanManager
    print("âœ“ manager_improved imports OK")
except ImportError as e:
    print(f"âœ— manager_improved import failed: {e}")

try:
    from girvi.models import Loan
    print("âœ“ models imports OK")
except ImportError as e:
    print(f"âœ— models import failed: {e}")
```

**Fix:** Lazy imports in services.py
```python
# Wrong: Import at top
from girvi.models import Loan  # Too early

# Right: Import inside function
def get_stats():
    from girvi.models import Loan  # Inside function
    return Loan.objects.all()
```

---

## Testing & Validation

### Quick Health Check

```python
def health_check():
    """Run this to verify everything works"""
    
    from girvi.models import Loan
    from girvi.manager_improved import ImprovedLoanManager
    from girvi.services import RateCacheService
    from apps.tenant_apps.rates.models import Rate
    
    checks = {}
    
    # Check 1: Can import?
    checks['imports'] = 'âœ“'
    
    # Check 2: Do we have test data?
    checks['loans_exist'] = Loan.objects.count() > 0
    checks['unreleased_exist'] = Loan.objects.unreleased().count() > 0
    
    # Check 3: Do we have rates?
    checks['gold_rate'] = Rate.objects.filter(metal_type='Gold').exists()
    checks['silver_rate'] = Rate.objects.filter(metal_type='Silver').exists()
    checks['bronze_rate'] = Rate.objects.filter(metal_type='Bronze').exists()
    
    # Check 4: Can we query?
    if checks['unreleased_exist']:
        loans = Loan.objects.unreleased().for_table_display()[:1]
        checks['queries_work'] = loans.count() > 0
        if loans.exists():
            loan = loans.first()
            checks['annotations_work'] = hasattr(loan, 'gold_weight')
    
    # Check 5: Can we cache rates?
    rate = RateCacheService.get_rate('Gold')
    checks['rate_cache'] = rate is not None and rate > 0
    
    # Check 6: Can we get dashboard stats?
    try:
        stats = Loan.objects.non_performing_loans_stats()
        checks['dashboard_stats'] = 'count' in stats
    except:
        checks['dashboard_stats'] = False
    
    # Print results
    print("\n=== Health Check Results ===")
    for check, result in checks.items():
        status = 'âœ“' if result else 'âœ—'
        print(f"{status} {check}: {result}")
    
    return all(checks.values())

# Run it
if health_check():
    print("\nâœ“ All systems OK! Ready to use.")
else:
    print("\nâœ— Some checks failed. See above.")
```

---

## Getting Help

If you're still stuck:

1. **Run health check** (above)
2. **Check the full guide**: `LOAN_QUERY_ANNOTATIONS_GUIDE.md`
3. **Review migration guide**: `MIGRATION_GUIDE_OLD_TO_IMPROVED_MANAGERS.md`
4. **Check method reference**: `METHOD_SELECTION_GUIDE.md`
5. **Look at examples**: `LOAN_VIEWS_TEMPLATES_EXAMPLES.md`

---

## Error Message Index

| Error | Location | Fix |
|-------|----------|-----|
| Cannot resolve keyword 'X' | QuerySet filter | Add required annotation method |
| ModuleNotFoundError: manager_improved | Import | Use correct path: `apps.tenant_apps.girvi.manager_improved` |
| RateCacheService returns 0 | Rates display | Check Rate model has entries |
| Dashboard shows incorrect totals | Aggregation | Verify queryset filters are correct |
| Slow queries | Performance | Add pagination with Paginator |
| Memory error on export | Large dataset | Use `.iterator()` or `.values()` |
| Circular import | Import cycle | Move imports inside functions |
| Template shows None | Data missing | Check loan has related LoanItem objects |

---

**Still stuck? Print debug info and check against examples in the guides!**

