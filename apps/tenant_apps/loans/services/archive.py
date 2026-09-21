"""Accept and export historical source claims without touching operational Loans."""
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.orgs.access import resolve_workspace_access
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import HistoricalLoanEvidence
from .archive_contract import ArchiveError, encode, review_document
from .history_contract import digest
from .history_setup import require_history_setup_access


def require_archive_read(workspace_id, actor, *, exporting=False):
    if not workspace_id or current_workspace_id() != workspace_id:
        raise PermissionDenied("Archive access requires the matching Workspace context.")
    workspace = Company.all_objects.get(pk=workspace_id)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    access.require("data.view")
    if exporting:
        access.require("data.export")
    if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise PermissionDenied("Archive access requires an active Workspace.")
    return workspace


def get_evidence(*, workspace_id, actor, evidence_id):
    require_archive_read(workspace_id, actor)
    try:
        return HistoricalLoanEvidence.objects.get(workspace_id=workspace_id, public_id=evidence_id)
    except (HistoricalLoanEvidence.DoesNotExist, ValueError, ValidationError) as exc:
        raise PermissionDenied("Historical evidence is unavailable in this Workspace.") from exc


@transaction.atomic
def accept_evidence(*, workspace_id, actor, document, expected_sha256, confirmed=False):
    require_history_setup_access(workspace_id, actor)
    workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
    require_history_setup_access(workspace_id, actor)
    review = review_document(document)
    if confirmed is not True or expected_sha256 != review["source_sha256"]:
        raise ArchiveError("Review and confirm this exact historical evidence before accepting it.")
    source = document["source"]
    identity = dict(workspace_id=workspace_id, source_namespace=UUID(source["namespace"]),
                    source_system=source["system"], source_id=source["loan_id"], source_sha256=expected_sha256)
    existing = HistoricalLoanEvidence.objects.filter(**identity).first()
    if existing:
        if existing.document != document:
            raise ArchiveError("The stored snapshot differs from this source evidence.")
        return existing
    evidence = HistoricalLoanEvidence.objects.create(**identity, document=document, review=review, accepted_by=actor)
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor,
                 description="Accepted historical closed-loan source claims; no operational loan created.",
                 data={"archive": evidence.pk, "sha256": expected_sha256})
    return evidence


@transaction.atomic
def export_evidence(*, workspace_id, actor, evidence_id):
    workspace = require_archive_read(workspace_id, actor, exporting=True)
    evidence = get_evidence(workspace_id=workspace_id, actor=actor, evidence_id=evidence_id)
    if digest(evidence.document) != evidence.source_sha256:
        raise ArchiveError("Stored historical evidence fingerprint does not match.")
    content = encode(evidence.document)
    AuditLog.log("DATA_EXPORT", company=workspace, user=actor,
                 description="Exported historical closed-loan source claims.",
                 data={"archive": evidence.pk, "sha256": evidence.source_sha256})
    return content
