"""
DEA Dashboard - Central overview of accounting system
Shows key metrics, alerts, charts, and quick access to common tasks
"""
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse
from djmoney.money import Money

from ..models import (
    Account,
    Ledger,
    LedgerBalance,
    AccountBalance,
    JournalEntry,
    Voucher,
    VoucherStatus,
    AccountingPeriod,
    AccountStatus,
)
from ..utils.currency import Balance


def _attach_balance_review_data(entries):
    reviewed_entries = []

    for entry in entries:
        is_balanced, _, _, imbalances = entry.validate_balanced()
        entry.balance_review = {
            "is_balanced": is_balanced,
            "imbalance_text": ", ".join(str(amount) for amount in imbalances.values()),
        }
        reviewed_entries.append(entry)

    return reviewed_entries


@login_required
def dashboard(request):
    """
    Main DEA dashboard showing:
    - Key financial metrics
    - Current period summary
    - Alerts and warnings
    - Top debtors/creditors
    - Recent transactions
    - Quick actions
    """
    current_period = AccountingPeriod.objects.get_current_period()

    if current_period and current_period.end_date:
        days_in_period = max(0, (current_period.end_date - timezone.now().date()).days)
    else:
        days_in_period = 0

    # Calculate key metrics
    metrics = _calculate_key_metrics(current_period)

    # Get current period P&L
    period_summary = _get_period_summary(current_period) if current_period else None

    # Get alerts
    alerts = _get_dashboard_alerts()

    # Get top accounts
    top_debtors = _get_top_debtors(limit=5)
    top_creditors = _get_top_creditors(limit=5)

    # Recent activity
    recent_vouchers = Voucher.objects.select_related(
        "voucher_type", "created_by"
    ).order_by("-created_at")[:10]

    recent_entries = _attach_balance_review_data(
        JournalEntry.objects.select_related("voucher", "period", "posted_by")
        .prefetch_related("ltxns", "atxns", "atxns__XactTypeCode")
        .order_by("-posted_at")[:10]
    )

    # Quick stats
    stats = {
        "total_vouchers": Voucher.objects.count(),
        "posted_vouchers": Voucher.objects.filter(status=VoucherStatus.POSTED).count(),
        "draft_vouchers": Voucher.objects.filter(status=VoucherStatus.DRAFT).count(),
        "active_accounts": Account.objects.filter(status=AccountStatus.ACTIVE).count(),
        "total_ledgers": Ledger.objects.count(),
        "open_periods": AccountingPeriod.objects.filter(
            status=AccountingPeriod.PeriodStatus.OPEN
        ).count(),
    }

    quick_actions = [
        {
            "label": "Create Invoice",
            "url": reverse("dea_sales_invoice_create"),
            "icon": "fa-file-invoice-dollar",
            "description": "Record customer sale",
        },
        {
            "label": "Create Expense",
            "url": reverse("dea_expense_create"),
            "icon": "fa-receipt",
            "description": "Record business expense",
        },
        {
            "label": "Record Payment",
            "url": reverse("dea_payment_create"),
            "icon": "fa-money-bill-wave",
            "description": "Record cash/bank movement",
        },
        {
            "label": "Journal Entry Voucher",
            "url": reverse("dea_journal_entry_voucher_create"),
            "icon": "fa-book",
            "description": "Manual GL adjustment",
        },
        {
            "label": "Manage Periods",
            "url": reverse("dea_period_list"),
            "icon": "fa-calendar-alt",
            "description": "Open, close, and lock periods",
        },
    ]

    workflows = [
        {
            "title": "Set Up Account Structure",
            "steps": [
                {"text": "View Chart of Accounts", "url": reverse("dea_chart_of_accounts")},
                {"text": "Create Business Accounts", "url": reverse("dea_account_list")},
                {"text": "Manage Accounting Periods", "url": reverse("dea_period_list")},
            ],
        },
        {
            "title": "Record Customer Transactions",
            "steps": [
                {"text": "View Customers", "url": reverse("dea_account_list")},
                {"text": "Create Invoice", "url": reverse("dea_sales_invoice_create")},
                {"text": "Record Payment", "url": reverse("dea_payment_create")},
            ],
        },
        {
            "title": "Record Expenses",
            "steps": [
                {"text": "Create Expense Voucher", "url": reverse("dea_expense_create")},
                {"text": "Review Expenses", "url": reverse("dea_expense_list")},
                {"text": "View All Vouchers", "url": reverse("dea_voucher_list")},
            ],
        },
        {
            "title": "Period-End Activities",
            "steps": [
                {"text": "Review General Ledger", "url": reverse("dea_ledger_list")},
                {"text": "Review Journal Entries", "url": reverse("dea_journal_entries_list")},
                {"text": "Open/Close Periods", "url": reverse("dea_period_list")},
            ],
        },
    ]

    context = {
        "current_period": current_period,
        "period_status": "Open" if current_period else "No Period",
        "days_in_period": days_in_period,
        "metrics": metrics,
        "financial_health": {
            "ar_balance": metrics.get("total_receivables", Balance()),
            "ap_balance": metrics.get("total_payables", Balance()),
            "cash_position": metrics.get("total_cash", Balance()),
            "net_pl": metrics.get("net_profit", Balance()),
        },
        "period_summary": period_summary,
        "alerts": alerts,
        "top_debtors": top_debtors,
        "top_creditors": top_creditors,
        "recent_vouchers": recent_vouchers,
        "recent_entries": recent_entries,
        "stats": stats,
        "quick_actions": quick_actions,
        "workflows": workflows,
        "report_links": [
            {"name": "Reports Hub", "url": reverse("dea_reports_hub")},
            {"name": "Trial Balance", "url": reverse("trial_balance")},
            {"name": "Balance Sheet", "url": reverse("balance_sheet")},
            {"name": "P&L", "url": reverse("profit_loss")},
            {"name": "Cash Flow", "url": reverse("cash_flow")},
            {"name": "A/R Aging", "url": reverse("ar_aging")},
            {"name": "A/P Aging", "url": reverse("ap_aging")},
            {"name": "Ratios", "url": reverse("financial_ratios")},
        ],
        "title": "Accounting Dashboard",
    }

    return render(request, "dea/dashboard.html", context)


def _calculate_key_metrics(period=None):
    """Calculate key financial metrics"""
    metrics = {}

    # Cash position - sum of all cash/bank ledgers
    cash_ledgers = Ledger.objects.filter(
        Q(name__icontains="cash") | Q(name__icontains="bank")
    )
    total_cash = Balance()
    for ledger in cash_ledgers:
        try:
            balance = ledger.get_current_balance()
            total_cash += balance
        except Exception:
            pass
    metrics["total_cash"] = total_cash

    # Total receivables (Debtor accounts)
    total_ar = Balance()
    for balance in AccountBalance.objects.filter(
        AccountType_Ext__XactTypeCode__XactTypeCode="Dr"
    ).select_related("account"):
        if balance.current_balance > 0:
            total_ar += Balance([balance.get_balance()])
    metrics["total_receivables"] = total_ar

    # Total payables (Creditor accounts)
    total_ap = Balance()
    for balance in AccountBalance.objects.filter(
        AccountType_Ext__XactTypeCode__XactTypeCode="Cr"
    ).select_related("account"):
        if balance.current_balance > 0:
            total_ap += Balance([balance.get_balance()])
    metrics["total_payables"] = total_ap

    # Net working capital (AR - AP)
    # This is simplified - proper NWC = Current Assets - Current Liabilities
    metrics["net_working_capital"] = total_ar - total_ap

    # Period-specific metrics
    if period:
        # Revenue for period
        revenue_ledgers = Ledger.objects.filter(
            AccountType__AccountType="Revenue", is_operating_revenue=True
        )
        period_revenue = Balance()
        for ledger in revenue_ledgers:
            try:
                amount = ledger.calculate_period_balance(period)
                period_revenue += Balance([amount])
            except Exception:
                pass
        metrics["period_revenue"] = period_revenue

        # Expenses for period
        expense_ledgers = Ledger.objects.filter(
            AccountType__AccountType="Expense", is_operating_expense=True
        )
        period_expenses = Balance()
        for ledger in expense_ledgers:
            try:
                amount = ledger.calculate_period_balance(period)
                period_expenses += Balance([amount])
            except Exception:
                pass
        metrics["period_expenses"] = period_expenses

        # Net profit
        metrics["net_profit"] = period_revenue - period_expenses

        # Profit margin (if revenue > 0)
        try:
            revenue_inr = period_revenue.get("INR", Money(0, "INR"))
            if revenue_inr.amount > 0:
                profit_inr = metrics["net_profit"].get("INR", Money(0, "INR"))
                margin = (profit_inr.amount / revenue_inr.amount) * 100
                metrics["profit_margin"] = f"{margin:.2f}%"
            else:
                metrics["profit_margin"] = "N/A"
        except Exception:
            metrics["profit_margin"] = "N/A"

    return metrics


def _get_period_summary(period):
    """Get detailed P&L summary for current period"""
    summary = {
        "period": period,
        "revenue": Balance(),
        "cogs": Balance(),
        "gross_profit": Balance(),
        "operating_expenses": Balance(),
        "operating_profit": Balance(),
        "other_income": Balance(),
        "other_expenses": Balance(),
        "net_profit": Balance(),
    }

    # Revenue
    for ledger in Ledger.objects.filter(
        AccountType__AccountType="Revenue", is_operating_revenue=True
    ):
        try:
            amount = ledger.calculate_period_balance(period)
            summary["revenue"] += Balance([amount])
        except Exception:
            pass

    # COGS
    for ledger in Ledger.objects.filter(
        AccountType__AccountType="Expense", is_direct_expense=True
    ):
        try:
            amount = ledger.calculate_period_balance(period)
            summary["cogs"] += Balance([amount])
        except Exception:
            pass

    # Gross Profit
    summary["gross_profit"] = summary["revenue"] - summary["cogs"]

    # Operating Expenses
    for ledger in Ledger.objects.filter(
        AccountType__AccountType="Expense", is_operating_expense=True
    ):
        try:
            amount = ledger.calculate_period_balance(period)
            summary["operating_expenses"] += Balance([amount])
        except Exception:
            pass

    # Operating Profit
    summary["operating_profit"] = (
        summary["gross_profit"] - summary["operating_expenses"]
    )

    # Other Income (non-operating revenue)
    for ledger in Ledger.objects.filter(
        AccountType__AccountType="Revenue", is_operating_revenue=False
    ):
        try:
            amount = ledger.calculate_period_balance(period)
            summary["other_income"] += Balance([amount])
        except Exception:
            pass

    # Other Expenses (non-operating)
    for ledger in Ledger.objects.filter(
        AccountType__AccountType="Expense",
        is_operating_expense=False,
        is_direct_expense=False,
    ):
        try:
            amount = ledger.calculate_period_balance(period)
            summary["other_expenses"] += Balance([amount])
        except Exception:
            pass

    # Net Profit
    summary["net_profit"] = (
        summary["operating_profit"]
        + summary["other_income"]
        - summary["other_expenses"]
    )

    return summary


def _get_dashboard_alerts():
    """Get alerts and warnings for dashboard"""
    alerts = []

    # Check for accounts over credit limit
    over_limit = Account.objects.filter(
        status=AccountStatus.ACTIVE, credit_limit__isnull=False
    )

    for account in over_limit:
        if account.is_over_credit_limit():
            alerts.append(
                {
                    "type": "danger",
                    "icon": "exclamation-triangle",
                    "title": "Credit Limit Exceeded",
                    "message": f"{account.contact.name} ({account.account_number}) is over credit limit",
                    "link": account.get_absolute_url(),
                    "link_text": "View Account",
                }
            )

    # Check for draft vouchers
    draft_count = Voucher.objects.filter(status=VoucherStatus.DRAFT).count()
    if draft_count > 0:
        alerts.append(
            {
                "type": "warning",
                "icon": "file-text",
                "title": "Unposted Vouchers",
                "message": f"{draft_count} draft voucher(s) pending posting",
                "link": "/dea/vouchers/?status=DRAFT",
                "link_text": "View Drafts",
            }
        )

    # Check for open accounting periods
    open_periods = AccountingPeriod.objects.filter(
        status=AccountingPeriod.PeriodStatus.OPEN
    )
    if open_periods.count() > 1:
        alerts.append(
            {
                "type": "info",
                "icon": "calendar",
                "title": "Multiple Open Periods",
                "message": f"{open_periods.count()} accounting periods are currently open",
                "link": "/dea/periods/",
                "link_text": "Manage Periods",
            }
        )

    # Check for old open periods (> 90 days old)
    ninety_days_ago = timezone.now().date() - timedelta(days=90)
    old_periods = open_periods.filter(end_date__lt=ninety_days_ago)
    if old_periods.exists():
        alerts.append(
            {
                "type": "warning",
                "icon": "clock",
                "title": "Old Open Periods",
                "message": f"{old_periods.count()} open period(s) older than 90 days",
                "link": "/dea/periods/",
                "link_text": "Close Periods",
            }
        )

    # Check for unbalanced journal entries
    recent_entries = (
        JournalEntry.objects.filter(
            voucher__status=VoucherStatus.POSTED,
            posted_at__gte=timezone.now() - timedelta(days=30),
        )
        .select_related("voucher")
        .prefetch_related("ltxns", "atxns", "atxns__XactTypeCode")[:50]
    )  # Check last 50 entries

    unbalanced = []
    for je in recent_entries:
        is_balanced, _, _, _ = je.validate_balanced()
        if not is_balanced:
            unbalanced.append(je)

    if unbalanced:
        if len(unbalanced) == 1:
            review_link = unbalanced[0].get_absolute_url()
            review_text = "Review Entry"
            review_message = f"Journal entry #{unbalanced[0].pk} is not balanced"
        else:
            review_link = "/dea/journal_entries/?balance_status=unbalanced"
            review_text = "Review Entries"
            review_message = f"{len(unbalanced)} journal entry(ies) are not balanced"

        alerts.append(
            {
                "type": "danger",
                "icon": "alert-triangle",
                "title": "Unbalanced Entries Found",
                "message": review_message,
                "link": review_link,
                "link_text": review_text,
            }
        )

    # Check for accounts with no transactions in 90 days
    inactive_accounts = (
        Account.objects.filter(status=AccountStatus.ACTIVE)
        .annotate(last_txn=Count("accounttransactions"))
        .filter(last_txn=0)
    )

    if inactive_accounts.count() > 10:
        alerts.append(
            {
                "type": "info",
                "icon": "user-x",
                "title": "Inactive Accounts",
                "message": f"{inactive_accounts.count()} active accounts with no transactions",
                "link": "/dea/account/",
                "link_text": "View Accounts",
            }
        )

    return alerts


def _get_top_debtors(limit=5):
    """Get top debtors by balance"""
    debtors = []

    for balance in (
        AccountBalance.objects.filter(
            AccountType_Ext__XactTypeCode__XactTypeCode="Dr", current_balance__gt=0
        )
        .select_related("account", "contact")
        .order_by("-current_balance")[:limit]
    ):
        debtors.append(
            {
                "account": balance.account,
                "contact": balance.contact,
                "balance": balance.get_balance(),
                "account_number": balance.account.account_number,
            }
        )

    return debtors


def _get_top_creditors(limit=5):
    """Get top creditors by balance"""
    creditors = []

    for balance in (
        AccountBalance.objects.filter(
            AccountType_Ext__XactTypeCode__XactTypeCode="Cr", current_balance__gt=0
        )
        .select_related("account", "contact")
        .order_by("-current_balance")[:limit]
    ):
        creditors.append(
            {
                "account": balance.account,
                "contact": balance.contact,
                "balance": balance.get_balance(),
                "account_number": balance.account.account_number,
            }
        )

    return creditors


@login_required
def dashboard_metrics_ajax(request):
    """AJAX endpoint for refreshing dashboard metrics"""
    current_period = AccountingPeriod.objects.get_current_period()
    metrics = _calculate_key_metrics(current_period)

    # Convert Balance objects to strings for JSON
    metrics_json = {}
    for key, value in metrics.items():
        if isinstance(value, Balance):
            metrics_json[key] = str(value)
        else:
            metrics_json[key] = value

    return JsonResponse({"success": True, "metrics": metrics_json})


@login_required
def receivables_aging(request):
    """Accounts Receivable aging report"""
    # Get all debtor accounts with positive balance
    debtors = Account.objects.filter(
        AccountType_Ext__XactTypeCode__XactTypeCode="Dr", status=AccountStatus.ACTIVE
    ).select_related("contact", "AccountType_Ext")

    aging_data = []
    today = timezone.now().date()

    for account in debtors:
        balance = account.current_balance()
        if balance.is_zero():
            continue

        # Get oldest unpaid transaction
        oldest_txn = (
            account.accounttransactions.filter(XactTypeCode__XactTypeCode="Dr")
            .order_by("created")
            .first()
        )

        if oldest_txn:
            days_old = (today - oldest_txn.created.date()).days

            # Categorize by age
            if days_old <= 30:
                bucket = "current"
            elif days_old <= 60:
                bucket = "31-60"
            elif days_old <= 90:
                bucket = "61-90"
            else:
                bucket = "90+"

            aging_data.append(
                {
                    "account": account,
                    "contact": account.contact,
                    "balance": balance,
                    "days_old": days_old,
                    "bucket": bucket,
                    "oldest_date": oldest_txn.created.date(),
                }
            )

    # Group by bucket
    buckets = {"current": [], "31-60": [], "61-90": [], "90+": []}

    totals = {
        "current": Balance(),
        "31-60": Balance(),
        "61-90": Balance(),
        "90+": Balance(),
    }

    for item in aging_data:
        bucket = item["bucket"]
        buckets[bucket].append(item)
        totals[bucket] += item["balance"]

    context = {
        "aging_data": aging_data,
        "buckets": buckets,
        "totals": totals,
        "grand_total": sum(totals.values(), Balance()),
        "title": "Accounts Receivable Aging",
    }

    return render(request, "dea/reports/ar_aging.html", context)


@login_required
def payables_aging(request):
    """Accounts Payable aging report"""
    # Get all creditor accounts with positive balance
    creditors = Account.objects.filter(
        AccountType_Ext__XactTypeCode__XactTypeCode="Cr", status=AccountStatus.ACTIVE
    ).select_related("contact", "AccountType_Ext")

    aging_data = []
    today = timezone.now().date()

    for account in creditors:
        balance = account.current_balance()
        if balance.is_zero():
            continue

        # Get oldest unpaid transaction
        oldest_txn = (
            account.accounttransactions.filter(XactTypeCode__XactTypeCode="Cr")
            .order_by("created")
            .first()
        )

        if oldest_txn:
            days_old = (today - oldest_txn.created.date()).days

            # Categorize by age
            if days_old <= 30:
                bucket = "current"
            elif days_old <= 60:
                bucket = "31-60"
            elif days_old <= 90:
                bucket = "61-90"
            else:
                bucket = "90+"

            aging_data.append(
                {
                    "account": account,
                    "contact": account.contact,
                    "balance": balance,
                    "days_old": days_old,
                    "bucket": bucket,
                    "oldest_date": oldest_txn.created.date(),
                }
            )

    # Group by bucket
    buckets = {"current": [], "31-60": [], "61-90": [], "90+": []}

    totals = {
        "current": Balance(),
        "31-60": Balance(),
        "61-90": Balance(),
        "90+": Balance(),
    }

    for item in aging_data:
        bucket = item["bucket"]
        buckets[bucket].append(item)
        totals[bucket] += item["balance"]

    context = {
        "aging_data": aging_data,
        "buckets": buckets,
        "totals": totals,
        "grand_total": sum(totals.values(), Balance()),
        "title": "Accounts Payable Aging",
    }

    return render(request, "dea/reports/ap_aging.html", context)


@login_required
def financial_ratios(request):
    """Calculate and display financial ratios"""
    # Get current balances
    current_assets = Balance()
    fixed_assets = Balance()
    current_liabilities = Balance()
    long_term_liabilities = Balance()
    equity = Balance()

    # Calculate asset balances
    for balance in LedgerBalance.objects.filter(
        AccountType__AccountType="Asset"
    ).select_related("ledgerno", "AccountType"):
        amount = balance.get_balance()
        # Simplified: you'd need to mark ledgers as current vs fixed
        if "current" in balance.ledger_name.lower():
            current_assets += Balance([amount])
        else:
            fixed_assets += Balance([amount])

    # Calculate liability balances
    for balance in LedgerBalance.objects.filter(
        AccountType__AccountType="Liability"
    ).select_related("ledgerno", "AccountType"):
        amount = balance.get_balance()
        if "current" in balance.ledger_name.lower():
            current_liabilities += Balance([amount])
        else:
            long_term_liabilities += Balance([amount])

    # Calculate equity
    for balance in LedgerBalance.objects.filter(
        AccountType__AccountType="Equity"
    ).select_related("ledgerno", "AccountType"):
        amount = balance.get_balance()
        equity += Balance([amount])

    # Calculate ratios (in INR for simplicity)
    ratios = {}

    try:
        ca_inr = current_assets.get("INR", Money(0, "INR")).amount
        cl_inr = current_liabilities.get("INR", Money(0, "INR")).amount

        # Current Ratio
        if cl_inr > 0:
            ratios["current_ratio"] = ca_inr / cl_inr
        else:
            ratios["current_ratio"] = None

        # Quick Ratio (simplified - should exclude inventory)
        if cl_inr > 0:
            ratios["quick_ratio"] = ca_inr / cl_inr  # Simplified
        else:
            ratios["quick_ratio"] = None

        # Debt to Equity
        total_liabilities = (
            current_liabilities.get("INR", Money(0, "INR")).amount
            + long_term_liabilities.get("INR", Money(0, "INR")).amount
        )
        equity_inr = equity.get("INR", Money(0, "INR")).amount

        if equity_inr > 0:
            ratios["debt_to_equity"] = total_liabilities / equity_inr
        else:
            ratios["debt_to_equity"] = None

    except Exception as e:
        ratios = {"error": str(e)}

    context = {
        "current_assets": current_assets,
        "fixed_assets": fixed_assets,
        "total_assets": current_assets + fixed_assets,
        "current_liabilities": current_liabilities,
        "long_term_liabilities": long_term_liabilities,
        "total_liabilities": current_liabilities + long_term_liabilities,
        "equity": equity,
        "ratios": ratios,
        "title": "Financial Ratios",
    }

    return render(request, "dea/reports/financial_ratios.html", context)
