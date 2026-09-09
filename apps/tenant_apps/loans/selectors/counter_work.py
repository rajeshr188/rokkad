"""Current counter work from loan states and canonical contractual obligations."""

from django.utils import timezone

from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from .obligation_state import calculate_obligation_state_as_of, get_active_repayment_schedule_as_of


def get_workspace_counter_work(*, workspace, as_of_date=None):
    if current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Counter work requires the matching Workspace context.")
    today = as_of_date or timezone.localdate()
    queues = {key: {"key": key, "title": title, "rows": []} for key, title in (
        ("draft", "Drafts to review"), ("approved", "Awaiting disbursal"),
        ("due", "Payments due today"), ("overdue", "Overdue payments"),
        ("review", "Schedule needs review"),
    )}
    loans = PawnLoan.objects.filter(workspace=workspace, state__in=("DRAFT", "APPROVED", "ACTIVE")).select_related("borrower").order_by("loan_date", "pk")
    for loan in loans:
        row = {"loan": loan, "date": loan.loan_date, "amount": None, "note": ""}
        if loan.state in ("DRAFT", "APPROVED"):
            queues[loan.state.lower()]["rows"].append(row)
            continue
        schedule = get_active_repayment_schedule_as_of(loan, today)
        state = calculate_obligation_state_as_of(schedule, today)
        if state.schedule_id is None or not state.obligations or state.integrity_findings:
            row["note"] = "No active repayment schedule or payment rows." if state.schedule_id is None or not state.obligations else "Repayment schedule has inconsistent allocations."
            queues["review"]["rows"].append(row)
            continue
        today_amount = state.due_now.total - state.overdue.total
        if today_amount > 0:
            queues["due"]["rows"].append({**row, "date": today, "amount": today_amount})
        if state.overdue.total > 0:
            earliest = min(item.due_date for item in state.obligations if item.due_date < today and item.total > 0)
            queues["overdue"]["rows"].append({**row, "date": earliest, "amount": state.overdue.total})
    for queue in queues.values():
        queue["rows"].sort(key=lambda row: (row["date"], row["loan"].pk))
        queue["count"] = len(queue["rows"])
    return {"as_of_date": today, "queues": queues}
