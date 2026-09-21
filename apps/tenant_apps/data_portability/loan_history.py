"""Persistent staging and explicit approval for Loans-owned historical import."""
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import transaction, IntegrityError

from apps.orgs.models import Company
from apps.tenant_apps.loans.services.portability_validation import PortabilityValidationError
from apps.tenant_apps.loans.services.history_contract import parse, digest, HistoryError
from apps.tenant_apps.loans.services.history_import import import_complete_history, require_history_access
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from .models import LoanHistoryBatch
from .children import parent_for

SALT = "loan-history-approval-v1"


def get_batch(*, workspace_id, actor, batch_id, lock=False):
    require_history_setup_access(workspace_id, actor)
    query = LoanHistoryBatch.objects.filter(workspace_id=workspace_id, profile="loan-history/1")
    if lock: query = query.select_for_update()
    try: return query.get(public_id=batch_id)
    except (LoanHistoryBatch.DoesNotExist, ValueError, ValidationError) as exc:
        raise PermissionDenied("Loan import is unavailable in this Workspace.") from exc


@transaction.atomic
def stage(*, workspace_id, actor, content):
    require_history_setup_access(workspace_id, actor)
    document = parse(content)
    require_history_access(workspace_id, actor, document)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    require_history_access(workspace_id, actor, document)
    if LoanHistoryBatch.objects.filter(workspace_id=workspace_id, state__in=["STAGED","READY"]).count() >= 20:
        raise HistoryError("Finish or cancel an unfinished Loans import before staging another (limit 20).")
    return LoanHistoryBatch.objects.create(workspace_id=workspace_id, created_by=actor,
        document=document, source_sha256=digest(document))


def resolve_mapping(document, workspace_id, values):
    if set(values) != {"revision_id", "series_id", "product_version_id"}: raise HistoryError("Select destination setup explicitly.")
    reference = document["loan"]["borrower"]
    parent = parent_for({"party_source_system":reference["source_system"], "party_external_id":reference["id"]}, workspace_id)
    if parent is None: raise HistoryError("Import the referenced Party first; borrower identity could not be resolved exactly.")
    return {**{k:int(v) for k,v in values.items()}, "borrower_id":parent.party_id}


def _execute(batch, actor, mapping):
    try:
        with transaction.atomic():
            return import_complete_history(workspace_id=batch.workspace_id, actor=actor, document=batch.document, mapping=mapping)
    except HistoryError:
        raise
    except PortabilityValidationError as exc:
        raise HistoryError(str(exc), category=exc.issue["category"],
                           code=exc.issue["code"], field=exc.issue["field"]) from exc
    except (ValueError, ValidationError, IntegrityError, ObjectDoesNotExist) as exc:
        raise HistoryError(str(exc), code="NATIVE_ADMISSION_REJECTED") from exc


@transaction.atomic
def preview(*, workspace_id, actor, batch_id, values):
    require_history_setup_access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state not in {"STAGED","READY"}: raise HistoryError("Only unfinished imports can be previewed.")
    mapping = resolve_mapping(batch.document, workspace_id, values)
    with transaction.atomic():
        _, summary = _execute(batch, actor, mapping)
        transaction.set_rollback(True)
    batch.mapping, batch.preview, batch.state = mapping, summary, "READY"
    batch.approval_digest = digest({"source":batch.source_sha256,"mapping":mapping,"preview":summary})
    batch.save(update_fields=["mapping","preview","state","approval_digest"])
    return signing.dumps({"workspace":workspace_id,"actor":actor.pk,"batch":str(batch.public_id),"digest":batch.approval_digest}, salt=SALT)


@transaction.atomic
def commit(*, workspace_id, actor, batch_id, approval, confirmed=False):
    require_history_setup_access(workspace_id, actor)
    if confirmed is not True: raise HistoryError("Confirm the entire historical loan and all reconciliation results.")
    try: token = signing.loads(approval, salt=SALT, max_age=3600)
    except signing.BadSignature as exc: raise HistoryError("Approval is invalid or expired; generate a fresh preview.") from exc
    if token.get("workspace") != workspace_id or token.get("actor") != actor.pk or token.get("batch") != str(batch_id):
        raise PermissionDenied("Approval belongs to another operator, Workspace or batch.")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state == "CANCELLED": raise HistoryError("Cancelled import cannot be committed.")
    require_history_access(workspace_id, actor, batch.document)
    current_digest = digest({"source":batch.source_sha256,"mapping":batch.mapping,"preview":batch.preview})
    if digest(batch.document) != batch.source_sha256 or current_digest != batch.approval_digest:
        raise HistoryError("Staged history or mapping changed; preview again.")
    if token.get("digest") != batch.approval_digest: raise HistoryError("Import changed after approval.")
    if batch.state == "COMPLETED": return batch.result
    if batch.state != "READY": raise HistoryError("Generate and review a preview first.")
    current_mapping = resolve_mapping(batch.document, workspace_id, {k:v for k,v in batch.mapping.items() if k!="borrower_id"})
    if current_mapping != batch.mapping: raise HistoryError("Borrower identity changed; preview again.")
    result, summary = _execute(batch, actor, current_mapping)
    if summary != batch.preview: raise HistoryError("Destination changed after preview; no history was imported.")
    batch.state, batch.result = "COMPLETED", result
    batch.save(update_fields=["state","result"])
    return result


@transaction.atomic
def cancel(*, workspace_id, actor, batch_id, confirmed=False):
    require_history_setup_access(workspace_id, actor)
    if confirmed is not True: raise HistoryError("Confirm cancellation and removal of the staged source values.")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state == "COMPLETED": raise HistoryError("Completed history cannot be cancelled or erased.")
    if batch.state == "CANCELLED": return
    batch.state, batch.document, batch.mapping, batch.preview, batch.approval_digest = "CANCELLED", {}, {}, {}, ""
    batch.save(update_fields=["state","document","mapping","preview","approval_digest"])
