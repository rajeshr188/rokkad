"""Versioned MVP adapter for sales and customer-receipt source events."""

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from . import facade
from .models import (
    AccountingBook,
    AccountingSourceDelivery,
    ExternalAccount,
    Ledger,
    LedgerSide,
    SourceDeliveryStatus,
)

SUPPORTED_TYPES = {"CASH_SALE", "CREDIT_SALE", "CUSTOMER_RECEIPT"}


@dataclass(frozen=True, slots=True)
class SalesReceiptEventV1:
    source_system: str
    source_type: str
    source_id: str
    source_version: str
    effective_date: date
    amount: Decimal
    currency: str = "INR"
    book_key: str = "PRIMARY"
    debit_ledger_key: str = ""
    credit_ledger_key: str = ""
    ledger_key: str = ""
    external_account_key: str = ""
    narration: str = ""
    open_item_key: str = ""
    due_date: date | None = None
    allocation_amount: Decimal = Decimal("0")
    schema_version: str = "1"


def _payload(event):
    data = asdict(event)
    data["effective_date"] = event.effective_date.isoformat()
    data["amount"] = str(event.amount)
    data["due_date"] = event.due_date.isoformat() if event.due_date else None
    data["allocation_amount"] = str(event.allocation_amount)
    return data


def _hash(event):
    encoded = json.dumps(_payload(event), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate(event):
    if event.schema_version != "1" or event.source_type not in SUPPORTED_TYPES:
        raise ValidationError("Unsupported sales/receipt event schema or type.")
    if event.amount <= 0 or event.currency != "INR":
        raise ValidationError("MVP source events require a positive INR amount.")
    if event.source_type == "CASH_SALE" and not (event.debit_ledger_key and event.credit_ledger_key):
        raise ValidationError("Cash sale requires debit and credit ledger keys.")
    if event.source_type != "CASH_SALE" and not (event.ledger_key and event.external_account_key):
        raise ValidationError("Account event requires ledger and external-account keys.")
    if event.allocation_amount < 0 or event.allocation_amount > event.amount:
        raise ValidationError("Receipt allocation must be between zero and the receipt amount.")
    if event.allocation_amount and (event.source_type != "CUSTOMER_RECEIPT" or not event.open_item_key):
        raise ValidationError("Receipt allocation requires a target open-item key.")


def deliver_sales_receipt_event(*, event, workspace, maker, authorizer, poster):
    _validate(event)
    book = AccountingBook.objects.select_related("organization").get(book_key=event.book_key)
    payload_hash = _hash(event)
    identity = dict(
        book=book, source_system=event.source_system, source_type=event.source_type,
        source_id=event.source_id, source_version=event.source_version,
    )
    delivery, _ = AccountingSourceDelivery.objects.get_or_create(
        **identity,
        defaults={"schema_version": event.schema_version, "payload_hash": payload_hash},
    )
    if delivery.payload_hash != payload_hash:
        raise ValidationError("Source identity was reused with a changed payload.")
    if delivery.status == SourceDeliveryStatus.POSTED:
        return delivery
    try:
        with transaction.atomic():
            delivery = AccountingSourceDelivery.objects.select_for_update().get(pk=delivery.pk)
            if delivery.status == SourceDeliveryStatus.POSTED:
                return delivery
            token = hashlib.sha256(
                f"{event.source_system}:{event.source_type}:{event.source_id}:{event.source_version}".encode()
            ).hexdigest()[:32]
            voucher = facade.create_draft(
                actor=maker, workspace=workspace, book=book,
                voucher_key=f"SRC-{token}", idempotency_key=f"source:{token}",
                effective_date=event.effective_date, source_system=event.source_system,
                source_type=event.source_type, source_id=event.source_id,
                source_version=event.source_version, rule_key=f"MVP_{event.source_type}",
                rule_version=event.schema_version, narration=event.narration,
            )
            money = dict(
                sequence=1, amount=event.amount, currency=event.currency,
                base_amount=event.amount, base_currency="INR", exchange_rate=Decimal("1"),
                rate_source="BOOK_BASE_CURRENCY", narration=event.narration,
            )
            if event.source_type == "CASH_SALE":
                facade.add_ledger_line(
                    actor=maker, workspace=workspace, voucher=voucher,
                    debit_ledger=Ledger.objects.get(book=book, ledger_key=event.debit_ledger_key),
                    credit_ledger=Ledger.objects.get(book=book, ledger_key=event.credit_ledger_key),
                    **money,
                )
            else:
                facade.add_account_line(
                    actor=maker, workspace=workspace, voucher=voucher,
                    ledger=Ledger.objects.get(book=book, ledger_key=event.ledger_key),
                    external_account=ExternalAccount.objects.get(
                        book=book, account_key=event.external_account_key
                    ),
                    ledger_side=(LedgerSide.CREDIT if event.source_type == "CREDIT_SALE" else LedgerSide.DEBIT),
                    **money,
                )
            voucher = facade.authorize(actor=authorizer, workspace=workspace, voucher=voucher)
            facade.post(actor=poster, workspace=workspace, voucher=voucher)
            account_transaction = (
                voucher.transactions.get(sequence=1).account_detail
                if event.source_type != "CASH_SALE" else None
            )
            if event.source_type == "CREDIT_SALE" and event.open_item_key:
                facade.create_receivable_item(
                    actor=maker, workspace=workspace, origin_transaction=account_transaction,
                    open_item_key=event.open_item_key, due_date=event.due_date,
                )
            if event.source_type == "CUSTOMER_RECEIPT" and event.allocation_amount:
                from .models import OpenItem
                facade.allocate_receipt(
                    actor=maker, workspace=workspace, settlement_transaction=account_transaction,
                    open_item=OpenItem.objects.get(book=book, open_item_key=event.open_item_key),
                    amount=event.allocation_amount,
                )
            delivery.voucher = voucher
            delivery.status = SourceDeliveryStatus.POSTED
            delivery.attempt_count += 1
            delivery.last_error = ""
            delivery.save(update_fields=("voucher", "status", "attempt_count", "last_error", "updated_at"))
            return delivery
    except Exception as exc:
        AccountingSourceDelivery.objects.filter(pk=delivery.pk).update(
            status=SourceDeliveryStatus.FAILED,
            attempt_count=F("attempt_count") + 1,
            last_error=str(exc)[:2000],
        )
        raise
