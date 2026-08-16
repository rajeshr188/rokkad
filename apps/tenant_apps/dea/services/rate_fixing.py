"""Backend service for MVP commodity rate fixing.

Purchase fixing turns open purchase exposure into monetary supplier payable.
Sale fixing turns open sale exposure into monetary customer receivable/revenue.
Both paths keep metal quantity out of financial currency fields.
"""

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from moneyed import Money

from apps.tenant_apps.dea.models import (
    Account,
    AccountingPeriod,
    CommodityMovement,
    ExposureLine,
    JournalEntry,
    Ledger,
    RateFixing,
    RateFixingAllocation,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherStatus,
    VoucherType,
)
from apps.tenant_apps.dea.models.commodity import MONETARY_CURRENCY_CODES
from apps.tenant_apps.dea.posting.commands import PostVoucherCommand
from apps.tenant_apps.dea.posting.context import compute_fingerprint
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine


PURCHASE_RATE_FIXING_VOUCHER_TYPE = "COMMODITY_PURCHASE_RATE_FIXING"
PURCHASE_RATE_FIXING_FINGERPRINT_VERSION = "commodity-purchase-rate-fixing-v1"
PURCHASE_RATE_FIXING_XACT_TYPE_EXT = "RFPU"
SALE_RATE_FIXING_VOUCHER_TYPE = "COMMODITY_SALE_RATE_FIXING"
SALE_RATE_FIXING_FINGERPRINT_VERSION = "commodity-sale-rate-fixing-v1"
SALE_RATE_FIXING_XACT_TYPE_EXT = "RFSA"


@dataclass(frozen=True)
class PurchaseRateFixingPayload:
    exposure: ExposureLine
    fixing_date: date
    fine_weight: Decimal
    rate: Decimal
    supplier_account: Account
    inventory_ledger: Ledger
    payable_ledger: Ledger
    currency: str = "INR"
    narration: str = ""


@dataclass(frozen=True)
class PurchaseRateFixingResult:
    created: bool
    rate_fixing: RateFixing
    voucher: Voucher
    journal_entry: JournalEntry
    allocation: RateFixingAllocation
    exposure: ExposureLine


@dataclass(frozen=True)
class SaleRateFixingPayload:
    exposure: ExposureLine
    fixing_date: date
    fine_weight: Decimal
    rate: Decimal
    customer_account: Account
    receivable_ledger: Ledger
    revenue_ledger: Ledger
    currency: str = "INR"
    narration: str = ""


@dataclass(frozen=True)
class SaleRateFixingResult:
    created: bool
    rate_fixing: RateFixing
    voucher: Voucher
    journal_entry: JournalEntry
    allocation: RateFixingAllocation
    exposure: ExposureLine


@transaction.atomic
def post_purchase_rate_fixing(
    payload: PurchaseRateFixingPayload,
    *,
    actor=None,
) -> PurchaseRateFixingResult:
    """Fix an open purchase exposure and create the monetary payable."""

    _validate_payload(payload)
    _validate_period(payload.fixing_date)
    _ensure_debit_credit_transaction_types()

    idempotency_key = _idempotency_key(payload)
    existing = (
        RateFixing.objects.select_related("voucher")
        .filter(idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        allocation = existing.allocations.select_related("exposure").get()
        journal_entry = _journal_entry_for_voucher(existing.voucher)
        return PurchaseRateFixingResult(
            created=False,
            rate_fixing=existing,
            voucher=existing.voucher,
            journal_entry=journal_entry,
            allocation=allocation,
            exposure=allocation.exposure,
        )

    exposure = (
        ExposureLine.objects.select_for_update()
        .select_related("party", "commodity")
        .get(pk=payload.exposure.pk)
    )
    _validate_locked_exposure(payload, exposure)

    amount = _valuation_amount(payload)
    rate_fixing = RateFixing.objects.create(
        fixing_no=_fixing_no(idempotency_key),
        fixing_date=payload.fixing_date,
        party=exposure.party,
        commodity=exposure.commodity,
        side=ExposureLine.Side.PURCHASE,
        fine_weight=payload.fine_weight,
        uom=exposure.uom,
        rate=payload.rate,
        currency=_currency(payload),
        valuation_amount=amount,
        status=RateFixing.Status.DRAFT,
        idempotency_key=idempotency_key,
        narration=payload.narration,
        created_by=actor,
        updated_by=actor,
    )
    allocation = RateFixingAllocation.objects.create(
        rate_fixing=rate_fixing,
        exposure=exposure,
        fine_weight=payload.fine_weight,
        amount=amount,
    )

    voucher = _create_financial_voucher(payload, rate_fixing, amount, actor=actor)
    journal_entry = PostVoucherCommand(DjangoPostingEngine()).execute(voucher, actor)
    voucher.refresh_from_db()

    remaining_weight = (exposure.open_fine_weight - payload.fine_weight).quantize(
        Decimal("0.001")
    )
    exposure.open_fine_weight = remaining_weight
    if remaining_weight == Decimal("0.000"):
        exposure.status = ExposureLine.Status.FIXED
        exposure.fixed_status = CommodityMovement.FixedStatus.FIXED
    else:
        exposure.status = ExposureLine.Status.PARTIALLY_FIXED
        exposure.fixed_status = CommodityMovement.FixedStatus.PARTIALLY_FIXED
    exposure.save(update_fields=["open_fine_weight", "status", "fixed_status", "updated_at"])

    rate_fixing.voucher = voucher
    rate_fixing.status = RateFixing.Status.POSTED
    rate_fixing.updated_by = actor
    rate_fixing.save(update_fields=["voucher", "status", "updated_by", "updated_at"])

    return PurchaseRateFixingResult(
        created=True,
        rate_fixing=rate_fixing,
        voucher=voucher,
        journal_entry=journal_entry,
        allocation=allocation,
        exposure=exposure,
    )


@transaction.atomic
def post_sale_rate_fixing(
    payload: SaleRateFixingPayload,
    *,
    actor=None,
) -> SaleRateFixingResult:
    """Fix an open sale exposure and create monetary receivable/revenue."""

    _validate_sale_payload(payload)
    _validate_period(payload.fixing_date)
    _ensure_debit_credit_transaction_types()

    idempotency_key = _sale_idempotency_key(payload)
    existing = (
        RateFixing.objects.select_related("voucher")
        .filter(idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        allocation = existing.allocations.select_related("exposure").get()
        journal_entry = _journal_entry_for_voucher(existing.voucher)
        return SaleRateFixingResult(
            created=False,
            rate_fixing=existing,
            voucher=existing.voucher,
            journal_entry=journal_entry,
            allocation=allocation,
            exposure=allocation.exposure,
        )

    exposure = (
        ExposureLine.objects.select_for_update()
        .select_related("party", "commodity")
        .get(pk=payload.exposure.pk)
    )
    _validate_locked_sale_exposure(payload, exposure)

    amount = _sale_valuation_amount(payload)
    rate_fixing = RateFixing.objects.create(
        fixing_no=_sale_fixing_no(idempotency_key),
        fixing_date=payload.fixing_date,
        party=exposure.party,
        commodity=exposure.commodity,
        side=ExposureLine.Side.SALE,
        fine_weight=payload.fine_weight,
        uom=exposure.uom,
        rate=payload.rate,
        currency=_sale_currency(payload),
        valuation_amount=amount,
        status=RateFixing.Status.DRAFT,
        idempotency_key=idempotency_key,
        narration=payload.narration,
        created_by=actor,
        updated_by=actor,
    )
    allocation = RateFixingAllocation.objects.create(
        rate_fixing=rate_fixing,
        exposure=exposure,
        fine_weight=payload.fine_weight,
        amount=amount,
    )

    voucher = _create_sale_financial_voucher(
        payload,
        rate_fixing,
        amount,
        actor=actor,
    )
    journal_entry = PostVoucherCommand(DjangoPostingEngine()).execute(voucher, actor)
    voucher.refresh_from_db()

    remaining_weight = (exposure.open_fine_weight - payload.fine_weight).quantize(
        Decimal("0.001")
    )
    exposure.open_fine_weight = remaining_weight
    if remaining_weight == Decimal("0.000"):
        exposure.status = ExposureLine.Status.FIXED
        exposure.fixed_status = CommodityMovement.FixedStatus.FIXED
    else:
        exposure.status = ExposureLine.Status.PARTIALLY_FIXED
        exposure.fixed_status = CommodityMovement.FixedStatus.PARTIALLY_FIXED
    exposure.save(update_fields=["open_fine_weight", "status", "fixed_status", "updated_at"])

    rate_fixing.voucher = voucher
    rate_fixing.status = RateFixing.Status.POSTED
    rate_fixing.updated_by = actor
    rate_fixing.save(update_fields=["voucher", "status", "updated_by", "updated_at"])

    return SaleRateFixingResult(
        created=True,
        rate_fixing=rate_fixing,
        voucher=voucher,
        journal_entry=journal_entry,
        allocation=allocation,
        exposure=exposure,
    )


def _validate_payload(payload: PurchaseRateFixingPayload) -> None:
    errors = {}
    currency = _currency(payload)
    if currency != "INR":
        errors["currency"] = "Purchase rate fixing MVP currently supports INR only."
    if currency not in MONETARY_CURRENCY_CODES:
        errors["currency"] = "Currency must be a supported monetary currency code."
    if payload.exposure.pk is None:
        errors["exposure"] = "Exposure must be saved before fixing."
    if payload.fine_weight <= 0:
        errors["fine_weight"] = "Fixing fine weight must be positive."
    if payload.rate <= 0:
        errors["rate"] = "Fixing rate must be positive."
    if payload.supplier_account.pk is None:
        errors["supplier_account"] = "Supplier account must be saved."
    if payload.inventory_ledger.pk is None or payload.payable_ledger.pk is None:
        errors["ledger"] = "Financial ledgers must be saved."

    if errors:
        raise ValidationError(errors)


def _validate_sale_payload(payload: SaleRateFixingPayload) -> None:
    errors = {}
    currency = _sale_currency(payload)
    if currency != "INR":
        errors["currency"] = "Sale rate fixing MVP currently supports INR only."
    if currency not in MONETARY_CURRENCY_CODES:
        errors["currency"] = "Currency must be a supported monetary currency code."
    if payload.exposure.pk is None:
        errors["exposure"] = "Exposure must be saved before fixing."
    if payload.fine_weight <= 0:
        errors["fine_weight"] = "Fixing fine weight must be positive."
    if payload.rate <= 0:
        errors["rate"] = "Fixing rate must be positive."
    if payload.customer_account.pk is None:
        errors["customer_account"] = "Customer account must be saved."
    if payload.receivable_ledger.pk is None or payload.revenue_ledger.pk is None:
        errors["ledger"] = "Financial ledgers must be saved."

    if errors:
        raise ValidationError(errors)


def _validate_locked_exposure(
    payload: PurchaseRateFixingPayload,
    exposure: ExposureLine,
) -> None:
    errors = {}
    if exposure.side != ExposureLine.Side.PURCHASE:
        errors["exposure"] = "Only purchase exposures can be fixed by this service."
    if exposure.status not in {
        ExposureLine.Status.OPEN,
        ExposureLine.Status.PARTIALLY_FIXED,
    }:
        errors["exposure"] = "Exposure is not open for purchase rate fixing."
    if exposure.fixed_status not in {
        CommodityMovement.FixedStatus.UNFIXED,
        CommodityMovement.FixedStatus.PARTIALLY_FIXED,
    }:
        errors["exposure"] = "Exposure fixed status is not open for fixing."
    if payload.fine_weight > exposure.open_fine_weight:
        errors["fine_weight"] = "Fixing fine weight cannot exceed open exposure."
    if payload.supplier_account.party_id and (
        payload.supplier_account.party_id != exposure.party_id
    ):
        errors["supplier_account"] = (
            "Supplier account party must match exposure party when linked."
        )

    if errors:
        raise ValidationError(errors)


def _validate_locked_sale_exposure(
    payload: SaleRateFixingPayload,
    exposure: ExposureLine,
) -> None:
    errors = {}
    if exposure.side != ExposureLine.Side.SALE:
        errors["exposure"] = "Only sale exposures can be fixed by this service."
    if exposure.status not in {
        ExposureLine.Status.OPEN,
        ExposureLine.Status.PARTIALLY_FIXED,
    }:
        errors["exposure"] = "Exposure is not open for sale rate fixing."
    if exposure.fixed_status not in {
        CommodityMovement.FixedStatus.UNFIXED,
        CommodityMovement.FixedStatus.PARTIALLY_FIXED,
    }:
        errors["exposure"] = "Exposure fixed status is not open for fixing."
    if payload.fine_weight > exposure.open_fine_weight:
        errors["fine_weight"] = "Fixing fine weight cannot exceed open exposure."
    if payload.customer_account.party_id and (
        payload.customer_account.party_id != exposure.party_id
    ):
        errors["customer_account"] = (
            "Customer account party must match exposure party when linked."
        )

    if errors:
        raise ValidationError(errors)


def _validate_period(fixing_date: date) -> None:
    period = AccountingPeriod.objects.get_period_for_date(fixing_date)
    if not period:
        raise ValidationError(f"No accounting period found for fixing date {fixing_date}")
    if not period.can_modify_transactions():
        raise ValidationError(
            f"Cannot post rate fixing dated {fixing_date}: accounting period "
            f"'{period.name}' is {period.status}."
        )


def _create_financial_voucher(
    payload: PurchaseRateFixingPayload,
    rate_fixing: RateFixing,
    amount: Decimal,
    *,
    actor=None,
) -> Voucher:
    voucher_type = _purchase_voucher_type()
    source_content_type = ContentType.objects.get_for_model(rate_fixing)
    voucher = Voucher.objects.create(
        voucher_no=_voucher_no(rate_fixing.idempotency_key),
        voucher_type=voucher_type,
        voucher_date=payload.fixing_date,
        status=VoucherStatus.DRAFT,
        created_by=actor,
        updated_by=actor,
        doc_content_type=source_content_type,
        doc_object_id=rate_fixing.pk,
        narration=payload.narration or "Purchase commodity rate fixing",
    )
    money = Money(amount, _currency(payload))
    VoucherLine.objects.bulk_create(
        [
            VoucherLine(
                voucher=voucher,
                line_no=1,
                side=VoucherLine.LineSide.DR,
                ledger=payload.inventory_ledger,
                amount=money,
                amount_base=Money(amount, "INR"),
                xact_type_ext=PURCHASE_RATE_FIXING_XACT_TYPE_EXT,
                narration=payload.narration or "Rate fixing inventory value",
            ),
            VoucherLine(
                voucher=voucher,
                line_no=2,
                side=VoucherLine.LineSide.CR,
                ledger=payload.payable_ledger,
                account=payload.supplier_account,
                amount=money,
                amount_base=Money(amount, "INR"),
                xact_type_ext=PURCHASE_RATE_FIXING_XACT_TYPE_EXT,
                narration=payload.narration or "Rate fixing supplier payable",
            ),
        ]
    )
    return voucher


def _create_sale_financial_voucher(
    payload: SaleRateFixingPayload,
    rate_fixing: RateFixing,
    amount: Decimal,
    *,
    actor=None,
) -> Voucher:
    voucher_type = _sale_voucher_type()
    source_content_type = ContentType.objects.get_for_model(rate_fixing)
    voucher = Voucher.objects.create(
        voucher_no=_sale_voucher_no(rate_fixing.idempotency_key),
        voucher_type=voucher_type,
        voucher_date=payload.fixing_date,
        status=VoucherStatus.DRAFT,
        created_by=actor,
        updated_by=actor,
        doc_content_type=source_content_type,
        doc_object_id=rate_fixing.pk,
        narration=payload.narration or "Sale commodity rate fixing",
    )
    money = Money(amount, _sale_currency(payload))
    VoucherLine.objects.bulk_create(
        [
            VoucherLine(
                voucher=voucher,
                line_no=1,
                side=VoucherLine.LineSide.DR,
                ledger=payload.receivable_ledger,
                account=payload.customer_account,
                amount=money,
                amount_base=Money(amount, "INR"),
                xact_type_ext=SALE_RATE_FIXING_XACT_TYPE_EXT,
                narration=payload.narration or "Rate fixing customer receivable",
            ),
            VoucherLine(
                voucher=voucher,
                line_no=2,
                side=VoucherLine.LineSide.CR,
                ledger=payload.revenue_ledger,
                amount=money,
                amount_base=Money(amount, "INR"),
                xact_type_ext=SALE_RATE_FIXING_XACT_TYPE_EXT,
                narration=payload.narration or "Rate fixing sales revenue",
            ),
        ]
    )
    return voucher


def _purchase_voucher_type() -> VoucherType:
    voucher_type, _created = VoucherType.objects.update_or_create(
        name=PURCHASE_RATE_FIXING_VOUCHER_TYPE,
        defaults={"description": "Purchase commodity rate fixing posting"},
    )
    return voucher_type


def _sale_voucher_type() -> VoucherType:
    voucher_type, _created = VoucherType.objects.update_or_create(
        name=SALE_RATE_FIXING_VOUCHER_TYPE,
        defaults={"description": "Sale commodity rate fixing posting"},
    )
    return voucher_type


def _valuation_amount(payload: PurchaseRateFixingPayload) -> Decimal:
    return (payload.fine_weight * payload.rate).quantize(Decimal("0.01"))


def _sale_valuation_amount(payload: SaleRateFixingPayload) -> Decimal:
    return (payload.fine_weight * payload.rate).quantize(Decimal("0.01"))


def _idempotency_key(payload: PurchaseRateFixingPayload) -> str:
    return compute_fingerprint(
        {
            "exposure": payload.exposure.pk,
            "fixing_date": payload.fixing_date.isoformat(),
            "fine_weight": str(payload.fine_weight),
            "rate": str(payload.rate),
            "currency": _currency(payload),
            "supplier_account": payload.supplier_account.pk,
            "inventory_ledger": payload.inventory_ledger.pk,
            "payable_ledger": payload.payable_ledger.pk,
        },
        PURCHASE_RATE_FIXING_FINGERPRINT_VERSION,
    )


def _sale_idempotency_key(payload: SaleRateFixingPayload) -> str:
    return compute_fingerprint(
        {
            "exposure": payload.exposure.pk,
            "fixing_date": payload.fixing_date.isoformat(),
            "fine_weight": str(payload.fine_weight),
            "rate": str(payload.rate),
            "currency": _sale_currency(payload),
            "customer_account": payload.customer_account.pk,
            "receivable_ledger": payload.receivable_ledger.pk,
            "revenue_ledger": payload.revenue_ledger.pk,
        },
        SALE_RATE_FIXING_FINGERPRINT_VERSION,
    )


def _fixing_no(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16].upper()
    return f"RF-{digest}"


def _sale_fixing_no(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16].upper()
    return f"SRF-{digest}"


def _voucher_no(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16].upper()
    return f"CRF-{digest}"


def _sale_voucher_no(idempotency_key: str) -> str:
    digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16].upper()
    return f"SRF-{digest}"


def _currency(payload: PurchaseRateFixingPayload) -> str:
    return (payload.currency or "").strip().upper()


def _sale_currency(payload: SaleRateFixingPayload) -> str:
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
        raise ValidationError("Existing rate fixing is not linked to a voucher.")
    journal_entry = voucher.journal_entries.order_by("-id").first()
    if journal_entry is None:
        raise ValidationError("Existing rate fixing voucher has no journal entry.")
    return journal_entry
