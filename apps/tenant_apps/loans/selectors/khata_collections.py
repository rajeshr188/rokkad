"""Today's collection attention; future instalments are estimates, never balances."""
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.domain.khata import anniversary
from apps.tenant_apps.loans.models import KhataOperation
from .khata import interest_schedule
from .khata_summary import summary_accounts, account_summary

ZERO = Decimal(0)


def collection_row(summary, *, horizon=7):
    account = summary["account"]
    if current_workspace_id() != account.workspace_id:
        raise ValueError("Khata collections require the matching Workspace context.")
    row = dict(summary, collection_status="review", next_due=None, next_unpaid=None,
        days_overdue=0, estimated=False)
    if summary.get("unavailable"):
        return row
    today = summary["as_of"]
    unpaid = [p for p in summary["schedule"] if p["outstanding"] > 0 and p["due_on"] <= today]
    if unpaid:
        due = min(p["due_on"] for p in unpaid)
        row.update(next_due=due,
            next_unpaid=sum((p["outstanding"] for p in unpaid if p["due_on"] == due), ZERO),
            days_overdue=(today - due).days, collection_status="overdue" if due < today else "due")
        return row
    # Restore the original anniversary after short months/leap years. Only
    # financially activated terms are replayed; pending proposals cannot forecast.
    months = (today.year - account.opened_on.year) * 12 + today.month - account.opened_on.month
    step = 12 if summary["agreement"].frequency == "ANNUAL" else 1
    index = max(step, (months // step) * step)
    while anniversary(account.opened_on, index) <= today:
        index += step
    due = anniversary(account.opened_on, index)
    projected = sum((p["outstanding"] for p in interest_schedule(account, due) if p["due_on"] == due), ZERO)
    if projected:
        row.update(next_due=due, next_unpaid=projected, estimated=True,
            collection_status="upcoming" if due <= today + timedelta(days=horizon) else "later")
    else:
        row["collection_status"] = "clear"
    return row


def collection_rows(*, workspace, filters=None, status="attention", horizon=7):
    """Filter all matched canonical rows before totals/paging. Review is never zero."""
    accounts = summary_accounts(workspace=workspace, balances_only=True,
        filters=dict(filters or {}, state="ACTIVE"))
    rows = []
    for account in accounts.iterator(chunk_size=250):
        try:
            summary = account_summary(account)
            row = collection_row(summary, horizon=horizon)
        except (ValueError, ArithmeticError, TypeError):
            row = dict(account=account, unavailable=True, collection_status="review",
                next_due=None, next_unpaid=None, days_overdue=0, estimated=False)
        if (row["collection_status"] == "review" or status == "all"
                or status == row["collection_status"]
                or status == "attention" and row["collection_status"] in ("due", "overdue", "upcoming")):
            rows.append(row)
    rows.sort(key=lambda r: (r["collection_status"] != "review", r["next_due"] or date.max,
        r["account"].pk))
    return rows


def recorded_exchange_warnings(*, workspace, account_ids):
    """Latest recorded warning, including an explicitly labelled compensated source."""
    if current_workspace_id() != workspace.pk:
        raise ValueError("Khata warnings require the matching Workspace context.")
    rows = KhataOperation.objects.filter(workspace=workspace, account_id__in=account_ids,
        kind="EXCHANGE", evidence__warnings__0__isnull=False).select_related("corrected_by").order_by(
            "account_id", "-sequence", "-pk").distinct("account_id")
    return {op.account_id: op for op in rows}
