"""Read-only integrity diagnostics for configurable document evidence."""

import hashlib
from dataclasses import dataclass

from apps.tenant_apps.loans.documents.layouts import DocumentLayoutValidator
from apps.tenant_apps.loans.models import (
    LoanDocumentAsset,
    LoanDocumentIssue,
    LoanDocumentLayoutRevision,
    current_tenant_workspace_id,
)


@dataclass(frozen=True)
class DocumentIntegrityFinding:
    category: str
    object_type: str
    object_id: int
    message: str


def get_document_integrity_findings():
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Document integrity checks require an active tenant schema.")
    findings = []
    revisions = LoanDocumentLayoutRevision.objects.filter(layout__workspace_id=workspace_id).select_related("layout")
    for revision in revisions:
        try:
            parsed = DocumentLayoutValidator.load(revision.definition)
        except ValueError as exc:
            findings.append(DocumentIntegrityFinding("LAYOUT_INVALID", "revision", revision.pk, str(exc)))
        else:
            if revision.content_hash != parsed.content_hash:
                findings.append(DocumentIntegrityFinding("LAYOUT_HASH", "revision", revision.pk, "Stored layout hash does not match its canonical definition."))
            if parsed.document_type != revision.layout.document_type:
                findings.append(DocumentIntegrityFinding("LAYOUT_SCOPE", "revision", revision.pk, "Revision document type differs from its layout."))
    for asset in LoanDocumentAsset.objects.filter(workspace_id=workspace_id).select_related("revision__layout"):
        if asset.revision.layout.workspace_id != asset.workspace_id:
            findings.append(DocumentIntegrityFinding("ASSET_SCOPE", "asset", asset.pk, "Asset workspace differs from its revision."))
            continue
        try:
            asset.file.open("rb"); content = asset.file.read(); asset.file.close()
        except Exception:
            findings.append(DocumentIntegrityFinding("ASSET_MISSING", "asset", asset.pk, "Asset file is missing or unreadable."))
        else:
            if hashlib.sha256(content).hexdigest() != asset.sha256:
                findings.append(DocumentIntegrityFinding("ASSET_HASH", "asset", asset.pk, "Asset bytes do not match the stored hash."))
    for issue in LoanDocumentIssue.objects.filter(workspace_id=workspace_id).select_related("revision__layout", "prior_issue"):
        if issue.revision_id and issue.revision.layout.workspace_id != issue.workspace_id:
            findings.append(DocumentIntegrityFinding("ISSUE_SCOPE", "issue", issue.pk, "Issue revision belongs to another workspace."))
        if issue.prior_issue_id and issue.prior_issue.workspace_id != issue.workspace_id:
            findings.append(DocumentIntegrityFinding("ISSUE_LINEAGE", "issue", issue.pk, "Prior issue belongs to another workspace."))
        try:
            issue.artifact.open("rb"); content = issue.artifact.read(); issue.artifact.close()
        except Exception:
            findings.append(DocumentIntegrityFinding("ISSUE_MISSING", "issue", issue.pk, "Issued PDF artifact is missing or unreadable."))
        else:
            if hashlib.sha256(content).hexdigest() != issue.pdf_hash:
                findings.append(DocumentIntegrityFinding("ISSUE_HASH", "issue", issue.pk, "Issued PDF bytes do not match the immutable hash."))
    return tuple(findings)


__all__ = ["DocumentIntegrityFinding", "get_document_integrity_findings"]
