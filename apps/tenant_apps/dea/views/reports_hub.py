from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse
from django.urls import reverse


@login_required
def reports_hub(request):
    """Centralized hub for all financial and operational reports."""
    report_groups = [
        {
            "title": "Financial Statements",
            "description": "Core statutory and management financial statements.",
            "items": [
                {"name": "Trial Balance", "url": reverse("trial_balance"), "icon": "fa-balance-scale"},
                {"name": "Balance Sheet", "url": reverse("balance_sheet"), "icon": "fa-landmark"},
                {"name": "Profit & Loss", "url": reverse("profit_loss"), "icon": "fa-chart-line"},
                {"name": "Cash Flow", "url": reverse("cash_flow"), "icon": "fa-money-bill-wave"},
            ],
        },
        {
            "title": "Analysis Reports",
            "description": "Aging and ratio analysis for finance monitoring.",
            "items": [
                {"name": "A/R Aging", "url": reverse("ar_aging"), "icon": "fa-user-clock"},
                {"name": "A/P Aging", "url": reverse("ap_aging"), "icon": "fa-file-invoice-dollar"},
                {"name": "Financial Ratios", "url": reverse("financial_ratios"), "icon": "fa-percentage"},
            ],
        },
        {
            "title": "Commodity Reports",
            "description": "Read-only metal quantity, exposure, and valuation reports.",
            "items": [
                {"name": "Metal Balance", "url": reverse("dea_metal_balance_report"), "icon": "fa-coins"},
                {"name": "Commodity Exposure", "url": reverse("dea_exposure_report"), "icon": "fa-chart-area"},
                {"name": "Commodity Valuation", "url": reverse("dea_valuation_report"), "icon": "fa-scale-balanced"},
            ],
        },
        {
            "title": "Transactional Reports",
            "description": "Day-to-day accounting ledgers and transaction views.",
            "items": [
                {"name": "Unified Transactions", "url": reverse("dea_transaction_list"), "icon": "fa-stream"},
                {"name": "Journal Entries", "url": reverse("dea_journal_entries_list"), "icon": "fa-book"},
                {"name": "Vouchers", "url": reverse("dea_voucher_list"), "icon": "fa-receipt"},
                {"name": "Ledger List", "url": reverse("dea_ledger_list"), "icon": "fa-list"},
                {"name": "Period List", "url": reverse("dea_period_list"), "icon": "fa-calendar-alt"},
            ],
        },
    ]

    context = {
        "title": "Reports Hub",
        "report_groups": report_groups,
    }
    return TemplateResponse(request, "dea/reports_hub.html", context)
