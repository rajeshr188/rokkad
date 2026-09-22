"""Append media to exact admitted origins, independently of monetary evidence."""
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.tenant_apps.loans.models import HistoricalLoanAttachment, PawnCollateralItem, PawnCollateralPhoto
from .history_setup import require_history_setup_access


@transaction.atomic
def attach_legacy_media(*, workspace_id, actor, target, file_name, evidence):
    require_history_setup_access(workspace_id, actor)
    if target.workspace_id != workspace_id:
        raise ValidationError("The media target belongs to a different Workspace.")
    source = evidence["source"]
    original = evidence["verified_source_file"]
    values = dict(workspace_id=workspace_id, file=file_name,
                  original_filename=source["stored_path"].rsplit("/", 1)[-1],
                  mime_type=original["content_type"], sha256=original["sha256"],
                  byte_size=original["byte_size"], source_evidence=evidence)
    if isinstance(target, PawnCollateralItem):
        photo = PawnCollateralPhoto.objects.create(
            **values, collateral_item=target, workflow_source="LEGACY_IMPORT", captured_by=actor)
        return {"kind": "collateral", "photo_id": photo.pk, "item_id": target.pk, "file_name": file_name}
    attachment = HistoricalLoanAttachment.objects.create(**values, evidence=target, imported_by=actor)
    return {"kind": "archive", "attachment_id": attachment.pk, "evidence_id": target.pk, "file_name": file_name}
