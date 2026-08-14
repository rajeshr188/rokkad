"""
Enhanced DEA Dashboard View - Unified UX
Phase 1.5 - Real data wired (Mar 27, 2026)
"""
from datetime import timedelta
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from ..models import (
    Account,
    AccountBalance,
    AccountStatus,
    AccountingPeriod,
    JournalEntry,
    Ledger,
    Voucher,
    VoucherStatus,
)
from ..utils.currency import Balance
from .access import can_view_dea_accountant_tools

# ---------------------------------------------------------------------------
# Financial data helpers
# ---------------------------------------------------------------------------

def calculate_ar_balance():
    """Sum of all active debtor (Dr) account balances."""
    total = Balance()
    for ab in AccountBalance.objects.filter(
        AccountType_Ext__XactTypeCode__XactTypeCode="Dr", current_balance__gt=0
    ).select_related("account"):
        total += Balance([ab.get_balance()])
    return total


def calculate_ap_balance():
    """Sum of all active creditor (Cr) account balances."""
    total = Balance()
    for ab in AccountBalance.objects.filter(
        AccountType_Ext__XactTypeCode__XactTypeCode="Cr", current_balance__gt=0
    ).select_related("account"):
        total += Balance([ab.get_balance()])
    return total


def calculate_cash_balance():
    """Sum of all cash/bank ledger balances."""
    total = Balance()
    for ledger in Ledger.objects.filter(
        Q(name__icontains="cash") | Q(name__icontains="bank")
    ):
        try:
            total += ledger.get_current_balance()
        except Exception:
            pass
    return total


def calculate_period_pl(period=None):
    """Net P&L (revenue - expenses) for the given or current period."""
    if period is None:
        period = AccountingPeriod.objects.get_current_period()
    if period is None:
        return Balance()
    revenue = Balance()
    expenses = Balance()
    for ledger in Ledger.objects.filter(AccountType__AccountType="Revenue"):
        try:
            revenue += Balance([ledger.calculate_period_balance(period)])
        except Exception:
            pass
    for ledger in Ledger.objects.filter(AccountType__AccountType="Expense"):
        try:
            expenses += Balance([ledger.calculate_period_balance(period)])
        except Exception:
            pass
    return revenue - expenses


def get_coa_preview():
    """Top accounts per class for the COA preview slot."""
    preview = []
    for at in ("Asset", "Liability", "Equity", "Revenue", "Expense"):
        qs = Ledger.objects.filter(
            AccountType__AccountType=at
        ).order_by("name")
        if not qs.exists():
            continue
        total = Balance()
        for ledger in qs[:3]:
            try:
                total += ledger.get_current_balance()
            except Exception:
                pass
        preview.append({
            "account_type": at,
            "count": qs.count(),
            "balance": total,
            "sample_accounts": list(qs.values_list("name", flat=True)[:3]),
        })
    return preview


# ---------------------------------------------------------------------------
# Alert & ranking helpers (mirrored from dashboard.py)
# ---------------------------------------------------------------------------

def _attach_balance_review_data(entries):
    reviewed = []
    for entry in entries:
        is_balanced, _, _, imbalances = entry.validate_balanced()
        entry.balance_review = {
            "is_balanced": is_balanced,
            "imbalance_text": ", ".join(str(a) for a in imbalances.values()),
        }
        reviewed.append(entry)
    return reviewed


def _get_dashboard_alerts():
    """Return alert dicts for the dashboard."""
    alerts = []

    # Accounts over credit limit
    for account in Account.objects.filter(
        status=AccountStatus.ACTIVE, credit_limit__isnull=False
    ):
        if account.is_over_credit_limit():
            alerts.append({
                "type": "danger",
                "icon": "exclamation-triangle",
                "title": "Credit Limit Exceeded",
                "message": f"{account.contact.name} ({account.account_number}) is over credit limit",
                "link": account.get_absolute_url(),
                "link_text": "View Account",
            })

    # Draft vouchers
    draft_count = Voucher.objects.filter(status=VoucherStatus.DRAFT).count()
    if draft_count:
        alerts.append({
            "type": "warning",
            "icon": "file-text",
            "title": "Unposted Vouchers",
            "message": f"{draft_count} draft voucher(s) pending posting",
            "link": "/dea/vouchers/?status=DRAFT",
            "link_text": "View Drafts",
        })

    # Multiple open periods
    open_periods = AccountingPeriod.objects.filter(
        status=AccountingPeriod.PeriodStatus.OPEN
    )
    if open_periods.count() > 1:
        alerts.append({
            "type": "info",
            "icon": "calendar",
            "title": "Multiple Open Periods",
            "message": f"{open_periods.count()} accounting periods are currently open",
            "link": "/dea/periods/",
            "link_text": "Manage Periods",
        })

    # Old open periods (> 90 days)
    ninety_days_ago = timezone.now().date() - timedelta(days=90)
    old_periods = open_periods.filter(end_date__lt=ninety_days_ago)
    if old_periods.exists():
        alerts.append({
            "type": "warning",
            "icon": "clock",
            "title": "Old Open Periods",
            "message": f"{old_periods.count()} open period(s) older than 90 days",
            "link": "/dea/periods/",
            "link_text": "Close Periods",
        })

    # Unbalanced journal entries (last 30 days)
    recent_entries = (
        JournalEntry.objects.filter(
            voucher__status=VoucherStatus.POSTED,
            posted_at__gte=timezone.now() - timedelta(days=30),
        )
        .select_related("voucher")
        .prefetch_related("ltxns", "atxns", "atxns__XactTypeCode")[:50]
    )
    unbalanced = [je for je in recent_entries if not je.validate_balanced()[0]]
    if unbalanced:
        if len(unbalanced) == 1:
            link, link_text = unbalanced[0].get_absolute_url(), "Review Entry"
            msg = f"Journal entry #{unbalanced[0].pk} is not balanced"
        else:
            link, link_text = "/dea/journal_entries/?balance_status=unbalanced", "Review Entries"
            msg = f"{len(unbalanced)} journal entry(ies) are not balanced"
        alerts.append({
            "type": "danger",
            "icon": "alert-triangle",
            "title": "Unbalanced Entries Found",
            "message": msg,
            "link": link,
            "link_text": link_text,
        })

    # Inactive accounts with no transactions
    inactive_count = (
        Account.objects.filter(status=AccountStatus.ACTIVE)
        .annotate(txn_count=Count("accounttransactions"))
        .filter(txn_count=0)
        .count()
    )
    if inactive_count > 10:
        alerts.append({
            "type": "info",
            "icon": "user-x",
            "title": "Inactive Accounts",
            "message": f"{inactive_count} active accounts with no transactions",
            "link": "/dea/account/",
            "link_text": "View Accounts",
        })

    return alerts


def _get_top_debtors(limit=5):
    debtors = []
    for ab in (
        AccountBalance.objects.filter(
            AccountType_Ext__XactTypeCode__XactTypeCode="Dr", current_balance__gt=0
        )
        .select_related("account", "contact")
        .order_by("-current_balance")[:limit]
    ):
        debtors.append({
            "account": ab.account,
            "contact": ab.contact,
            "balance": ab.get_balance(),
            "account_number": ab.account.account_number,
        })
    return debtors


def _get_top_creditors(limit=5):
    creditors = []
    for ab in (
        AccountBalance.objects.filter(
            AccountType_Ext__XactTypeCode__XactTypeCode="Cr", current_balance__gt=0
        )
        .select_related("account", "contact")
        .order_by("-current_balance")[:limit]
    ):
        creditors.append({
            "account": ab.account,
            "contact": ab.contact,
            "balance": ab.get_balance(),
            "account_number": ab.account.account_number,
        })
    return creditors

@login_required
def dashboard_enhanced(request):
    """
    Enhanced dashboard — primary landing page once URL is swapped.
    Combines the full data from dashboard.py with the UX structure
    (quick actions, guided workflows, COA preview) from this view.
    """
    current_period = AccountingPeriod.objects.get_current_period()

    # Days remaining in current period
    if current_period and current_period.end_date:
        days_in_period = max(0, (current_period.end_date - timezone.now().date()).days)
    else:
        days_in_period = 0

    # Financial data
    ar_balance = calculate_ar_balance()
    ap_balance = calculate_ap_balance()
    cash_balance = calculate_cash_balance()
    net_pl = calculate_period_pl(current_period)

    # Alerts, top accounts, recent activity
    alerts = _get_dashboard_alerts()
    top_debtors = _get_top_debtors(limit=5)
    top_creditors = _get_top_creditors(limit=5)

    recent_vouchers = Voucher.objects.select_related(
        "voucher_type", "created_by"
    ).order_by("-created_at")[:10]

    recent_entries = _attach_balance_review_data(
        JournalEntry.objects.select_related("voucher", "period", "posted_by")
        .prefetch_related("ltxns", "atxns", "atxns__XactTypeCode")
        .order_by("-posted_at")[:10]
    )

    show_accountant_tools = can_view_dea_accountant_tools(request)

    context = {
        "current_period": current_period,
        "period_status": "Open" if current_period else "No Period",
        "days_in_period": days_in_period,
        "quick_actions": [
            {"label": "Business Events", "url": reverse("dea_business_events_dashboard"), "icon": "fa-route", "description": "Run business-event workflows"},
            {"label": "Reports Hub", "url": reverse("dea_reports_hub"), "icon": "fa-chart-bar", "description": "Open financial and commodity reports"},
            {"label": "Metal Balance", "url": reverse("dea_metal_balance_report"), "icon": "fa-coins", "description": "Review commodity position balances"},
            {"label": "Exposure Report", "url": reverse("dea_exposure_report"), "icon": "fa-balance-scale", "description": "Track open purchase and sale exposure"},
        ],
        "metrics": {
            "total_vouchers": Voucher.objects.count(),
            "posted_vouchers": Voucher.objects.filter(status=VoucherStatus.POSTED).count(),
            "draft_vouchers": Voucher.objects.filter(status=VoucherStatus.DRAFT).count(),
            "active_accounts": Account.objects.filter(status=AccountStatus.ACTIVE).count(),
            "total_ledgers": Ledger.objects.count(),
            "open_periods": AccountingPeriod.objects.filter(
                status=AccountingPeriod.PeriodStatus.OPEN
            ).count(),
        },
        "financial_health": {
            "ar_balance": ar_balance,
            "ap_balance": ap_balance,
            "cash_position": cash_balance,
            "net_pl": net_pl,
        },
        "alerts": alerts,
        "top_debtors": top_debtors,
        "top_creditors": top_creditors,
        "workflows": [
            {"title": "Business Events Workflow", "steps": [
                {"text": "Open Business Events Dashboard", "url": reverse("dea_business_events_dashboard")},
                {"text": "Preview and confirm events", "url": reverse("dea_business_events_dashboard")},
                {"text": "Review reports", "url": reverse("dea_reports_hub")},
            ]},
            {"title": "Commodity Monitoring", "steps": [
                {"text": "Check Metal Balance", "url": reverse("dea_metal_balance_report")},
                {"text": "Check Commodity Exposure", "url": reverse("dea_exposure_report")},
                {"text": "Check Commodity Valuation", "url": reverse("dea_valuation_report")},
            ]},
            {"title": "Financial Reporting", "steps": [
                {"text": "Open Reports Hub", "url": reverse("dea_reports_hub")},
                {"text": "Run Trial Balance", "url": reverse("trial_balance")},
                {"text": "Run Balance Sheet", "url": reverse("balance_sheet")},
            ]},
        ],
        "coa_preview": get_coa_preview(),
        "recent_vouchers": recent_vouchers,
        "recent_entries": recent_entries,
        "report_links": [
            {"name": "Trial Balance", "url": reverse("trial_balance")},
            {"name": "Balance Sheet", "url": reverse("balance_sheet")},
            {"name": "P&L", "url": reverse("profit_loss")},
            {"name": "Cash Flow", "url": reverse("cash_flow")},
            {"name": "A/R Aging", "url": reverse("ar_aging")},
            {"name": "A/P Aging", "url": reverse("ap_aging")},
            {"name": "Ratios", "url": reverse("financial_ratios")},
        ],
        "commodity_report_links": [
            {"name": "Metal Balance", "url": reverse("dea_metal_balance_report")},
            {"name": "Commodity Exposure", "url": reverse("dea_exposure_report")},
            {"name": "Commodity Valuation", "url": reverse("dea_valuation_report")},
        ],
        "show_accountant_tools": show_accountant_tools,
        "title": "Accounting Dashboard",
    }

    if show_accountant_tools:
        context["quick_actions"].extend(
            [
                {"label": "Voucher Hub", "url": reverse("dea_voucher_hub"), "icon": "fa-book", "description": "Open manual accounting tools"},
                {"label": "Manage Periods", "url": reverse("dea_period_list"), "icon": "fa-calendar-alt", "description": "Open, close, and lock periods"},
            ]
        )
        context["workflows"].append(
            {
                "title": "Accountant Manual Tools",
                "steps": [
                    {"text": "Open Voucher Hub", "url": reverse("dea_voucher_hub")},
                    {"text": "Open Manual Journal Vouchers", "url": reverse("dea_journal_entry_voucher_list")},
                    {"text": "Open Opening Balance Wizard", "url": reverse("dea_opening_balance_wizard")},
                ],
            }
        )
    return render(request, "dea/dashboard_enhanced.html", context)
