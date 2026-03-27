# DEA System UI/UX Enhancement - Detailed Implementation Guide

**Version**: 1.0  
**Date**: March 25, 2026  
**Status**: Ready for Development

---

## PHASE 1: FOUNDATION & DASHBOARD (Weeks 1-2)

### 1.1 Dashboard Home Page Enhancement

#### Current State
- Basic metrics display
- Limited actionable elements
- No workflow guidance

#### Target Design

**Layout Structure**:
```
┌─ Header Section ──────────────────────────────────────┐
│ "Accounting Dashboard" | Current Period Info          │
│ Quick Actions: [Invoice] [Expense] [Payment] [Journal]│
└───────────────────────────────────────────────────────┘

┌─ Key Metrics Row ─────┬─ Financial Health ─┬ Period Info ─┐
│ • Vouchers Count      │ • AR Balance       │ • Status     │
│ • Draft vs Posted     │ • AP Balance       │ • Days Left  │
│ • Total Accounts      │ • Cash Position    │ • Actions    │
│ • Ledgers Count       │ • Net P&L          │              │
└───────────────────────┴─ Financial Health ─┴──────────────┘

┌─ Guided Workflows Section (Collapsible) ──────────────┐
│ Step-by-step guides for common tasks                 │
│ (Setup accounts, Record transactions, Period-end)    │
└───────────────────────────────────────────────────────┘

┌─ Three Column Section ────────────────────────────────┐
│ • Recent Vouchers    │ • COA Preview      │ • Key Info │
│ • Latest Entries     │ • Account Classes  │ • Balances │
│ • Status Summary     │ • Drill-down Links │ • Alerts   │
└───────────────────────────────────────────────────────┘

┌─ Reports Quick Links ─────────────────────────────────┐
│ [Trial Balance] [Balance Sheet] [P&L] [Cash Flow]    │
│ [View All Reports →]                                 │
└───────────────────────────────────────────────────────┘
```

#### Implementation Tasks

**Backend (`dashboard.py`)**:

```python
def dashboard(request):
    """Enhanced dashboard with unified UX"""
    context = {
        # Period & Status
        'current_period': get_current_period(),
        'period_status': calculate_period_status(),
        'days_in_period': calculate_days_remaining(),
        
        # Quick Action Links
        'quick_actions': [
            {
                'label': 'Create Invoice',
                'url': reverse('sales_invoice_create'),
                'icon': 'fa-file-invoice-dollar',
                'description': 'Record customer sale'
            },
            # ... more actions
        ],
        
        # Key Metrics Section
        'metrics': {
            'total_vouchers': Voucher.objects.count(),
            'posted_vouchers': Voucher.objects.filter(status=VoucherStatus.POSTED).count(),
            'draft_vouchers': Voucher.objects.filter(status=VoucherStatus.DRAFT).count(),
            'active_accounts': Account.objects.filter(status=AccountStatus.ACTIVE).count(),
            'total_ledgers': Ledger.objects.count(),
        },
        
        # Financial Health
        'financial_health': {
            'ar_balance': calculate_ar_balance(),  # Sum of receivables
            'ap_balance': calculate_ap_balance(),  # Sum of payables
            'cash_position': calculate_cash_balance(),
            'net_pl': calculate_period_pl(),
        },
        
        # Guided Workflows
        'workflows': [
            {
                'title': 'Set Up Account Structure',
                'steps': [
                    {'text': 'View Chart of Accounts', 'url': '/dea/chart-of-accounts/'},
                    {'text': 'Set Opening Balances', 'url': '/dea/opening-balance/create/'},
                    {'text': 'Create Business Accounts', 'url': '/dea/accounts/create/'},
                ]
            },
            # ... more workflows
        ],
        
        # COA Preview (Top 5 account classes with balances)
        'coa_preview': get_coa_summary(),
        
        # Recent Activity
        'recent_vouchers': Voucher.objects.select_related('voucher_type', 'created_by')[:8],
        'recent_entries': JournalEntry.objects.select_related('voucher')[:8],
        
        # Reports Hub
        'report_links': [
            {'name': 'Trial Balance', 'url': reverse('trial_balance')},
            {'name': 'Balance Sheet', 'url': reverse('balance_sheet')},
            # ... more reports
        ],
    }
    return render(request, 'dea/dashboard.html', context)
```

**Template (`dashboard.html`)**:

```html
{% extends 'layouts/workspace.html' %}
{% load static %}

{% block title %}Accounting Dashboard{% endblock %}

{% block content %}
<!-- Header Section -->
<div class="dashboard-header mb-4">
    <div class="row">
        <div class="col-md-8">
            <h1><i class="fas fa-chart-line"></i> Accounting Dashboard</h1>
            <p class="text-muted">{{ current_period.name }} ({{ current_period.start_date|date:"M d" }} - {{ current_period.end_date|date:"M d, Y" }})</p>
        </div>
        <div class="col-md-4 text-end">
            <button class="btn btn-sm btn-outline-primary" onclick="refreshDashboard()">
                <i class="fas fa-sync"></i> Refresh
            </button>
        </div>
    </div>
</div>

<!-- Quick Actions Section -->
<div class="quick-actions-section mb-4">
    <h5 class="mb-3"><i class="fas fa-lightning-bolt"></i> Quick Actions</h5>
    <div class="row g-2">
        {% for action in quick_actions %}
        <div class="col-md-6 col-lg-3">
            <a href="{{ action.url }}" class="btn btn-outline-primary btn-block d-flex flex-column align-items-center p-3">
                <i class="fas {{ action.icon }} fa-2x mb-2"></i>
                <strong>{{ action.label }}</strong>
                <small class="text-muted">{{ action.description }}</small>
            </a>
        </div>
        {% endfor %}
    </div>
</div>

<!-- Key Metrics & Financial Health -->
<div class="metrics-section mb-4">
    <div class="row">
        <!-- Volume Metrics -->
        <div class="col-md-4">
            <div class="card metric-card border-start border-primary">
                <div class="card-body">
                    <h6 class="card-title text-uppercase small">Transaction Volume</h6>
                    <div class="metric-item d-flex justify-content-between py-2 border-bottom">
                        <span>Posted Vouchers</span>
                        <strong>{{ metrics.posted_vouchers }}</strong>
                    </div>
                    <div class="metric-item d-flex justify-content-between py-2 border-bottom">
                        <span>Draft Vouchers</span>
                        <strong>{{ metrics.draft_vouchers }}</strong>
                    </div>
                    <div class="metric-item d-flex justify-content-between py-2">
                        <span>Active Accounts</span>
                        <strong>{{ metrics.active_accounts }}</strong>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Financial Health -->
        <div class="col-md-4">
            <div class="card metric-card border-start border-success">
                <div class="card-body">
                    <h6 class="card-title text-uppercase small">Financial Health</h6>
                    <div class="metric-item d-flex justify-content-between py-2 border-bottom">
                        <span>A/R Balance</span>
                        <strong class="text-success">{{ financial_health.ar_balance|floatformat:0 }}</strong>
                    </div>
                    <div class="metric-item d-flex justify-content-between py-2 border-bottom">
                        <span>A/P Balance</span>
                        <strong class="text-danger">{{ financial_health.ap_balance|floatformat:0 }}</strong>
                    </div>
                    <div class="metric-item d-flex justify-content-between py-2">
                        <span>Net P&L</span>
                        <strong class="text-info">{{ financial_health.net_pl|floatformat:0 }}</strong>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Period Status -->
        <div class="col-md-4">
            <div class="card metric-card border-start border-warning">
                <div class="card-body">
                    <h6 class="card-title text-uppercase small">Period Status</h6>
                    <div class="metric-item d-flex justify-content-between py-2 border-bottom">
                        <span>Status</span>
                        <span class="badge bg-{{ period_status.color }}">{{ period_status.text }}</span>
                    </div>
                    <div class="metric-item d-flex justify-content-between py-2 border-bottom">
                        <span>Days Remaining</span>
                        <strong>{{ days_in_period }}</strong>
                    </div>
                    <div class="metric-item d-flex justify-content-between py-2">
                        <span>Action</span>
                        <a href="#" class="text-decoration-none">{{ period_status.action }}</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Guided Workflows (Collapsible Accordion) -->
<div class="workflows-section mb-4">
    <h5 class="mb-3"><i class="fas fa-graduation-cap"></i> Guided Workflows</h5>
    <div class="accordion" id="workflowAccordion">
        {% for workflow in workflows %}
        <div class="accordion-item">
            <h2 class="accordion-header">
                <button class="accordion-button{% if not forloop.first %} collapsed{% endif %}" 
                        type="button" data-bs-toggle="collapse" 
                        data-bs-target="#workflow{{ forloop.counter }}">
                    <i class="fas fa-circle-{{ forloop.counter }} me-2"></i>
                    {{ workflow.title }}
                </button>
            </h2>
            <div id="workflow{{ forloop.counter }}" class="accordion-collapse collapse{% if forloop.first %} show{% endif %}" 
                 data-bs-parent="#workflowAccordion">
                <div class="accordion-body">
                    <ol>
                    {% for step in workflow.steps %}
                        <li class="mb-2">
                            <a href="{{ step.url }}" class="text-decoration-none">
                                {{ step.text }} <i class="fas fa-arrow-right ms-2"></i>
                            </a>
                        </li>
                    {% endfor %}
                    </ol>
                </div>
            </div>
        </div>
        {% endfor %}
    </div>
</div>

<!-- COA Preview + Recent Activity + Key Info -->
<div class="row mb-4">
    <!-- COA Preview -->
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-header bg-light">
                <h5 class="mb-0"><i class="fas fa-sitemap"></i> Chart of Accounts</h5>
            </div>
            <div class="card-body">
                {% for class in coa_preview %}
                <div class="coa-item mb-2">
                    <strong>{{ class.name }}</strong>
                    <span class="badge bg-secondary float-end">{{ class.balance }}</span>
                    <div class="small text-muted">{{ class.count }} accounts</div>
                </div>
                {% endfor %}
                <a href="{% url 'dea_chart_of_accounts' %}" class="btn btn-sm btn-outline-primary w-100 mt-3">
                    View Full COA
                </a>
            </div>
        </div>
    </div>
    
    <!-- Recent Vouchers -->
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-header bg-light">
                <h5 class="mb-0"><i class="fas fa-receipt"></i> Recent Vouchers</h5>
            </div>
            <div class="card-body">
                <div class="recent-list">
                {% for voucher in recent_vouchers %}
                    <div class="recent-item d-flex justify-content-between align-items-center mb-2 pb-2 border-bottom">
                        <div>
                            <div class="small"><strong>{{ voucher.voucher_type.name }}</strong></div>
                            <div class="text-muted small">{{ voucher.created_at|date:"M d H:i" }}</div>
                        </div>
                        <span class="badge bg-{{ voucher.status|lower }}">{{ voucher.status }}</span>
                    </div>
                {% endfor %}
                </div>
                <a href="{% url 'dea_voucher_list' %}" class="btn btn-sm btn-outline-primary w-100 mt-3">
                    View All Vouchers
                </a>
            </div>
        </div>
    </div>
    
    <!-- Key Alerts -->
    <div class="col-md-4">
        <div class="card h-100">
            <div class="card-header bg-light">
                <h5 class="mb-0"><i class="fas fa-bell"></i> Alerts & Warnings</h5>
            </div>
            <div class="card-body">
                <div class="alerts-section">
                {% if alerts %}
                    {% for alert in alerts %}
                    <div class="alert alert-{{ alert.severity }} alert-dismissible fade show mb-2" role="alert">
                        <i class="fas fa-{{ alert.icon }} me-2"></i>
                        <strong>{{ alert.title }}</strong>
                        <p class="mb-0 small">{{ alert.message }}</p>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle"></i> No alerts
                    </div>
                {% endif %}
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Reports Hub -->
<div class="reports-section">
    <h5 class="mb-3"><i class="fas fa-chart-bar"></i> Financial Reports</h5>
    <div class="row g-2">
        {% for report in report_links %}
        <div class="col-md-6 col-lg-2">
            <a href="{{ report.url }}" class="btn btn-outline-secondary btn-sm w-100 text-start">
                <i class="fas fa-file-alt me-2"></i>{{ report.name }}
            </a>
        </div>
        {% endfor %}
        <div class="col-md-6 col-lg-2">
            <a href="{% url 'dea_reports_hub' %}" class="btn btn-primary btn-sm w-100">
                View All Reports <i class="fas fa-arrow-right ms-1"></i>
            </a>
        </div>
    </div>
</div>

{% endblock %}

{% block extra_js %}
<script>
function refreshDashboard() {
    location.reload();
}
</script>
{% endblock %}
```

### 1.2 Database Optimization Queries

**New helper functions for dashboard**:

```python
# dea/utils/dashboard.py

def calculate_ar_balance():
    """Calculate total accounts receivable balance"""
    from django.db.models import Sum, Q
    from .models import Ledger
    
    # Find all receivable accounts
    receivables = Ledger.objects.filter(
        AccountType__description__icontains='receivable'
    )
    
    total = receivables.aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0
    
    return total

def calculate_ap_balance():
    """Calculate total accounts payable balance"""
    from django.db.models import Sum, Q
    from .models import Ledger
    
    payables = Ledger.objects.filter(
        AccountType__description__icontains='payable'
    )
    
    total = payables.aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0
    
    return abs(total)  # Return as positive

def calculate_cash_balance():
    """Calculate total cash position"""
    from django.db.models import Sum
    from .models import Ledger
    
    cash_accounts = Ledger.objects.filter(
        name__icontains='cash'
    ) | Ledger.objects.filter(
        name__icontains='bank'
    )
    
    total = cash_accounts.aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0
    
    return total

def calculate_period_pl():
    """Calculate net P&L for current period"""
    from django.db.models import Sum
    from .models import Ledger, AccountingPeriod
    
    current_period = AccountingPeriod.objects.get_current_period()
    
    # Revenue accounts (negative balance = income)
    revenue = Ledger.objects.filter(
        AccountType__name__icontains='revenue'
    ).aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0
    
    # Expense accounts (positive balance = expense)
    expense = Ledger.objects.filter(
        AccountType__name__icontains='expense'
    ).aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0
    
    return -revenue + expense  # Net result

def get_coa_summary():
    """Get summary of chart of accounts by class"""
    from django.db.models import Count, Sum
    from .models import Ledger
    
    summary = Ledger.objects.filter(
        status=AccountStatus.ACTIVE
    ).values('AccountType__description').annotate(
        count=Count('id'),
        balance=Sum('ledgerbalance__balance_amount')
    ).order_by('AccountType__description')
    
    return summary
```

---

## PHASE 2: CHART OF ACCOUNTS NAVIGATOR (Weeks 3-4)

### 2.1 New View: Chart of Accounts

**Views (`dea/views/chart_of_accounts.py`)**:

```python
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum, Count, Q

from ..models import Ledger, Account, LedgerBalance, AccountBalance, AccountStatus

class ChartOfAccountsView(LoginRequiredMixin, TemplateView):
    template_name = 'dea/chart_of_accounts.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all active ledgers organized by class
        ledgers = Ledger.objects.select_related(
            'parent', 'AccountType', 'AccountType__description'
        ).filter(
            status=AccountStatus.ACTIVE
        ).order_by('AccountType', 'parent', 'name')
        
        # Build hierarchical structure
        context['coa_hierarchy'] = self._build_hierarchy(ledgers)
        
        # Summary stats
        context['total_accounts'] = Ledger.objects.filter(status=AccountStatus.ACTIVE).count()
        context['account_classes'] = self._get_account_classes()
        context['total_balance'] = self._get_total_balance()
        
        return context
    
    def _build_hierarchy(self, ledgers):
        """Build hierarchical tree structure from ledgers"""
        hierarchy = {}
        
        for ledger in ledgers:
            class_name = ledger.AccountType.name
            
            if class_name not in hierarchy:
                hierarchy[class_name] = {
                    'class': class_name,
                    'groups': {},
                    'total_balance': 0
                }
            
            # Build tree
            if ledger.parent:
                parent_name = ledger.parent.name
                if parent_name not in hierarchy[class_name]['groups']:
                    hierarchy[class_name]['groups'][parent_name] = {
                        'name': parent_name,
                        'accounts': []
                    }
                
                hierarchy[class_name]['groups'][parent_name]['accounts'].append({
                    'id': ledger.id,
                    'code': ledger.code or '',
                    'name': ledger.name,
                    'balance': self._get_ledger_balance(ledger),
                    'status': ledger.status,
                    'type': ledger.AccountType.name,
                    'url': ledger.get_absolute_url()
                })
        
        return hierarchy
    
    def _get_ledger_balance(self, ledger):
        """Get current balance for a ledger"""
        try:
            balance = ledger.ledgerbalance.balance_amount
        except LedgerBalance.DoesNotExist:
            balance = 0
        return balance
    
    def _get_account_classes(self):
        """Get list of account classes"""
        return Ledger.objects.values_list(
            'AccountType__name', flat=True
        ).distinct().order_by('AccountType__name')
    
    def _get_total_balance(self):
        """Get total balance of all accounts"""
        return LedgerBalance.objects.aggregate(
            total=Sum('balance_amount')
        )['total'] or 0
```

**Template (`chart_of_accounts.html`)**:

```html
{% extends 'layouts/workspace.html' %}
{% load static %}

{% block title %}Chart of Accounts{% endblock %}

{% block content %}
<div class="chart-of-accounts-container">
    <!-- Header -->
    <div class="coa-header mb-4">
        <h1><i class="fas fa-sitemap"></i> Chart of Accounts</h1>
        <p class="text-muted">Total Active Accounts: {{ total_accounts }}</p>
    </div>
    
    <!-- Search & Filters -->
    <div class="coa-controls mb-4">
        <div class="row">
            <div class="col-md-6">
                <input type="text" id="accountSearch" class="form-control" 
                       placeholder="Search accounts by name or code...">
            </div>
            <div class="col-md-3">
                <select class="form-select" id="classFilter">
                    <option value="">All Account Classes</option>
                    {% for class in account_classes %}
                    <option value="{{ class }}">{{ class }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="col-md-3">
                <select class="form-select" id="statusFilter">
                    <option value="">All Status</option>
                    <option value="ACTIVE">Active</option>
                    <option value="INACTIVE">Inactive</option>
                </select>
            </div>
        </div>
    </div>
    
    <!-- COA Table -->
    <div class="coa-content">
        {% for class_name, class_data in coa_hierarchy.items %}
        <div class="coa-section mb-4 class-section" data-class="{{ class_name }}">
            <h3 class="section-header">
                <i class="fas fa-folder-open me-2"></i>{{ class_name }}
                <span class="badge bg-secondary float-end">{{ class_data.groups|length }} groups</span>
            </h3>
            
            <div class="table-responsive">
                <table class="table table-hover coa-table">
                    <thead>
                        <tr>
                            <th>Account Name</th>
                            <th width="15%">Code</th>
                            <th width="15%">Type</th>
                            <th width="15%" class="text-end">Balance</th>
                            <th width="10%">Status</th>
                            <th width="10%"></th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for parent_name, group in class_data.groups.items %}
                        <tr class="group-header">
                            <td colspan="6" class="bg-light">
                                <strong><i class="fas fa-folder me-2"></i>{{ parent_name }}</strong>
                            </td>
                        </tr>
                        {% for account in group.accounts %}
                        <tr class="account-row" data-name="{{ account.name|lower }}" 
                            data-code="{{ account.code|lower }}" data-status="{{ account.status }}">
                            <td>
                                <a href="{{ account.url }}" class="text-decoration-none">
                                    {{ account.name }}
                                </a>
                            </td>
                            <td><code>{{ account.code }}</code></td>
                            <td>{{ account.type }}</td>
                            <td class="text-end">
                                <strong class="{% if account.balance < 0 %}text-danger{% else %}text-success{% endif %}">
                                    {{ account.balance|floatformat:0 }}
                                </strong>
                            </td>
                            <td>
                                <span class="badge bg-{% if account.status == 'ACTIVE' %}success{% else %}secondary{% endif %}">
                                    {{ account.status }}
                                </span>
                            </td>
                            <td class="text-center">
                                <a href="{{ account.url }}" class="btn btn-xs btn-outline-primary" 
                                   title="View Details">
                                    <i class="fas fa-arrow-right"></i>
                                </a>
                            </td>
                        </tr>
                        {% endfor %}
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endfor %}
    </div>
</div>

{% endblock %}

{% block extra_js %}
<script>
document.getElementById('accountSearch').addEventListener('keyup', function(e) {
    const searchTerm = e.target.value.toLowerCase();
    document.querySelectorAll('.account-row').forEach(row => {
        const name = row.dataset.name || '';
        const code = row.dataset.code || '';
        row.style.display = (name.includes(searchTerm) || code.includes(searchTerm)) ? '' : 'none';
    });
});

document.getElementById('classFilter').addEventListener('change', function(e) {
    const selectedClass = e.target.value;
    document.querySelectorAll('.class-section').forEach(section => {
        section.style.display = (!selectedClass || section.dataset.class === selectedClass) ? '' : 'none';
    });
});
</script>
{% endblock %}
```

---

## PHASE 3: VOUCHER CREATION HUB (Weeks 4-5)

### 3.1 New View: Voucher Creation Hub

**Views (`dea/views/voucher_creation.py`)**:

```python
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse

class VoucherCreationHubView(LoginRequiredMixin, TemplateView):
    template_name = 'dea/voucher_creation_hub.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['voucher_types'] = [
            {
                'id': 'customer-invoice',
                'title': 'Customer Invoice',
                'subtitle': 'Revenue from sales',
                'icon': 'fa-file-invoice-dollar',
                'description': 'Record sales to customers and create customer invoices',
                'gl_impact': {
                    'debit': 'Accounts Receivable',
                    'credit': 'Sales Revenue'
                },
                'when_to_use': 'When you sell products or services to customers',
                'url': reverse('sales_invoice_create'),
                'keywords': ['invoice', 'customer', 'revenue', 'sales'],
                'similar': ['supplier-invoice']
            },
            {
                'id': 'supplier-invoice',
                'title': 'Supplier Invoice',
                'subtitle': 'Cost of goods/services',
                'icon': 'fa-file-invoice',
                'description': 'Record purchases from suppliers and create supplier bills',
                'gl_impact': {
                    'debit': 'Expense/Inventory',
                    'credit': 'Accounts Payable'
                },
                'when_to_use': 'When you receive a bill from suppliers for goods or services',
                'url': reverse('purchase_invoice_create'),
                'keywords': ['bill', 'supplier', 'purchase', 'vendor'],
                'similar': ['customer-invoice']
            },
            {
                'id': 'payment',
                'title': 'Payment Entry',
                'subtitle': 'Cash movements',
                'icon': 'fa-money-bill-wave',
                'description': 'Record cash receipts and payments',
                'gl_impact': {
                    'debit': 'Cash/Bank',
                    'credit': 'Receivable/Payable'
                },
                'when_to_use': 'When you receive money or pay bills',
                'url': reverse('payment_create'),
                'keywords': ['payment', 'cash', 'bank', 'receipt'],
                'similar': []
            },
            {
                'id': 'expense',
                'title': 'Operating Expense',
                'subtitle': 'Business expenses',
                'icon': 'fa-receipt',
                'description': 'Record operating expenses like rent, utilities, salaries',
                'gl_impact': {
                    'debit': 'Various Expense Accounts',
                    'credit': 'Cash/Payable'
                },
                'when_to_use': 'For recurring business expenses',
                'url': reverse('expense_create'),
                'keywords': ['expense', 'rent', 'utilities', 'salary', 'cost'],
                'similar': []
            },
            {
                'id': 'journal-entry',
                'title': 'Journal Entry',
                'subtitle': 'GL adjustments',
                'icon': 'fa-book',
                'description': 'Make manual GL entries for corrections and adjustments',
                'gl_impact': {
                    'debit': 'User-selected',
                    'credit': 'User-selected'
                },
                'when_to_use': 'For month-end adjustments, accruals, corrections',
                'url': reverse('journal_entry_create'),
                'keywords': ['journal', 'entry', 'adjustment', 'accrual', 'correction'],
                'similar': []
            },
            {
                'id': 'opening-balance',
                'title': 'Opening Balance',
                'subtitle': 'Period initialization',
                'icon': 'fa-list-ol',
                'description': 'Set initial GL account balances for first period',
                'gl_impact': {
                    'debit': 'Various GL Accounts',
                    'credit': 'Various GL Accounts'
                },
                'when_to_use': 'When starting a new accounting period',
                'url': reverse('opening_balance_create'),
                'keywords': ['opening', 'balance', 'initial', 'setup', 'period'],
                'similar': []
            },
        ]
        
        return context
```

**Template (`voucher_creation_hub.html`)**:

```html
{% extends 'layouts/workspace.html' %}
{% load static %}

{% block title %}Create Transaction{% endblock %}

{% block content %}
<div class="voucher-creation-hub">
    <!-- Header -->
    <div class="voucher-header mb-4">
        <h1><i class="fas fa-pencil-alt"></i> Create Transaction</h1>
        <p class="text-muted">Choose the type of transaction to record</p>
    </div>
    
    <!-- Help Section -->
    <div class="alert alert-info alert-dismissible fade show" role="alert">
        <i class="fas fa-lightbulb me-2"></i>
        <strong>Not sure which to choose?</strong> Look for descriptions and GL impacts below.
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    </div>
    
    <!-- Search -->
    <div class="search-section mb-4">
        <input type="text" class="form-control form-control-lg" id="voucherSearch"
               placeholder="Search for transaction type (e.g., 'invoice', 'expense', 'payment')...">
    </div>
    
    <!-- Voucher Types Grid -->
    <div class="voucher-types-grid">
        {% for voucher in voucher_types %}
        <div class="voucher-card" data-keywords="{{ voucher.keywords|join:',' }}">
            <a href="{{ voucher.url }}" class="card-link">
                <div class="card h-100 hover-shadow">
                    <div class="card-header bg-light">
                        <div class="row align-items-center">
                            <div class="col-auto">
                                <i class="fas {{ voucher.icon }} fa-2x text-primary"></i>
                            </div>
                            <div class="col">
                                <h5 class="card-title mb-0">{{ voucher.title }}</h5>
                                <small class="text-muted">{{ voucher.subtitle }}</small>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card-body">
                        <p class="card-text text-muted mb-3">{{ voucher.description }}</p>
                        
                        <!-- GL Impact -->
                        <div class="gl-impact mb-3">
                            <small class="d-block text-uppercase text-muted mb-2">GL Impact:</small>
                            <div class="row g-2">
                                <div class="col-6">
                                    <div class="bg-light p-2 rounded">
                                        <small class="text-muted d-block">Debit</small>
                                        <strong>{{ voucher.gl_impact.debit }}</strong>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="bg-light p-2 rounded">
                                        <small class="text-muted d-block">Credit</small>
                                        <strong>{{ voucher.gl_impact.credit }}</strong>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- When to Use -->
                        <div class="when-to-use">
                            <small class="text-muted d-block mb-1">
                                <i class="fas fa-check-circle text-success me-1"></i>
                                {{ voucher.when_to_use }}
                            </small>
                        </div>
                    </div>
                    
                    <div class="card-footer bg-white">
                        <button class="btn btn-primary w-100">
                            Create <i class="fas fa-arrow-right ms-2"></i>
                        </button>
                    </div>
                </div>
            </a>
        </div>
        {% endfor %}
    </div>
</div>

{% endblock %}

{% block extra_js %}
<script>
document.getElementById('voucherSearch').addEventListener('keyup', function(e) {
    const searchTerm = e.target.value.toLowerCase();
    document.querySelectorAll('.voucher-card').forEach(card => {
        const keywords = card.dataset.keywords.toLowerCase();
        card.style.display = keywords.includes(searchTerm) ? '' : 'none';
    });
});
</script>
{% endblock %}

{% block extra_css %}
<style>
.voucher-types-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: 1.5rem;
}

.voucher-card {
    transition: all 0.3s ease;
}

.voucher-card .card {
    border: 1px solid #e0e0e0;
    transition: all 0.3s ease;
}

.voucher-card:hover .card {
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    border-color: #007bff;
    transform: translateY(-2px);
}

.gl-impact {
    background-color: #f8f9fa;
    padding: 1rem;
    border-left: 3px solid #007bff;
}

.hover-shadow {
    transition: all 0.3s ease;
}

@media (max-width: 768px) {
    .voucher-types-grid {
        grid-template-columns: 1fr;
    }
}
</style>
{% endblock %}
```

---

## SUMMARY OF FILES TO CREATE/MODIFY

### Files to Create (Phase 1-3)
```
NEW FILES:
├── apps/tenant_apps/dea/views/chart_of_accounts.py
├── apps/tenant_apps/dea/views/voucher_creation.py
├── apps/tenant_apps/dea/views/reports_hub.py
├── apps/tenant_apps/dea/utils/dashboard.py
├── templates/dea/chart_of_accounts.html
├── templates/dea/voucher_creation_hub.html
├── templates/dea/reports_hub.html
├── templates/dea/components/metric_card.html
├── templates/dea/components/quick_actions.html
├── templates/dea/components/guided_workflows.html
└── static/dea/css/enhanced_ui.css

MODIFIED FILES:
├── apps/tenant_apps/dea/views/dashboard.py (enhance with new metrics)
├── apps/tenant_apps/dea/urls.py (add new routes)
├── templates/dea/dashboard.html (complete redesign)
├── apps/tenant_apps/dea/views/__init__.py (import new views)
└── django_project/urls.py (include dea routes if needed)
```

---

**Status**: This guide is ready for development upon stakeholder approval of design.

**Next Step**: Create wireframes and finalize design system before implementation begins.

---

*Document prepared for DEA System UI/UX Enhancement Project*  
*Version: 1.0 | Date: March 25, 2026 | Status: DRAFT - READY FOR REVIEW*
