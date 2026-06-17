---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Loan Query Annotations - Usage Guide

This guide shows how to use the new modular, chainable QuerySet methods for displaying loan data in tables and dashboards.

## Table of Contents
1. [Overview](#overview)
2. [Individual Annotation Methods](#individual-annotation-methods)
3. [Quick Start - Table Display](#quick-start---table-display)
4. [Quick Start - Dashboard](#quick-start---dashboard)
5. [Advanced Usage](#advanced-usage)
6. [API Reference](#api-reference)

---

## Overview

**Old Approach:**
```python
# Massive 150+ line method with all annotations at once
loans = Loan.objects.unreleased().with_details(grate, srate, brate)
# Hard to compose, hard to modify, hard to test
```

**New Approach:**
```python
# Chain only what you need
loans = (
    Loan.objects.unreleased()
    .with_duration_metrics()      # Add time metrics
    .with_metal_weights()          # Add weight metrics
    .with_current_value()          # Add value metrics (requires weights!)
    .filter(is_overdue=True)       # Filter on computed values
)
```

**Benefits:**
- âœ… Compose exactly what you need
- âœ… Much easier to test individual pieces
- âœ… Clearer performance requirements
- âœ… Easy to modify one calculation without affecting others

---

## Individual Annotation Methods

### Duration Metrics

Add time-based measurements:

```python
loans = Loan.objects.with_duration_metrics()

# Adds these fields to each loan:
# - days_since_created: int - number of days since loan creation (or release date)
# - months_since_created: int - number of months (more accurate than days/30)

for loan in loans:
    print(f"{loan.loan_id}: {loan.days_since_created} days, {loan.months_since_created} months")
```

### Interest Metrics

Calculate interest and payment information (REQUIRES `with_duration_metrics()`):

```python
loans = Loan.objects\
    .with_duration_metrics()\
    .with_interest_metrics()

# Adds:
# - total_interest: decimal - interest * months
# - total_due: decimal - loan_amount + total_interest

# Example: Find loans where interest accrued is high
high_interest = loans.annotate(
    interest_ratio=F('total_interest') / F('loan_amount')
).filter(interest_ratio__gt=0.5)
```

### Metal Weights

Get itemwise weights broken down by metal type:

```python
loans = Loan.objects.with_metal_weights()

# Adds for each metal type (Gold, Silver, Bronze):
# - gold_weight: decimal - gross weight of gold items
# - pure_gold_weight: decimal - weight adjusted by purity (0.75 purity = 75%)
# - silver_weight, pure_silver_weight
# - bronze_weight, pure_bronze_weight

for loan in loans:
    print(f"Gold: {loan.gold_weight}g (pure: {loan.pure_gold_weight}g)")
    print(f"Silver: {loan.silver_weight}g (pure: {loan.pure_silver_weight}g)")
```

### Itemwise Loan Amounts

Get loan amounts broken down by metal type:

```python
loans = Loan.objects.with_itemwise_amounts()

# Adds:
# - gold_loanamount: decimal
# - silver_loanamount: decimal
# - bronze_loanamount: decimal

for loan in loans:
    total = (
        loan.gold_loanamount +
        loan.silver_loanamount +
        loan.bronze_loanamount
    )
    print(f"Total borrowed: â‚¹{total}")
```

### Current Value

Calculate collateral value at current market rates (REQUIRES `with_metal_weights()`):

```python
loans = Loan.objects\
    .with_metal_weights()\
    .with_current_value()

# Adds:
# - gold_value: decimal - pure_gold_weight * current_gold_rate
# - silver_value: decimal - pure_silver_weight * current_silver_rate
# - bronze_value: decimal - pure_bronze_weight * current_bronze_rate
# - total_current_value: decimal - sum of all metal values

# Uses live rates from Rate model (cached for 5 minutes)

for loan in loans:
    print(f"Collateral value: â‚¹{loan.total_current_value}")
```

### Overdue Status

Determine if loan is overdue (REQUIRES `with_interest_metrics()` and `with_current_value()`):

```python
loans = (
    Loan.objects
    .with_duration_metrics()
    .with_interest_metrics()
    .with_metal_weights()
    .with_current_value()
    .with_overdue_status()
)

# Adds:
# - is_overdue: boolean - True if current_value < total_due

overdue = loans.filter(is_overdue=True)
print(f"Overdue loans: {overdue.count()}")
```

---

## Quick Start - Table Display

### Use Case: Display all loans in a table with full metrics

```python
# View (views.py)
def loan_table_view(request):
    loans = (
        Loan.objects
        .unreleased()
        .select_related('customer', 'series')
        .for_table_display()  # Convenience method: all annotations
    )
    
    return render(request, 'girvi/loan_table.html', {'loans': loans})
```

### Template (loan_table.html)

```html
<table>
    <thead>
        <tr>
            <th>Loan ID</th>
            <th>Duration (Months)</th>
            <th>Gold Weight</th>
            <th>Gold Pure Weight</th>
            <th>Gold Amount</th>
            <th>Silver Weight</th>
            <th>Interest Due</th>
            <th>Total Due</th>
            <th>Current Value</th>
            <th>Status</th>
        </tr>
    </thead>
    <tbody>
        {% for loan in loans %}
        <tr class="{% if loan.is_overdue %}table-danger{% endif %}">
            <td>{{ loan.loan_id }}</td>
            <td>{{ loan.months_since_created }}</td>
            <td>{{ loan.gold_weight|floatformat:3 }}</td>
            <td>{{ loan.pure_gold_weight|floatformat:3 }}</td>
            <td>â‚¹{{ loan.gold_loanamount|floatformat:2 }}</td>
            <td>{{ loan.silver_weight|floatformat:3 }}</td>
            <td>â‚¹{{ loan.total_interest|floatformat:2 }}</td>
            <td>â‚¹{{ loan.total_due|floatformat:2 }}</td>
            <td>â‚¹{{ loan.total_current_value|floatformat:2 }}</td>
            <td>
                {% if loan.is_overdue %}
                    <span class="badge bg-danger">Overdue</span>
                {% else %}
                    <span class="badge bg-success">Good</span>
                {% endif %}
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>
```

---

## Quick Start - Dashboard

### Use Case 1: Non-Performance Loans Summary

```python
# View
def dashboard_view(request):
    # Get aggregated stats for non-performing loans
    non_perf = Loan.objects.non_performing_loans_stats()
    
    context = {
        'non_performing': non_perf,
    }
    return render(request, 'girvi/dashboard.html', context)
```

### Use Case 2: Long-Dead Loans Summary

```python
# View
def dashboard_view(request):
    # Loans unreleased for 12+ months
    long_dead = Loan.objects.long_dead_loans_stats()
    
    context = {
        'long_dead': long_dead,
    }
    return render(request, 'girvi/dashboard.html', context)
```

### Template (dashboard.html)

```html
<div class="dashboard">
    <!-- Non-Performing Loans Card -->
    <div class="card">
        <h5>Non-Performing Loans</h5>
        <div class="metrics">
            <div>
                <strong>Count:</strong> {{ non_performing.count }}
            </div>
            <div>
                <strong>Total Due:</strong> â‚¹{{ non_performing.total_due|floatformat:2 }}
            </div>
            <div>
                <strong>Total Collateral Value:</strong> 
                â‚¹{{ non_performing.total_collateral_value|floatformat:2 }}
            </div>
            <div>
                <strong>Difference (under-collateralized by):</strong>
                â‚¹{{ non_performing.total_due|add:non_performing.total_collateral_value|floatformat:2 }}
            </div>
        </div>
        
        <h6>Collateral Breakdown (Current Rates)</h6>
        <table>
            <tr>
                <th>Metal</th>
                <th>Gross Weight</th>
                <th>Pure Weight</th>
                <th>Rate</th>
                <th>Value</th>
            </tr>
            {% for metal, data in non_performing.metals.items %}
            <tr>
                <td>{{ metal }}</td>
                <td>{{ data.weight|floatformat:3 }}g</td>
                <td>{{ data.pure_weight|floatformat:3 }}g</td>
                <td>â‚¹{{ data.rate|floatformat:2 }}</td>
                <td>â‚¹{{ data.value|floatformat:2 }}</td>
            </tr>
            {% endfor %}
        </table>
        
        <small>Rates updated: {{ non_performing.rates_timestamp }}</small>
    </div>
    
    <!-- Long-Dead Loans Card -->
    <div class="card">
        <h5>Long-Dead Loans ({{ long_dead.threshold_months }}+ months)</h5>
        <!-- Same as above, but for long_dead data -->
    </div>
</div>
```

---

## Advanced Usage

### Custom Filtering & Aggregation

```python
# Get all non-released loans, order by overdue status, show top 50
loans = (
    Loan.objects.unreleased()
    .for_table_display()
    .filter(is_overdue=True)
    .order_by('-total_due')[:50]
)

# Advanced aggregation
from django.db.models import Count, Avg

stats = (
    Loan.objects.unreleased()
    .for_dashboard_metrics()
    .filter(is_overdue=True)
    .aggregate(
        count=Count('id'),
        total_due=Sum('total_due'),
        avg_duration=Avg('months_since_created'),
        avg_collateral_value=Avg('total_current_value'),
        total_gold=Sum('pure_gold_weight'),
    )
)

print(f"Overdue loans: {stats['count']}")
print(f"Average duration: {stats['avg_duration']:.1f} months")
print(f"Shortfall: â‚¹{stats['total_due'] - stats['avg_collateral_value']}")
```

### Selective Annotations

Only get what you need for performance:

```python
# Just weights and duration (fast)
loans = (
    Loan.objects.unreleased()
    .with_duration_metrics()
    .with_metal_weights()
)

# Add value calculation (requires current rates)
loans = loans.with_current_value()

# Add interest (for filtering/display)
loans = (
    loans
    .with_interest_metrics()
    .with_overdue_status()
)

# Filter on computed fields
old_overdue = loans.filter(
    months_since_created__gte=12,
    is_overdue=True
)
```

### Combining with Custom Querysets

```python
# Custom queryset combining multiple filters
class NonPerformingLoanManager(models.Manager):
    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(release__isnull=True)
            .for_dashboard_metrics()
            .filter(is_overdue=True)
        )

# Usage
non_perf_loans = NonPerformingLoan.objects.all()  # Already filtered & annotated
```

### Using with Pagination

```python
from django.core.paginator import Paginator

loans = Loan.objects.unreleased().for_table_display()
paginator = Paginator(loans, 25)
page_number = request.GET.get('page')
page_obj = paginator.get_page(page_number)

context = {'page_obj': page_obj}
```

---

## API Reference

### QuerySet Methods

**Duration & Time:**
- `with_duration_metrics()` - Add days/months since creation

**Financial:**
- `with_interest_metrics()` - Add interest and total due calculations
- `with_itemwise_amounts()` - Add loan amounts by metal type

**Physical Collateral:**
- `with_metal_weights()` - Add gross and pure weights by metal type
- `with_current_value()` - Add current collateral values (uses live rates)

**Status:**
- `with_overdue_status()` - Add overdue determination

**Convenience (combine multiple):**
- `for_table_display()` - All annotations for table rows
- `for_dashboard_metrics()` - Optimized for aggregations

### Manager Methods

**Dashboard Metrics:**
- `non_performing_loans_stats()` - Aggregated stats for non-performing loans
- `long_dead_loans_stats(threshold_months=None)` - Stats for long-dormant loans

### Services (if needed directly)

From `girvi.services`:

**RateCacheService:**
```python
from girvi.services import RateCacheService

rate = RateCacheService.get_rate('Gold')  # Get cached rate
rates = RateCacheService.get_all_rates()  # Get all three metals
RateCacheService.invalidate()  # Clear cache (when rates update)
```

**InterestCalculationService:**
```python
from girvi.services import InterestCalculationService

months = InterestCalculationService.months_between(loan.loan_date, end_date)
```

**DashboardMetricsService:**
```python
from girvi.services import DashboardMetricsService

metrics = DashboardMetricsService.get_non_performing_loans_stats()
metrics = DashboardMetricsService.get_long_dead_loans_stats(threshold_months=18)
```

---

## Performance Tips

1. **Use `select_related()` for ForeignKeys:**
   ```python
   loans = (
       Loan.objects.unreleased()
       .select_related('customer', 'series')
       .for_table_display()
   )
   ```

2. **Use `prefetch_related()` for reverse ForeignKeys:**
   ```python
   loans = (
       Loan.objects.unreleased()
       .prefetch_related('loanitems')
       .for_table_display()
   )
   ```

3. **Limit annotations if not needed:**
   ```python
   # Don't use for_table_display() for aggregations
   # Use for_dashboard_metrics() or individual methods instead
   
   # Bad (loads all annotations)
   total = loans.for_table_display().aggregate(total=Sum('loan_amount'))
   
   # Good (only needed annotations)
   total = Loan.objects.unreleased().aggregate(total=Sum('loan_amount'))
   ```

4. **The RateCacheService already caches for 5 minutes:**
   - Rates are cached automatically
   - To refresh manually: `RateCacheService.invalidate()`

5. **Use `.values()` for large aggregations:**
   ```python
   # If you only need aggregates, use values to exclude row data
   monthly_stats = (
       Loan.objects.unreleased()
       .annotate(month=TruncMonth('loan_date'))
       .values('month')
       .annotate(total=Sum('loan_amount'), count=Count('id'))
   )
   ```

---

## Troubleshooting

**Error: "Cannot resolve keyword 'is_overdue' in filter"**
- You haven't called `with_overdue_status()` yet
- Solution: Chain it before filtering

**Error: "Cannot resolve keyword 'total_current_value' in order_by"**
- You haven't called `with_current_value()` yet
- Solution: Call it before ordering

**Slow queries with many annotations?**
- Use only the methods you need
- Combine `select_related()` and `prefetch_related()` 
- Consider splitting into separate queries

**Rates showing as 0?**
- Check that Rate objects exist in the database for all metals
- Try: `Rate.objects.filter(metal__in=['Gold', 'Silver', 'Bronze'])`

---

## Migration from Old `with_details()` Method

If you have existing code using `with_details()`:

**Old:**
```python
loans = Loan.objects.with_details(grate, srate, brate)
```

**New:**
```python
loans = Loan.objects.for_table_display()  # Simpler, rate lookup automatic
```

The old method still exists for backwards compatibility but is deprecated. Migrate gradually to the new methods.

