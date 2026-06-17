---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Practical Views & Templates Examples

This document shows concrete, copy-paste ready code for common use cases.

## Table Display View

### views.py

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator

from .models import Loan


@login_required
def loan_list_view(request):
    """Display loans with all metrics in a table."""
    
    # Get base queryset
    queryset = (
        Loan.objects
        .filter(release__isnull=True)  # Only unreleased
        .select_related('customer', 'series')
        .for_table_display()
    )
    
    # Filtering
    status_filter = request.GET.get('status')
    if status_filter == 'overdue':
        queryset = queryset.filter(is_overdue=True)
    elif status_filter == 'good':
        queryset = queryset.filter(is_overdue=False)
    
    # Sorting
    sort_by = request.GET.get('sort', '-loan_date')
    queryset = queryset.order_by(sort_by)
    
    # Pagination
    paginator = Paginator(queryset, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary stats
    all_loans = (
        Loan.objects
        .filter(release__isnull=True)
        .for_dashboard_metrics()
    )
    summary_stats = all_loans.aggregate(
        total_loans=Count('id'),
        total_due=Sum('total_due'),
        total_value=Sum('total_current_value'),
        overdue_count=Count('id', filter=Q(is_overdue=True)),
    )
    
    context = {
        'page_obj': page_obj,
        'summary': summary_stats,
        'current_status': status_filter or 'all',
    }
    
    return render(request, 'girvi/loan_list.html', context)


@login_required
def loan_detail_view(request, pk):
    """Display single loan with all details."""
    
    loan = (
        Loan.objects
        .filter(id=pk)
        .select_related('customer', 'series')
        .prefetch_related('loanitems', 'loan_payments')
        .for_table_display()
        .first()
    )
    
    if not loan:
        raise Http404("Loan not found")
    
    # Get payment history
    payments = loan.loan_payments.all().order_by('-payment_date')
    
    context = {
        'loan': loan,
        'payments': payments,
        'loan_items': loan.loanitems.all(),
    }
    
    return render(request, 'girvi/loan_detail.html', context)
```

### loan_list.html

```html
{% extends "base.html" %}
{% load humanize %}

{% block content %}
<div class="container-fluid">
    <h1>Loans</h1>
    
    <!-- Summary Stats -->
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="card bg-primary text-white">
                <div class="card-body">
                    <h5 class="card-title">Total Loans</h5>
                    <h2>{{ summary.total_loans }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-danger text-white">
                <div class="card-body">
                    <h5 class="card-title">Overdue Loans</h5>
                    <h2>{{ summary.overdue_count }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-warning text-white">
                <div class="card-body">
                    <h5 class="card-title">Total Due</h5>
                    <h2>â‚¹{{ summary.total_due|floatformat:0 }}</h2>
                </div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="card bg-info text-white">
                <div class="card-body">
                    <h5 class="card-title">Collateral Value</h5>
                    <h2>â‚¹{{ summary.total_value|floatformat:0 }}</h2>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Filters -->
    <div class="card mb-3">
        <div class="card-body">
            <form method="get" class="row g-3">
                <div class="col-auto">
                    <label class="form-label">Status:</label>
                    <select name="status" class="form-select">
                        <option value="">All</option>
                        <option value="overdue" {% if current_status == 'overdue' %}selected{% endif %}>
                            Overdue
                        </option>
                        <option value="good" {% if current_status == 'good' %}selected{% endif %}>
                            Good Standing
                        </option>
                    </select>
                </div>
                <div class="col-auto">
                    <label class="form-label">Sort:</label>
                    <select name="sort" class="form-select">
                        <option value="-loan_date">Recent First</option>
                        <option value="loan_date">Oldest First</option>
                        <option value="-total_due">Most Due</option>
                        <option value="months_since_created">Newest Loans</option>
                        <option value="-months_since_created">Oldest Loans</option>
                    </select>
                </div>
                <div class="col-auto">
                    <button type="submit" class="btn btn-primary">Filter</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Loans Table -->
    <div class="card">
        <div class="table-responsive">
            <table class="table table-hover mb-0">
                <thead class="table-light">
                    <tr>
                        <th>Loan ID</th>
                        <th>Customer</th>
                        <th>Duration</th>
                        <th>Gold</th>
                        <th>Silver</th>
                        <th>Amount</th>
                        <th>Interest</th>
                        <th>Total Due</th>
                        <th>Collateral</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for loan in page_obj %}
                    <tr class="{% if loan.is_overdue %}table-danger{% else %}table-success{% endif %}">
                        <td>
                            <a href="{% url 'girvi:girvi_loan_detail' loan.pk %}">
                                {{ loan.loan_id }}
                            </a>
                        </td>
                        <td>{{ loan.customer.get_full_name }}</td>
                        <td>
                            <span class="badge bg-secondary">
                                {{ loan.months_since_created|floatformat:0 }}m
                            </span>
                        </td>
                        <td>
                            {{ loan.gold_weight|floatformat:2 }}g
                            <br>
                            <small class="text-muted">â‚¹{{ loan.gold_loanamount|floatformat:0 }}</small>
                        </td>
                        <td>
                            {{ loan.silver_weight|floatformat:2 }}g
                            <br>
                            <small class="text-muted">â‚¹{{ loan.silver_loanamount|floatformat:0 }}</small>
                        </td>
                        <td>â‚¹{{ loan.loan_amount|floatformat:0 }}</td>
                        <td>â‚¹{{ loan.total_interest|floatformat:0 }}</td>
                        <td>
                            â‚¹{{ loan.total_due|floatformat:0 }}
                            <br>
                            <small class="text-muted">
                                {% if loan.is_overdue %}
                                    Short: â‚¹{{ loan.total_due|add:loan.total_current_value|floatformat:0 }}
                                {% endif %}
                            </small>
                        </td>
                        <td>â‚¹{{ loan.total_current_value|floatformat:0 }}</td>
                        <td>
                            {% if loan.is_overdue %}
                                <span class="badge bg-danger">Overdue</span>
                            {% else %}
                                <span class="badge bg-success">Good</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% empty %}
                    <tr>
                        <td colspan="10" class="text-center py-4">No loans found</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <!-- Pagination -->
    {% if page_obj.has_other_pages %}
    <nav aria-label="Page navigation" class="mt-4">
        <ul class="pagination">
            {% if page_obj.has_previous %}
            <li class="page-item">
                <a class="page-link" href="?page=1">First</a>
            </li>
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.previous_page_number }}">Previous</a>
            </li>
            {% endif %}
            
            {% for num in page_obj.paginator.page_range %}
            <li class="page-item {% if page_obj.number == num %}active{% endif %}">
                <a class="page-link" href="?page={{ num }}">{{ num }}</a>
            </li>
            {% endfor %}
            
            {% if page_obj.has_next %}
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.next_page_number }}">Next</a>
            </li>
            <li class="page-item">
                <a class="page-link" href="?page={{ page_obj.paginator.num_pages }}">Last</a>
            </li>
            {% endif %}
        </ul>
    </nav>
    {% endif %}
</div>

<style>
.table-danger { background-color: #f8d7da !important; }
.table-success { background-color: #d4edda !important; }
</style>
{% endblock %}
```

---

## Dashboard View

### views.py

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import Loan


@login_required
def dashboard_view(request):
    """Display loan performance dashboard."""
    
    # Non-performing loans
    non_perf = Loan.objects.non_performing_loans_stats()
    
    # Long-dead loans
    long_dead = Loan.objects.long_dead_loans_stats()
    
    # Overall stats
    all_loans = Loan.objects.unreleased().for_dashboard_metrics().aggregate(
        count=Count('id'),
        total_due=Sum('total_due'),
        total_value=Sum('total_current_value'),
    )
    
    context = {
        'non_performing': non_perf,
        'long_dead': long_dead,
        'overall': all_loans,
    }
    
    return render(request, 'girvi/dashboard.html', context)
```

### dashboard.html

```html
{% extends "base.html" %}

{% block content %}
<div class="container-fluid">
    <h1 class="mb-4">Loan Dashboard</h1>
    
    <!-- Key Metrics Row -->
    <div class="row mb-4">
        <div class="col-lg-3 mb-3">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title text-muted">Total Loans</h6>
                    <h3>{{ overall.count }}</h3>
                </div>
            </div>
        </div>
        <div class="col-lg-3 mb-3">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title text-muted">Total Due</h6>
                    <h3>â‚¹<span class="currency">{{ overall.total_due|floatformat:0 }}</span></h3>
                </div>
            </div>
        </div>
        <div class="col-lg-3 mb-3">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title text-muted">Collateral Value</h6>
                    <h3>â‚¹<span class="currency">{{ overall.total_value|floatformat:0 }}</span></h3>
                </div>
            </div>
        </div>
        <div class="col-lg-3 mb-3">
            <div class="card">
                <div class="card-body">
                    <h6 class="card-title text-muted">Shortfall</h6>
                    <h3>â‚¹<span class="currency">{{ overall.total_due|add:overall.total_value|floatformat:0 }}</span></h3>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Non-Performing Loans Card -->
    <div class="row mb-4">
        <div class="col-lg-6">
            <div class="card border-danger">
                <div class="card-header bg-danger text-white">
                    <h5 class="mb-0">Non-Performing Loans (Value < Due)</h5>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-sm-6">
                            <h6 class="text-muted">Count</h6>
                            <h4>{{ non_performing.count }}</h4>
                        </div>
                        <div class="col-sm-6">
                            <h6 class="text-muted">Total Due</h6>
                            <h4>â‚¹{{ non_performing.total_due|floatformat:0 }}</h4>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-sm-6">
                            <h6 class="text-muted">Collateral Value</h6>
                            <h4>â‚¹{{ non_performing.total_collateral_value|floatformat:0 }}</h4>
                        </div>
                        <div class="col-sm-6">
                            <h6 class="text-muted">Shortfall</h6>
                            <h4 class="text-danger">
                                â‚¹{{ non_performing.total_due|add:non_performing.total_collateral_value|floatformat:0 }}
                            </h4>
                        </div>
                    </div>
                    
                    <h6 class="mt-4 mb-3">Collateral by Metal Type</h6>
                    <table class="table table-sm">
                        <tr>
                            <th>Metal</th>
                            <th>Pure Weight</th>
                            <th>Rate</th>
                            <th>Value</th>
                        </tr>
                        {% for metal, data in non_performing.metals.items %}
                        <tr>
                            <td><strong>{{ metal }}</strong></td>
                            <td>{{ data.pure_weight|floatformat:2 }}g</td>
                            <td>â‚¹{{ data.rate|floatformat:2 }}</td>
                            <td>â‚¹{{ data.value|floatformat:0 }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                    
                    <small class="text-muted">
                        Rates updated: {{ non_performing.rates_timestamp|date:"M d, Y H:i" }}
                    </small>
                </div>
            </div>
        </div>
        
        <!-- Long-Dead Loans Card -->
        <div class="col-lg-6">
            <div class="card border-warning">
                <div class="card-header bg-warning">
                    <h5 class="mb-0">Long-Dead Loans (12+ months, Unreleased)</h5>
                </div>
                <div class="card-body">
                    <div class="row mb-3">
                        <div class="col-sm-6">
                            <h6 class="text-muted">Count</h6>
                            <h4>{{ long_dead.count }}</h4>
                        </div>
                        <div class="col-sm-6">
                            <h6 class="text-muted">Total Due</h6>
                            <h4>â‚¹{{ long_dead.total_due|floatformat:0 }}</h4>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-sm-6">
                            <h6 class="text-muted">Collateral Value</h6>
                            <h4>â‚¹{{ long_dead.total_collateral_value|floatformat:0 }}</h4>
                        </div>
                        <div class="col-sm-6">
                            <h6 class="text-muted">Difference</h6>
                            <h4>
                                {% if long_dead.total_due > long_dead.total_collateral_value %}
                                    <span class="text-danger">
                                        -â‚¹{{ long_dead.total_due|add:long_dead.total_collateral_value|floatformat:0 }}
                                    </span>
                                {% else %}
                                    <span class="text-success">
                                        +â‚¹{{ long_dead.total_collateral_value|add:long_dead.total_due|floatformat:0 }}
                                    </span>
                                {% endif %}
                            </h4>
                        </div>
                    </div>
                    
                    <h6 class="mt-4 mb-3">Collateral by Metal Type</h6>
                    <table class="table table-sm">
                        <tr>
                            <th>Metal</th>
                            <th>Pure Weight</th>
                            <th>Rate</th>
                            <th>Value</th>
                        </tr>
                        {% for metal, data in long_dead.metals.items %}
                        <tr>
                            <td><strong>{{ metal }}</strong></td>
                            <td>{{ data.pure_weight|floatformat:2 }}g</td>
                            <td>â‚¹{{ data.rate|floatformat:2 }}</td>
                            <td>â‚¹{{ data.value|floatformat:0 }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                    
                    <small class="text-muted">
                        Rates updated: {{ long_dead.rates_timestamp|date:"M d, Y H:i" }}
                    </small>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
// Add thousand separators to currency values
document.querySelectorAll('.currency').forEach(elem => {
    const value = parseInt(elem.textContent);
    elem.textContent = value.toLocaleString('en-IN');
});
</script>
{% endblock %}
```

---

## AJAX Refresh Example

```javascript
// Refresh dashboard every 5 minutes
setInterval(function() {
    fetch('/girvi/dashboard/stats/')
        .then(response => response.json())
        .then(data => {
            document.querySelector('[data-stat="non-performing-count"]').textContent = data.non_performing.count;
            document.querySelector('[data-stat="non-performing-due"]').textContent = formatCurrency(data.non_performing.total_due);
            document.querySelector('[data-stat="long-dead-count"]').textContent = data.long_dead.count;
            // ... update other fields
        });
}, 5 * 60 * 1000); // 5 minutes

function formatCurrency(value) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(value);
}
```

---

## Quick Integration Checklist

- [ ] Add `services.py` calculation classes (already done if using updated code)
- [ ] Update `managers.py` with new QuerySet methods (already done if using updated code)
- [ ] Create `dashboard_view()` in `views.py`
- [ ] Create `loan_list_view()` in `views.py`
- [ ] Add URLs to `urls.py`
- [ ] Create `dashboard.html` template
- [ ] Create `loan_list.html` template
- [ ] Test with sample data
- [ ] Add to navigation menu

