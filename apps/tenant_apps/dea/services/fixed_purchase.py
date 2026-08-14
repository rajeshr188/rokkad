"""Backend service for MVP fixed commodity purchase posting.

This is intentionally document/service-level only. It does not introduce UI or
operational purchase-module coupling.
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
from moneyed import Money

from apps.tenant_apps.dea.models import (
    Account,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    JournalEntry,
    Ledger,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherStatus,
    VoucherType,
)
from apps.tenant_apps.dea.models.commodity import MONETARY_CURRENCY_CODES
from apps.tenant_apps.dea.posting.commands import PostVoucherCommand
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.services.commodity_posting import (
    CommodityMovementPayload,
    build_commodity_movement_idempotency_key,
    post_commodity_movement,
)


FIXED_PURCHASE_VOUCHER_TYPE = "COMMODITY_FIXED_PURCHASE"
FIXED_PURCHASE_EVENT_TYPE = "fixed-purchase"
FIXED_PURCHASE_XACT_TYPE_EXT = "CPUR"


@dataclass(frozen=True)
class FixedPurchasePostingPayload:
    source: Model
    purchase_date: date
    supplier_account: Account
    inventory_ledger: Ledger
    payable_ledger: Ledger
    commodity: Commodity
    gross_weight: Decimal
    purity: Decimal
    fine_weight: Decimal
    from_commodity_account: CommodityAccount
    to_commodity_account: CommodityAccount
    money_amount: Decimal
    currency: str = "INR"
    uom: str = Commodity.UnitOfMeasure.GRAM
    narration: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class FixedPurchasePostingResult:
    created: bool
    voucher: Voucher
    journal_entry: JournalEntry
    commodity_movement: CommodityMovement


@transaction.atomic
def post_fixed_purchase(
    payload: FixedPurchasePostingPayload,
    *,
    actor=None,
) -> FixedPurchasePostingResult:
    """Post a fixed metal purchase as financial accounting plus commodity movement.

    MVP policy:
    - financial side is INR-only until FX purchase valuation policy is explicit;
    - commodity quantity is posted to `CommodityMovement`, never as a money currency;
    - duplicate economic payloads return the existing voucher/journal/movement.
    """

    _validate_payload(payload)
    _ensure_debit_credit_transaction_types()

    movement_payload = _movement_payload(payload)
    movement_idempotency_key = build_commodity_movement_idempotency_key(
        movement_payload
    )
    existing_movement = (
        CommodityMovement.objects.select_related("voucher")
        .filter(idempotency_key=movement_idempotency_key)
        .first()
    )
    if existing_movement:
        voucher = existing_movement.voucher
        journal_entry = _journal_entry_for_voucher(voucher)
        return FixedPurchasePostingResult(
            created=False,
            voucher=voucher,
            journal_entry=journal_entry,
            commodity_movement=existing_movement,
        )

    voucher_type = _fixed_purchase_voucher_type()
    source_content_type = ContentType.objects.get_for_model(payload.source)
    if Voucher.objects.filter(
        doc_content_type=source_content_type,
        doc_object_id=payload.source.pk,
        voucher_type=voucher_type,
        status=VoucherStatus.POSTED,
    ).exists():
        raise ValidationError(
            "A posted fixed purchase voucher already exists for this source. "
            "Reverse/correct the existing posting before posting a changed payload."
        )

    voucher = Voucher.objects.create(
        voucher_no=_voucher_no(movement_idempotency_key),
        voucher_type=voucher_type,
        voucher_date=payload.purchase_date,
        status=VoucherStatus.DRAFT,
        created_by=actor,
        updated_by=actor,
        doc_content_type=source_content_type,
        doc_object_id=payload.source.pk,
        narration=payload.narration or "Fixed commodity purchase",
    )
    _create_voucher_lines(voucher, payload)

    journal_entry = PostVoucherCommand(DjangoPostingEngine()).execute(voucher, actor)
    voucher.refresh_from_db()

    movement_result = post_commodity_movement(
        _movement_payload(payload, voucher=voucher),
        actor=actor,
    )

    return FixedPurchasePostingResult(
        created=movement_result.created,
        voucher=voucher,
        journal_entry=journal_entry,
        commodity_movement=movement_result.record,
    )


def _validate_payload(payload: FixedPurchasePostingPayload) -> None:
    errors = {}
    currency = _currency(payload)
    if currency != "INR":
        errors["currency"] = "Fixed purchase MVP currently supports INR only."
    if currency not in MONETARY_CURRENCY_CODES:
        errors["currency"] = "Currency must be a supported monetary currency code."
    if payload.money_amount <= 0:
        errors["money_amount"] = "Money amount must be positive."
    if payload.gross_weight <= 0:
        errors["gross_weight"] = "Gross weight must be positive."
    if payload.purity <= 0:
        errors["purity"] = "Purity must be positive."
    if payload.fine_weight <= 0:
        errors["fine_weight"] = "Fine weight must be positive."
    if payload.source.pk is None:
        errors["source"] = "Source document must be saved before posting."
    if payload.commodity.pk is None:
        errors["commodity"] = "Commodity must be saved."
    if payload.supplier_account.pk is None:
        errors["supplier_account"] = "Supplier account must be saved."
    if payload.inventory_ledger.pk is None or payload.payable_ledger.pk is None:
        errors["ledger"] = "Financial ledgers must be saved."
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


def _fixed_purchase_voucher_type() -> VoucherType:
    voucher_type, _created = VoucherType.objects.update_or_create(
        name=FIXED_PURCHASE_VOUCHER_TYPE,
        defaults={"description": "Fixed commodity purchase posting"},
    )
    return voucher_type


def _create_voucher_lines(
    voucher: Voucher,
    payload: FixedPurchasePostingPayload,
) -> None:
    currency = _currency(payload)
    amount = Money(payload.money_amount, currency)
    VoucherLine.objects.bulk_create(
        [
            VoucherLine(
                voucher=voucher,
                line_no=1,
                side=VoucherLine.LineSide.DR,
                ledger=payload.inventory_ledger,
                amount=amount,
                amount_base=Money(payload.money_amount, "INR"),
                xact_type_ext=FIXED_PURCHASE_XACT_TYPE_EXT,
                narration=payload.narration or "Fixed purchase inventory",
            ),
            VoucherLine(
                voucher=voucher,
                line_no=2,
                side=VoucherLine.LineSide.CR,
                ledger=payload.payable_ledger,
                account=payload.supplier_account,
                amount=amount,
                amount_base=Money(payload.money_amount, "INR"),
                xact_type_ext=FIXED_PURCHASE_XACT_TYPE_EXT,
                narration=payload.narration or "Fixed purchase supplier payable",
            ),
        ]
    )


def _movement_payload(
    payload: FixedPurchasePostingPayload,
    *,
    voucher: Voucher | None = None,
) -> CommodityMovementPayload:
    rate = (payload.money_amount / payload.fine_weight).quantize(Decimal("0.0001"))
    return CommodityMovementPayload(
        source=payload.source,
        event_type=FIXED_PURCHASE_EVENT_TYPE,
        movement_date=payload.purchase_date,
        commodity=payload.commodity,
        gross_weight=payload.gross_weight,
        purity=payload.purity,
        fine_weight=payload.fine_weight,
        movement_type=CommodityMovement.MovementType.PURCHASE_RECEIPT,
        fixed_status=CommodityMovement.FixedStatus.FIXED,
        from_account=payload.from_commodity_account,
        to_account=payload.to_commodity_account,
        voucher=voucher,
        uom=payload.uom,
        rate=rate,
        rate_currency=_currency(payload),
        valuation_currency=_currency(payload),
        valuation_amount=payload.money_amount,
        narration=payload.narration,
        metadata={
            "service": "fixed_purchase",
            **(payload.metadata or {}),
        },
    )


def _voucher_no(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[
        :16
    ].upper()
    return f"CFP-{digest}"


def _currency(payload: FixedPurchasePostingPayload) -> str:
    return (payload.currency or "").strip().upper()


def _ensure_debit_credit_transaction_types() -> None:
    TransactionType_DE.objects.get_or_create(
        XactTypeCode="Dr",
        defaults={"name": "Debit"},
    )
    TransactionType_DE.objects.get_or_create(
        XactTypeCode="Cr",
        defaults={"name": "Credit"},
    )


def _journal_entry_for_voucher(voucher: Voucher | None) -> JournalEntry:
    if voucher is None:
        raise ValidationError("Existing commodity movement is not linked to a voucher.")
    journal_entry = voucher.journal_entries.order_by("-id").first()
    if journal_entry is None:
        raise ValidationError("Existing fixed purchase voucher has no journal entry.")
    return journal_entry
