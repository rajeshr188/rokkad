"""Read-only integrity diagnostics for configurable document evidence."""

import hashlib
from dataclasses import dataclass

from apps.tenant_apps.loans.documents.layouts import DocumentLayoutValidator
from apps.tenant_apps.loans.models import (
    LoanDocumentAsset,
    LoanDocumentIssue,
    LoanDocumentLayoutAssignment,
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
    assignments = LoanDocumentLayoutAssignment.objects.filter(
        workspace_id=workspace_id,
        document_type="loan_ticket",
        is_active=True,
        revision__state=LoanDocumentLayoutRevision.State.PUBLISHED,
    ).select_related("revision")
    for assignment in assignments:
        try:
            layout = DocumentLayoutValidator.load(assignment.revision.definition)
        except ValueError:
            continue
        if not _includes_original_and_duplicate(layout):
            findings.append(DocumentIntegrityFinding(
                "PILOT_TICKET_COPY_BUNDLE",
                "assignment",
                assignment.pk,
                "The active pilot loan-ticket layout must issue both Original and Duplicate copies. Choose a BOTH or A4 side-by-side sheet preset, or Original/Duplicate copy mode.",
            ))
        if not _includes_required_ticket_signatures(layout):
            findings.append(DocumentIntegrityFinding(
                "PILOT_TICKET_SIGNATURES",
                "assignment",
                assignment.pk,
                "The active pilot loan-ticket layout must provide borrower/customer and authorized staff signature labels on both Original and Duplicate fronts.",
            ))
    return tuple(findings)


def _includes_original_and_duplicate(layout):
    if layout.sheet is not None:
        return layout.sheet.composition in {
            "A5_BOTH_SIMPLEX",
            "A5_BOTH_DUPLEX",
            "A4_SIDE_BY_SIDE",
            "A4_SIDE_BY_SIDE_DUPLEX",
        }
    return layout.copy_mode in {
        "ORIGINAL_DUPLICATE",
        "ORIGINAL_DUPLICATE_DUPLEX",
    }


def _includes_required_ticket_signatures(layout):
    def walk(blocks):
        for block in blocks:
            yield block
            yield from walk(block.blocks)
            for column in block.columns:
                yield from walk(column.blocks)

    def has_required_roles(block):
        labels = tuple(
            label.strip().lower()
            for label in block.text.split("|")
            if label.strip()
        )
        return (
            any("borrower" in label or "customer" in label for label in labels)
            and any(
                "staff" in label
                or "pawnbroker" in label
                or "authorized" in label
                for label in labels
            )
        )

    signature_blocks = tuple(
        block
        for block in walk(layout.blocks)
        if block.type == "signature"
        and block.visible_when is None
        and has_required_roles(block)
    )
    return all(
        any(block.copy_scope in {"BOTH", copy_scope} for block in signature_blocks)
        for copy_scope in ("ORIGINAL", "DUPLICATE")
    )


__all__ = ["DocumentIntegrityFinding", "get_document_integrity_findings"]
