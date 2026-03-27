"""
Enhanced DEA Dashboard View - Unified UX
Phase 1 Implementation (2026)
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from ..models import (
    Voucher, VoucherStatus, Account, AccountStatus, Ledger, JournalEntry, AccountingPeriod
)

# Helper functions (to be moved to utils/dashboard.py in future phases)
def calculate_ar_balance():
    # Placeholder: Sum of all receivable accounts
    return 0

def calculate_ap_balance():
    # Placeholder: Sum of all payable accounts
    return 0

def calculate_cash_balance():
    # Placeholder: Sum of all cash/bank ledgers
    return 0

def calculate_period_pl():
    # Placeholder: Net P&L for current period
    return 0

def get_coa_preview():
    # Placeholder: Top 5 account classes with balances
    return []

@login_required
def dashboard_enhanced(request):
    """
    Enhanced dashboard with unified UX and clear entry points.
    """
    current_period = AccountingPeriod.objects.get_current_period()
    context = {
        'current_period': current_period,
        'period_status': 'Open' if current_period else 'No Period',
        'days_in_period': 0,  # Placeholder
        'quick_actions': [
            {'label': 'Create Invoice', 'url': reverse('dea_sales_invoice_create'), 'icon': 'fa-file-invoice-dollar', 'description': 'Record customer sale'},
            {'label': 'Create Expense', 'url': reverse('dea_expense_create'), 'icon': 'fa-receipt', 'description': 'Record business expense'},
            {'label': 'Record Payment', 'url': reverse('dea_payment_create'), 'icon': 'fa-money-bill-wave', 'description': 'Record cash/bank movement'},
            {'label': 'Journal Entry', 'url': reverse('dea_journal_entry_create'), 'icon': 'fa-book', 'description': 'Manual GL adjustment'},
        ],
        'metrics': {
            'total_vouchers': Voucher.objects.count(),
            'posted_vouchers': Voucher.objects.filter(status=VoucherStatus.POSTED).count(),
            'draft_vouchers': Voucher.objects.filter(status=VoucherStatus.DRAFT).count(),
            'active_accounts': Account.objects.filter(status=AccountStatus.ACTIVE).count(),
            'total_ledgers': Ledger.objects.count(),
        },
        'financial_health': {
            'ar_balance': calculate_ar_balance(),
            'ap_balance': calculate_ap_balance(),
            'cash_position': calculate_cash_balance(),
            'net_pl': calculate_period_pl(),
        },
        'workflows': [
            {'title': 'Set Up Account Structure', 'steps': [
                {'text': 'View Chart of Accounts', 'url': '/dea/chart-of-accounts/'},
                {'text': 'Set Opening Balances', 'url': '/dea/opening-balance/create/'},
                {'text': 'Create Business Accounts', 'url': '/dea/accounts/create/'},
            ]},
            {'title': 'Record Customer Transactions', 'steps': [
                {'text': 'View Customers', 'url': '/dea/account/'},
                {'text': 'Create Invoice', 'url': '/dea/sales-invoice/create/'},
                {'text': 'Record Payment', 'url': '/dea/payment/create/'},
            ]},
            {'title': 'Record Supplier Transactions', 'steps': [
                {'text': 'View Suppliers', 'url': '/dea/account/?type=supplier'},
                {'text': 'Create Bill', 'url': '/dea/purchase-invoice/create/'},
                {'text': 'Record Payment', 'url': '/dea/payment/create/'},
            ]},
            {'title': 'Record Operating Expenses', 'steps': [
                {'text': 'Create Expense Entry', 'url': '/dea/expense/create/'},
                {'text': 'Categorize Expense', 'url': '/dea/expense/'},
                {'text': 'Post Expense', 'url': '/dea/expense/'},
            ]},
            {'title': 'Period-End Activities', 'steps': [
                {'text': 'Review GL', 'url': '/dea/ledger/'},
                {'text': 'Generate Reports', 'url': '/dea/reports/'},
                {'text': 'Close Period', 'url': '/dea/period/close/'},
            ]},
        ],
        'coa_preview': get_coa_preview(),
        'recent_vouchers': Voucher.objects.select_related('voucher_type', 'created_by').order_by('-created_at')[:8],
        'recent_entries': JournalEntry.objects.select_related('voucher').order_by('-posted_at')[:8],
        'report_links': [
            {'name': 'Trial Balance', 'url': reverse('trial_balance')},
            {'name': 'Balance Sheet', 'url': reverse('balance_sheet')},
            {'name': 'P&L', 'url': reverse('profit_loss')},
            {'name': 'Cash Flow', 'url': reverse('cash_flow')},
        ],
        'alerts': [],  # Placeholder for alert system
        'title': 'Accounting Dashboard (Enhanced)',
    }
    return render(request, 'dea/dashboard_enhanced.html', context)
