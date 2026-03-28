import logging

from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse

from ..models import AccountingPeriod

logger = logging.getLogger(__name__)

# Voucher type definitions — url_name must be registered in urls.py
_VOUCHER_TYPES = [
    {
        "key": "journal_entry_voucher",
        "label": "Journal Entry Voucher",
        "icon": "📒",
        "description": "Manually record any double-entry transaction (adjustments, accruals, corrections).",
        "url_name": "dea_journal_entry_voucher_create",
        "category": "General",
    },
    {
        "key": "payment",
        "label": "Payment Voucher",
        "icon": "💳",
        "description": "Record a payment made to a vendor or other party (cash or bank).",
        "url_name": "dea_payment_create",
        "category": "Payments & Receipts",
    },
    {
        "key": "expense",
        "label": "Expense Voucher",
        "icon": "🧾",
        "description": "Record a business expense against an expense ledger account.",
        "url_name": "dea_expense_create",
        "category": "Expenses",
    },
    {
        "key": "sales_invoice",
        "label": "Sales Invoice",
        "icon": "🏷",
        "description": "Create a sales invoice and post the corresponding revenue and receivable.",
        "url_name": "dea_sales_invoice_create",
        "category": "Sales",
    },
]


@login_required
def voucher_hub(request):
    """
    Voucher Creation Hub — a single landing page showing all voucher types
    with brief descriptions and direct links to their creation forms.
    """
    try:
        open_period = AccountingPeriod.objects.filter(
            status=AccountingPeriod.PeriodStatus.OPEN
        ).latest("start_date")
    except AccountingPeriod.DoesNotExist:
        open_period = None

    context = {
        "voucher_types": _VOUCHER_TYPES,
        "open_period": open_period,
        "title": "Create Voucher",
    }
    return TemplateResponse(request, "dea/voucher_hub.html", context)
