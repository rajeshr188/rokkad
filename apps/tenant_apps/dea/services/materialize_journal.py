from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from moneyed import Money

from ..models import (
    AccountingPeriod,
    AccountTransaction,
    JournalEntry,
    LedgerTransaction,
    TransactionType_Ext,
    Voucher,
    VoucherLine,
    VoucherStatus,
)


def _money(amount: Decimal, currency: str) -> Money:
    return Money(amount, currency)


def _validate_voucher_line_balance(voucher: Voucher, lines):
    if not lines:
        raise ValidationError("Voucher has no lines to post.")

    seen_dr = False
    seen_cr = False

    totals = {}
    base_totals = {}
    for line in lines:
        side_mult = Decimal("1") if line.side == VoucherLine.LineSide.DR else Decimal("-1")
        currency = str(line.amount.currency)

        seen_dr = seen_dr or line.side == VoucherLine.LineSide.DR
        seen_cr = seen_cr or line.side == VoucherLine.LineSide.CR

        totals[currency] = totals.get(currency, Decimal("0")) + (line.amount.amount * side_mult)

        base_value = (
            line.amount_base.amount
            if line.amount_base is not None
            else line.amount.amount
        )
        base_totals[currency] = base_totals.get(currency, Decimal("0")) + (base_value * side_mult)

    if not (seen_dr and seen_cr):
        raise ValidationError("Voucher lines must include at least one debit and one credit.")

    for currency, total in totals.items():
        if abs(total) > Decimal("0.01"):
            raise ValidationError(f"Voucher line totals are unbalanced for {currency}: {total}")

    for currency, total in base_totals.items():
        if abs(total) > Decimal("0.01"):
            raise ValidationError(
                f"Voucher base totals are unbalanced for {currency}: {total}"
            )


@transaction.atomic
def sync_voucher_lines_from_bundle(voucher: Voucher, bundle) -> int:
    """Normalize PostingBundle output into canonical VoucherLine rows."""
    voucher = Voucher.objects.select_for_update().get(pk=voucher.pk)
    if voucher.status in {VoucherStatus.POSTED, VoucherStatus.REVERSED}:
        raise ValidationError("Cannot refresh lines on posted/reversed voucher")

    VoucherLine.objects.filter(voucher=voucher).delete()

    account_map = {}
    for account_line in bundle.account_lines:
        key = (
            account_line.side,
            int(account_line.ledger_id),
            str(account_line.currency),
            Decimal(str(account_line.amount)),
        )
        account_map.setdefault(key, []).append(
            (
                int(account_line.account_id),
                account_line.xact_type_ext,
            )
        )

    new_lines = []
    line_no = 1

    for dual_line in bundle.ledger_lines:
        amount = Decimal(str(dual_line.amount))
        amount_base = Decimal(str(dual_line.amount_base))
        currency = str(dual_line.currency)

        for side, ledger_id in (
            (VoucherLine.LineSide.DR, dual_line.debit_ledger_id),
            (VoucherLine.LineSide.CR, dual_line.credit_ledger_id),
        ):
            key = (side, int(ledger_id), currency, amount)
            account_id = None
            xact_type_ext = "TXN"
            if key in account_map and account_map[key]:
                account_id, xact_type_ext = account_map[key].pop(0)

            new_lines.append(
                VoucherLine(
                    voucher=voucher,
                    line_no=line_no,
                    side=side,
                    ledger_id=ledger_id,
                    account_id=account_id,
                    amount=_money(amount, currency),
                    amount_base=_money(amount_base, "INR"),
                    xact_type_ext=xact_type_ext,
                    exchange_rate=Decimal("1"),
                )
            )
            line_no += 1

    VoucherLine.objects.bulk_create(new_lines)
    return len(new_lines)


@transaction.atomic
def materialize_journal_from_voucher_lines(*, voucher: Voucher, posted_by_id: int, period=None):
    """Create JournalEntry, LedgerTransaction and AccountTransaction from VoucherLine rows."""
    voucher = Voucher.objects.select_for_update().get(pk=voucher.pk)
    line_qs = (
        VoucherLine.objects.select_for_update()
        .filter(voucher=voucher)
        .order_by("line_no", "id")
    )
    lines = list(line_qs)

    _validate_voucher_line_balance(voucher, lines)

    if period is None:
        period = AccountingPeriod.objects.get_period_for_date(voucher.voucher_date)
    if not period:
        raise ValidationError(
            f"No accounting period found for voucher date {voucher.voucher_date}"
        )

    je = JournalEntry.objects.create(
        voucher=voucher,
        posted_by_id=posted_by_id,
        period=period,
    )

    ledger_txns = []
    account_txns = []

    txn_type_ext_cache = {}

    currencies = sorted({str(line.amount.currency) for line in lines})
    for currency in currencies:
        dr_lines = [
            {
                "line": line,
                "remaining": Decimal(str(line.amount.amount)),
                "remaining_base": Decimal(
                    str(line.amount_base.amount if line.amount_base is not None else line.amount.amount)
                ),
            }
            for line in lines
            if str(line.amount.currency) == currency and line.side == VoucherLine.LineSide.DR
        ]
        cr_lines = [
            {
                "line": line,
                "remaining": Decimal(str(line.amount.amount)),
                "remaining_base": Decimal(
                    str(line.amount_base.amount if line.amount_base is not None else line.amount.amount)
                ),
            }
            for line in lines
            if str(line.amount.currency) == currency and line.side == VoucherLine.LineSide.CR
        ]

        i = 0
        j = 0
        while i < len(dr_lines) and j < len(cr_lines):
            dr_item = dr_lines[i]
            cr_item = cr_lines[j]

            amount = min(dr_item["remaining"], cr_item["remaining"])
            amount_base = min(dr_item["remaining_base"], cr_item["remaining_base"])

            ledger_txns.append(
                LedgerTransaction(
                    journal_entry=je,
                    ledgerno_dr_id=dr_item["line"].ledger_id,
                    ledgerno_id=cr_item["line"].ledger_id,
                    amount=_money(amount, currency),
                    amount_base=_money(amount_base, "INR"),
                )
            )

            dr_item["remaining"] -= amount
            cr_item["remaining"] -= amount
            dr_item["remaining_base"] -= amount_base
            cr_item["remaining_base"] -= amount_base

            if dr_item["remaining"] <= Decimal("0.000001"):
                i += 1
            if cr_item["remaining"] <= Decimal("0.000001"):
                j += 1

    for line in lines:
        if not line.account_id:
            continue

        xact_key = line.xact_type_ext or "TXN"
        if xact_key not in txn_type_ext_cache:
            txn_type_ext_cache[xact_key], _ = TransactionType_Ext.objects.get_or_create(
                XactTypeCode_ext=xact_key,
                defaults={"description": f"{xact_key} transaction"},
            )

        account_txns.append(
            AccountTransaction(
                journal_entry=je,
                ledgerno_id=line.ledger_id,
                Account_id=line.account_id,
                XactTypeCode_id=line.side,
                XactTypeCode_ext=txn_type_ext_cache[xact_key],
                amount=line.amount,
            )
        )

    if ledger_txns:
        LedgerTransaction.objects.bulk_create(ledger_txns)
    if account_txns:
        AccountTransaction.objects.bulk_create(account_txns)

    return je
