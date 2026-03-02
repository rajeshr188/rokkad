# Loan Annotations - Quick Reference Card

Use this as a quick lookup for the most common queries.

## For Table Display

### Display all unreleased loans with metrics
```python
loans = Loan.objects.unreleased().select_related('customer', 'series').for_table_display()

# Available fields per loan:
# - days_since_created, months_since_created
# - gold_weight, pure_gold_weight, gold_loanamount, gold_value
# - silver_weight, pure_silver_weight, silver_loanamount, silver_value
# - bronze_weight, pure_bronze_weight, bronze_loanamount, bronze_value
# - loan_amount, total_interest, total_due, total_current_value
# - is_overdue (True/False)
```

### Display only overdue loans
```python
overdue = (
    Loan.objects.unreleased()
    .for_table_display()
    .filter(is_overdue=True)
)
```

### Sort by oldest loans
```python
loans = (
    Loan.objects.unreleased()
    .for_table_display()
    .order_by('months_since_created')  # Newest first
)
```

### Sort by highest due amount
```python
loans = (
    Loan.objects.unreleased()
    .for_table_display()
    .order_by('-total_due')
)
```

---

## For Dashboards

### Get non-performing loans stats
```python
stats = Loan.objects.non_performing_loans_stats()

# Returns dict with:
# stats['count'] - number of loans
# stats['total_due'] - total amount owed
# stats['total_collateral_value'] - total value of collateral
# stats['metals']['Gold']['value'] - gold value
# stats['metals']['Silver']['value'] - silver value
# stats['metals']['Bronze']['value'] - bronze value
# stats['current_rates'] - {'Gold': X, 'Silver': Y, 'Bronze': Z}
# stats['rates_timestamp'] - when rates were fetched
```

### Get long-dead loans (12+ months)
```python
stats = Loan.objects.long_dead_loans_stats()

# Same structure as non_performing stats
```

### Get long-dead loans (custom threshold)
```python
stats = Loan.objects.long_dead_loans_stats(threshold_months=6)
```

---

## For Filtering & Aggregation

### Count loans by status
```python
from django.db.models import Count, Q

stats = Loan.objects.unreleased().for_dashboard_metrics().aggregate(
    total=Count('id'),
    overdue=Count('id', filter=Q(is_overdue=True)),
    good=Count('id', filter=Q(is_overdue=False)),
)

# stats['total'] = 100
# stats['overdue'] = 25
# stats['good'] = 75
```

### Sum due amounts by status
```python
from django.db.models import Sum, Q

stats = Loan.objects.unreleased().for_dashboard_metrics().aggregate(
    all_due=Sum('total_due'),
    overdue_due=Sum('total_due', filter=Q(is_overdue=True)),
    good_due=Sum('total_due', filter=Q(is_overdue=False)),
)
```

### Get average collateral value
```python
from django.db.models import Avg

avg = Loan.objects.unreleased().for_dashboard_metrics().aggregate(
    avg_value=Avg('total_current_value')
)

# avg['avg_value'] = 45000
```

### Find loans by age
```python
# Recent loans (0-3 months)
recent = Loan.objects.unreleased().for_dashboard_metrics().filter(
    months_since_created__lte=3
)

# Mature loans (3-12 months)
mature = Loan.objects.unreleased().for_dashboard_metrics().filter(
    months_since_created__gt=3,
    months_since_created__lte=12
)

# Ancient loans (12+ months)
ancient = Loan.objects.unreleased().for_dashboard_metrics().filter(
    months_since_created__gt=12
)
```

---

## For Custom Queries

### Only get weights (no interest/value)
```python
loans = (
    Loan.objects.unreleased()
    .with_duration_metrics()
    .with_metal_weights()
)

# Fast, minimal annotations
```

### Get weights and values (but not interest)
```python
loans = (
    Loan.objects.unreleased()
    .with_metal_weights()
    .with_current_value()
)

# Good for collateral verification
```

### Order by weight
```python
loans = (
    Loan.objects.unreleased()
    .with_metal_weights()
    .order_by('-gold_weight')
)
```

### Find loans with specific metals
```python
from django.db.models import Q

gold_loans = (
    Loan.objects.unreleased()
    .with_metal_weights()
    .filter(gold_weight__gt=0)
)

silver_only = (
    Loan.objects.unreleased()
    .with_metal_weights()
    .filter(silver_weight__gt=0, gold_weight=0, bronze_weight=0)
)
```

---

## For Rate Management

### Get current gold rate
```python
from girvi.services import RateCacheService

rate = RateCacheService.get_rate('Gold')
```

### Get all rates
```python
rates = RateCacheService.get_all_rates()
# rates['Gold'] = 80
# rates['Silver'] = 0.90
# rates['Bronze'] = 0.15
```

### Refresh rates (after import)
```python
RateCacheService.invalidate()

# Next query will fetch fresh rates from database
```

---

## Template Usage

### Display single loan row
```html
<tr>
    <td>{{ loan.loan_id }}</td>
    <td>{{ loan.months_since_created|floatformat:0 }}m</td>
    <td>{{ loan.gold_weight|floatformat:3 }}g @ ₹{{ loan.gold_value|floatformat:0 }}</td>
    <td>₹{{ loan.total_due|floatformat:0 }}</td>
    <td>₹{{ loan.total_current_value|floatformat:0 }}</td>
    <td>
        {% if loan.is_overdue %}
            <span class="badge bg-danger">Overdue</span>
        {% else %}
            <span class="badge bg-success">Good</span>
        {% endif %}
    </td>
</tr>
```

### Display dashboard card
```html
<div class="card">
    <h5>Non-Performing Loans</h5>
    <p>Count: {{ non_perf.count }}</p>
    <p>Total Due: ₹{{ non_perf.total_due|floatformat:0 }}</p>
    <p>Shortfall: ₹{{ non_perf.total_due|add:non_perf.total_collateral_value|floatformat:0 }}</p>
    
    <h6>Gold: {{ non_perf.metals.Gold.pure_weight|floatformat:2 }}g @ ₹{{ non_perf.metals.Gold.value|floatformat:0 }}</h6>
    <h6>Silver: {{ non_perf.metals.Silver.pure_weight|floatformat:2 }}g @ ₹{{ non_perf.metals.Silver.value|floatformat:0 }}</h6>
</div>
```

---

## CSV Export

```python
import csv
from django.http import HttpResponse

def export_loans(request):
    loans = Loan.objects.unreleased().for_table_display()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="loans.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Customer', 'Months', 'Gold(g)', 'Silver(g)', 'Amount', 'Due', 'Value', 'Status'])
    
    for loan in loans:
        writer.writerow([
            loan.loan_id,
            loan.customer.get_full_name(),
            int(loan.months_since_created),
            f"{loan.gold_weight:.2f}",
            f"{loan.silver_weight:.2f}",
            f"{loan.loan_amount:.0f}",
            f"{loan.total_due:.0f}",
            f"{loan.total_current_value:.0f}",
            'Overdue' if loan.is_overdue else 'Good'
        ])
    
    return response
```

---

## Common Errors & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `Cannot resolve keyword 'is_overdue'` | Missing annotation | Add `.with_overdue_status()` |
| `Cannot resolve keyword 'total_due'` | Missing annotation | Add `.with_interest_metrics()` |
| `Cannot resolve keyword 'total_current_value'` | Missing annotation | Add `.with_current_value()` |
| Slow queries | Too many annotations | Use only needed methods |
| Rates show as 0 | No Rate objects | Add rates to Rate model |
| Memory error | Loading too many rows | Add `.values()` or paginate |

---

## Method Dependencies

**IMPORTANT:** These methods depend on others being called first!

```
with_duration_metrics()
    ↓
    └─→ with_interest_metrics() needs this

with_metal_weights()
    ↓
    └─→ with_current_value() needs this
    └─→ with_overdue_status() needs this (if comparing value < due)

For complete setup, use:
    for_table_display() OR for_dashboard_metrics()
```

---

## Performance Tips

| Tip | Impact |
|-----|--------|
| Use `select_related()` for ForeignKeys | 10-50x faster |
| Use `prefetch_related()` for reverse relations | 10-100x faster |
| Add database indexes | 10-100x faster |
| Only request needed annotations | 2-5x faster |
| Use `.values()` for aggregations | 10-50x faster |

---

## Useful Django ORM Patterns

### Get top 10 loans by due amount
```python
Loan.objects.unreleased().for_table_display().order_by('-total_due')[:10]
```

### Get first loan
```python
Loan.objects.unreleased().for_table_display().first()
```

### Get last loan by date
```python
Loan.objects.unreleased().for_table_display().order_by('-loan_date').first()
```

### Check if any overdue
```python
Loan.objects.unreleased().for_dashboard_metrics().filter(is_overdue=True).exists()
```

### Count specific type
```python
Loan.objects.unreleased().for_table_display().filter(gold_weight__gt=0).count()
```

### Update multiple loans
```python
Loan.objects.filter(id__in=[1,2,3]).update(status='REVIEWED')
```

---

## Debug Info

### Print SQL query
```python
from django.db import connection

loans = Loan.objects.unreleased().for_table_display()

# Force evaluation
list(loans)

# Print SQL
print(loans.query)

# Print all queries
for query in connection.queries:
    print(query['sql'])
```

### Check database indexes
```sql
-- Check existing indexes
SELECT * FROM pg_indexes WHERE tablename='girvi_loan';

-- Add index if missing
CREATE INDEX idx_loan_status ON girvi_loan(status);
CREATE INDEX idx_loan_release ON girvi_loan(release_id);
```

### Test performance
```bash
# Run with DEBUG=True (development only)
# Check Django shell: len(connection.queries)

python manage.py shell
>>> from django.db import connection, reset_queries
>>> from django.conf import settings
>>> settings.DEBUG = True
>>> loans = Loan.objects.unreleased().for_table_display()[:100]
>>> list(loans)
>>> len(connection.queries)  # Shows number of queries
>>> for q in connection.queries: print(q['time'])  # Shows time per query
```

---

## Saving This Card

**To use offline:**
1. Save as PDF or print this page
2. Keep in your project documentation
3. Reference when writing views

**In your IDE:**
Add as a snippet in VS Code: Settings → User Snippets → python
