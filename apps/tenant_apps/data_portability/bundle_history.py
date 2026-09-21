"""Workspace-authorized access to immutable bundle membership and fresh receipts."""
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError

from .access import require_access
from .models import ImportBundle


def get_history(*, workspace_id, actor, bundle_id):
    require_access(workspace_id, actor, "import")
    try:
        return ImportBundle.objects.select_related(*ImportBundle.PROFILE_FIELDS).get(
            workspace_id=workspace_id, public_id=bundle_id)
    except (ImportBundle.DoesNotExist, ValueError, ValidationError) as exc:
        raise PermissionDenied("Bundle history is unavailable in this Workspace.") from exc


def review_receipt(history):
    return signing.dumps({"workspace": history.workspace_id, "history": str(history.public_id),
                          "batches": history.receipt_entries()}, salt="party-bundle-staging")


def cancel_unfinished(*, workspace_id, actor, bundle_id, confirmed=False):
    """Cancel the current unfinished members atomically; never erase completed work."""
    from django.db import transaction
    from apps.orgs.audit import AuditLog
    from apps.orgs.models import Company
    from .models import ImportBatch
    from .parsers import PortabilityError
    from .services import cancel_import

    require_access(workspace_id, actor, "import")
    if confirmed is not True:
        raise PortabilityError("Confirm cancellation of the unfinished bundle profiles.")
    with transaction.atomic():
        workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
        history = get_history(workspace_id=workspace_id, actor=actor, bundle_id=bundle_id)
        ids = [batch.pk for _, batch in history.profile_batches() if batch]
        batches = list(ImportBatch.objects.filter(workspace_id=workspace_id, pk__in=ids)
                       .select_for_update().order_by("pk"))
        cancelled = []
        for batch in batches:
            if batch.state in {"NEEDS_MAPPING", "READY"}:
                cancel_import(workspace_id=workspace_id, actor=actor, batch_id=batch.public_id)
                cancelled.append(str(batch.public_id))
        if cancelled:
            AuditLog.log("DATA_IMPORT", company=workspace, user=actor,
                description="Cancelled unfinished Party bundle profiles; completed evidence and history retained.",
                data={"bundle": str(history.public_id), "cancelled_batches": cancelled,
                      "completed_batches": [str(batch.public_id) for batch in batches if batch.state == "COMPLETED"]})
        return len(cancelled)
