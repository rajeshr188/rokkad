"""Backend service for MVP karigar metal custody movements.

Karigar issue/receipt moves metal between business-owned accounts and karigar
custody accounts. It does not post P&L, making charges, or monetary AR/AP.
"""

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from apps.tenant_apps.dea.models import (
    AccountingPeriod,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    Voucher,
    VoucherStatus,
    VoucherType,
)
from apps.tenant_apps.dea.posting.context import compute_fingerprint
from apps.tenant_apps.dea.services.commodity_posting import (
    CommodityMovementPayload,
    build_commodity_movement_idempotency_key,
    post_commodity_movement,
)
from apps.tenant_apps.party.models import Party


KARIGAR_ISSUE_VOUCHER_TYPE = "COMMODITY_KARIGAR_ISSUE"
KARIGAR_RECEIPT_VOUCHER_TYPE = "COMMODITY_KARIGAR_RECEIPT"
KARIGAR_ISSUE_EVENT_TYPE = "karigar-issue"
KARIGAR_RECEIPT_EVENT_TYPE = "karigar-receipt"
KARIGAR_ISSUE_FINGERPRINT_VERSION = "commodity-karigar-issue-v1"
KARIGAR_RECEIPT_FINGERPRINT_VERSION = "commodity-karigar-receipt-v1"


@dataclass(frozen=True)
class KarigarIssuePayload:
    source: Model
    issue_date: date
    karigar: Party
    commodity: Commodity
    gross_weight: Decimal
    purity: Decimal
    fine_weight: Decimal
    from_commodity_account: CommodityAccount
    to_karigar_account: CommodityAccount
    uom: str = Commodity.UnitOfMeasure.GRAM
    narration: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class KarigarReceiptPayload:
    source: Model
    receipt_date: date
    karigar: Party
    commodity: Commodity
    gross_weight: Decimal
    purity: Decimal
    fine_weight: Decimal
    from_karigar_account: CommodityAccount
    to_commodity_account: CommodityAccount
    uom: str = Commodity.UnitOfMeasure.GRAM
    narration: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class KarigarMovementResult:
    created: bool
    voucher: Voucher
    commodity_movement: CommodityMovement


@transaction.atomic
def post_karigar_issue(
    payload: KarigarIssuePayload,
    *,
    actor=None,
) -> KarigarMovementResult:
    """Move metal from owned/vault account to karigar custody."""

    _validate_issue_payload(payload)
    _validate_period(payload.issue_date, "karigar issue")

    movement_payload = _issue_movement_payload(payload)
    idempotency_key = build_commodity_movement_idempotency_key(movement_payload)
    existing = (
        CommodityMovement.objects.select_related("voucher")
        .filter(idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        if existing.voucher_id is None:
            raise ValidationError("Existing karigar issue movement is not linked to a voucher.")
        return KarigarMovementResult(
            created=False,
            voucher=existing.voucher,
            commodity_movement=existing,
        )

    voucher_type = _voucher_type(
        KARIGAR_ISSUE_VOUCHER_TYPE,
        "Karigar metal issue posting",
    )
    _reject_existing_changed_posting(
        source=payload.source,
        voucher_type=voucher_type,
        message=(
            "A posted karigar issue voucher already exists for this source. "
            "Reverse/correct the existing posting before posting a changed payload."
        ),
    )
    voucher = _create_posted_voucher(
        source=payload.source,
        voucher_type=voucher_type,
        voucher_date=payload.issue_date,
        voucher_no_prefix="CKI",
        fingerprint_payload={
            "source": f"{payload.source._meta.label_lower}:{payload.source.pk}",
            "movement_key": idempotency_key,
        },
        fingerprint_version=KARIGAR_ISSUE_FINGERPRINT_VERSION,
        narration=payload.narration or "Karigar metal issue",
        actor=actor,
    )
    movement_result = post_commodity_movement(
        _issue_movement_payload(payload, voucher=voucher),
        actor=actor,
    )
    return KarigarMovementResult(
        created=movement_result.created,
        voucher=voucher,
        commodity_movement=movement_result.record,
    )


@transaction.atomic
def post_karigar_receipt(
    payload: KarigarReceiptPayload,
    *,
    actor=None,
) -> KarigarMovementResult:
    """Move metal from karigar custody back to owned/vault account."""

    _validate_receipt_payload(payload)
    _validate_period(payload.receipt_date, "karigar receipt")

    movement_payload = _receipt_movement_payload(payload)
    idempotency_key = build_commodity_movement_idempotency_key(movement_payload)
    existing = (
        CommodityMovement.objects.select_related("voucher")
        .filter(idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        if existing.voucher_id is None:
            raise ValidationError("Existing karigar receipt movement is not linked to a voucher.")
        return KarigarMovementResult(
            created=False,
            voucher=existing.voucher,
            commodity_movement=existing,
        )

    voucher_type = _voucher_type(
        KARIGAR_RECEIPT_VOUCHER_TYPE,
        "Karigar metal receipt posting",
    )
    _reject_existing_changed_posting(
        source=payload.source,
        voucher_type=voucher_type,
        message=(
            "A posted karigar receipt voucher already exists for this source. "
            "Reverse/correct the existing posting before posting a changed payload."
        ),
    )
    voucher = _create_posted_voucher(
        source=payload.source,
        voucher_type=voucher_type,
        voucher_date=payload.receipt_date,
        voucher_no_prefix="CKR",
        fingerprint_payload={
            "source": f"{payload.source._meta.label_lower}:{payload.source.pk}",
            "movement_key": idempotency_key,
        },
        fingerprint_version=KARIGAR_RECEIPT_FINGERPRINT_VERSION,
        narration=payload.narration or "Karigar metal receipt",
        actor=actor,
    )
    movement_result = post_commodity_movement(
        _receipt_movement_payload(payload, voucher=voucher),
        actor=actor,
    )
    return KarigarMovementResult(
        created=movement_result.created,
        voucher=voucher,
        commodity_movement=movement_result.record,
    )


def _validate_issue_payload(payload: KarigarIssuePayload) -> None:
    errors = _common_errors(
        source=payload.source,
        karigar=payload.karigar,
        commodity=payload.commodity,
        gross_weight=payload.gross_weight,
        purity=payload.purity,
        fine_weight=payload.fine_weight,
    )
    if (
        payload.from_commodity_account.pk is None
        or payload.to_karigar_account.pk is None
    ):
        errors["commodity_account"] = "Commodity accounts must be saved."
    elif (
        payload.from_commodity_account.commodity_id != payload.commodity.pk
        or payload.to_karigar_account.commodity_id != payload.commodity.pk
    ):
        errors["commodity_account"] = "Commodity accounts must match movement commodity."
    if payload.to_karigar_account.purpose != CommodityAccount.Purpose.KARIGAR_CUSTODY:
        errors["to_karigar_account"] = "Issue destination must be a karigar custody account."
    if payload.to_karigar_account.party_id != payload.karigar.pk:
        errors["to_karigar_account"] = "Karigar custody account must belong to karigar."

    if errors:
        raise ValidationError(errors)


def _validate_receipt_payload(payload: KarigarReceiptPayload) -> None:
    errors = _common_errors(
        source=payload.source,
        karigar=payload.karigar,
        commodity=payload.commodity,
        gross_weight=payload.gross_weight,
        purity=payload.purity,
        fine_weight=payload.fine_weight,
    )
    if (
        payload.from_karigar_account.pk is None
        or payload.to_commodity_account.pk is None
    ):
        errors["commodity_account"] = "Commodity accounts must be saved."
    elif (
        payload.from_karigar_account.commodity_id != payload.commodity.pk
        or payload.to_commodity_account.commodity_id != payload.commodity.pk
    ):
        errors["commodity_account"] = "Commodity accounts must match movement commodity."
    if payload.from_karigar_account.purpose != CommodityAccount.Purpose.KARIGAR_CUSTODY:
        errors["from_karigar_account"] = (
            "Receipt source must be a karigar custody account."
        )
    if payload.from_karigar_account.party_id != payload.karigar.pk:
        errors["from_karigar_account"] = (
            "Karigar custody account must belong to karigar."
        )

    if errors:
        raise ValidationError(errors)


def _common_errors(
    *,
    source: Model,
    karigar: Party,
    commodity: Commodity,
    gross_weight: Decimal,
    purity: Decimal,
    fine_weight: Decimal,
) -> dict:
    errors = {}
    if source.pk is None:
        errors["source"] = "Source document must be saved before posting."
    if karigar.pk is None:
        errors["karigar"] = "Karigar party must be saved."
    if commodity.pk is None:
        errors["commodity"] = "Commodity must be saved."
    if gross_weight <= 0:
        errors["gross_weight"] = "Gross weight must be positive."
    if purity <= 0:
        errors["purity"] = "Purity must be positive."
    if fine_weight <= 0:
        errors["fine_weight"] = "Fine weight must be positive."
    return errors


def _validate_period(event_date: date, label: str) -> None:
    period = AccountingPeriod.objects.get_period_for_date(event_date)
    if not period:
        raise ValidationError(f"No accounting period found for {label} date {event_date}")
    if not period.can_modify_transactions():
        raise ValidationError(
            f"Cannot post {label} dated {event_date}: accounting period "
            f"'{period.name}' is {period.status}."
        )


def _issue_movement_payload(
    payload: KarigarIssuePayload,
    *,
    voucher: Voucher | None = None,
) -> CommodityMovementPayload:
    return CommodityMovementPayload(
        source=payload.source,
        event_type=KARIGAR_ISSUE_EVENT_TYPE,
        movement_date=payload.issue_date,
        commodity=payload.commodity,
        gross_weight=payload.gross_weight,
        purity=payload.purity,
        fine_weight=payload.fine_weight,
        movement_type=CommodityMovement.MovementType.KARIGAR_ISSUE,
        fixed_status=CommodityMovement.FixedStatus.NOT_APPLICABLE,
        from_account=payload.from_commodity_account,
        to_account=payload.to_karigar_account,
        voucher=voucher,
        uom=payload.uom,
        narration=payload.narration,
        metadata={
            "service": "karigar_issue",
            "karigar_id": payload.karigar.pk,
            **(payload.metadata or {}),
        },
    )


def _receipt_movement_payload(
    payload: KarigarReceiptPayload,
    *,
    voucher: Voucher | None = None,
) -> CommodityMovementPayload:
    return CommodityMovementPayload(
        source=payload.source,
        event_type=KARIGAR_RECEIPT_EVENT_TYPE,
        movement_date=payload.receipt_date,
        commodity=payload.commodity,
        gross_weight=payload.gross_weight,
        purity=payload.purity,
        fine_weight=payload.fine_weight,
        movement_type=CommodityMovement.MovementType.KARIGAR_RECEIPT,
        fixed_status=CommodityMovement.FixedStatus.NOT_APPLICABLE,
        from_account=payload.from_karigar_account,
        to_account=payload.to_commodity_account,
        voucher=voucher,
        uom=payload.uom,
        narration=payload.narration,
        metadata={
            "service": "karigar_receipt",
            "karigar_id": payload.karigar.pk,
            **(payload.metadata or {}),
        },
    )


def _voucher_type(name: str, description: str) -> VoucherType:
    voucher_type, _created = VoucherType.objects.update_or_create(
        name=name,
        defaults={"description": description},
    )
    return voucher_type


def _reject_existing_changed_posting(
    *,
    source: Model,
    voucher_type: VoucherType,
    message: str,
) -> None:
    source_content_type = ContentType.objects.get_for_model(source)
    if Voucher.objects.filter(
        doc_content_type=source_content_type,
        doc_object_id=source.pk,
        voucher_type=voucher_type,
        status=VoucherStatus.POSTED,
    ).exists():
        raise ValidationError(message)


def _create_posted_voucher(
    *,
    source: Model,
    voucher_type: VoucherType,
    voucher_date: date,
    voucher_no_prefix: str,
    fingerprint_payload: dict[str, Any],
    fingerprint_version: str,
    narration: str,
    actor=None,
) -> Voucher:
    source_content_type = ContentType.objects.get_for_model(source)
    fingerprint = compute_fingerprint(fingerprint_payload, fingerprint_version)
    return Voucher.objects.create(
        voucher_no=_voucher_no(voucher_no_prefix, fingerprint),
        voucher_type=voucher_type,
        voucher_date=voucher_date,
        status=VoucherStatus.POSTED,
        created_by=actor,
        updated_by=actor,
        doc_content_type=source_content_type,
        doc_object_id=source.pk,
        fingerprint=fingerprint,
        last_posted_at=timezone.now(),
        narration=narration,
    )


def _voucher_no(prefix: str, fingerprint: str) -> str:
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"
