import logging

from django.contrib.auth.decorators import login_required
from django.template.response import TemplateResponse

from ..models import Ledger, LedgerBalance
from ..utils.currency import Balance, Money

logger = logging.getLogger(__name__)


# COA display order
_ACCOUNT_TYPE_ORDER = ["Asset", "Liability", "Equity", "Revenue", "Expense"]


@login_required
def chart_of_accounts(request):
    """
    Chart of Accounts Navigator — groups all ledgers by AccountType, shows
    current balances from the LedgerBalance view, preserves MPTT tree ordering.
    """
    # Pull balances once; LedgerBalance is a DB view (managed=False), one row per ledger.
    balance_map: dict[int, LedgerBalance] = {
        lb.ledgerno_id: lb
        for lb in LedgerBalance.objects.select_related("AccountType").all()
    }

    # Pull ledgers in MPTT tree order with their account types
    all_ledgers = Ledger.objects.select_related(
        "AccountType", "parent"
    ).order_by("tree_id", "lft")

    # Group by AccountType.AccountType string, preserving display order
    groups: list[dict] = []
    seen: dict[str, dict] = {}

    for at_label in _ACCOUNT_TYPE_ORDER:
        seen[at_label] = {
            "label": at_label,
            "rows": [],
            "total": Balance(),
        }

    for ledger in all_ledgers:
        at_label = ledger.AccountType.AccountType
        if at_label not in seen:
            seen[at_label] = {"label": at_label, "rows": [], "total": Balance()}

        lb = balance_map.get(ledger.pk)
        if lb is not None:
            balance = Money(lb.current_balance, lb.currency)
        else:
            balance = None

        seen[at_label]["rows"].append({
            "ledger": ledger,
            "depth": ledger.level,           # MPTT level for indentation
            "code": ledger.code,
            "name": ledger.name,
            "balance": balance,
            "detail_url": ledger.get_absolute_url(),
        })

        if balance is not None:
            seen[at_label]["total"] += Balance([balance])

    # Build ordered list, skip empty groups
    for at_label in _ACCOUNT_TYPE_ORDER:
        group = seen[at_label]
        if group["rows"]:
            groups.append(group)

    # Any extra types not in our display order
    for at_label, group in seen.items():
        if at_label not in _ACCOUNT_TYPE_ORDER and group["rows"]:
            groups.append(group)

    context = {
        "groups": groups,
        "total_ledgers": len(all_ledgers),
        "title": "Chart of Accounts",
    }
    return TemplateResponse(request, "dea/chart_of_accounts.html", context)
