# Code Snippets: Copy-Paste Ready

Quick, copy-paste code for the most common scenarios.

---

## 1️⃣ Setup (Do Once)

### Update Model

```python
# apps/tenant_apps/girvi/models/loan.py

# OLD
from ..managers import LoanManager, ReleasedManager, UnReleasedManager

# NEW
from ..manager_improved import (
    ImprovedLoanManager as LoanManager,
    ImprovedReleasedManager as ReleasedManager,
    ImprovedUnReleasedManager as UnReleasedManager,
)

class Loan(models.Model):
    # ... fields ...
    
    objects = LoanManager()
    released = ReleasedManager()
    unreleased = UnReleasedManager()
```

---

## 2️⃣ Table Display (Copy to Views)

### Basic Loan List

```python
# views.py

def loan_list(request):
    """Display all unreleased loans with metrics"""
    loans = Loan.objects.unreleased().for_table_display()
    
    # Optional: Filter
    if status := request.GET.get('status'):
        loans = loans.filter(loan_status=status)
    
    # Optional: Paginate
    from django.core.paginator import Paginator
    paginator = Paginator(loans, 25)
    page = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'loans/list.html', {'page': page})
```

### HTML Template

```html
<!-- templates/loans/list.html -->

<table class="table">
  <thead>
    <tr>
      <th>Loan ID</th>
      <th>Created</th>
      <th>Gold Weight</th>
      <th>Gold Amount</th>
      <th>Interest</th>
      <th>Current Value</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    {% for loan in page %}
      <tr>
        <td>{{ loan.loan_id }}</td>
        <td>{{ loan.created_date|date:"Y-m-d" }}</td>
        <td>{{ loan.gold_weight }} gm</td>
        <td>₹ {{ loan.gold_loanamount }}</td>
        <td>₹ {{ loan.total_interest }}</td>
        <td>₹ {{ loan.total_current_value }}</td>
        <td>
          {% if loan.is_overdue %}
            <span class="badge badge-danger">Overdue</span>
          {% else %}
            <span class="badge badge-success">On Time</span>
          {% endif %}
        </td>
      </tr>
    {% endfor %}
  </tbody>
</table>

<!-- Pagination -->
{% if page.has_other_pages %}
  <nav>
    {% if page.has_previous %}
      <a href="?page=1">First</a>
      <a href="?page={{ page.previous_page_number }}">Previous</a>
    {% endif %}
    
    <span>Page {{ page.number }} of {{ page.paginator.num_pages }}</span>
    
    {% if page.has_next %}
      <a href="?page={{ page.next_page_number }}">Next</a>
      <a href="?page={{ page.paginator.num_pages }}">Last</a>
    {% endif %}
  </nav>
{% endif %}
```

---

## 3️⃣ Dashboard (Copy to Views)

### Dashboard View

```python
# views.py

def dashboard(request):
    """Show loan statistics dashboard"""
    
    # Get stats for non-performing loans
    non_performing = Loan.objects.non_performing_loans_stats()
    
    # Get stats for long-dead loans (inactive for >12 months)
    long_dead = Loan.objects.long_dead_loans_stats(threshold_months=12)
    
    # Get summary counts
    total_loans = Loan.objects.unreleased().count()
    good_standing = Loan.objects.good_standing().count()
    
    context = {
        'total_loans': total_loans,
        'good_standing_count': good_standing,
        'overdue_count': non_performing['count'],
        'overdue_due': non_performing['total_due'],
        'overdue_collateral_value': non_performing['total_collateral_value'],
        'overdue_metals': non_performing['metals'],
        'overdue_rates': non_performing['current_rates'],
        
        'long_dead_count': long_dead['count'],
        'long_dead_due': long_dead['total_due'],
        'long_dead_collateral_value': long_dead['total_collateral_value'],
        'long_dead_metals': long_dead['metals'],
    }
    
    return render(request, 'dashboard.html', context)
```

### Dashboard Template

```html
<!-- templates/dashboard.html -->

<div class="container">
  <h1>Loan Dashboard</h1>
  
  <!-- Summary Cards -->
  <div class="row">
    <div class="col-md-3">
      <div class="card">
        <div class="card-body">
          <h5>Total Loans</h5>
          <p class="h3">{{ total_loans }}</p>
        </div>
      </div>
    </div>
    
    <div class="col-md-3">
      <div class="card">
        <div class="card-body">
          <h5>Good Standing</h5>
          <p class="h3 text-success">{{ good_standing_count }}</p>
        </div>
      </div>
    </div>
    
    <div class="col-md-3">
      <div class="card">
        <div class="card-body">
          <h5>Overdue</h5>
          <p class="h3 text-danger">{{ overdue_count }}</p>
        </div>
      </div>
    </div>
    
    <div class="col-md-3">
      <div class="card">
        <div class="card-body">
          <h5>Long Dead (12+ months)</h5>
          <p class="h3 text-warning">{{ long_dead_count }}</p>
        </div>
      </div>
    </div>
  </div>
  
  <!-- Overdue Details -->
  <div class="row mt-5">
    <div class="col-md-6">
      <h3>Overdue Loans</h3>
      <p>Amount Due: <strong>₹ {{ overdue_due }}</strong></p>
      <p>Collateral Value: <strong>₹ {{ overdue_collateral_value }}</strong></p>
      
      <h5>Collateral Breakdown</h5>
      <table class="table table-sm">
        <tr>
          <th>Metal</th>
          <th>Weight</th>
          <th>Value</th>
          <th>Rate</th>
        </tr>
        {% for metal, details in overdue_metals.items %}
          <tr>
            <td>{{ metal }}</td>
            <td>{{ details.pure_weight }} gm</td>
            <td>₹ {{ details.value }}</td>
            <td>₹ {{ details.rate }}/gm</td>
          </tr>
        {% endfor %}
      </table>
    </div>
    
    <div class="col-md-6">
      <h3>Long Dead Loans (12+ months)</h3>
      <p>Amount Due: <strong>₹ {{ long_dead_due }}</strong></p>
      <p>Collateral Value: <strong>₹ {{ long_dead_collateral_value }}</strong></p>
      
      <h5>Collateral Breakdown</h5>
      <table class="table table-sm">
        <tr>
          <th>Metal</th>
          <th>Weight</th>
          <th>Value</th>
        </tr>
        {% for metal, details in long_dead_metals.items %}
          <tr>
            <td>{{ metal }}</td>
            <td>{{ details.pure_weight }} gm</td>
            <td>₹ {{ details.value }}</td>
          </tr>
        {% endfor %}
      </table>
    </div>
  </div>
</div>
```

---

## 4️⃣ Filtering (Copy to Views)

### Filter Overdue Loans

```python
# views.py

def overdue_loans(request):
    """Show only overdue loans"""
    loans = Loan.objects.overdue().for_table_display()
    return render(request, 'loans/overdue.html', {'loans': loans})
```

### Filter Good Standing

```python
def good_standing_loans(request):
    """Show only loans in good standing"""
    loans = Loan.objects.good_standing().for_table_display()
    return render(request, 'loans/good_standing.html', {'loans': loans})
```

### Filter Long Dead

```python
def long_dead_loans(request):
    """Show loans dormant for >12 months"""
    loans = Loan.objects.long_dead(months=12).for_table_display()
    return render(request, 'loans/long_dead.html', {'loans': loans})
```

### Custom Filters

```python
def custom_filter(request):
    """Show loans matching custom criteria"""
    loans = Loan.objects.unreleased().for_table_display()
    
    # Filter by amount
    if min_amount := request.GET.get('min_amount'):
        loans = loans.filter(total_loanamount__gte=min_amount)
    
    # Filter by duration
    if months_old := request.GET.get('months_old'):
        loans = loans.filter(months_since_created__gte=months_old)
    
    # Filter by metal
    if metal := request.GET.get('metal'):
        field = f'{metal.lower()}_weight'
        loans = loans.filter(**{f'{field}__gt': 0})
    
    return render(request, 'loans/filtered.html', {'loans': loans})
```

---

## 5️⃣ Export to CSV (Copy to Views)

### Basic CSV Export

```python
# views.py
import csv
from django.http import HttpResponse

def export_loans_csv(request):
    """Export unreleased loans to CSV"""
    loans = (Loan.objects
        .unreleased()
        .for_table_display()
        .values(
            'loan_id',
            'customer__name',
            'gold_weight',
            'gold_loanamount',
            'total_interest',
            'total_due',
            'total_current_value',
            'is_overdue'
        )
    )
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="loans.csv"'
    
    fieldnames = [
        'Loan ID', 'Customer', 'Gold Weight (gm)', 
        'Amount', 'Interest', 'Due Amount', 'Current Value', 'Overdue'
    ]
    
    writer = csv.DictWriter(response, fieldnames=fieldnames)
    writer.writeheader()
    
    for loan in loans:
        writer.writerow({
            'Loan ID': loan['loan_id'],
            'Customer': loan['customer__name'],
            'Gold Weight (gm)': loan['gold_weight'],
            'Amount': loan['gold_loanamount'],
            'Interest': loan['total_interest'],
            'Due Amount': loan['total_due'],
            'Current Value': loan['total_current_value'],
            'Overdue': 'Yes' if loan['is_overdue'] else 'No',
        })
    
    return response
```

### Large Dataset Export (Memory Safe)

```python
def export_loans_large_csv(request):
    """Export loans to CSV (memory safe for large datasets)"""
    loans = (Loan.objects
        .unreleased()
        .for_table_display()
        .iterator(chunk_size=500)  # Load 500 at a time
    )
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="loans_large.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Loan ID', 'Customer', 'Gold Weight', 'Amount', 'Interest'])
    
    for loan in loans:
        writer.writerow([
            loan.loan_id,
            loan.customer.name if loan.customer else '',
            loan.gold_weight,
            loan.gold_loanamount,
            loan.total_interest,
        ])
    
    return response
```

---

## 6️⃣ Aggregations (Copy to Views)

### Sum All Metrics

```python
from django.db.models import Sum, Count, Avg

def aggregations(request):
    """Calculate aggregate statistics"""
    stats = (Loan.objects
        .unreleased()
        .for_dashboard_metrics()
        .aggregate(
            total_loans=Count('id'),
            total_amount=Sum('total_loanamount'),
            avg_amount=Avg('total_loanamount'),
            total_due=Sum('total_due'),
            total_interest=Sum('total_interest'),
            total_gold_weight=Sum('gold_weight'),
            total_gold_value=Sum('gold_value'),
            total_silver_weight=Sum('silver_weight'),
            total_bronze_weight=Sum('bronze_weight'),
        )
    )
    
    return render(request, 'aggregations.html', {'stats': stats})
```

### Group By Metals

```python
from django.db.models import Sum

def metals_breakdown(request):
    """Breakdown by metal type"""
    from girvi.models import LoanItem
    
    items = (LoanItem.objects
        .select_related('loan')
        .filter(loan__status='unreleased')
    )
    
    breakdown = (items
        .values('metal_type')
        .annotate(
            count=Count('id'),
            total_weight=Sum('weight'),
            total_pure_weight=Sum('pure_weight'),
        )
        .order_by('metal_type')
    )
    
    return render(request, 'metals.html', {'breakdown': breakdown})
```

---

## 7️⃣ Admin Actions (Copy to Admin)

### Admin List Display

```python
# admin.py
from django.contrib import admin
from .models import Loan

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = [
        'loan_id',
        'customer',
        'get_gold_weight',
        'get_total_amount',
        'get_total_interest',
        'get_is_overdue',
    ]
    list_filter = ['status', 'created_date']
    search_fields = ['loan_id', 'customer__name']
    
    def get_queryset(self, request):
        """Use improved queryset with all annotations"""
        return Loan.objects.for_table_display()
    
    @admin.display(description='Gold Weight (gm)')
    def get_gold_weight(self, obj):
        return obj.gold_weight
    
    @admin.display(description='Amount')
    def get_total_amount(self, obj):
        return obj.total_loanamount
    
    @admin.display(description='Interest')
    def get_total_interest(self, obj):
        return obj.total_interest
    
    @admin.display(description='Overdue', boolean=True)
    def get_is_overdue(self, obj):
        return obj.is_overdue
```

---

## 8️⃣ API Serializers (Copy to Serializers)

### DRF Serializer

```python
# serializers.py
from rest_framework import serializers
from .models import Loan

class LoanDetailSerializer(serializers.ModelSerializer):
    # Duration
    days_since_created = serializers.IntegerField(read_only=True)
    months_since_created = serializers.IntegerField(read_only=True)
    
    # Metals
    gold_weight = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    gold_loanamount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    gold_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    silver_weight = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    silver_loanamount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    silver_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    bronze_weight = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    bronze_loanamount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    bronze_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    
    # Interest & Status
    total_interest = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_current_value = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Loan
        fields = [
            'id', 'loan_id', 'customer',
            'days_since_created', 'months_since_created',
            'gold_weight', 'gold_loanamount', 'gold_value',
            'silver_weight', 'silver_loanamount', 'silver_value',
            'bronze_weight', 'bronze_loanamount', 'bronze_value',
            'total_interest', 'total_due', 'total_current_value',
            'is_overdue',
        ]

class LoanListAPIView(generics.ListAPIView):
    serializer_class = LoanDetailSerializer
    
    def get_queryset(self):
        return Loan.objects.unreleased().for_table_display()
```

---

## 9️⃣ Rate Caching (Copy to Services)

### Manual Rate Cache Check

```python
from girvi.services import RateCacheService

# Get single rate
gold_rate = RateCacheService.get_rate('Gold')
print(f"Current Gold rate: {gold_rate}")

# Get all rates
all_rates = RateCacheService.get_all_rates()
print(f"All rates: {all_rates}")

# Invalidate cache manually
RateCacheService.invalidate()
```

### Using in View

```python
def loan_valuation(request, loan_id):
    """Calculate loan valuation with current rates"""
    from girvi.services import RateCacheService
    
    loan = Loan.objects.for_table_display().get(id=loan_id)
    
    # Rates are automatically cached
    rates = RateCacheService.get_all_rates()
    
    context = {
        'loan': loan,
        'gold_rate': rates.get('Gold'),
        'silver_rate': rates.get('Silver'),
        'bronze_rate': rates.get('Bronze'),
        'timestamp': RateCacheService.get_cache_timestamp(),
    }
    
    return render(request, 'valuation.html', context)
```

---

## 🔟 API Endpoints (Copy to URLs)

### URL Configuration

```python
# urls.py
from django.urls import path
from . import views, api_views

urlpatterns = [
    # Views
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/overdue/', views.overdue_loans, name='overdue_loans'),
    path('loans/good-standing/', views.good_standing_loans, name='good_standing'),
    path('loans/long-dead/', views.long_dead_loans, name='long_dead'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Exports
    path('export/loans/csv/', views.export_loans_csv, name='export_csv'),
    path('export/loans/large/csv/', views.export_loans_large_csv, name='export_large_csv'),
    
    # API
    path('api/loans/', api_views.LoanListAPIView.as_view(), name='api_loans'),
    path('api/stats/', api_views.LoanStatsAPIView.as_view(), name='api_stats'),
]
```

---

## ✅ Quick Health Check

### Run This to Verify

```python
# Django shell: python manage.py shell

from girvi.models import Loan
from girvi.services import RateCacheService, InterestCalculationService

# Check 1: Can import
print("✓ Imports OK")

# Check 2: Do we have data
print(f"Total loans: {Loan.objects.count()}")
print(f"Unreleased: {Loan.objects.unreleased().count()}")

# Check 3: Can query
loans = Loan.objects.unreleased().for_table_display()[:1]
if loans.exists():
    loan = loans.first()
    print(f"✓ Query OK - Sample loan: {loan.loan_id}")
    print(f"  Gold weight: {loan.gold_weight}")
    print(f"  Total interest: {loan.total_interest}")

# Check 4: Rates cached
rate = RateCacheService.get_rate('Gold')
print(f"✓ Gold rate: {rate}")

# Check 5: Dashboard stats
stats = Loan.objects.non_performing_loans_stats()
print(f"✓ Dashboard stats - {stats.get('count')} overdue loans")

print("\n✓ All checks passed!")
```

---

## 📋 Cheat Sheet

```python
# Table display (all metrics)
Loan.objects.unreleased().for_table_display()

# Dashboard stats
Loan.objects.non_performing_loans_stats()
Loan.objects.long_dead_loans_stats(threshold_months=12)

# Convenience filters
Loan.objects.overdue()
Loan.objects.good_standing()
Loan.objects.long_dead(months=12)

# Individual annotations (chain as needed)
Loan.objects.with_duration_metrics()
Loan.objects.with_interest_metrics()
Loan.objects.with_metal_weights()
Loan.objects.with_itemwise_amounts()
Loan.objects.with_current_value()
Loan.objects.with_overdue_status()

# Rate caching
RateCacheService.get_rate('Gold')
RateCacheService.get_all_rates()
RateCacheService.invalidate()

# Aggregations
from django.db.models import Sum, Count
Loan.objects.for_dashboard_metrics().aggregate(
    count=Count('id'),
    total=Sum('total_due')
)
```

---

**Copy, paste, and modify as needed!** 🚀
