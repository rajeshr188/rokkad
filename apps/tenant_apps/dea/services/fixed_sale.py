"""Backend service for MVP fixed commodity sale posting.

Fixed sale posts monetary customer receivable/revenue and a side-by-side
commodity movement that reduces owned metal.
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


FIXED_SALE_VOUCHER_TYPE = "COMMODITY_FIXED_SALE"
FIXED_SALE_EVENT_TYPE = "fixed-sale"
FIXED_SALE_XACT_TYPE_EXT = "CSAL"


@dataclass(frozen=True)
class FixedSalePostingPayload:
    source: Model
    sale_date: date
    customer_account: Account
    receivable_ledger: Ledger
    revenue_ledger: Ledger
    commodity: Commodity
    gross_weight: Decimal
    purity: Decimal
    fine_weight: Decimal
    from_commodity_account: CommodityAccount
    money_amount: Decimal
    currency: str = "INR"
    uom: str = Commodity.UnitOfMeasure.GRAM
    narration: str = ""
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class FixedSalePostingResult:
    created: bool
    voucher: Voucher
    journal_entry: JournalEntry
    commodity_movement: CommodityMovement


@transaction.atomic
def post_fixed_sale(
    payload: FixedSalePostingPayload,
    *,
    actor=None,
) -> FixedSalePostingResult:
    """Post a fixed metal sale as financial accounting plus commodity issue."""

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
        return FixedSalePostingResult(
            created=False,
            voucher=voucher,
            journal_entry=journal_entry,
            commodity_movement=existing_movement,
        )

    voucher_type = _fixed_sale_voucher_type()
    source_content_type = ContentType.objects.get_for_model(payload.source)
    if Voucher.objects.filter(
        doc_content_type=source_content_type,
        doc_object_id=payload.source.pk,
        voucher_type=voucher_type,
        status=VoucherStatus.POSTED,
    ).exists():
        raise ValidationError(
            "A posted fixed sale voucher already exists for this source. "
            "Reverse/correct the existing posting before posting a changed payload."
        )

    voucher = Voucher.objects.create(
        voucher_no=_voucher_no(movement_idempotency_key),
        voucher_type=voucher_type,
        voucher_date=payload.sale_date,
        status=VoucherStatus.DRAFT,
        created_by=actor,
        updated_by=actor,
        doc_content_type=source_content_type,
        doc_object_id=payload.source.pk,
        narration=payload.narration or "Fixed commodity sale",
    )
    _create_voucher_lines(voucher, payload)

    journal_entry = PostVoucherCommand(DjangoPostingEngine()).execute(voucher, actor)
    voucher.refresh_from_db()

    movement_result = post_commodity_movement(
        _movement_payload(payload, voucher=voucher),
        actor=actor,
    )

    return FixedSalePostingResult(
        created=movement_result.created,
        voucher=voucher,
        journal_entry=journal_entry,
        commodity_movement=movement_result.record,
    )


def _validate_payload(payload: FixedSalePostingPayload) -> None:
    errors = {}
    currency = _currency(payload)
    if currency != "INR":
        errors["currency"] = "Fixed sale MVP currently supports INR only."
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
    if payload.customer_account.pk is None:
        errors["customer_account"] = "Customer account must be saved."
    if payload.receivable_ledger.pk is None or payload.revenue_ledger.pk is None:
        errors["ledger"] = "Financial ledgers must be saved."
    if payload.from_commodity_account.pk is None:
        errors["commodity_account"] = "Commodity account must be saved."
    if payload.from_commodity_account.commodity_id != payload.commodity.pk:
        errors["commodity_account"] = (
            "Commodity account must belong to the sold commodity."
        )

    if errors:
        raise ValidationError(errors)


def _fixed_sale_voucher_type() -> VoucherType:
    voucher_type, _created = VoucherType.objects.update_or_create(
        name=FIXED_SALE_VOUCHER_TYPE,
        defaults={"description": "Fixed commodity sale posting"},
    )
    return voucher_type


def _create_voucher_lines(
    voucher: Voucher,
    payload: FixedSalePostingPayload,
) -> None:
    currency = _currency(payload)
    amount = Money(payload.money_amount, currency)
    VoucherLine.objects.bulk_create(
        [
            VoucherLine(
                voucher=voucher,
                line_no=1,
                side=VoucherLine.LineSide.DR,
                ledger=payload.receivable_ledger,
                account=payload.customer_account,
                amount=amount,
                amount_base=Money(payload.money_amount, "INR"),
                xact_type_ext=FIXED_SALE_XACT_TYPE_EXT,
                narration=payload.narration or "Fixed sale customer receivable",
            ),
            VoucherLine(
                voucher=voucher,
                line_no=2,
                side=VoucherLine.LineSide.CR,
                ledger=payload.revenue_ledger,
                amount=amount,
                amount_base=Money(payload.money_amount, "INR"),
                xact_type_ext=FIXED_SALE_XACT_TYPE_EXT,
                narration=payload.narration or "Fixed sale revenue",
            ),
        ]
    )


def _movement_payload(
    payload: FixedSalePostingPayload,
    *,
    voucher: Voucher | None = None,
) -> CommodityMovementPayload:
    rate = (payload.money_amount / payload.fine_weight).quantize(Decimal("0.0001"))
    return CommodityMovementPayload(
        source=payload.source,
        event_type=FIXED_SALE_EVENT_TYPE,
        movement_date=payload.sale_date,
        commodity=payload.commodity,
        gross_weight=payload.gross_weight,
        purity=payload.purity,
        fine_weight=payload.fine_weight,
        movement_type=CommodityMovement.MovementType.SALE_ISSUE,
        fixed_status=CommodityMovement.FixedStatus.FIXED,
        from_account=payload.from_commodity_account,
        to_account=None,
        voucher=voucher,
        uom=payload.uom,
        rate=rate,
        rate_currency=_currency(payload),
        valuation_currency=_currency(payload),
        valuation_amount=payload.money_amount,
        narration=payload.narration,
        metadata={
            "service": "fixed_sale",
            **(payload.metadata or {}),
        },
    )


def _voucher_no(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[
        :16
    ].upper()
    return f"CFS-{digest}"


def _currency(payload: FixedSalePostingPayload) -> str:
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
        raise ValidationError("Existing fixed sale voucher has no journal entry.")
    return journal_entry
