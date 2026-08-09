from datetime import date
from decimal import Decimal
from unittest import TestCase

from apps.tenant_apps.accounting.domain import (
    AccountClassificationSnapshot,
    AccountPurpose,
    AccountTransaction,
    DomainValidationError,
    LedgerSide,
    LedgerTransaction,
    MonetaryAmount,
    ReportingClass,
    TransactionBatch,
)


def inr(value: str) -> MonetaryAmount:
    return MonetaryAmount(
        amount=Decimal(value),
        currency="INR",
        base_amount=Decimal(value),
        base_currency="INR",
        exchange_rate=Decimal("1"),
        rate_source="BOOK_BASE_CURRENCY",
    )


def borrower_classification(version: str = "BORROWER-V1") -> AccountClassificationSnapshot:
    return AccountClassificationSnapshot(
        version_key=version,
        purpose=AccountPurpose.BORROWER_LOAN_RECEIVABLE,
        reporting_class=ReportingClass.ASSET,
        reporting_ledger_key="LOANS_RECEIVABLE",
        normal_side=LedgerSide.DEBIT,
    )


class MonetaryAmountTests(TestCase):
    def test_requires_positive_finite_amounts(self):
        with self.assertRaises(DomainValidationError):
            inr("0")
        with self.assertRaises(DomainValidationError):
            inr("NaN")

    def test_normalizes_currency_and_requires_same_currency_identity(self):
        amount = MonetaryAmount(
            amount="10.00",
            currency="inr",
            base_amount="10.00",
            base_currency="INR",
            exchange_rate="1",
            rate_source="base",
        )
        self.assertEqual(amount.currency, "INR")
        with self.assertRaises(DomainValidationError):
            MonetaryAmount(
                amount="10",
                currency="INR",
                base_amount="11",
                base_currency="INR",
                exchange_rate="1",
                rate_source="base",
            )


class AtomicTransactionTests(TestCase):
    def test_ledger_transaction_is_an_atomic_balanced_pair(self):
        transaction = LedgerTransaction(
            transaction_key="SALE-1",
            debit_ledger_key="CASH",
            credit_ledger_key="SALES_REVENUE",
            money=inr("100"),
        )
        self.assertEqual(transaction.debit_ledger_key, "CASH")
        self.assertEqual(transaction.credit_ledger_key, "SALES_REVENUE")

    def test_ledger_pair_requires_distinct_sides(self):
        with self.assertRaises(DomainValidationError):
            LedgerTransaction(
                transaction_key="BAD-1",
                debit_ledger_key="CASH",
                credit_ledger_key="CASH",
                money=inr("100"),
            )

    def test_account_transaction_has_one_internal_and_reciprocal_external_side(self):
        transaction = AccountTransaction(
            transaction_key="DISBURSAL-1",
            ledger_key="BANK",
            external_account_key="BORROWER:42:LOAN_RECEIVABLE",
            ledger_side=LedgerSide.CREDIT,
            classification=borrower_classification(),
            money=inr("100000"),
        )
        self.assertEqual(transaction.external_account_side, LedgerSide.DEBIT)
        self.assertEqual(
            transaction.classification.reporting_ledger_key, "LOANS_RECEIVABLE"
        )

    def test_account_transaction_requires_frozen_classification(self):
        with self.assertRaises(DomainValidationError):
            AccountTransaction(
                transaction_key="BAD-ACCOUNT-1",
                ledger_key="BANK",
                external_account_key="BORROWER:42",
                ledger_side=LedgerSide.CREDIT,
                classification=None,  # type: ignore[arg-type]
                money=inr("100"),
            )


class TransactionBatchTests(TestCase):
    def repayment_batch(self) -> TransactionBatch:
        return TransactionBatch(
            batch_key="REPAYMENT-1",
            book_key="BOOK-INR",
            idempotency_key="loan-42:repayment:1",
            effective_date=date(2026, 8, 7),
            transactions=(
                AccountTransaction(
                    transaction_key="REPAYMENT-1-PRINCIPAL",
                    ledger_key="CASH",
                    external_account_key="BORROWER:42:LOAN_RECEIVABLE",
                    ledger_side=LedgerSide.DEBIT,
                    classification=borrower_classification(),
                    money=inr("10000"),
                    narration="Principal receipt",
                ),
                LedgerTransaction(
                    transaction_key="REPAYMENT-1-INTEREST",
                    debit_ledger_key="CASH",
                    credit_ledger_key="INTEREST_INCOME",
                    money=inr("4000"),
                    narration="Interest receipt",
                ),
                LedgerTransaction(
                    transaction_key="REPAYMENT-1-FEE",
                    debit_ledger_key="CASH",
                    credit_ledger_key="FEE_INCOME",
                    money=inr("1000"),
                    narration="Fee receipt",
                ),
            ),
        )

    def test_compound_event_is_an_ordered_batch_of_explicit_pairs(self):
        batch = self.repayment_batch()
        self.assertEqual(len(batch.transactions), 3)
        self.assertEqual(
            [item.transaction_key for item in batch.transactions],
            [
                "REPAYMENT-1-PRINCIPAL",
                "REPAYMENT-1-INTEREST",
                "REPAYMENT-1-FEE",
            ],
        )

    def test_batch_must_be_non_empty_and_keys_unique(self):
        with self.assertRaises(DomainValidationError):
            TransactionBatch(
                batch_key="EMPTY",
                book_key="BOOK-INR",
                idempotency_key="empty",
                effective_date=date(2026, 8, 7),
                transactions=(),
            )
        transaction = LedgerTransaction(
            transaction_key="DUPLICATE",
            debit_ledger_key="CASH",
            credit_ledger_key="SALES_REVENUE",
            money=inr("1"),
        )
        with self.assertRaises(DomainValidationError):
            TransactionBatch(
                batch_key="DUPLICATE-BATCH",
                book_key="BOOK-INR",
                idempotency_key="duplicate",
                effective_date=date(2026, 8, 7),
                transactions=(transaction, transaction),
            )

    def test_reversal_flips_every_pair_in_reverse_order(self):
        original = self.repayment_batch()
        reversal = original.reversed(
            batch_key="REPAYMENT-1-REV",
            idempotency_key="loan-42:repayment:1:reversal",
            effective_date=date(2026, 8, 8),
        )
        self.assertEqual(reversal.reversal_of_batch_key, original.batch_key)
        self.assertEqual(
            [item.transaction_key for item in reversal.transactions],
            [
                "REPAYMENT-1-FEE:REV",
                "REPAYMENT-1-INTEREST:REV",
                "REPAYMENT-1-PRINCIPAL:REV",
            ],
        )
        fee = reversal.transactions[0]
        self.assertIsInstance(fee, LedgerTransaction)
        self.assertEqual(fee.debit_ledger_key, "FEE_INCOME")
        self.assertEqual(fee.credit_ledger_key, "CASH")
        principal = reversal.transactions[2]
        self.assertIsInstance(principal, AccountTransaction)
        self.assertEqual(principal.ledger_side, LedgerSide.CREDIT)
        self.assertEqual(principal.external_account_side, LedgerSide.DEBIT)
        self.assertIs(principal.classification, original.transactions[0].classification)
