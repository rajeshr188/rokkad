"""Read-only integrity diagnostics for the standalone accounting MVP."""

from dataclasses import dataclass
from decimal import Decimal

from .models import (
    AccountingBook,
    AccountingSourceDelivery,
    OpenItem,
    PersistedVoucherState,
    SourceDeliveryStatus,
    TransactionDiscriminator,
)
from .selectors import (
    open_item_outstanding,
    posted_classification_reconciliation,
    posted_financial_statements,
    posted_trial_balance,
)
from .services import voucher_fingerprint


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    code: str
    message: str
    book_key: str = ""


def accounting_integrity_findings() -> tuple[IntegrityFinding, ...]:
    findings = []
    for book in AccountingBook.objects.all().order_by("book_key"):
        for voucher in book.vouchers.filter(state=PersistedVoucherState.POSTED):
            if not hasattr(voucher, "posting_batch"):
                findings.append(IntegrityFinding("POSTED_WITHOUT_BATCH", str(voucher.pk), book.book_key))
                continue
            try:
                expected = voucher_fingerprint(voucher)
            except Exception as exc:
                findings.append(IntegrityFinding("INVALID_TRANSACTION_SHAPE", f"{voucher.pk}: {exc}", book.book_key))
                continue
            if expected != voucher.fingerprint or expected != voucher.posting_batch.fingerprint:
                findings.append(IntegrityFinding("FINGERPRINT_MISMATCH", str(voucher.pk), book.book_key))
            if not voucher.created_by_identity or not voucher.authorized_by_identity or not voucher.posting_batch.posted_by_identity:
                findings.append(IntegrityFinding("MISSING_ACTOR_EVIDENCE", str(voucher.pk), book.book_key))
            for row in voucher.transactions.all():
                ledger = hasattr(row, "ledger_detail")
                account = hasattr(row, "account_detail")
                valid = (row.discriminator == TransactionDiscriminator.LEDGER and ledger and not account) or (
                    row.discriminator == TransactionDiscriminator.ACCOUNT and account and not ledger
                )
                if not valid:
                    findings.append(IntegrityFinding("SUBTYPE_CARDINALITY", str(row.pk), book.book_key))
        trial = posted_trial_balance(book=book)
        statements = posted_financial_statements(book=book)
        if trial.signed_total != Decimal("0"):
            findings.append(IntegrityFinding("TRIAL_BALANCE", str(trial.signed_total), book.book_key))
        if statements.balance_sheet_signed_total != Decimal("0"):
            findings.append(IntegrityFinding("BALANCE_SHEET", str(statements.balance_sheet_signed_total), book.book_key))
        for row in posted_classification_reconciliation(book=book):
            if row.difference != Decimal("0"):
                findings.append(IntegrityFinding("CLASSIFICATION", f"{row.key}: {row.difference}", book.book_key))
        for item in OpenItem.objects.filter(book=book):
            outstanding = open_item_outstanding(item)
            if outstanding.amount < 0 or outstanding.base_amount < 0:
                findings.append(IntegrityFinding("OVERALLOCATED_OPEN_ITEM", item.open_item_key, book.book_key))
    for delivery in AccountingSourceDelivery.objects.filter(status=SourceDeliveryStatus.FAILED):
        findings.append(IntegrityFinding("FAILED_DELIVERY", f"{delivery.source_type}/{delivery.source_id}: {delivery.last_error}", delivery.book.book_key))
    return tuple(findings)
