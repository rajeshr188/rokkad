"""Backend service for MVP unfixed commodity purchase posting.

Unfixed purchase records metal receipt/exposure without creating a final
monetary payable. Rate fixing is responsible for later financial settlement.
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
    ExposureLine,
    Voucher,
    VoucherStatus,
    VoucherType,
)
from apps.tenant_apps.dea.models.commodity import MONETARY_CURRENCY_CODES
from apps.tenant_apps.dea.posting.context import compute_fingerprint
from apps.tenant_apps.dea.services.commodity_posting import (
    CommodityMovementPayload,
    ExposurePayload,
    build_commodity_movement_idempotency_key,
    build_exposure_idempotency_key,
    open_exposure,
    post_commodity_movement,
)
from apps.tenant_apps.party.models import Party


UNFIXED_PURCHASE_VOUCHER_TYPE = "COMMODITY_UNFIXED_PURCHASE"
UNFIXED_PURCHASE_MOVEMENT_EVENT_TYPE = "unfixed-purchase-receipt"
UNFIXED_PURCHASE_EXPOSURE_EVENT_TYPE = "unfixed-purchase-exposure"
UNFIXED_PURCHASE_FINGERPRINT_VERSION = "commodity-unfixed-purchase-v1"


@dataclass(frozen=True)
class UnfixedPurchasePostingPayload:
    source: Model
    purchase_date: date
    party: Party
    commodity: Commodity
    gross_weight: Decimal
    purity: Decimal
    fine_weight: Decimal
    from_commodity_account: CommodityAccount
    to_commodity_account: CommodityAccount
    uom: str = Commodity.UnitOfMeasure.GRAM
    rate_basis: str = ""
    valuation_currency: str = "INR"
    last_valuation_rate: Decimal | None = None
    last_valuation_amount: Decimal | None = None
    narration: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class UnfixedPurchasePostingResult:
    created: bool
    voucher: Voucher
    commodity_movement: CommodityMovement
    exposure: ExposureLine


@transaction.atomic
def post_unfixed_purchase(
    payload: UnfixedPurchasePostingPayload,
    *,
    actor=None,
) -> UnfixedPurchasePostingResult:
    """Post an unfixed purchase as commodity movement plus open exposure only."""

    _validate_payload(payload)
    _validate_period(payload.purchase_date)

    movement_payload = _movement_payload(payload)
    exposure_payload = _exposure_payload(payload)
    movement_key = build_commodity_movement_idempotency_key(movement_payload)
    exposure_key = build_exposure_idempotency_key(exposure_payload)

    existing_movement = (
        CommodityMovement.objects.select_related("voucher")
        .filter(idempotency_key=movement_key)
        .first()
    )
    existing_exposure = (
        ExposureLine.objects.select_related("voucher")
        .filter(idempotency_key=exposure_key)
        .first()
    )
    if existing_movement and existing_exposure:
        if existing_movement.voucher_id != existing_exposure.voucher_id:
            raise ValidationError(
                "Existing unfixed purchase movement/exposure are linked to different vouchers."
            )
        return UnfixedPurchasePostingResult(
            created=False,
            voucher=existing_movement.voucher,
            commodity_movement=existing_movement,
            exposure=existing_exposure,
        )
    if existing_movement or existing_exposure:
        raise ValidationError(
            "Incomplete existing unfixed purchase posting found. "
            "Manual verification is required before retrying."
        )

    voucher_type = _unfixed_purchase_voucher_type()
    source_content_type = ContentType.objects.get_for_model(payload.source)
    if Voucher.objects.filter(
        doc_content_type=source_content_type,
        doc_object_id=payload.source.pk,
        voucher_type=voucher_type,
        status=VoucherStatus.POSTED,
    ).exists():
        raise ValidationError(
            "A posted unfixed purchase voucher already exists for this source. "
            "Reverse/correct the existing posting before posting a changed payload."
        )

    fingerprint = compute_fingerprint(
        {
            "source": f"{payload.source._meta.label_lower}:{payload.source.pk}",
            "movement_key": movement_key,
            "exposure_key": exposure_key,
        },
        UNFIXED_PURCHASE_FINGERPRINT_VERSION,
    )
    voucher = Voucher.objects.create(
        voucher_no=_voucher_no(fingerprint),
        voucher_type=voucher_type,
        voucher_date=payload.purchase_date,
        status=VoucherStatus.POSTED,
        created_by=actor,
        updated_by=actor,
        doc_content_type=source_content_type,
        doc_object_id=payload.source.pk,
        fingerprint=fingerprint,
        last_posted_at=timezone.now(),
        narration=payload.narration or "Unfixed commodity purchase",
    )

    movement_result = post_commodity_movement(
        _movement_payload(payload, voucher=voucher),
        actor=actor,
    )
    exposure_result = open_exposure(
        _exposure_payload(payload, voucher=voucher),
        actor=actor,
    )

    return UnfixedPurchasePostingResult(
        created=movement_result.created or exposure_result.created,
        voucher=voucher,
        commodity_movement=movement_result.record,
        exposure=exposure_result.record,
    )


def _validate_payload(payload: UnfixedPurchasePostingPayload) -> None:
    errors = {}
    valuation_currency = _valuation_currency(payload)
    if valuation_currency not in MONETARY_CURRENCY_CODES:
        errors["valuation_currency"] = (
            "Valuation currency must be a supported monetary currency code."
        )
    if payload.last_valuation_rate is not None and payload.last_valuation_rate <= 0:
        errors["last_valuation_rate"] = "Last valuation rate must be positive."
    if payload.last_valuation_amount is not None and payload.last_valuation_amount <= 0:
        errors["last_valuation_amount"] = "Last valuation amount must be positive."
    if payload.gross_weight <= 0:
        errors["gross_weight"] = "Gross weight must be positive."
    if payload.purity <= 0:
        errors["purity"] = "Purity must be positive."
    if payload.fine_weight <= 0:
        errors["fine_weight"] = "Fine weight must be positive."
    if payload.source.pk is None:
        errors["source"] = "Source document must be saved before posting."
    if payload.party.pk is None:
        errors["party"] = "Party must be saved."
    if payload.commodity.pk is None:
        errors["commodity"] = "Commodity must be saved."
    if (
        payload.from_commodity_account.pk is None
        or payload.to_commodity_account.pk is None
    ):
        errors["commodity_account"] = "Commodity accounts must be saved."
    if (
        payload.from_commodity_account.commodity_id != payload.commodity.pk
        or payload.to_commodity_account.commodity_id != payload.commodity.pk
    ):
        errors["commodity_account"] = (
            "Commodity accounts must belong to the purchased commodity."
        )

    if errors:
        raise ValidationError(errors)


def _unfixed_purchase_voucher_type() -> VoucherType:
    voucher_type, _created = VoucherType.objects.update_or_create(
        name=UNFIXED_PURCHASE_VOUCHER_TYPE,
        defaults={"description": "Unfixed commodity purchase posting"},
    )
    return voucher_type


def _validate_period(purchase_date: date) -> None:
    period = AccountingPeriod.objects.get_period_for_date(purchase_date)
    if not period:
        raise ValidationError(
            f"No accounting period found for unfixed purchase date {purchase_date}"
        )
    if not period.can_modify_transactions():
        raise ValidationError(
            f"Cannot post unfixed purchase dated {purchase_date}: accounting period "
            f"'{period.name}' is {period.status}."
        )


def _movement_payload(
    payload: UnfixedPurchasePostingPayload,
    *,
    voucher: Voucher | None = None,
) -> CommodityMovementPayload:
    return CommodityMovementPayload(
        source=payload.source,
        event_type=UNFIXED_PURCHASE_MOVEMENT_EVENT_TYPE,
        movement_date=payload.purchase_date,
        commodity=payload.commodity,
        gross_weight=payload.gross_weight,
        purity=payload.purity,
        fine_weight=payload.fine_weight,
        movement_type=CommodityMovement.MovementType.PURCHASE_RECEIPT,
        fixed_status=CommodityMovement.FixedStatus.UNFIXED,
        from_account=payload.from_commodity_account,
        to_account=payload.to_commodity_account,
        voucher=voucher,
        uom=payload.uom,
        narration=payload.narration,
        metadata={
            "service": "unfixed_purchase",
            "rate_basis": payload.rate_basis,
            **(payload.metadata or {}),
        },
    )


def _exposure_payload(
    payload: UnfixedPurchasePostingPayload,
    *,
    voucher: Voucher | None = None,
) -> ExposurePayload:
    return ExposurePayload(
        source=payload.source,
        event_type=UNFIXED_PURCHASE_EXPOSURE_EVENT_TYPE,
        party=payload.party,
        commodity=payload.commodity,
        side=ExposureLine.Side.PURCHASE,
        fixed_status=CommodityMovement.FixedStatus.UNFIXED,
        original_fine_weight=payload.fine_weight,
        open_fine_weight=payload.fine_weight,
        voucher=voucher,
        uom=payload.uom,
        rate_basis=payload.rate_basis,
        valuation_currency=_valuation_currency(payload),
        last_valuation_rate=payload.last_valuation_rate,
        last_valuation_amount=payload.last_valuation_amount,
    )


def _voucher_no(fingerprint: str) -> str:
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16].upper()
    return f"CUP-{digest}"


def _valuation_currency(payload: UnfixedPurchasePostingPayload) -> str:
    return (payload.valuation_currency or "").strip().upper()
