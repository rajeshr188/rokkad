from __future__ import annotations

from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A6
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.orgs.access import resolve_workspace_access
from apps.tenant_apps.loans.access import LOANS_OWNER_ACTION
from apps.tenant_apps.loans.domain import CollateralCustodyState
from apps.tenant_apps.loans.models import (
    PawnCollateralItem,
    PawnCollateralStorageMovement,
    PawnStorageLocation,
    current_tenant_workspace_id,
)


class PawnStorageError(ValueError):
    pass


@transaction.atomic
def create_storage_location(
    *,
    workspace,
    level,
    code,
    name,
    parent=None,
    capacity=None,
    actor=None,
):
    _require_owner(workspace, actor)
    location = PawnStorageLocation(
        workspace=workspace,
        parent=parent,
        level=level,
        code=str(code).strip().upper(),
        name=str(name).strip(),
        capacity=capacity,
        created_by=actor,
    )
    location.save()
    return location


@transaction.atomic
def place_or_transfer_collateral(
    collateral_item_id: int,
    *,
    destination_id: int,
    reason: str,
    actor,
):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnStorageError("Storage operations require an active tenant schema.")
    try:
        item = (
            PawnCollateralItem.objects.select_for_update()
            .select_related("loan__workspace")
            .get(pk=collateral_item_id, loan__workspace_id=workspace_id)
        )
        destination = PawnStorageLocation.objects.select_for_update().get(
            pk=destination_id,
            workspace_id=workspace_id,
            is_active=True,
        )
    except (PawnCollateralItem.DoesNotExist, PawnStorageLocation.DoesNotExist) as exc:
        raise PawnStorageError("Collateral item or destination was not found in this workspace.") from exc
    _require_owner(item.loan.workspace, actor)
    from .physical_verification import (
        PawnPhysicalVerificationBlockerError,
        assert_physical_verification_clear,
    )

    try:
        assert_physical_verification_clear(
            (item.pk,), operation="Collateral storage transfer"
        )
    except PawnPhysicalVerificationBlockerError as exc:
        raise PawnStorageError(str(exc)) from exc
    if item.custody_state != CollateralCustodyState.IN_VAULT.value:
        raise PawnStorageError("Only collateral currently held in the vault can be placed or transferred.")
    if destination.level not in {
        PawnStorageLocation.Level.BOX,
        PawnStorageLocation.Level.SLOT,
    }:
        raise PawnStorageError("Collateral must be placed in a Box or optional Slot.")
    if item.current_storage_location_id == destination.pk:
        raise PawnStorageError("Collateral is already stored at that destination.")
    if destination.capacity is not None:
        occupied = destination.current_collateral_items.select_for_update().count()
        if occupied >= destination.capacity:
            raise PawnStorageError("The destination storage location is at capacity.")
    reason = str(reason or "").strip()
    if item.current_storage_location_id and not reason:
        raise PawnStorageError("A reason is required for a storage transfer.")
    previous = item.current_storage_location
    movement = PawnCollateralStorageMovement.objects.create(
        collateral_item=item,
        from_location=previous,
        to_location=destination,
        kind=(
            PawnCollateralStorageMovement.Kind.TRANSFER
            if previous is not None
            else PawnCollateralStorageMovement.Kind.PLACEMENT
        ),
        reason=reason,
        moved_by=actor,
    )
    item.current_storage_location = destination
    item.save(update_fields=["current_storage_location", "updated_at"])
    return movement


@transaction.atomic
def remove_collateral_from_storage(
    item,
    *,
    workflow_source: str,
    source_reference: str,
    actor=None,
):
    item = (
        PawnCollateralItem.objects.select_for_update()
        .get(pk=item.pk)
    )
    if item.current_storage_location_id is None:
        return None
    movement = PawnCollateralStorageMovement.objects.create(
        collateral_item=item,
        from_location=item.current_storage_location,
        to_location=None,
        kind=PawnCollateralStorageMovement.Kind.REMOVAL,
        reason="Removed by collateral lifecycle workflow.",
        workflow_source=workflow_source,
        source_reference=str(source_reference),
        moved_by=actor,
    )
    item.current_storage_location = None
    item.save(update_fields=["current_storage_location", "updated_at"])
    return movement


@transaction.atomic
def carry_storage_to_renewal_successor(
    source_item,
    successor_item,
    *,
    renewal,
    actor=None,
    workflow_source="RENEWAL",
):
    source_item = (
        PawnCollateralItem.objects.select_for_update()
        .get(pk=source_item.pk)
    )
    successor_item = PawnCollateralItem.objects.select_for_update().get(
        pk=successor_item.pk
    )
    location = source_item.current_storage_location
    if location is None:
        return ()
    removal = remove_collateral_from_storage(
        source_item,
        workflow_source=workflow_source,
        source_reference=str(renewal.pk),
        actor=actor,
    )
    placement = PawnCollateralStorageMovement.objects.create(
        collateral_item=successor_item,
        from_location=None,
        to_location=location,
        kind=PawnCollateralStorageMovement.Kind.PLACEMENT,
        reason="Carried forward with retained renewal collateral.",
        workflow_source=workflow_source,
        source_reference=str(renewal.pk),
        moved_by=actor,
    )
    successor_item.current_storage_location = location
    successor_item.save(update_fields=["current_storage_location", "updated_at"])
    return removal, placement


def render_storage_location_label(location, *, qr_target):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A6)
    width, height = A6
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(12 * mm, height - 18 * mm, location.code)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(12 * mm, height - 26 * mm, location.name[:45])
    pdf.drawString(12 * mm, height - 33 * mm, location.path_label[:60])
    qr = QrCodeWidget(qr_target)
    bounds = qr.getBounds()
    size = 48 * mm
    drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
    drawing.add(qr)
    renderPDF.draw(drawing, pdf, 12 * mm, 18 * mm)
    pdf.setFont("Helvetica", 8)
    pdf.drawString(12 * mm, 12 * mm, "Scan as storage-transfer destination")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _require_owner(workspace, actor):
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if not access.can(LOANS_OWNER_ACTION):
        raise PawnStorageError("Only the workspace Owner may manage collateral storage during the pilot.")


__all__ = [
    "PawnStorageError",
    "carry_storage_to_renewal_successor",
    "create_storage_location",
    "place_or_transfer_collateral",
    "remove_collateral_from_storage",
    "render_storage_location_label",
]
