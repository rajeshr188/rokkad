"""Read-only projections over persisted posted accounting truth."""

from datetime import date

from django.db.models import Prefetch

from ..domain.projections import (
    project_external_account_balances,
    project_financial_statements,
    project_internal_ledger_balances,
    project_journal_lines,
    project_trial_balance,
    reconcile_external_classifications,
)
from ..domain.transactions import (
    AccountClassificationSnapshot,
    AccountPurpose,
    AccountTransaction as DomainAccountTransaction,
    LedgerSide as DomainLedgerSide,
    LedgerTransaction as DomainLedgerTransaction,
    MonetaryAmount,
    ReportingClass as DomainReportingClass,
    TransactionBatch as DomainTransactionBatch,
)
from ..domain.projections import LedgerDefinition
from ..models import (
    AccountingBook,
    AccountingTransaction,
    Ledger,
    PersistedVoucherState,
    TransactionBatch,
    TransactionDiscriminator,
)


def _posted_batches(
    *, book: AccountingBook, date_from: date | None, date_to: date | None
) -> tuple[DomainTransactionBatch, ...]:
    transactions = AccountingTransaction.objects.select_related(
        "ledger_detail__debit_ledger",
        "ledger_detail__credit_ledger",
        "account_detail__ledger",
        "account_detail__external_account",
        "account_detail__classification__reporting_ledger",
    ).order_by("sequence")
    queryset = (
        TransactionBatch.objects.filter(
            book=book, voucher__state=PersistedVoucherState.POSTED
        )
        .select_related("voucher", "reversal_of__voucher")
        .prefetch_related(Prefetch("voucher__transactions", queryset=transactions))
        .order_by("voucher__effective_date", "voucher__voucher_key")
    )
    if date_from is not None:
        queryset = queryset.filter(voucher__effective_date__gte=date_from)
    if date_to is not None:
        queryset = queryset.filter(voucher__effective_date__lte=date_to)

    batches = []
    for stored_batch in queryset:
        rows = []
        for stored in stored_batch.voucher.transactions.all():
            money = MonetaryAmount(
                amount=stored.amount,
                currency=stored.currency,
                base_amount=stored.base_amount,
                base_currency=stored.base_currency,
                exchange_rate=stored.exchange_rate,
                rate_source=stored.rate_source,
            )
            if stored.discriminator == TransactionDiscriminator.LEDGER:
                detail = stored.ledger_detail
                rows.append(
                    DomainLedgerTransaction(
                        transaction_key=str(stored.id),
                        debit_ledger_key=detail.debit_ledger.ledger_key,
                        credit_ledger_key=detail.credit_ledger.ledger_key,
                        money=money,
                        narration=stored.narration,
                    )
                )
            else:
                detail = stored.account_detail
                classification = detail.classification
                rows.append(
                    DomainAccountTransaction(
                        transaction_key=str(stored.id),
                        ledger_key=detail.ledger.ledger_key,
                        external_account_key=detail.external_account.account_key,
                        ledger_side=DomainLedgerSide(detail.ledger_side),
                        classification=AccountClassificationSnapshot(
                            version_key=classification.version_key,
                            purpose=AccountPurpose(detail.external_account.purpose),
                            reporting_class=DomainReportingClass(
                                classification.reporting_class
                            ),
                            reporting_ledger_key=(
                                classification.reporting_ledger.ledger_key
                            ),
                            normal_side=DomainLedgerSide(classification.normal_side),
                        ),
                        money=money,
                        narration=stored.narration,
                    )
                )
        batches.append(
            DomainTransactionBatch(
                batch_key=stored_batch.voucher.voucher_key,
                book_key=book.book_key,
                idempotency_key=stored_batch.voucher.idempotency_key,
                effective_date=stored_batch.voucher.effective_date,
                transactions=tuple(rows),
                reversal_of_batch_key=(
                    stored_batch.reversal_of.voucher.voucher_key
                    if stored_batch.reversal_of_id
                    else None
                ),
            )
        )
    return tuple(batches)


def _ledger_definitions(book: AccountingBook) -> dict[str, LedgerDefinition]:
    return {
        ledger.ledger_key: LedgerDefinition(
            ledger_key=ledger.ledger_key,
            reporting_class=DomainReportingClass(ledger.reporting_class),
            normal_side=DomainLedgerSide(ledger.normal_side),
        )
        for ledger in Ledger.objects.filter(book=book)
    }


def posted_journal_lines(*, book, date_from=None, date_to=None):
    return project_journal_lines(
        _posted_batches(book=book, date_from=date_from, date_to=date_to)
    )


def posted_internal_ledger_balances(*, book, date_from=None, date_to=None):
    return project_internal_ledger_balances(
        _posted_batches(book=book, date_from=date_from, date_to=date_to)
    )


def posted_external_account_balances(*, book, date_from=None, date_to=None):
    return project_external_account_balances(
        _posted_batches(book=book, date_from=date_from, date_to=date_to)
    )


def posted_trial_balance(*, book, date_from=None, date_to=None):
    batches = _posted_batches(book=book, date_from=date_from, date_to=date_to)
    return project_trial_balance(batches, ledger_definitions=_ledger_definitions(book))


def posted_financial_statements(*, book, date_from=None, date_to=None):
    batches = _posted_batches(book=book, date_from=date_from, date_to=date_to)
    return project_financial_statements(
        batches, ledger_definitions=_ledger_definitions(book)
    )


def posted_classification_reconciliation(*, book, date_from=None, date_to=None):
    batches = _posted_batches(book=book, date_from=date_from, date_to=date_to)
    return reconcile_external_classifications(
        batches, ledger_definitions=_ledger_definitions(book)
    )
