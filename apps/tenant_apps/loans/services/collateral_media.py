from __future__ import annotations

import hashlib
from dataclasses import dataclass
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .action_access import require_loan_action
from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.loans.models import (
    PawnCollateralItem,
    PawnCollateralLabelIssue,
    PawnCollateralPhoto,
    current_tenant_workspace_id,
)


MAX_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_SIGNATURES = (
    ("image/jpeg", (b"\xff\xd8\xff",)),
    ("image/png", (b"\x89PNG\r\n\x1a\n",)),
)


class PawnCollateralMediaError(ValueError):
    pass


@dataclass(frozen=True)
class PawnCollateralLabelResult:
    issue: PawnCollateralLabelIssue
    content: bytes


def validate_collateral_photo(upload):
    if upload is None:
        raise PawnCollateralMediaError("Select a JPEG or PNG collateral photograph.")
    size = int(getattr(upload, "size", 0) or 0)
    if size <= 0 or size > MAX_PHOTO_BYTES:
        raise PawnCollateralMediaError("Collateral photographs must be between 1 byte and 10 MB.")
    position = upload.tell() if hasattr(upload, "tell") else 0
    header = upload.read(16)
    upload.seek(position)
    detected = next(
        (mime for mime, signatures in ALLOWED_SIGNATURES if any(header.startswith(value) for value in signatures)),
        None,
    )
    if detected is None:
        raise PawnCollateralMediaError("Collateral photographs must be valid JPEG or PNG files.")
    declared = (getattr(upload, "content_type", "") or "").lower()
    if declared and declared not in {"image/jpeg", "image/png"}:
        raise PawnCollateralMediaError("Collateral photograph content type must be JPEG or PNG.")
    return detected


@transaction.atomic
def append_collateral_photo(
    collateral_item_id: int,
    *,
    upload,
    actor=None,
    workflow_source: str | None = None,
) -> PawnCollateralPhoto:
    item = _locked_item(collateral_item_id)
    require_loan_action(item.loan, actor, "data.edit")
    return _append_collateral_photo(collateral_item_id, upload=upload, actor=actor,
                                    workflow_source=workflow_source)


@transaction.atomic
def _append_collateral_photo(collateral_item_id, *, upload, actor, workflow_source=None):
    """Internal photo persistence for an already-authorized draft/renewal command."""
    item = _locked_item(collateral_item_id)
    mime_type = validate_collateral_photo(upload)
    if workflow_source is None:
        workflow_source = (
            PawnCollateralPhoto.WorkflowSource.DRAFT
            if item.loan.state == PawnLoanState.DRAFT.value
            else PawnCollateralPhoto.WorkflowSource.POST_APPROVAL
        )
    if workflow_source == PawnCollateralPhoto.WorkflowSource.DRAFT and item.loan.state != PawnLoanState.DRAFT.value:
        raise PawnCollateralMediaError("Draft photographs can only be captured while the loan is a draft.")
    if workflow_source == PawnCollateralPhoto.WorkflowSource.RENEWAL and item.loan.state != PawnLoanState.DRAFT.value:
        raise PawnCollateralMediaError("Renewal photographs must be captured before successor approval.")
    position = upload.tell() if hasattr(upload, "tell") else 0
    digest = hashlib.sha256()
    for chunk in upload.chunks() if hasattr(upload, "chunks") else iter(lambda: upload.read(64 * 1024), b""):
        digest.update(chunk)
    upload.seek(position)
    return PawnCollateralPhoto.objects.create(
        collateral_item=item,
        file=upload,
        original_filename=(getattr(upload, "name", "collateral-photo") or "collateral-photo")[:255],
        mime_type=mime_type,
        sha256=digest.hexdigest(),
        byte_size=int(upload.size),
        workflow_source=workflow_source,
        captured_by=actor,
    )


@transaction.atomic
def delete_draft_collateral_photo(collateral_item_id, photo_id, *, actor):
    from apps.tenant_apps.loans.models import LoanChangeLog, PawnLoan

    # Match approval's lock order so approval and removal cannot race.
    workspace_id = current_tenant_workspace_id()
    item_ref = PawnCollateralItem.objects.filter(pk=collateral_item_id, workspace_id=workspace_id).first() if workspace_id else None
    if item_ref is None:
        raise PawnCollateralMediaError("Collateral item was not found in the active workspace.")
    loan = PawnLoan.objects.select_for_update().get(pk=item_ref.loan_id, workspace_id=workspace_id)
    require_loan_action(loan, actor, "data.edit")
    if loan.state != PawnLoanState.DRAFT.value:
        raise PawnCollateralMediaError("Photographs can only be deleted while the loan is a draft.")
    if not PawnCollateralItem.objects.select_for_update().filter(pk=collateral_item_id, loan=loan).exists():
        raise PawnCollateralMediaError("Collateral changed loans. Reload the loan before deleting a photograph.")
    photo = PawnCollateralPhoto.objects.select_for_update().filter(pk=photo_id, collateral_item_id=collateral_item_id).first()
    if photo is None:
        raise PawnCollateralMediaError("Photograph was not found on this collateral item.")
    if photo.renewal_copies.exists():
        raise PawnCollateralMediaError("This photograph is retained as renewal evidence and cannot be deleted.")
    storage, name = photo.file.storage, photo.file.name
    metadata = {"action": "collateral_photo_deleted", "collateral_item_id": collateral_item_id,
                "photo_id": photo.pk, "original_filename": photo.original_filename, "sha256": photo.sha256}
    # Deliberate queryset deletion, using the existing draft-only PostgreSQL guard.
    PawnCollateralPhoto.objects.filter(pk=photo.pk).delete()
    LoanChangeLog.objects.create(loan=loan, actor=actor, event_kind="DRAFT_UPDATED",
                                from_state="DRAFT", to_state="DRAFT", metadata=metadata)
    if name and not photo.inherited_from_id and not PawnCollateralPhoto.objects.filter(file=name).exists():
        transaction.on_commit(lambda: storage.delete(name))


@transaction.atomic
def inherit_collateral_photos(source_item, successor_item, *, actor=None):
    require_loan_action(source_item.loan, actor, "data.edit")
    require_loan_action(successor_item.loan, actor, "data.edit")
    return _inherit_collateral_photos(source_item, successor_item, actor=actor)


def _inherit_collateral_photos(source_item, successor_item, *, actor):
    """Internal evidence copy used by an authorized renewal."""
    inherited = []
    for source in source_item.photos.order_by("captured_at", "pk"):
        inherited.append(
            PawnCollateralPhoto.objects.create(
                collateral_item=successor_item,
                file=source.file.name,
                original_filename=source.original_filename,
                mime_type=source.mime_type,
                sha256=source.sha256,
                byte_size=source.byte_size,
                workflow_source=PawnCollateralPhoto.WorkflowSource.RENEWAL,
                inherited_from=source,
                captured_by=actor,
            )
        )
    return tuple(inherited)


@transaction.atomic
def render_collateral_label(
    collateral_item_id: int,
    *,
    qr_target: str,
    action: str,
    actor=None,
) -> PawnCollateralLabelResult:
    item = _locked_item(collateral_item_id)
    require_loan_action(item.loan, actor, "data.view")
    try:
        action = PawnCollateralLabelIssue.Action(action)
    except ValueError as exc:
        raise PawnCollateralMediaError("Unknown collateral-label action.") from exc
    content = _label_pdf(item, qr_target)
    issue = PawnCollateralLabelIssue.objects.create(
        collateral_item=item,
        action=action,
        qr_target=qr_target,
        payload_sha256=hashlib.sha256(content).hexdigest(),
        issued_by=actor,
    )
    return PawnCollateralLabelResult(issue=issue, content=content)


def _locked_item(collateral_item_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnCollateralMediaError("Collateral media requires an active tenant schema.")
    try:
        return (
            PawnCollateralItem.objects.select_for_update()
            .select_related("loan", "loan__borrower")
            .get(pk=collateral_item_id, loan__workspace_id=workspace_id)
        )
    except PawnCollateralItem.DoesNotExist as exc:
        raise PawnCollateralMediaError("Collateral item was not found in the active workspace.") from exc


def _label_pdf(item, qr_target):
    page_size = landscape((60 * mm, 100 * mm))
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=page_size)
    width, height = page_size
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(6 * mm, height - 9 * mm, item.loan.loan_number)
    pdf.setFont("Helvetica", 8)
    identifier = f"CI-{str(item.public_id).replace('-', '')[:12].upper()}"
    rows = (
        identifier,
        item.description,
        f"Party: {item.loan.borrower.display_name}",
        f"Weight: {item.net_weight} g",
    )
    y = height - 17 * mm
    for value in rows:
        pdf.drawString(6 * mm, y, str(value)[:55])
        y -= 5 * mm
    qr = QrCodeWidget(qr_target)
    bounds = qr.getBounds()
    size = 28 * mm
    drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, pdf, width - 34 * mm, 5 * mm)
    pdf.setFont("Helvetica", 6)
    pdf.drawString(6 * mm, 5 * mm, "Scan to open collateral in its owning loan")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


__all__ = [
    "PawnCollateralLabelResult",
    "PawnCollateralMediaError",
    "append_collateral_photo",
    "inherit_collateral_photos",
    "render_collateral_label",
    "validate_collateral_photo",
]
