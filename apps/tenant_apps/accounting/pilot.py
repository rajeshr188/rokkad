"""Deterministic, synthetic K6 accounting acceptance pilot."""

from datetime import date, datetime, timezone
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from .models import (
    AccountingBook,
    AccountingOrganization,
    AccountingPeriod,
    ExternalAccount,
    ExternalAccountPurpose,
    Ledger,
    LedgerNodeKind,
    LedgerSide,
    OpenItem,
    PeriodStatus,
    PersistedVoucherState,
    ReportingClass,
    VoucherPurpose,
)
from .selectors import (
    open_item_outstanding,
    posted_classification_reconciliation,
    posted_external_account_balances,
    posted_financial_statements,
    posted_internal_ledger_balances,
    posted_journal_lines,
    posted_trial_balance,
    posted_unapplied_settlements,
)
from .services import (
    add_account_transaction,
    add_ledger_transaction,
    allocate_open_item,
    append_external_account_classification,
    authorize_voucher,
    correct_posted_batch,
    create_draft_voucher,
    create_open_item,
    post_authorized_voucher,
)

PILOT_DATE = date(2026, 8, 7)
PILOT_TIME = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)


def _guard_pilot_schema() -> None:
    schema = connection.schema_name
    if not settings.DEBUG or not schema.startswith("accounting_pilot_"):
        raise ValidationError(
            "Acceptance pilot requires DEBUG and an accounting_pilot_* tenant schema."
        )


def _ledger(book, *, key, code, reporting_class, normal_side):
    ledger, created = Ledger.objects.get_or_create(
        book=book,
        ledger_key=key,
        defaults={
            "code": code,
            "name": key.replace("_", " ").title(),
            "reporting_class": reporting_class,
            "normal_side": normal_side,
            "node_kind": LedgerNodeKind.POSTING,
        },
    )
    if not created and (
        ledger.code != code
        or ledger.reporting_class != reporting_class
        or ledger.normal_side != normal_side
        or ledger.node_kind != LedgerNodeKind.POSTING
    ):
        raise ValidationError(f"Pilot ledger {key} conflicts with existing configuration.")
    return ledger


def _draft(*, book, key, number, source_type, source_id, source_version="1", group=""):
    existing = book.vouchers.filter(voucher_key=key).first()
    if existing:
        return existing
    return create_draft_voucher(
        book=book,
        voucher_key=key,
        voucher_number=number,
        idempotency_key=f"pilot:{key}",
        effective_date=PILOT_DATE,
        source_system="SYNTHETIC_ACCEPTANCE_PILOT",
        source_type=source_type,
        source_id=source_id,
        source_version=source_version,
        rule_key=f"PILOT_{source_type}",
        rule_version="1",
        correction_group_key=group,
    )


def _authorize_and_post(voucher, actor_id):
    if voucher.state == PersistedVoucherState.DRAFT:
        authorize_voucher(voucher=voucher, actor_id=actor_id, authorized_at=PILOT_TIME)
        voucher.refresh_from_db()
    if voucher.state == PersistedVoucherState.AUTHORIZED:
        return post_authorized_voucher(
            voucher=voucher, actor_id=actor_id, posted_at=PILOT_TIME
        )
    return voucher.posting_batch


@transaction.atomic
def run_acceptance_pilot(*, actor_id: int) -> dict:
    _guard_pilot_schema()
    organization, _ = AccountingOrganization.objects.get_or_create(
        organization_key="PILOT_ORG",
        defaults={"name": "Synthetic Accounting Pilot"},
    )
    book, _ = AccountingBook.objects.get_or_create(
        organization=organization,
        book_key="PILOT_INR",
        defaults={
            "name": "Synthetic INR Pilot Book",
            "base_currency": "INR",
            "decimal_places": 2,
        },
    )
    AccountingPeriod.objects.get_or_create(
        book=book,
        period_key="FY2026_PILOT",
        defaults={
            "start_date": date(2026, 4, 1),
            "end_date": date(2027, 3, 31),
            "status": PeriodStatus.OPEN,
        },
    )
    cash = _ledger(
        book, key="PILOT_CASH", code="1100", reporting_class=ReportingClass.ASSET,
        normal_side=LedgerSide.DEBIT,
    )
    receivable = _ledger(
        book, key="PILOT_RECEIVABLE", code="1200", reporting_class=ReportingClass.ASSET,
        normal_side=LedgerSide.DEBIT,
    )
    revenue = _ledger(
        book, key="PILOT_SALES", code="4100", reporting_class=ReportingClass.REVENUE,
        normal_side=LedgerSide.CREDIT,
    )
    customer, _ = ExternalAccount.objects.get_or_create(
        book=book,
        account_key="PILOT_CUSTOMER:AR",
        defaults={
            "party_key": "SYNTHETIC_CUSTOMER_1",
            "purpose": ExternalAccountPurpose.CUSTOMER_RECEIVABLE,
            "name": "Synthetic Customer",
        },
    )
    if not customer.classification_versions.exists():
        append_external_account_classification(
            external_account=customer,
            version_key="PILOT_AR_V1",
            effective_from=date(2026, 4, 1),
            reporting_ledger=receivable,
            reporting_class=ReportingClass.ASSET,
            normal_side=LedgerSide.DEBIT,
        )

    cash_sale = _draft(
        book=book, key="PILOT_CASH_SALE", number="PILOT-2026-0001",
        source_type="CASH_SALE", source_id="SYNTHETIC-CS-1",
    )
    if not cash_sale.transactions.exists():
        add_ledger_transaction(
            voucher=cash_sale, sequence=1, debit_ledger=cash, credit_ledger=revenue,
            amount=Decimal("1000"), currency="INR", base_amount=Decimal("1000"),
            base_currency="INR", exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
    cash_sale_batch = _authorize_and_post(cash_sale, actor_id)

    credit_sale = _draft(
        book=book, key="PILOT_CREDIT_SALE", number="PILOT-2026-0002",
        source_type="CREDIT_SALE", source_id="SYNTHETIC-INV-1",
    )
    if not credit_sale.transactions.exists():
        add_account_transaction(
            voucher=credit_sale, sequence=1, ledger=revenue,
            external_account=customer, ledger_side=LedgerSide.CREDIT,
            amount=Decimal("1000"), currency="INR", base_amount=Decimal("1000"),
            base_currency="INR", exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
    _authorize_and_post(credit_sale, actor_id)
    invoice_tx = credit_sale.transactions.get(sequence=1).account_detail
    open_item = OpenItem.objects.filter(origin_transaction=invoice_tx).first()
    if open_item is None:
        open_item = create_open_item(
            origin_transaction=invoice_tx,
            open_item_key="SYNTHETIC-INV-1",
            created_by_id=actor_id,
            due_date=date(2026, 8, 31),
        )

    receipt = _draft(
        book=book, key="PILOT_RECEIPT", number="PILOT-2026-0003",
        source_type="CUSTOMER_RECEIPT", source_id="SYNTHETIC-RCPT-1",
    )
    if not receipt.transactions.exists():
        add_account_transaction(
            voucher=receipt, sequence=1, ledger=cash, external_account=customer,
            ledger_side=LedgerSide.DEBIT, amount=Decimal("600"), currency="INR",
            base_amount=Decimal("600"), base_currency="INR",
            exchange_rate=Decimal("1"), rate_source="BOOK_BASE_CURRENCY",
        )
    _authorize_and_post(receipt, actor_id)
    receipt_tx = receipt.transactions.get(sequence=1).account_detail
    if not receipt_tx.open_item_allocations.exists():
        allocate_open_item(
            settlement_transaction=receipt_tx, open_item=open_item, sequence=1,
            amount=Decimal("400"), base_amount=Decimal("400"), created_by_id=actor_id,
        )

    replacement = _draft(
        book=book, key="PILOT_CASH_SALE_CORRECTED", number="PILOT-2026-0005",
        source_type="CASH_SALE_CORRECTION", source_id="SYNTHETIC-CS-1",
        source_version="2", group="PILOT-CORRECTION-1",
    )
    if not replacement.transactions.exists():
        add_ledger_transaction(
            voucher=replacement, sequence=1, debit_ledger=cash, credit_ledger=revenue,
            amount=Decimal("900"), currency="INR", base_amount=Decimal("900"),
            base_currency="INR", exchange_rate=Decimal("1"),
            rate_source="BOOK_BASE_CURRENCY",
        )
    if replacement.state == PersistedVoucherState.DRAFT:
        authorize_voucher(voucher=replacement, actor_id=actor_id, authorized_at=PILOT_TIME)
        replacement.refresh_from_db()
    if replacement.state != PersistedVoucherState.POSTED:
        correct_posted_batch(
            original=cash_sale_batch,
            replacement_voucher=replacement,
            reversal_voucher_key="PILOT_CASH_SALE_REVERSAL",
            reversal_voucher_number="PILOT-2026-0004",
            reversal_idempotency_key="pilot:PILOT_CASH_SALE_REVERSAL",
            correction_date=PILOT_DATE,
            actor_id=actor_id,
            occurred_at=PILOT_TIME,
            reason="Synthetic correction from 1000 to 900",
            correction_group_key="PILOT-CORRECTION-1",
        )

    trial = posted_trial_balance(book=book)
    statements = posted_financial_statements(book=book)
    reconciliations = posted_classification_reconciliation(book=book)
    outstanding = open_item_outstanding(open_item)
    unapplied = posted_unapplied_settlements(book=book)
    if trial.signed_total != 0 or statements.balance_sheet_signed_total != 0:
        raise ValidationError("Synthetic pilot reports did not balance.")
    if any(row.difference != 0 for row in reconciliations):
        raise ValidationError("Synthetic pilot classification did not reconcile.")
    return {
        "schema": connection.schema_name,
        "book": book.book_key,
        "voucher_count": book.vouchers.filter(state=PersistedVoucherState.POSTED).count(),
        "journal_line_count": len(posted_journal_lines(book=book)),
        "internal_balances": {
            row.key: str(row.signed_base_amount)
            for row in posted_internal_ledger_balances(book=book)
        },
        "external_balances": {
            row.key: str(row.signed_base_amount)
            for row in posted_external_account_balances(book=book)
        },
        "trial_balance_total": str(trial.signed_total),
        "current_period_result": str(statements.current_period_result),
        "balance_sheet_total": str(statements.balance_sheet_signed_total),
        "classification_difference": str(
            sum((row.difference for row in reconciliations), Decimal("0"))
        ),
        "open_item_outstanding": str(outstanding.amount),
        "unapplied_settlements": [
            {
                "voucher_number": row.voucher_number,
                "external_account": row.external_account_key,
                "received": str(row.amount),
                "allocated": str(row.allocated_amount),
                "unapplied": str(row.unapplied_amount),
                "currency": row.currency,
            }
            for row in unapplied
        ],
    }
