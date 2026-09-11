"""Current counter work from loan states and canonical contractual obligations."""

from django.utils import timezone

from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from .obligation_state import get_obligation_states_for_loans


def get_workspace_counter_work(*, workspace, as_of_date=None):
    if current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Counter work requires the matching Workspace context.")
    today = as_of_date or timezone.localdate()
    queues = {key: {"key": key, "title": title, "rows": []} for key, title in (
        ("draft", "Drafts to review"), ("approved", "Awaiting disbursal"),
        ("due", "Payments due today"), ("overdue", "Overdue payments"),
        ("review", "Schedule needs review"),
    )}
    loans = list(PawnLoan.objects.filter(workspace=workspace, state__in=("DRAFT", "APPROVED", "ACTIVE")).select_related("borrower").order_by("loan_date", "pk"))
    states = get_obligation_states_for_loans(
        workspace=workspace, loan_ids=[loan.pk for loan in loans if loan.state == "ACTIVE"],
        as_of_date=today,
    )
    for loan in loans:
        row = {"loan": loan, "date": loan.loan_date, "amount": None, "note": ""}
        if loan.state in ("DRAFT", "APPROVED"):
            queues[loan.state.lower()]["rows"].append(row)
            continue
        state = states[loan.pk]
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
