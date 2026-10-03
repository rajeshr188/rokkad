"""Account-scoped source history reads; display filters never affect balances."""
from django.db.models import Q

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import KhataCollateralItem, KhataOperation


def history_operations(account, data):
    if current_workspace_id() != account.workspace_id:
        raise ValueError("Khata history requires the matching Workspace context.")
    operations = KhataOperation.objects.filter(workspace_id=account.workspace_id, account_id=account.pk)
    if data.get("kind"):
        operations = operations.filter(kind=data["kind"])
    if data.get("operation"):
        operations = operations.filter(pk=data["operation"])
    if data.get("from_date"):
        operations = operations.filter(business_date__gte=data["from_date"])
    if data.get("to_date"):
        operations = operations.filter(business_date__lte=data["to_date"])
    term = data.get("q", "").strip()
    if term:
        match = Q(pk=int(term)) if term.isdecimal() and len(term) <= 18 else (
            Q(description__icontains=term) | Q(storage_reference__icontains=term) | Q(public_id__icontains=term))
        items = KhataCollateralItem.objects.filter(workspace_id=account.workspace_id, account_id=account.pk).filter(match)
        operations = operations.filter(Q(received_item__in=items) | Q(item__in=items)
            | Q(collateral_selections__item__in=items) | Q(evidence__payment_reference__icontains=term)
            | Q(evidence__reference__icontains=term)).distinct()
    prefix = "" if data.get("sort") == "oldest" else "-"
    return operations.select_related("received_item", "item", "corrected_by", "created_by").order_by(
        prefix + "business_date", prefix + "sequence", prefix + "pk")
