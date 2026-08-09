"""Non-financial open-item and allocation mutation boundaries."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from ..models import AccountTransaction, OpenItem, OpenItemAllocation


def _net_totals(queryset):
    totals = queryset.aggregate(
        original_amount=Sum("amount", filter=Q(reversal_of__isnull=True)),
        original_base=Sum("base_amount", filter=Q(reversal_of__isnull=True)),
        reversed_amount=Sum("amount", filter=Q(reversal_of__isnull=False)),
        reversed_base=Sum("base_amount", filter=Q(reversal_of__isnull=False)),
    )
    return (
        (totals["original_amount"] or Decimal("0"))
        - (totals["reversed_amount"] or Decimal("0")),
        (totals["original_base"] or Decimal("0"))
        - (totals["reversed_base"] or Decimal("0")),
    )


@transaction.atomic
def create_open_item(
    *,
    origin_transaction: AccountTransaction,
    open_item_key: str,
    created_by_id: int,
    due_date: date | None = None,
) -> OpenItem:
    origin = AccountTransaction.objects.select_for_update().select_related(
        "transaction__voucher__book", "external_account"
    ).get(pk=origin_transaction.pk)
    money = origin.transaction
    return OpenItem.objects.create(
        book=money.voucher.book,
        open_item_key=open_item_key,
        origin_transaction=origin,
        external_account=origin.external_account,
        due_date=due_date,
        original_amount=money.amount,
        currency=money.currency,
        original_base_amount=money.base_amount,
        base_currency=money.base_currency,
        created_by_id=created_by_id,
    )


@transaction.atomic
def allocate_open_item(
    *,
    settlement_transaction: AccountTransaction,
    open_item: OpenItem,
    sequence: int,
    amount: Decimal,
    base_amount: Decimal,
    created_by_id: int,
) -> OpenItemAllocation:
    settlement = AccountTransaction.objects.select_for_update(of=("self",)).select_related(
        "transaction__voucher", "external_account"
    ).get(pk=settlement_transaction.pk)
    locked_item = OpenItem.objects.select_for_update(of=("self",)).select_related(
        "origin_transaction__transaction__voucher__posting_batch", "external_account"
    ).get(pk=open_item.pk)
    if locked_item.origin_transaction.transaction.voucher.posting_batch.reversal_batches.exists():
        raise ValidationError("A reversed open item cannot receive allocations.")
    settlement_used, settlement_base_used = _net_totals(
        OpenItemAllocation.objects.filter(settlement_transaction=settlement)
    )
    item_used, item_base_used = _net_totals(
        OpenItemAllocation.objects.filter(open_item=locked_item)
    )
    if settlement_used + amount > settlement.transaction.amount:
        raise ValidationError("Allocation exceeds the settlement transaction amount.")
    if settlement_base_used + base_amount > settlement.transaction.base_amount:
        raise ValidationError("Allocation exceeds the settlement base amount.")
    if item_used + amount > locked_item.original_amount:
        raise ValidationError("Allocation exceeds the open-item amount outstanding.")
    if item_base_used + base_amount > locked_item.original_base_amount:
        raise ValidationError("Allocation exceeds the open-item base amount outstanding.")
    return OpenItemAllocation.objects.create(
        settlement_transaction=settlement,
        open_item=locked_item,
        sequence=sequence,
        amount=amount,
        currency=locked_item.currency,
        base_amount=base_amount,
        base_currency=locked_item.base_currency,
        created_by_id=created_by_id,
    )


def compensate_reversed_settlement_allocations(
    *, original_batch, reversal_batch, created_by_id: int
) -> tuple[OpenItemAllocation, ...]:
    """Mirror allocations whose settlement transactions were just reversed."""
    original_count = original_batch.voucher.transactions.count()
    originals = list(
        OpenItemAllocation.objects.select_for_update()
        .filter(
            settlement_transaction__transaction__voucher=original_batch.voucher,
            reversal_of__isnull=True,
        )
        .select_related("settlement_transaction__transaction", "open_item")
        .order_by("settlement_transaction__transaction__sequence", "sequence")
    )
    compensations = []
    for original in originals:
        reversed_sequence = (
            original_count
            + 1
            - original.settlement_transaction.transaction.sequence
        )
        reversal_settlement = AccountTransaction.objects.get(
            transaction__voucher=reversal_batch.voucher,
            transaction__sequence=reversed_sequence,
        )
        compensation, _ = OpenItemAllocation.objects.get_or_create(
            reversal_of=original,
            defaults={
                "settlement_transaction": reversal_settlement,
                "open_item": original.open_item,
                "sequence": original.sequence,
                "amount": original.amount,
                "currency": original.currency,
                "base_amount": original.base_amount,
                "base_currency": original.base_currency,
                "created_by_id": created_by_id,
            },
        )
        compensations.append(compensation)
    return tuple(compensations)
