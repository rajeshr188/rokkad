"""Read models for non-financial settlement evidence."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import models
from django.db.models import Q, Sum

from ..models import AccountTransaction, OpenItem, PersistedVoucherState


@dataclass(frozen=True, slots=True)
class OpenItemOutstanding:
    amount: Decimal
    base_amount: Decimal
    currency: str
    base_currency: str


@dataclass(frozen=True, slots=True)
class UnappliedSettlement:
    voucher_number: str
    voucher_key: str
    external_account_key: str
    party_key: str
    amount: Decimal
    allocated_amount: Decimal
    unapplied_amount: Decimal
    currency: str
    base_amount: Decimal
    allocated_base_amount: Decimal
    unapplied_base_amount: Decimal
    base_currency: str


def open_item_outstanding(open_item: OpenItem) -> OpenItemOutstanding:
    origin_batch = open_item.origin_transaction.transaction.voucher.posting_batch
    if origin_batch.reversal_batches.exists():
        return OpenItemOutstanding(
            amount=Decimal("0"), base_amount=Decimal("0"),
            currency=open_item.currency, base_currency=open_item.base_currency,
        )
    totals = open_item.allocations.aggregate(
        original_amount=Sum("amount", filter=Q(reversal_of__isnull=True)),
        original_base=Sum("base_amount", filter=Q(reversal_of__isnull=True)),
        reversed_amount=Sum("amount", filter=Q(reversal_of__isnull=False)),
        reversed_base=Sum("base_amount", filter=Q(reversal_of__isnull=False)),
    )
    net_amount = (totals["original_amount"] or Decimal("0")) - (
        totals["reversed_amount"] or Decimal("0")
    )
    net_base = (totals["original_base"] or Decimal("0")) - (
        totals["reversed_base"] or Decimal("0")
    )
    return OpenItemOutstanding(
        amount=open_item.original_amount - net_amount,
        base_amount=open_item.original_base_amount - net_base,
        currency=open_item.currency,
        base_currency=open_item.base_currency,
    )


def posted_unapplied_settlements(*, book) -> tuple[UnappliedSettlement, ...]:
    """Return unused capacity on posted, unreversed external-account settlements."""
    settlements = (
        AccountTransaction.objects.filter(
            transaction__voucher__book=book,
            transaction__voucher__state=PersistedVoucherState.POSTED,
            ledger_side=models.F("classification__normal_side"),
            transaction__voucher__posting_batch__reversal_batches__isnull=True,
        )
        .select_related(
            "transaction__voucher", "external_account", "classification"
        )
        .prefetch_related("open_item_allocations")
        .order_by(
            "transaction__voucher__effective_date",
            "transaction__voucher__voucher_number",
            "transaction__sequence",
        )
        .distinct()
    )
    rows = []
    for settlement in settlements:
        originals = Decimal("0")
        originals_base = Decimal("0")
        reversals = Decimal("0")
        reversals_base = Decimal("0")
        for allocation in settlement.open_item_allocations.all():
            if allocation.reversal_of_id is None:
                originals += allocation.amount
                originals_base += allocation.base_amount
            else:
                reversals += allocation.amount
                reversals_base += allocation.base_amount
        allocated = originals - reversals
        allocated_base = originals_base - reversals_base
        money = settlement.transaction
        unapplied = money.amount - allocated
        unapplied_base = money.base_amount - allocated_base
        if unapplied == 0 and unapplied_base == 0:
            continue
        rows.append(
            UnappliedSettlement(
                voucher_number=money.voucher.voucher_number,
                voucher_key=money.voucher.voucher_key,
                external_account_key=settlement.external_account.account_key,
                party_key=settlement.external_account.party_key,
                amount=money.amount,
                allocated_amount=allocated,
                unapplied_amount=unapplied,
                currency=money.currency,
                base_amount=money.base_amount,
                allocated_base_amount=allocated_base,
                unapplied_base_amount=unapplied_base,
                base_currency=money.base_currency,
            )
        )
    return tuple(rows)
