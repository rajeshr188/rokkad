import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.db.models import Model

from apps.tenant_apps.dea.models import (
    Commodity,
    CommodityAccount,
    CommodityMovement,
    ExposureLine,
    Voucher,
)
from apps.tenant_apps.party.models import Party


@dataclass(frozen=True)
class CommodityMovementPayload:
    source: Model
    event_type: str
    movement_date: date
    commodity: Commodity
    gross_weight: Decimal
    purity: Decimal
    fine_weight: Decimal
    movement_type: str
    fixed_status: str
    from_account: CommodityAccount | None = None
    to_account: CommodityAccount | None = None
    voucher: Voucher | None = None
    uom: str = Commodity.UnitOfMeasure.GRAM
    rate: Decimal | None = None
    rate_currency: str = ""
    valuation_currency: str = ""
    valuation_amount: Decimal | None = None
    narration: str = ""
    metadata: dict[str, Any] | None = None
    movement_no: str = ""


@dataclass(frozen=True)
class ExposurePayload:
    source: Model
    event_type: str
    party: Party
    commodity: Commodity
    side: str
    fixed_status: str
    original_fine_weight: Decimal
    open_fine_weight: Decimal
    voucher: Voucher | None = None
    status: str = ExposureLine.Status.OPEN
    uom: str = Commodity.UnitOfMeasure.GRAM
    rate_basis: str = ""
    valuation_currency: str = "INR"
    last_valuation_rate: Decimal | None = None
    last_valuation_amount: Decimal | None = None
    exposure_no: str = ""


@dataclass(frozen=True)
class CommodityPostingResult:
    created: bool
    record: CommodityMovement | ExposureLine


def post_commodity_movement(
    payload: CommodityMovementPayload,
    *,
    actor=None,
) -> CommodityPostingResult:
    idempotency_key = build_commodity_movement_idempotency_key(payload)
    existing = CommodityMovement.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return CommodityPostingResult(created=False, record=existing)

    movement_no = payload.movement_no or _record_number("CM", idempotency_key)
    source_content_type = ContentType.objects.get_for_model(payload.source)

    try:
        with transaction.atomic():
            movement = CommodityMovement.objects.create(
                movement_no=movement_no,
                movement_date=payload.movement_date,
                source_content_type=source_content_type,
                source_object_id=payload.source.pk,
                voucher=payload.voucher,
                commodity=payload.commodity,
                uom=payload.uom,
                gross_weight=payload.gross_weight,
                purity=payload.purity,
                fine_weight=payload.fine_weight,
                from_account=payload.from_account,
                to_account=payload.to_account,
                movement_type=payload.movement_type,
                fixed_status=payload.fixed_status,
                rate=payload.rate,
                rate_currency=payload.rate_currency,
                valuation_currency=payload.valuation_currency,
                valuation_amount=payload.valuation_amount,
                idempotency_key=idempotency_key,
                narration=payload.narration,
                metadata=payload.metadata or {},
                created_by=actor,
            )
    except IntegrityError:
        existing = CommodityMovement.objects.get(idempotency_key=idempotency_key)
        return CommodityPostingResult(created=False, record=existing)

    return CommodityPostingResult(created=True, record=movement)


def open_exposure(
    payload: ExposurePayload,
    *,
    actor=None,
) -> CommodityPostingResult:
    idempotency_key = build_exposure_idempotency_key(payload)
    existing = ExposureLine.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        return CommodityPostingResult(created=False, record=existing)

    exposure_no = payload.exposure_no or _record_number("EXP", idempotency_key)
    source_content_type = ContentType.objects.get_for_model(payload.source)

    try:
        with transaction.atomic():
            exposure = ExposureLine.objects.create(
                exposure_no=exposure_no,
                source_content_type=source_content_type,
                source_object_id=payload.source.pk,
                voucher=payload.voucher,
                party=payload.party,
                commodity=payload.commodity,
                side=payload.side,
                status=payload.status,
                fixed_status=payload.fixed_status,
                original_fine_weight=payload.original_fine_weight,
                open_fine_weight=payload.open_fine_weight,
                uom=payload.uom,
                rate_basis=payload.rate_basis,
                valuation_currency=payload.valuation_currency,
                last_valuation_rate=payload.last_valuation_rate,
                last_valuation_amount=payload.last_valuation_amount,
                idempotency_key=idempotency_key,
                created_by=actor,
            )
    except IntegrityError:
        existing = ExposureLine.objects.get(idempotency_key=idempotency_key)
        return CommodityPostingResult(created=False, record=existing)

    return CommodityPostingResult(created=True, record=exposure)


def build_commodity_idempotency_key(
    *,
    prefix: str,
    source: Model,
    event_type: str,
    economic_payload: dict[str, Any],
) -> str:
    source_label = source._meta.label_lower
    payload_hash = hashlib.sha256(
        json.dumps(_normalize(economic_payload), sort_keys=True).encode("utf-8")
    ).hexdigest()[:24]
    return f"commodity:{prefix}:{source_label}:{source.pk}:{event_type}:{payload_hash}"


def build_commodity_movement_idempotency_key(
    payload: CommodityMovementPayload,
) -> str:
    return build_commodity_idempotency_key(
        prefix="movement",
        source=payload.source,
        event_type=payload.event_type,
        economic_payload=_movement_economic_payload(payload),
    )


def build_exposure_idempotency_key(payload: ExposurePayload) -> str:
    return build_commodity_idempotency_key(
        prefix="exposure",
        source=payload.source,
        event_type=payload.event_type,
        economic_payload=_exposure_economic_payload(payload),
    )


def _record_number(prefix: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _movement_economic_payload(payload: CommodityMovementPayload) -> dict[str, Any]:
    data = asdict(payload)
    data.pop("source")
    data.pop("voucher")
    data.pop("movement_no")
    data["commodity"] = payload.commodity.pk
    data["from_account"] = payload.from_account.pk if payload.from_account else None
    data["to_account"] = payload.to_account.pk if payload.to_account else None
    return data


def _exposure_economic_payload(payload: ExposurePayload) -> dict[str, Any]:
    data = asdict(payload)
    data.pop("source")
    data.pop("voucher")
    data.pop("exposure_no")
    data["party"] = payload.party.pk
    data["commodity"] = payload.commodity.pk
    return data


def _normalize(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Model):
        return value.pk
    if isinstance(value, dict):
        return {key: _normalize(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value
