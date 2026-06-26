"""Backend service for MVP monetary receipt/payment settlement.

This service is intentionally financial-only. Normal cash/bank settlement must
not create commodity movement, exposure, or rate-fixing rows.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Model
from django.utils import timezone
from moneyed import Money

from apps.tenant_apps.dea.models import (
    Account,
    AccountingPeriod,
    CashFlowDirection,
    JournalEntry,
    Ledger,
    PaymentMethod,
    PaymentType,
    PaymentVoucher,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherStatus,
    VoucherType,
)
from apps.tenant_apps.dea.models.commodity import MONETARY_CURRENCY_CODES
from apps.tenant_apps.dea.posting.commands import PostVoucherCommand
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine


CUSTOMER_RECEIPT_VOUCHER_TYPE = "MONETARY_CUSTOMER_RECEIPT"
SUPPLIER_PAYMENT_VOUCHER_TYPE = "MONETARY_SUPPLIER_PAYMENT"
CUSTOMER_RECEIPT_XACT_TYPE_EXT = "MCR"
SUPPLIER_PAYMENT_XACT_TYPE_EXT = "MSP"


@dataclass(frozen=True)
class CustomerReceiptPayload:
    source: Model
    receipt_date: date
    customer_account: Account
    cash_or_bank_ledger: Ledger
    receivable_ledger: Ledger
    money_amount: Decimal
    reference_number: str
    currency: str = "INR"
    payment_method: str = PaymentMethod.CASH
    narration: str = ""


@dataclass(frozen=True)
class SupplierPaymentPayload:
    source: Model
    payment_date: date
    supplier_account: Account
    payable_ledger: Ledger
    cash_or_bank_ledger: Ledger
    money_amount: Decimal
    reference_number: str
    currency: str = "INR"
    payment_method: str = PaymentMethod.CASH
    narration: str = ""


@dataclass(frozen=True)
class MonetarySettlementResult:
    created: bool
    payment_voucher: PaymentVoucher
    voucher: Voucher
    journal_entry: JournalEntry


@transaction.atomic
def post_customer_receipt(
    payload: CustomerReceiptPayload,
    *,
    actor=None,
) -> MonetarySettlementResult:
    """Post customer cash/bank receipt against monetary receivable."""

    _validate_customer_receipt(payload)
    _validate_period(payload.receipt_date)
    _ensure_debit_credit_transaction_types()

    existing = _existing_payment(
        source=payload.source,
        reference_number=payload.reference_number,
    )
    if existing:
        _assert_existing_payment_matches(
            existing,
            amount=payload.money_amount,
            currency=_receipt_currency(payload),
            direction=CashFlowDirection.RECEIPT,
        )
        voucher = _accounting_voucher_for_payment(
            existing,
            CUSTOMER_RECEIPT_VOUCHER_TYPE,
        )
        return MonetarySettlementResult(
            created=False,
            payment_voucher=existing,
            voucher=voucher,
            journal_entry=_journal_entry_for_voucher(voucher),
        )

    payment = _create_payment_voucher(
        source=payload.source,
        direction=CashFlowDirection.RECEIPT,
        payment_type=PaymentType.RECEIPT,
        event_date=payload.receipt_date,
        amount=payload.money_amount,
        currency=_receipt_currency(payload),
        reference_number=payload.reference_number,
        payment_method=payload.payment_method,
        narration=payload.narration or "Customer receipt",
        actor=actor,
    )
    voucher = _create_customer_receipt_voucher(payment, payload, actor=actor)
    journal_entry = PostVoucherCommand(DjangoPostingEngine()).execute(voucher, actor)
    voucher.refresh_from_db()
    payment.posted = True
    payment.save(update_fields=["posted"])

    return MonetarySettlementResult(
        created=True,
        payment_voucher=payment,
        voucher=voucher,
        journal_entry=journal_entry,
    )


@transaction.atomic
def post_supplier_payment(
    payload: SupplierPaymentPayload,
    *,
    actor=None,
) -> MonetarySettlementResult:
    """Post cash/bank payment against monetary supplier payable."""

    _validate_supplier_payment(payload)
    _validate_period(payload.payment_date)
    _ensure_debit_credit_transaction_types()

    existing = _existing_payment(
        source=payload.source,
        reference_number=payload.reference_number,
    )
    if existing:
        _assert_existing_payment_matches(
            existing,
            amount=payload.money_amount,
            currency=_payment_currency(payload),
            direction=CashFlowDirection.PAYMENT,
        )
        voucher = _accounting_voucher_for_payment(
            existing,
            SUPPLIER_PAYMENT_VOUCHER_TYPE,
        )
        return MonetarySettlementResult(
            created=False,
            payment_voucher=existing,
            voucher=voucher,
            journal_entry=_journal_entry_for_voucher(voucher),
        )

    payment = _create_payment_voucher(
        source=payload.source,
        direction=CashFlowDirection.PAYMENT,
        payment_type=PaymentType.RECEIPT,
        event_date=payload.payment_date,
        amount=payload.money_amount,
        currency=_payment_currency(payload),
        reference_number=payload.reference_number,
        payment_method=payload.payment_method,
        narration=payload.narration or "Supplier payment",
        actor=actor,
    )
    voucher = _create_supplier_payment_voucher(payment, payload, actor=actor)
    journal_entry = PostVoucherCommand(DjangoPostingEngine()).execute(voucher, actor)
    voucher.refresh_from_db()
    payment.posted = True
    payment.save(update_fields=["posted"])

    return MonetarySettlementResult(
        created=True,
        payment_voucher=payment,
        voucher=voucher,
        journal_entry=journal_entry,
    )


def _validate_customer_receipt(payload: CustomerReceiptPayload) -> None:
    errors = _common_errors(
        source=payload.source,
        amount=payload.money_amount,
        currency=_receipt_currency(payload),
        reference_number=payload.reference_number,
    )
    if payload.customer_account.pk is None:
        errors["customer_account"] = "Customer account must be saved."
    if payload.cash_or_bank_ledger.pk is None or payload.receivable_ledger.pk is None:
        errors["ledger"] = "Financial ledgers must be saved."
    if errors:
        raise ValidationError(errors)


def _validate_supplier_payment(payload: SupplierPaymentPayload) -> None:
    errors = _common_errors(
        source=payload.source,
        amount=payload.money_amount,
        currency=_payment_currency(payload),
        reference_number=payload.reference_number,
    )
    if payload.supplier_account.pk is None:
        errors["supplier_account"] = "Supplier account must be saved."
    if payload.payable_ledger.pk is None or payload.cash_or_bank_ledger.pk is None:
        errors["ledger"] = "Financial ledgers must be saved."
    if errors:
        raise ValidationError(errors)


def _common_errors(
    *,
    source: Model,
    amount: Decimal,
    currency: str,
    reference_number: str,
) -> dict:
    errors = {}
    if currency != "INR":
        errors["currency"] = "Monetary settlement MVP currently supports INR only."
    if currency not in MONETARY_CURRENCY_CODES:
        errors["currency"] = "Currency must be a supported monetary currency code."
    if amount <= 0:
        errors["money_amount"] = "Money amount must be positive."
    if source.pk is None:
        errors["source"] = "Source document must be saved before settlement."
    if not reference_number.strip():
        errors["reference_number"] = "Reference number is required for idempotency."
    return errors


def _validate_period(event_date: date) -> None:
    period = AccountingPeriod.objects.get_period_for_date(event_date)
    if not period:
        raise ValidationError(f"No accounting period found for settlement date {event_date}")
    if not period.can_modify_transactions():
        raise ValidationError(
            f"Cannot post settlement dated {event_date}: accounting period "
            f"'{period.name}' is {period.status}."
        )


def _create_payment_voucher(
    *,
    source: Model,
    direction: str,
    payment_type: str,
    event_date: date,
    amount: Decimal,
    currency: str,
    reference_number: str,
    payment_method: str,
    narration: str,
    actor=None,
) -> PaymentVoucher:
    return PaymentVoucher.objects.create(
        source_document=source,
        direction=direction,
        payment_type=payment_type,
        total_amount=Money(amount, currency),
        amount_in_base_currency=Money(amount, "INR"),
        payment_date=_payment_datetime(event_date),
        payment_method=payment_method,
        reference_number=reference_number.strip(),
        description=narration,
        created_by=actor,
        updated_by=actor,
    )


def _create_customer_receipt_voucher(
    payment: PaymentVoucher,
    payload: CustomerReceiptPayload,
    *,
    actor=None,
) -> Voucher:
    voucher_type = _voucher_type(
        CUSTOMER_RECEIPT_VOUCHER_TYPE,
        "Customer monetary receipt posting",
    )
    voucher = _create_voucher(
        payment=payment,
        voucher_type=voucher_type,
        event_date=payload.receipt_date,
        voucher_prefix="MCR",
        narration=payload.narration or "Customer receipt",
        actor=actor,
    )
    amount = Money(payload.money_amount, _receipt_currency(payload))
    VoucherLine.objects.bulk_create(
        [
            VoucherLine(
                voucher=voucher,
                line_no=1,
                side=VoucherLine.LineSide.DR,
                ledger=payload.cash_or_bank_ledger,
                amount=amount,
                amount_base=Money(payload.money_amount, "INR"),
                xact_type_ext=CUSTOMER_RECEIPT_XACT_TYPE_EXT,
                narration=payload.narration or "Cash/bank received",
            ),
            VoucherLine(
                voucher=voucher,
                line_no=2,
                side=VoucherLine.LineSide.CR,
                ledger=payload.receivable_ledger,
                account=payload.customer_account,
                amount=amount,
                amount_base=Money(payload.money_amount, "INR"),
                xact_type_ext=CUSTOMER_RECEIPT_XACT_TYPE_EXT,
                narration=payload.narration or "Customer receivable settled",
            ),
        ]
    )
    return voucher


def _create_supplier_payment_voucher(
    payment: PaymentVoucher,
    payload: SupplierPaymentPayload,
    *,
    actor=None,
) -> Voucher:
    voucher_type = _voucher_type(
        SUPPLIER_PAYMENT_VOUCHER_TYPE,
        "Supplier monetary payment posting",
    )
    voucher = _create_voucher(
        payment=payment,
        voucher_type=voucher_type,
        event_date=payload.payment_date,
        voucher_prefix="MSP",
        narration=payload.narration or "Supplier payment",
        actor=actor,
    )
    amount = Money(payload.money_amount, _payment_currency(payload))
    VoucherLine.objects.bulk_create(
        [
            VoucherLine(
                voucher=voucher,
                line_no=1,
                side=VoucherLine.LineSide.DR,
                ledger=payload.payable_ledger,
                account=payload.supplier_account,
                amount=amount,
                amount_base=Money(payload.money_amount, "INR"),
                xact_type_ext=SUPPLIER_PAYMENT_XACT_TYPE_EXT,
                narration=payload.narration or "Supplier payable settled",
            ),
            VoucherLine(
                voucher=voucher,
                line_no=2,
                side=VoucherLine.LineSide.CR,
                ledger=payload.cash_or_bank_ledger,
                amount=amount,
                amount_base=Money(payload.money_amount, "INR"),
                xact_type_ext=SUPPLIER_PAYMENT_XACT_TYPE_EXT,
                narration=payload.narration or "Cash/bank paid",
            ),
        ]
    )
    return voucher


def _create_voucher(
    *,
    payment: PaymentVoucher,
    voucher_type: VoucherType,
    event_date: date,
    voucher_prefix: str,
    narration: str,
    actor=None,
) -> Voucher:
    payment_ct = ContentType.objects.get_for_model(PaymentVoucher)
    return Voucher.objects.create(
        voucher_no=_voucher_no(voucher_prefix, payment),
        voucher_type=voucher_type,
        voucher_date=event_date,
        status=VoucherStatus.DRAFT,
        created_by=actor,
        updated_by=actor,
        doc_content_type=payment_ct,
        doc_object_id=payment.pk,
        narration=narration,
    )


def _existing_payment(*, source: Model, reference_number: str) -> PaymentVoucher | None:
    source_ct = ContentType.objects.get_for_model(source)
    return PaymentVoucher.objects.filter(
        source_content_type=source_ct,
        source_object_id=source.pk,
        reference_number=reference_number.strip(),
    ).first()


def _assert_existing_payment_matches(
    payment: PaymentVoucher,
    *,
    amount: Decimal,
    currency: str,
    direction: str,
) -> None:
    if (
        payment.direction != direction
        or payment.total_amount.amount != amount
        or str(payment.total_amount.currency) != currency
    ):
        raise ValidationError(
            "A payment with this source/reference already exists with a different "
            "economic payload. Reverse/correct it before reposting."
        )
    if not payment.posted:
        raise ValidationError(
            "A matching payment exists but is not posted. Manual verification is required."
        )


def _accounting_voucher_for_payment(
    payment: PaymentVoucher,
    voucher_type_name: str,
) -> Voucher:
    payment_ct = ContentType.objects.get_for_model(PaymentVoucher)
    return Voucher.objects.get(
        doc_content_type=payment_ct,
        doc_object_id=payment.pk,
        voucher_type__name=voucher_type_name,
        status=VoucherStatus.POSTED,
    )


def _voucher_type(name: str, description: str) -> VoucherType:
    voucher_type, _created = VoucherType.objects.update_or_create(
        name=name,
        defaults={"description": description},
    )
    return voucher_type


def _voucher_no(prefix: str, payment: PaymentVoucher) -> str:
    seed = f"{payment.pk}:{payment.reference_number}:{payment.total_amount}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16].upper()
    return f"{prefix}-{digest}"


def _payment_datetime(event_date: date):
    naive = datetime.combine(event_date, time.min)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _receipt_currency(payload: CustomerReceiptPayload) -> str:
    return (payload.currency or "").strip().upper()


def _payment_currency(payload: SupplierPaymentPayload) -> str:
    return (payload.currency or "").strip().upper()


def _journal_entry_for_voucher(voucher: Voucher | None) -> JournalEntry:
    if voucher is None:
        raise ValidationError("Existing payment is not linked to a voucher.")
    journal_entry = voucher.journal_entries.order_by("-id").first()
    if journal_entry is None:
        raise ValidationError("Existing payment voucher has no journal entry.")
    return journal_entry


def _ensure_debit_credit_transaction_types() -> None:
    TransactionType_DE.objects.get_or_create(
        XactTypeCode="Dr",
        defaults={"name": "Debit"},
    )
    TransactionType_DE.objects.get_or_create(
        XactTypeCode="Cr",
        defaults={"name": "Credit"},
    )
