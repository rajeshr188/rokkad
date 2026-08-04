"""Read-only DEA evidence for PawnLoan accounting reconciliation."""

from dataclasses import dataclass
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.dea.models.journal import JournalEntry
from apps.tenant_apps.dea.models.voucher import Voucher, VoucherLine, VoucherStatus


@dataclass(frozen=True)
class LoanAccountingReference:
    voucher_exists: bool
    journal_exists: bool
    source_matches: bool
    journal_matches_voucher: bool
    voucher_status: str | None
    source_voucher_count: int
    debit_total: Decimal
    credit_total: Decimal


def inspect_pawn_loan_accounting_reference(
    *,
    voucher_id: int,
    journal_entry_id: int,
    source_event_id: int,
) -> LoanAccountingReference:
    """Inspect referenced DEA records without exposing DEA models to Loans."""
    voucher = Voucher.objects.filter(pk=voucher_id).first()
    journal = JournalEntry.objects.filter(pk=journal_entry_id).first()
    event_type = ContentType.objects.filter(
        app_label="loans",
        model="pawnloanaccountingevent",
    ).first()
    source_matches = bool(
        voucher
        and event_type
        and voucher.doc_content_type_id == event_type.pk
        and voucher.doc_object_id == source_event_id
    )
    source_voucher_count = 0
    if event_type:
        source_voucher_count = Voucher.objects.filter(
            doc_content_type=event_type,
            doc_object_id=source_event_id,
        ).exclude(status=VoucherStatus.DRAFT).count()

    debit_total = Decimal("0")
    credit_total = Decimal("0")
    if voucher:
        lines = tuple(voucher.lines.all())
        ledger_only_lines = tuple(line for line in lines if not line.account_id)
        financial_lines = (
            ledger_only_lines
            if _lines_are_balanced(ledger_only_lines)
            else lines
        )
        for line in financial_lines:
            amount = Decimal(str(line.amount.amount))
            if line.side == VoucherLine.LineSide.DR:
                debit_total += amount
            else:
                credit_total += amount
    return LoanAccountingReference(
        voucher_exists=voucher is not None,
        journal_exists=journal is not None,
        source_matches=source_matches,
        journal_matches_voucher=bool(journal and voucher and journal.voucher_id == voucher.pk),
        voucher_status=voucher.status if voucher else None,
        source_voucher_count=source_voucher_count,
        debit_total=debit_total,
        credit_total=credit_total,
    )


def _lines_are_balanced(lines):
    if not lines:
        return False
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    for line in lines:
        amount = Decimal(str(line.amount.amount))
        if line.side == VoucherLine.LineSide.DR:
            debit_total += amount
        else:
            credit_total += amount
    return debit_total > 0 and credit_total > 0 and abs(debit_total - credit_total) <= Decimal("0.01")


__all__ = ["LoanAccountingReference", "inspect_pawn_loan_accounting_reference"]
