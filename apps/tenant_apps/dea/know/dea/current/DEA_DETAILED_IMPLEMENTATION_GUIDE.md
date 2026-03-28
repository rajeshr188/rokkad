# DEA System UI/UX Enhancement - Detailed Implementation Guide

**Version**: 1.1 — Updated Mar 27, 2026  
**Date**: March 25, 2026 (updated Mar 27)  
**Status**: Phase 1 ✅ COMPLETE — Ready to implement Phase 2

> **UPDATE (Mar 27)**: Phase 1 has been completed. Do NOT recreate the dashboard.
> See [DEA_DASHBOARD_GUIDE.md](../DEA_DASHBOARD_GUIDE.md) for full details on what is implemented.
> This guide now starts at Phase 2.

---

## PHASE 1: FOUNDATION & DASHBOARD ✅ COMPLETE (as of Mar 27)

### 1.1 Dashboard Implementation — DONE

#### What Was Implemented

**`views/dashboard.py`** (650 lines, production-ready):
- Full metrics: Cash, AR, AP, Working Capital
- Period P&L summary: Revenue → COGS → Gross Profit → Net Profit → Margin %
- 5 alert types: credit limit exceeded, draft vouchers, unbalanced JE, old periods, inactive accounts
- Top 5 Debtors / Top 5 Creditors tables
- Recent Activity: 10 vouchers + 10 journal entries
- AJAX refresh at `/dea/dashboard/metrics/ajax/`

**`views/dashboard_enhanced.py`** (skeleton, ~150 lines):
- Quick actions (4 types) wired
- 5 guided workflow accordions — all content done
- COA preview slot — slot exists, needs real data
- Report links — all wired

**Aging & Ratios** (separate pages):
- `/dea/reports/receivables/aging/` — 4-bucket AR aging
- `/dea/reports/payables/aging/` — 4-bucket AP aging
- `/dea/reports/ratios/` — Liquidity + Leverage ratios

#### ONLY REMAINING TASK: Wire `dashboard_enhanced.py` placeholder functions

These 5 functions currently return `0` or `[]`. Replace with real queries mirroring patterns already used by `dashboard.py`:

```python
# File: apps/tenant_apps/dea/views/dashboard_enhanced.py

def calculate_ar_balance():
    """Replace with: sum of open receivable account balances
    Mirror: receivables_aging() in dashboard.py for account query pattern"""
    return 0  # ← REPLACE THIS

def calculate_ap_balance():
    """Replace with: sum of open payable account balances
    Mirror: payables_aging() in dashboard.py for account query pattern"""
    return 0  # ← REPLACE THIS

def calculate_cash_balance():
    """Replace with: sum of cash/bank ledger balances
    Mirror: _calculate_key_metrics() in dashboard.py"""
    return 0  # ← REPLACE THIS

def calculate_period_pl():
    """Replace with: current period net profit/loss
    Mirror: _get_period_summary() in dashboard.py"""
    return 0  # ← REPLACE THIS

def get_coa_preview():
    """Replace with: top accounts by class (Asset/Liability/Equity/Revenue/Expense)
    Returns list of dicts: [{name, balance, account_class}, ...]"""
    return []  # ← REPLACE THIS
```

Once wired, swap `/dea/dashboard/enhanced/` to be the primary landing page.

---

## PHASE 1.5: Wire Enhanced Dashboard Data (1-2 days — START HERE)

> This is the only remaining Phase 1 task. The main dashboard is done. The enhanced dashboard
> skeleton is done. All that remains is replacing 5 placeholder functions with real data.

**File to edit**: `apps/tenant_apps/dea/views/dashboard_enhanced.py`

The `get_coa_summary()` and balance helper functions below are the EXACT implementations needed
for `dashboard_enhanced.py`. Use them as starting points — do **not** create a new dashboard view.

```python
# apps/tenant_apps/dea/views/dashboard_enhanced.py
# Replace placeholder functions as follows:

def calculate_ar_balance():
    """Sum of open receivable account balances"""
    from django.db.models import Sum
    from ..models import Ledger, AccountStatus
    return Ledger.objects.filter(
        AccountType__name__icontains='receivable'
    ).aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0

def calculate_ap_balance():
    """Sum of open payable account balances"""
    from django.db.models import Sum
    from ..models import Ledger
    return Ledger.objects.filter(
        AccountType__name__icontains='payable'
    ).aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0

def calculate_cash_balance():
    """Sum of cash/bank account balances"""
    from django.db.models import Sum
    from ..models import Ledger
    return Ledger.objects.filter(
        AccountType__name__icontains='cash'
    ).aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0

def calculate_period_pl():
    """Current period net profit/loss (mirror _get_period_summary in dashboard.py)"""
    from django.db.models import Sum
    from ..models import Ledger, AccountStatus

    revenue = Ledger.objects.filter(
        AccountType__name__icontains='revenue'
    ).aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0

    expense = Ledger.objects.filter(
        AccountType__name__icontains='expense'
    ).aggregate(
        total=Sum('ledgerbalance__balance_amount')
    )['total'] or 0

    return -revenue + expense  # Net result

def get_coa_preview():
    """Top accounts by class for dashboard COA preview slot"""
    from django.db.models import Count, Sum
    from ..models import Ledger, AccountStatus

    summary = Ledger.objects.filter(
        status=AccountStatus.ACTIVE
    ).values('AccountType__description').annotate(
        count=Count('id'),
        balance=Sum('ledgerbalance__balance_amount')
    ).order_by('AccountType__description')

    return summary
```

---

## PHASE 2: CHART OF ACCOUNTS NAVIGATOR (Weeks 1-2 from now)

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

### Phase 1.5 (START HERE — wire existing skeleton)
```
MODIFY (do NOT create new dashboard files):
└── apps/tenant_apps/dea/views/dashboard_enhanced.py
    (replace 5 placeholder functions with real queries)
```

### Phase 2-3 New Files
```
NEW FILES:
├── apps/tenant_apps/dea/views/chart_of_accounts.py
├── apps/tenant_apps/dea/views/voucher_creation.py
├── apps/tenant_apps/dea/views/reports_hub.py
├── templates/dea/chart_of_accounts.html
├── templates/dea/voucher_creation_hub.html
├── templates/dea/reports_hub.html
├── templates/dea/components/metric_card.html
├── templates/dea/components/quick_actions.html
├── templates/dea/components/guided_workflows.html
└── static/dea/css/enhanced_ui.css

MODIFIED FILES (Phase 2+):
├── apps/tenant_apps/dea/urls.py (add new routes)
├── apps/tenant_apps/dea/views/__init__.py (import new views)
└── django_project/urls.py (include dea routes if needed)

DO NOT MODIFY (already production-ready):
├── apps/tenant_apps/dea/views/dashboard.py  ← 650 lines, fully working
└── templates/dea/dashboard.html             ← fully working template
```

---

**Status**: Phase 1 complete. Start with Phase 1.5 (wire `dashboard_enhanced.py`), then Phase 2 (COA Navigator).

**Next Step**: Replace the 5 placeholder functions in `dashboard_enhanced.py` with real queries (see Phase 1.5 above).

---

*Document prepared for DEA System UI/UX Enhancement Project*  
*Version: 1.1 | Date: March 27, 2026 | Status: IN PROGRESS — Phase 1 Complete*
