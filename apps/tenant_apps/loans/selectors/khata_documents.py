"""Search retained issues only; never regenerate PDFs or replay account balances."""
import uuid

from django.db.models import Q

from apps.tenant_apps.loans.models import KhataDocumentIssue


def saved_documents(account, data):
    issues = KhataDocumentIssue.objects.filter(workspace_id=account.workspace_id, account_id=account.pk)
    q = (data.get("q") or "").strip()
    if q:
        match = Q(payload__title__icontains=q) | Q(payload__source__evidence__payment_reference__icontains=q)
        if q.isdecimal() and len(q) <= 18:
            number = int(q)
            match |= Q(pk=number) | Q(source_operation_id=number) | Q(payload__items__contains=[{"id": number}]) | Q(payload__collateral__contains=[{"id": number}])
        else:
            try:
                identity = uuid.UUID(q)
            except ValueError:
                pass
            else:
                match |= Q(request_key=identity) | Q(payload__items__contains=[{"public_id": str(identity)}])
        issues = issues.filter(match)
    if data.get("kind"):
        issues = issues.filter(kind=data["kind"])
    if data.get("from_date"):
        issues = issues.filter(as_of__gte=data["from_date"])
    if data.get("to_date"):
        issues = issues.filter(as_of__lte=data["to_date"])
    prefix = "" if data.get("sort") == "oldest" else "-"
    return issues.select_related("source_operation__corrected_by").order_by(prefix + "created_at", prefix + "pk")
