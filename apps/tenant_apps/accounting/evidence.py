"""Accountant-readable evidence assembled from persisted read boundaries."""

from dataclasses import asdict

from .diagnostics import accounting_integrity_findings
from .models import AccountingSourceDelivery, OpenItem, PersistedVoucherState, TransactionBatch
from .selectors import (
    open_item_outstanding,
    posted_external_account_balances,
    posted_financial_statements,
    posted_journal_lines,
    posted_trial_balance,
    posted_unapplied_settlements,
)


def accountant_evidence_pack(*, book):
    statements = posted_financial_statements(book=book)
    trial = posted_trial_balance(book=book)
    return {
        "book": book.book_key,
        "base_currency": book.base_currency,
        "vouchers": [
            {
                "number": row.voucher_number, "key": row.voucher_key,
                "date": row.effective_date.isoformat(), "state": row.state,
                "source": f"{row.source_system}/{row.source_type}/{row.source_id}/{row.source_version}",
                "creator": row.created_by_identity, "authorizer": row.authorized_by_identity,
                "poster": row.posting_batch.posted_by_identity,
            }
            for row in book.vouchers.filter(state=PersistedVoucherState.POSTED)
            .select_related("posting_batch").order_by("effective_date", "voucher_number")
        ],
        "journal": [
            {
                "voucher": row.batch_key, "transaction": row.transaction_key,
                "account": row.posting_key, "account_kind": row.account_kind.value,
                "side": row.side.value, "amount": str(row.amount_base),
                "currency": row.base_currency,
            }
            for row in posted_journal_lines(book=book)
        ],
        "trial_balance": [
            {"account": row.key, "class": row.reporting_class.value, "signed_amount": str(row.signed_base_amount)}
            for row in trial.rows
        ],
        "trial_balance_difference": str(trial.signed_total),
        "profit_and_loss": [
            {"account": row.key, "class": row.reporting_class.value, "signed_amount": str(row.signed_base_amount)}
            for row in statements.profit_and_loss_rows
        ],
        "current_period_result": str(statements.current_period_result),
        "balance_sheet": [
            {"account": row.key, "class": row.reporting_class.value, "signed_amount": str(row.signed_base_amount)}
            for row in statements.balance_sheet_rows
        ],
        "balance_sheet_difference": str(statements.balance_sheet_signed_total),
        "external_accounts": [
            {"account": row.key, "signed_amount": str(row.signed_base_amount)}
            for row in posted_external_account_balances(book=book)
        ],
        "open_items": [
            {
                "item": item.open_item_key, "account": item.external_account.account_key,
                "original": str(item.original_amount),
                "outstanding": str(open_item_outstanding(item).amount),
                "currency": item.currency, "due_date": item.due_date.isoformat() if item.due_date else None,
            }
            for item in OpenItem.objects.filter(book=book).select_related("external_account")
        ],
        "unapplied_settlements": [
            {
                "voucher": row.voucher_number, "account": row.external_account_key,
                "received": str(row.amount), "allocated": str(row.allocated_amount),
                "unapplied": str(row.unapplied_amount), "currency": row.currency,
            }
            for row in posted_unapplied_settlements(book=book)
        ],
        "reversals": [
            {
                "original": row.reversal_of.voucher.voucher_number,
                "reversal": row.voucher.voucher_number, "reason": row.reversal_reason,
                "correction_group": row.correction_group_key,
            }
            for row in TransactionBatch.objects.filter(book=book, reversal_of__isnull=False)
            .select_related("voucher", "reversal_of__voucher")
        ],
        "source_deliveries": [
            {
                "source": f"{row.source_system}/{row.source_type}/{row.source_id}/{row.source_version}",
                "status": row.status, "attempts": row.attempt_count,
                "voucher": row.voucher.voucher_number if row.voucher_id else None,
                "error": row.last_error,
            }
            for row in AccountingSourceDelivery.objects.filter(book=book).select_related("voucher")
        ],
        "integrity_findings": [asdict(row) for row in accounting_integrity_findings() if not row.book_key or row.book_key == book.book_key],
    }
