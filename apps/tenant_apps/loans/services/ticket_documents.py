"""First-issue display/media evidence for precision tickets; no live valuation."""

from dataclasses import dataclass, replace
from decimal import Decimal

from django.utils import timezone
from num2words import num2words

from apps.tenant_apps.party.document_selectors import document_identity
from apps.tenant_apps.loans.documents.assets import DocumentAssetError, DocumentAssetValidator
from apps.tenant_apps.loans.documents.payloads import (
    DocumentField, DocumentMedia, PawnLoanDocumentProjectionBuilder, TICKET_FIELD_KEYS,
)
from apps.tenant_apps.loans.models import PawnCollateralPhoto
from .action_access import require_loan_action
from apps.tenant_apps.loans.documents.display import display_date, display_money, collateral_description


@dataclass(frozen=True)
class PreparedTicket:
    payload: object
    assets: tuple
    source_snapshot: dict


def _photo_asset(file, key, workspace_id, expected_hash=None):
    try:
        file.open("rb")
        try:
            content = file.read(DocumentAssetValidator.MAX_IMAGE_BYTES + 1)
        finally:
            file.close()
        asset = DocumentAssetValidator.validate(key=key, kind="IMAGE", content=content, workspace_id=workspace_id)
        if expected_hash and asset.sha256 != expected_hash:
            raise DocumentAssetError("Selected photo does not match its approved checksum.")
        return asset
    except Exception as exc:
        # Storage exceptions may contain credentials/URLs. Do not expose them.
        raise DocumentAssetError("Selected photograph is unavailable or does not match its evidence.") from exc


def _principal_words(amount):
    value = Decimal(str(amount))
    if not value.is_finite() or value < 0 or value != value.quantize(Decimal("0.01")):
        raise ValueError("Approved principal must be a non-negative rupee/paise amount.")
    rupees = int(value)
    paise = int((value - rupees) * 100)
    words = f"{num2words(rupees, lang='en_IN')} rupees"
    if paise:
        words += f" and {num2words(paise, lang='en_IN')} paise"
    return words.capitalize() + " only"


def prepare_ticket_document(*, loan, layout, actor, address_id=None, preview=False):
    require_loan_action(loan, actor, "data.view")
    if layout.schema_version != 4 or layout.document_type != "loan_ticket":
        raise ValueError("Extended ticket evidence requires a precision ticket layout.")
    approval = loan.approval_snapshots.order_by("-version").first()
    payload = PawnLoanDocumentProjectionBuilder.loan_ticket(loan)
    source = approval.payload
    if source["borrower_id"] != loan.borrower_id:
        raise ValueError("Approved borrower does not match this loan.")
    return _prepare_ticket_display(
        loan=loan, layout=layout, actor=actor, address_id=address_id, preview=preview,
        payload=payload, source=source,
        evidence={"approval_id": approval.pk, "approval_fingerprint": approval.fingerprint},
    )


def _prepare_ticket_display(*, loan, layout, actor, address_id, preview, payload, source, evidence):
    """Shared display/media projection; callers supply their own frozen evidence."""
    bindings = {block.binding for block in layout.all_blocks()}
    license_values = {
        "license.business_name": loan.license.business_name.strip(),
        "license.business_address": loan.license.business_address.strip(),
    }
    for key, value in license_values.items():
        if key in bindings and not value:
            if not preview:
                raise ValueError("Complete the printed business name and address in this loan's license before issuing this ticket.")
            license_values[key] = "[License business name not configured]" if key.endswith("name") else "[License business address not configured]"
    identity = document_identity(
        workspace=loan.workspace, party_id=source["borrower_id"], actor=actor,
        address_id=address_id,
        include_address=bool(bindings & {"borrower.address", "borrower.contact_block", "loan.summary_label"}),
    )
    items = source["collateral"]
    descriptions = "\n".join(f"{index}. {collateral_description(item)}" for index, item in enumerate(items, 1))
    weights = {}
    for item in items:
        metal = str(item["metal"]).title()
        weights[metal] = weights.get(metal, Decimal("0")) + Decimal(str(item["net_weight"]))
    weight_text = "\n".join(f"{metal}: {weight:f} g" for metal, weight in sorted(weights.items()))
    appraisals = [item.get("latest_appraised_value") for item in items]
    appraisal = "Unknown" if any(value is None for value in appraisals) else f"{sum((Decimal(str(value)) for value in appraisals), Decimal('0')):.2f}"
    captured_at = timezone.now()
    local_capture = timezone.localtime(captured_at, timezone.get_default_timezone())
    offset = local_capture.strftime("%z")
    generated_at = local_capture.strftime("%d/%m/%Y %H:%M:%S %Z") + f" (UTC{offset[:3]}:{offset[3:]})"
    values = {
        **license_values,
        "license.proprietor_name": loan.license.proprietor_name.strip(),
        "document.generated_at": generated_at,
        "license.number": loan.license.license_number,
        "borrower.name": identity.name, "borrower.relationship": identity.relationship,
        "borrower.address": identity.address, "borrower.phone": identity.phone,
        "borrower.contact_block": "\n".join(value for value in (identity.name, identity.relationship, identity.address, identity.phone) if value),
        "collateral.description_lines": descriptions,
        "collateral.net_weight_by_metal": weight_text,
        "collateral.approved_appraisal_total": appraisal,
        "loan.principal_words": _principal_words(source["principal_amount"]),
        "loan.summary_label": "\n".join((f"{source['loan_number']} / {display_date(source['loan_date'])}", f"Rs {display_money(source['principal_amount'], grouping=True)} / {weight_text}", identity.name, descriptions)),
    }
    fields = tuple(replace(field, value=f"{identity.name} ({identity.code})") if field.key == "borrower.display" else field for field in payload.fields)
    fields += tuple(DocumentField(key, label, values[key]) for label, key in TICKET_FIELD_KEYS.items())
    assets, media, media_evidence = [], [], {}
    for binding in sorted(bindings & {"borrower.photo", "collateral.first_approved_photo"}):
        key = "ticket." + binding
        file, expected_hash, photo_evidence = None, None, {}
        status = "ABSENT"
        if binding == "borrower.photo":
            file = identity.photo
            photo_evidence = {"party_id": identity.party_id, "file_name": file.name or ""}
        elif items:
            first = items[0]
            photo_evidence = {"item_id": first["item_id"]}
            if "photo_evidence" not in first:
                status = "UNAVAILABLE"
            elif first["photo_evidence"]:
                approved_photo = sorted(first["photo_evidence"], key=lambda value: int(value["photo_id"]))[0]
                expected_hash = approved_photo.get("sha256")
                photo_evidence.update(photo_id=approved_photo["photo_id"], sha256=expected_hash)
                photo = PawnCollateralPhoto.objects.filter(
                    pk=approved_photo["photo_id"], workspace_id=loan.workspace_id,
                    collateral_item_id=first["item_id"], collateral_item__loan_id=loan.pk,
                ).first()
                if photo is None or not photo.file or not expected_hash or photo.sha256 != expected_hash:
                    status = "UNAVAILABLE"
                else:
                    file = photo.file
        if file:
            try:
                asset = _photo_asset(file, key, loan.workspace_id, expected_hash)
            except DocumentAssetError:
                status = "UNAVAILABLE"
            else:
                status = "AVAILABLE"
                assets.append(asset)
                photo_evidence.update(sha256=asset.sha256, file_name=file.name)
        optional = all(block.optional_photo for block in layout.all_blocks() if block.binding == binding)
        if not preview and status != "AVAILABLE" and not (status == "ABSENT" and optional):
            raise DocumentAssetError(f"{binding}: selected photograph is {status.lower()}; review the photo before issuing.")
        media.append(DocumentMedia(binding, key, status))
        media_evidence[binding] = {**photo_evidence, "status": status, "optional": optional}
    payload = replace(payload, schema_version=2, fields=fields, media=tuple(media))
    snapshot = {
        "schema_version": 2, "workspace_id": loan.workspace_id,
        "captured_at": captured_at.isoformat(),
        "verification_id": payload.verification_id,
        **evidence,
        "customer": {"party_id": identity.party_id, "address_id": identity.address_id},
        "fields": {field.key: str(field.value) for field in fields}, "media": media_evidence,
    }
    return PreparedTicket(payload, tuple(assets), snapshot)
