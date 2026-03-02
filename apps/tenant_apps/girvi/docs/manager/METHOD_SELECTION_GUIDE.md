# Method Selection Guide: Choosing the Right QuerySet Method

This guide helps you pick the right QuerySet method for your use case.

---

## Decision Tree

```
Need loan data?
│
├─ For table display (list all loans with metrics)?
│  └─► Use: Loan.objects.unreleased().for_table_display()
│       Returns: All annotations (weights, amounts, interest, values, status)
│
├─ For dashboard (aggregate stats)?
│  └─► Use: Loan.objects.for_dashboard_metrics()
│       Returns: Same annotations, ready to aggregate
│
├─ Need custom filter (e.g., only overdue)?
│  └─ Filter condition?
│     ├─ is_overdue = True?
│     │  └─► Use: Loan.objects.overdue()
│     │
│     ├─ months_since_created > 12?
│     │  └─► Use: Loan.objects.long_dead(months=12)
│     │
│     ├─ status = 'good_standing'?
│     │  └─► Use: Loan.objects.good_standing()
│     │
│     └─ Custom condition?
│        └─► Use: Loan.objects.for_table_display().filter(your_condition...)
│
├─ Just need specific annotations?
│  └─ Which ones?
│     ├─ Only duration? → with_duration_metrics()
│     ├─ Only interest? → with_interest_metrics()
│     ├─ Only weights? → with_metal_weights()
│     ├─ Only amounts? → with_itemwise_amounts()
│     ├─ Only values? → with_current_value()
│     ├─ Only status? → with_overdue_status()
│     └─ Multiple? → Chain them: .with_duration_metrics().with_interest_metrics()
│
└─ Using dashboard service directly?
   └─ Use: Loan.objects.non_performing_loans_stats()
            OR: Loan.objects.long_dead_loans_stats(threshold_months=12)
```

---

## Method Matrix

### Quick Reference

| Use Case | Method | Returns | Fields |
|----------|--------|---------|--------|
| Show all loans | `for_table_display()` | QuerySet | All 20+ fields |
| Show aggregated | `for_dashboard_metrics()` | QuerySet | All 20+ fields, ready to aggregate |
| Filter overdue | `overdue()` | QuerySet | With `is_overdue` annotation |
| Filter old loans | `long_dead()` | QuerySet | With `months_since_created` |
| Filter good status | `good_standing()` | QuerySet | Filtered by status |
| Dashboard stats | `non_performing_loans_stats()` | Dict | Count, totals, metals breakdown |
| Long-dead stats | `long_dead_loans_stats()` | Dict | Count, totals, metals breakdown |

---

## Detailed Method Reference

### 1. for_table_display()

**Purpose:** Get everything needed for a loan table view

**Chains:** All 6 methods
- `with_duration_metrics()`
- `with_metal_weights()`
- `with_itemwise_amounts()`
- `with_interest_metrics()`
- `with_current_value()`
- `with_overdue_status()`

**Usage:**
```python
loans = Loan.objects.unreleased().for_table_display()

# In template:
{% for loan in loans %}
  <tr>
    <td>{{ loan.duration_in_months }}</td>
    <td>{{ loan.gold_weight }}</td>
    <td>{{ loan.gold_loanamount }}</td>
    <td>{{ loan.total_interest }}</td>
    <td>{{ loan.gold_value }}</td>
    <td>{{ loan.is_overdue|yesno:"Yes,No" }}</td>
  </tr>
{% endfor %}
```

**Performance:** 1-2 queries (with proper select_related)

**When to use:**
- ✅ Table views with multiple metrics
- ✅ Reports showing loan details
- ❌ NOT for aggregations (use `for_dashboard_metrics()`)
- ❌ NOT if you only need 1-2 fields (use individual methods)

---

### 2. for_dashboard_metrics()

**Purpose:** Get annotations ready for aggregation

**Chains:** Same as `for_table_display()` but intended for aggregation

**Usage:**
```python
from django.db.models import Sum, Count

# Get single stat
total_due = (
    Loan.objects
    .unreleased()
    .for_dashboard_metrics()
    .aggregate(total=Sum('total_due'))
)

# Get multiple stats
stats = (
    Loan.objects
    .unreleased()
    .for_dashboard_metrics()
    .aggregate(
        count=Count('id'),
        total_amount=Sum('total_loanamount'),
        total_due=Sum('total_due'),
        total_interest=Sum('total_interest'),
    )
)
```

**Performance:** 1-2 queries

**When to use:**
- ✅ Aggregation queries
- ✅ Dashboard calculations
- ✅ Report totals
- ❌ NOT for displaying individual rows

---

### 3. Convenience Filters

#### 3.1 overdue()
```python
# Get only overdue loans
loans = Loan.objects.overdue()  # All released + unreleased overdue

# Overdue unreleased
loans = Loan.objects.unreleased().overdue()

# In views
def overdue_view(request):
    loans = Loan.objects.overdue().for_table_display()
    return render(request, 'overdue.html', {'loans': loans})
```

**Performance:** 1 query (filter only)

#### 3.2 good_standing()
```python
# Get only loans in good standing
loans = Loan.objects.good_standing().for_table_display()
```

**Performance:** 1 query (filter only)

#### 3.3 long_dead(months=12)
```python
# Get loans dormant for >12 months
loans = Loan.objects.long_dead(months=12)

# Chainable with other filters
loans = Loan.objects.unreleased().long_dead().for_table_display()
```

**Performance:** 1-2 queries (duration annotation + filter)

---

### 4. Individual Annotation Methods

#### 4.1 with_duration_metrics()

**Adds:**
- `days_since_created`
- `months_since_created`
- `days_to_release`
- `months_to_release`

```python
loans = Loan.objects.unreleased().with_duration_metrics()
for loan in loans:
    print(f"{loan.id}: {loan.months_since_created} months old")
```

#### 4.2 with_interest_metrics()

**Adds:**
- `total_interest`
- `total_due`
- `per_month_interest`

```python
loans = Loan.objects.unreleased().with_interest_metrics()
total_interest = loans.aggregate(Sum('total_interest'))
```

#### 4.3 with_metal_weights()

**Adds for each metal (Gold, Silver, Bronze):**
- `{metal}_weight` (total weight)
- `pure_{metal}_weight` (pure weight)

```python
loans = Loan.objects.unreleased().with_metal_weights()
for loan in loans:
    print(f"Gold: {loan.gold_weight} gm (pure: {loan.pure_gold_weight})")
    print(f"Silver: {loan.silver_weight} gm")
    print(f"Bronze: {loan.bronze_weight} gm")
```

#### 4.4 with_itemwise_amounts()

**Adds for each metal:**
- `{metal}_loanamount` (loan amount for this metal)
- `total_loanamount` (sum of all metals)

```python
loans = Loan.objects.unreleased().with_itemwise_amounts()
for loan in loans:
    print(f"Gold loan: {loan.gold_loanamount}")
    print(f"Silver loan: {loan.silver_loanamount}")
    print(f"Total: {loan.total_loanamount}")
```

#### 4.5 with_current_value()

**Adds for each metal:**
- `{metal}_value` (current market value)
- `total_current_value` (sum of all metals)

```python
loans = Loan.objects.unreleased().with_current_value()
for loan in loans:
    print(f"Current gold value: {loan.gold_value}")
    print(f"Total collateral value: {loan.total_current_value}")
```

#### 4.6 with_overdue_status()

**Adds:**
- `is_overdue` (boolean)

```python
loans = Loan.objects.for_table_display().filter(is_overdue=True)
```

---

### 5. Dashboard Service Methods

#### 5.1 non_performing_loans_stats()

**Returns:** Dict with keys:

```python
stats = Loan.objects.non_performing_loans_stats()

# Result structure:
{
    'count': 45,
    'total_due': Decimal('2500000.00'),
    'total_principal': Decimal('2000000.00'),
    'metals': {
        'Gold': {
            'weight': Decimal('150.50'),
            'pure_weight': Decimal('145.25'),
            'value': Decimal('850000.00'),
            'rate': Decimal('5666.25'),  # Current market rate
            'rate_timestamp': datetime(...),
            'loan_amount': Decimal('900000.00'),
            'items_count': 12,
        },
        'Silver': {...},
        'Bronze': {...},
    },
    'total_collateral_value': Decimal('1250000.00'),
    'current_rates': {
        'Gold': 5666.25,
        'Silver': 75.50,
        'Bronze': 2.25,
    },
    'rates_timestamp': datetime(...),
}
```

**Definition:** Loans with `is_overdue=True`

**Usage:**
```python
def dashboard_view(request):
    non_perf = Loan.objects.non_performing_loans_stats()
    
    context = {
        'overdue_count': non_perf['count'],
        'overdue_due_amount': non_perf['total_due'],
        'gold_value': non_perf['metals']['Gold']['value'],
        'gold_rate': non_perf['current_rates']['Gold'],
    }
    return render(request, 'dashboard.html', context)
```

#### 5.2 long_dead_loans_stats(threshold_months=None)

**Returns:** Same structure as `non_performing_loans_stats()`

**Definition:** Loans with `months_since_created >= threshold_months` and either:
- `is_overdue=True`, OR
- No recent activity

**Default threshold:** 12 months

**Usage:**
```python
# Get stats for 12-month old loans
long_dead = Loan.objects.long_dead_loans_stats()

# Get stats for 6-month old loans
long_dead_6m = Loan.objects.long_dead_loans_stats(threshold_months=6)

# Get stats for very old loans
long_dead_24m = Loan.objects.long_dead_loans_stats(threshold_months=24)
```

---

## Chaining Guide

### Valid Chains

All these work:

```python
# Add annotations one by one
loans = (Loan.objects
    .unreleased()
    .with_duration_metrics()
    .with_metal_weights()
)

# Or use the convenience methods
loans = Loan.objects.unreleased().for_table_display()

# Or chain multiple
loans = (Loan.objects
    .unreleased()
    .with_duration_metrics()
    .with_interest_metrics()
    .with_current_value()
    .filter(is_overdue=True)
)

# Or start with filters then add annotations
loans = (Loan.objects
    .unreleased()
    .filter(loan_status='active')  # Django ORM filter
    .for_table_display()           # Add our annotations
)
```

### Invalid Chains

❌ These don't work:

```python
# Can't use dashboard method with table display (they're independent)
loans = Loan.objects.for_table_display().for_dashboard_metrics()

# Can't use convenience methods twice
loans = Loan.objects.overdue().good_standing()  # Contradictory!

# Can't aggregate without chaining first
stats = Loan.objects.aggregate(Count('id'))  # No annotations!
# Instead:
stats = Loan.objects.for_dashboard_metrics().aggregate(Count('id'))
```

---

## Performance Recommendations

| Scenario | Method | Queries | Speed |
|----------|--------|---------|-------|
| Single loan | `.for_table_display()` | 1-2 | Fast |
| Table view (20 loans) | `.for_table_display()` | 1-2 | Fast |
| Large export (5000 loans) | `.values()` + specific fields | 1 | Fastest |
| Dashboard tile | `.non_performing_loans_stats()` | 1-2 | Fast |
| Complex filter + aggregate | Chain + `.aggregate()` | 2-3 | Medium |

### Optimization Tips

1. **Use select_related() for foreign keys:**
   ```python
   loans = (Loan.objects
       .unreleased()
       .select_related('customer', 'series')  # Add if filtering by these
       .for_table_display()
   )
   ```

2. **Use only() to limit fields:**
   ```python
   loans = (Loan.objects
       .unreleased()
       .only('id', 'loan_id', 'customer')
       .for_table_display()
   )
   ```

3. **Use .values() for exports:**
   ```python
   # Faster than model instances
   loans = (Loan.objects
       .unreleased()
       .for_table_display()
       .values('id', 'loan_id', 'gold_weight', 'total_interest')
   )
   ```

4. **Use pagination with large sets:**
   ```python
   from django.core.paginator import Paginator
   
   loans = Loan.objects.unreleased().for_table_display()
   paginator = Paginator(loans, 50)  # 50 per page
   page = paginator.get_page(request.GET.get('page'))
   ```

---

## Common Use Cases

### Use Case 1: Loan Status Dashboard

```python
def dashboard(request):
    # Non-performing loans stats
    non_perf = Loan.objects.non_performing_loans_stats()
    
    # Long-dead loans stats
    long_dead = Loan.objects.long_dead_loans_stats(threshold_months=12)
    
    # Good standing count
    good_standing = Loan.objects.good_standing().count()
    
    context = {
        'non_performing': non_perf,
        'long_dead': long_dead,
        'good_standing_count': good_standing,
    }
    return render(request, 'dashboard.html', context)
```

### Use Case 2: Detailed Loan Table

```python
def loan_list(request):
    loans = Loan.objects.unreleased().for_table_display()
    
    # Optional: Filter by status
    if status := request.GET.get('status'):
        loans = loans.filter(loan_status=status)
    
    # Optional: Sort by any annotation
    if sort := request.GET.get('sort'):
        loans = loans.order_by(sort)
    
    # Paginate
    from django.core.paginator import Paginator
    paginator = Paginator(loans, 25)
    page = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'loans/list.html', {'page': page})
```

### Use Case 3: Export to CSV

```python
import csv
from django.http import HttpResponse

def export_loans(request):
    loans = (Loan.objects
        .unreleased()
        .for_table_display()
        .values(
            'loan_id',
            'gold_weight',
            'gold_loanamount',
            'total_interest',
            'gold_value',
            'is_overdue'
        )
    )
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="loans.csv"'
    
    writer = csv.DictWriter(response, fieldnames=[...])
    writer.writeheader()
    writer.writerows(loans)
    
    return response
```

### Use Case 4: Custom Aggregations

```python
from django.db.models import Sum, Count, Avg

def analytics(request):
    stats = (Loan.objects
        .unreleased()
        .for_dashboard_metrics()
        .aggregate(
            total_loans=Count('id'),
            total_amount=Sum('total_loanamount'),
            avg_amount=Avg('total_loanamount'),
            total_due=Sum('total_due'),
            total_gold=Sum('gold_weight'),
            total_gold_value=Sum('gold_value'),
        )
    )
    
    return render(request, 'analytics.html', {'stats': stats})
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Cannot resolve keyword 'gold_weight'" | Forgot annotation | Add `.with_metal_weights()` |
| "Cannot resolve keyword 'is_overdue'" | Forgot annotation | Add `.with_overdue_status()` |
| "Rates showing as 0" | Rate model empty | Check Rate model entries |
| "FieldError: Cannot resolve keyword 'xyz'" | Typo in field name | Check docstring for exact names |
| "Slow queries" | No pagination | Add pagination for large sets |
| "Memory error" | Loading too many rows | Use `.values()` or pagination |

---

## Summary

**Pick your method:**
- Display all metrics → `for_table_display()`
- Aggregate stats → `for_dashboard_metrics()`
- Just filter → `overdue()`, `good_standing()`, `long_dead()`
- Just one metric → Individual methods like `with_metal_weights()`
- Dashboard analysis → `non_performing_loans_stats()`, `long_dead_loans_stats()`

**Then chain if needed:**
```python
Loan.objects.unreleased().for_table_display().filter(is_overdue=True).order_by('-created_at')
```

**And aggregate if needed:**
```python
Loan.objects.for_dashboard_metrics().aggregate(total=Sum('total_due'))
```

**Questions?** See the full guides:
- `LOAN_QUERY_ANNOTATIONS_GUIDE.md` - Complete reference
- `MIGRATION_GUIDE_OLD_TO_IMPROVED_MANAGERS.md` - Migration steps
- `LOAN_VIEWS_TEMPLATES_EXAMPLES.md` - Ready-to-use code
