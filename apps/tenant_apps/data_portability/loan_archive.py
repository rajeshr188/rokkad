"""Source staging and explicit approval for the Loans historical-only archive."""
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.orgs.models import Company
from apps.tenant_apps.loans.services.archive_contract import ArchiveError, parse, review_document
from apps.tenant_apps.loans.services.archive import accept_evidence
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from .models import LoanArchiveBatch

SALT = "closed-loan-evidence-approval-v1"


def get_batch(*, workspace_id, actor, batch_id, lock=False):
    require_history_setup_access(workspace_id, actor)
    query = LoanArchiveBatch.objects.filter(workspace_id=workspace_id)
    if lock:
        query = query.select_for_update()
    try:
        return query.get(public_id=batch_id)
    except (LoanArchiveBatch.DoesNotExist, ValueError, ValidationError) as exc:
        raise PermissionDenied("Archive staging is unavailable in this Workspace.") from exc


@transaction.atomic
def stage(*, workspace_id, actor, content):
    require_history_setup_access(workspace_id, actor)
    document = parse(content)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    require_history_setup_access(workspace_id, actor)
    if LoanArchiveBatch.objects.filter(workspace_id=workspace_id, state="STAGED").count() >= 20:
        raise ArchiveError("Finish or cancel an unfinished archive upload first (limit 20).")
    return LoanArchiveBatch.objects.create(workspace_id=workspace_id, document=document,
                                           source_sha256=digest(document), created_by=actor)


def preview(*, workspace_id, actor, batch_id):
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id)
    if batch.state != "STAGED":
        raise ArchiveError("Only staged historical evidence can be reviewed for acceptance.")
    review = review_document(batch.document)
    if review["source_sha256"] != batch.source_sha256:
        raise ArchiveError("The staged source fingerprint changed.")
    approval = signing.dumps({"workspace": workspace_id, "actor": actor.pk,
        "batch": str(batch.public_id), "sha256": batch.source_sha256,
        "review_sha256": digest(review)}, salt=SALT)
    return review, approval


@transaction.atomic
def commit(*, workspace_id, actor, batch_id, approval, confirmed=False):
    require_history_setup_access(workspace_id, actor)
    if confirmed is not True:
        raise ArchiveError("Confirm retention of these source claims and their review findings.")
    try:
        token = signing.loads(approval, salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ArchiveError("Approval is invalid or expired; review the evidence again.") from exc
    if token.get("workspace") != workspace_id or token.get("actor") != actor.pk or token.get("batch") != str(batch_id):
        raise PermissionDenied("Approval belongs to another Workspace, operator or batch.")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state == "CANCELLED":
        raise ArchiveError("Cancelled staging cannot be accepted.")
    if token.get("sha256") != batch.source_sha256 or digest(batch.document) != batch.source_sha256:
        raise ArchiveError("The approved source evidence changed.")
    if token.get("review_sha256") != digest(review_document(batch.document)):
        raise ArchiveError("The review findings changed; review the evidence again.")
    evidence = accept_evidence(workspace_id=workspace_id, actor=actor, document=batch.document,
                               expected_sha256=batch.source_sha256, confirmed=True)
    if batch.state != "COMPLETED":
        batch.state, batch.result = "COMPLETED", evidence
        batch.save(update_fields=["state", "result"])
    return evidence


@transaction.atomic
def cancel(*, workspace_id, actor, batch_id, confirmed=False):
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if confirmed is not True:
        raise ArchiveError("Confirm cancellation and removal of staged source values.")
    if batch.state == "COMPLETED":
        raise ArchiveError("Accepted evidence cannot be cancelled or erased.")
    if batch.state != "CANCELLED":
        batch.document, batch.state = {}, "CANCELLED"
        batch.save(update_fields=["document", "state"])
