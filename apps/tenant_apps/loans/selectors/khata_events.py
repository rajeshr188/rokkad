"""Readable saved operation evidence, without revaluing or replaying today's money."""
from decimal import Decimal

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import KhataOperation


def event_operations(account):
    if current_workspace_id() != account.workspace_id:
        raise ValueError("Khata events require the matching Workspace context.")
    return KhataOperation.objects.filter(workspace_id=account.workspace_id, account=account).select_related(
        "created_by", "agreement", "policy", "approval", "parent", "correction_of", "corrected_by", "item", "received_item")


def event_details(operation):
    if current_workspace_id() != operation.workspace_id:
        raise ValueError("Khata events require the matching Workspace context.")
    evidence = operation.evidence
    snapshot = evidence.get("review", evidence)
    # Whitelisted facts retain recorded meaning. Zero is evidence, not missing.
    facts = []
    money_fields = (("old_limit", "Previous agreed limit"), ("new_limit", "New agreed limit"),
        ("principal", "Principal at review"), ("new_principal", "Principal after change"),
        ("principal_repayment", "Approved principal repayment"), ("retained_value", "Recorded retained value"),
        ("backing", "Recorded LTV backing"), ("due_interest", "Interest due at review"),
        ("overdue_interest", "Interest overdue at review"))
    for key, label in money_fields:
        if key in snapshot:
            facts.append((label, Decimal(snapshot[key])))
    references = []
    for key, label in (("payment_reference", "Actual cash / payment reference"),
            ("agreement_reference", "Borrower consent / agreement reference"),
            ("reason", "Reason"), ("recipient", "Actual recipient"),
            ("received_from", "Received from"), ("reference", "Handover reference"),
            ("resolution_reference", "Correction / refund reference"), ("cash_resolution", "Cash resolution")):
        if evidence.get(key):
            references.append((label, evidence[key]))
    if operation.approval_id and operation.approval.evidence.get("agreement_reference"):
        references.append(("Borrower consent / agreement reference", operation.approval.evidence["agreement_reference"]))
    valuations = list(operation.valuations.filter(workspace_id=operation.workspace_id,
        item__account_id=operation.account_id).select_related("item").order_by("item_id"))
    values = {v.item_id: v for v in valuations}
    groups = {}
    for selection in operation.collateral_selections.filter(workspace_id=operation.workspace_id,
            item__account_id=operation.account_id).select_related("item").order_by("role", "item_id"):
        group = groups.setdefault((selection.item.metal, selection.role), dict(metal=selection.item.get_metal_display(),
            role=selection.role, rows=[], value=Decimal(0), net=Decimal(0), value_complete=True))
        valuation = values.get(selection.item_id)
        group["rows"].append(dict(item=selection.item, valuation=valuation))
        group["net"] += selection.item.net_weight
        if valuation is None:
            group["value_complete"] = False
        else:
            group["value"] += valuation.value
    related = [(label, getattr(operation, name)) for name, label in (
        ("approval", "Approval source"), ("parent", "Return reservation source"),
        ("correction_of", "Corrects source"), ("corrected_by", "Corrected by")) if getattr(operation, name, None)]
    periods = operation.interest_periods.filter(workspace_id=operation.workspace_id, account_id=operation.account_id).prefetch_related(
        "segments__agreement").order_by("index")
    allocations = operation.interest_allocations.filter(workspace_id=operation.workspace_id,
        period__account_id=operation.account_id).select_related("period").order_by("period__index")
    return dict(operation=operation, snapshot=snapshot, facts=facts, references=references,
        recorded_ltv=operation.agreement.ltv * 100 if operation.agreement_id else None,
        groups=list(groups.values()), valuations=valuations, related=related,
        shortfalls=[(metal.title(), Decimal(value)) for metal, value in snapshot.get("shortfalls", {}).items()],
        warnings=snapshot.get("warnings", []), periods=periods, allocations=allocations)
