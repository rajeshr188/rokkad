"""K1 scenario corpus for the proposed standalone accounting ontology.

The small fold helpers are test oracles, not production reporting code.  K2
will implement projections independently and compare them with these expected
effects.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from unittest import TestCase

from apps.tenant_apps.accounting.domain import (
    AccountClassificationSnapshot,
    AccountPurpose,
    AccountSettlement,
    AccountTransaction,
    DomainValidationError,
    LedgerSide,
    LedgerTransaction,
    MonetaryAmount,
    OpenItemAllocation,
    ReportingClass,
    TransactionBatch,
)


POSTING_DATE = date(2026, 8, 7)


def inr(value: str) -> MonetaryAmount:
    return MonetaryAmount(
        amount=Decimal(value),
        currency="INR",
        base_amount=Decimal(value),
        base_currency="INR",
        exchange_rate=Decimal("1"),
        rate_source="BOOK_BASE_CURRENCY",
    )


def classification(
    *,
    version: str,
    purpose: AccountPurpose,
    reporting_class: ReportingClass,
    reporting_ledger: str,
    normal_side: LedgerSide,
) -> AccountClassificationSnapshot:
    return AccountClassificationSnapshot(
        version_key=version,
        purpose=purpose,
        reporting_class=reporting_class,
        reporting_ledger_key=reporting_ledger,
        normal_side=normal_side,
    )


CUSTOMER_RECEIVABLE = classification(
    version="CUSTOMER-AR-V1",
    purpose=AccountPurpose.CUSTOMER_RECEIVABLE,
    reporting_class=ReportingClass.ASSET,
    reporting_ledger="ACCOUNTS_RECEIVABLE",
    normal_side=LedgerSide.DEBIT,
)
SUPPLIER_PAYABLE = classification(
    version="SUPPLIER-AP-V1",
    purpose=AccountPurpose.SUPPLIER_PAYABLE,
    reporting_class=ReportingClass.LIABILITY,
    reporting_ledger="ACCOUNTS_PAYABLE",
    normal_side=LedgerSide.CREDIT,
)
BORROWER_RECEIVABLE = classification(
    version="BORROWER-LOAN-V1",
    purpose=AccountPurpose.BORROWER_LOAN_RECEIVABLE,
    reporting_class=ReportingClass.ASSET,
    reporting_ledger="LOANS_RECEIVABLE",
    normal_side=LedgerSide.DEBIT,
)


def batch(key: str, *transactions) -> TransactionBatch:
    return TransactionBatch(
        batch_key=key,
        book_key="BOOK-INR",
        idempotency_key=f"scenario:{key}",
        effective_date=POSTING_DATE,
        transactions=tuple(transactions),
    )


def fold_effects(*batches: TransactionBatch):
    """Return debit-positive base effects for internal and external sides."""
    internal = defaultdict(Decimal)
    external = defaultdict(Decimal)
    classified = defaultdict(Decimal)
    for item_batch in batches:
        for transaction in item_batch.transactions:
            amount = transaction.money.base_amount
            if isinstance(transaction, LedgerTransaction):
                internal[transaction.debit_ledger_key] += amount
                internal[transaction.credit_ledger_key] -= amount
            else:
                ledger_sign = Decimal("1") if transaction.ledger_side is LedgerSide.DEBIT else Decimal("-1")
                external_sign = -ledger_sign
                internal[transaction.ledger_key] += ledger_sign * amount
                external[transaction.external_account_key] += external_sign * amount
                classified[transaction.classification.reporting_ledger_key] += external_sign * amount
    return dict(internal), dict(external), dict(classified)


def total_effect(*effects: dict[str, Decimal]) -> Decimal:
    return sum((sum(effect.values(), Decimal("0")) for effect in effects), Decimal("0"))


class AccountingScenarioCorpusTests(TestCase):
    def test_cash_sale_is_one_internal_atomic_pair(self):
        sale = batch(
            "CASH-SALE-1",
            LedgerTransaction(
                transaction_key="CASH-SALE-1-T1",
                debit_ledger_key="CASH",
                credit_ledger_key="SALES_REVENUE",
                money=inr("1000"),
            ),
        )
        internal, external, classified = fold_effects(sale)
        self.assertEqual(internal, {"CASH": Decimal("1000"), "SALES_REVENUE": Decimal("-1000")})
        self.assertEqual(external, {})
        self.assertEqual(classified, {})
        self.assertEqual(total_effect(internal, external), Decimal("0"))

    def test_credit_sale_uses_customer_as_the_reciprocal_side(self):
        sale = batch(
            "CREDIT-SALE-1",
            AccountTransaction(
                transaction_key="CREDIT-SALE-1-T1",
                ledger_key="SALES_REVENUE",
                external_account_key="CUSTOMER:ABC:RECEIVABLE",
                ledger_side=LedgerSide.CREDIT,
                classification=CUSTOMER_RECEIVABLE,
                money=inr("1000"),
            ),
        )
        internal, external, classified = fold_effects(sale)
        self.assertEqual(internal, {"SALES_REVENUE": Decimal("-1000")})
        self.assertEqual(external, {"CUSTOMER:ABC:RECEIVABLE": Decimal("1000")})
        self.assertEqual(classified, {"ACCOUNTS_RECEIVABLE": Decimal("1000")})
        self.assertEqual(total_effect(internal, external), Decimal("0"))

    def test_customer_receipt_can_be_partially_allocated_without_new_financial_effect(self):
        receipt_transaction = AccountTransaction(
            transaction_key="RECEIPT-1-T1",
            ledger_key="CASH",
            external_account_key="CUSTOMER:ABC:RECEIVABLE",
            ledger_side=LedgerSide.DEBIT,
            classification=CUSTOMER_RECEIVABLE,
            money=inr("600"),
        )
        receipt = batch("RECEIPT-1", receipt_transaction)
        settlement = AccountSettlement(
            settlement_key="RECEIPT-1-SETTLEMENT",
            account_transaction=receipt_transaction,
            allocations=(
                OpenItemAllocation(
                    open_item_key="INVOICE-1",
                    external_account_key="CUSTOMER:ABC:RECEIVABLE",
                    money=inr("400"),
                ),
            ),
        )
        internal, external, _ = fold_effects(receipt)
        self.assertEqual(internal, {"CASH": Decimal("600")})
        self.assertEqual(external, {"CUSTOMER:ABC:RECEIVABLE": Decimal("-600")})
        self.assertEqual(settlement.unallocated_amount, Decimal("200"))
        self.assertEqual(total_effect(internal, external), Decimal("0"))

    def test_supplier_purchase_and_payment_clear_the_external_balance(self):
        purchase = batch(
            "PURCHASE-1",
            AccountTransaction(
                transaction_key="PURCHASE-1-T1",
                ledger_key="PURCHASE_EXPENSE",
                external_account_key="SUPPLIER:XYZ:PAYABLE",
                ledger_side=LedgerSide.DEBIT,
                classification=SUPPLIER_PAYABLE,
                money=inr("750"),
            ),
        )
        payment = batch(
            "PAYMENT-1",
            AccountTransaction(
                transaction_key="PAYMENT-1-T1",
                ledger_key="BANK",
                external_account_key="SUPPLIER:XYZ:PAYABLE",
                ledger_side=LedgerSide.CREDIT,
                classification=SUPPLIER_PAYABLE,
                money=inr("750"),
            ),
        )
        internal, external, classified = fold_effects(purchase, payment)
        self.assertEqual(internal, {"PURCHASE_EXPENSE": Decimal("750"), "BANK": Decimal("-750")})
        self.assertEqual(external, {"SUPPLIER:XYZ:PAYABLE": Decimal("0")})
        self.assertEqual(classified, {"ACCOUNTS_PAYABLE": Decimal("0")})
        self.assertEqual(total_effect(internal, external), Decimal("0"))

    def test_loan_disbursal_uses_borrower_receivable_as_the_external_side(self):
        disbursal = batch(
            "LOAN-DISBURSAL-1",
            AccountTransaction(
                transaction_key="LOAN-DISBURSAL-1-T1",
                ledger_key="BANK",
                external_account_key="BORROWER:42:LOAN_RECEIVABLE",
                ledger_side=LedgerSide.CREDIT,
                classification=BORROWER_RECEIVABLE,
                money=inr("100000"),
            ),
        )
        internal, external, classified = fold_effects(disbursal)
        self.assertEqual(internal, {"BANK": Decimal("-100000")})
        self.assertEqual(external, {"BORROWER:42:LOAN_RECEIVABLE": Decimal("100000")})
        self.assertEqual(classified, {"LOANS_RECEIVABLE": Decimal("100000")})
        self.assertEqual(total_effect(internal, external), Decimal("0"))

    def test_loan_repayment_is_an_explicit_principal_interest_fee_batch(self):
        repayment = batch(
            "LOAN-REPAYMENT-1",
            AccountTransaction(
                transaction_key="LOAN-REPAYMENT-1-PRINCIPAL",
                ledger_key="CASH",
                external_account_key="BORROWER:42:LOAN_RECEIVABLE",
                ledger_side=LedgerSide.DEBIT,
                classification=BORROWER_RECEIVABLE,
                money=inr("10000"),
            ),
            LedgerTransaction(
                transaction_key="LOAN-REPAYMENT-1-INTEREST",
                debit_ledger_key="CASH",
                credit_ledger_key="INTEREST_INCOME",
                money=inr("4000"),
            ),
            LedgerTransaction(
                transaction_key="LOAN-REPAYMENT-1-FEE",
                debit_ledger_key="CASH",
                credit_ledger_key="FEE_INCOME",
                money=inr("1000"),
            ),
        )
        internal, external, classified = fold_effects(repayment)
        self.assertEqual(
            internal,
            {
                "CASH": Decimal("15000"),
                "INTEREST_INCOME": Decimal("-4000"),
                "FEE_INCOME": Decimal("-1000"),
            },
        )
        self.assertEqual(external, {"BORROWER:42:LOAN_RECEIVABLE": Decimal("-10000")})
        self.assertEqual(classified, {"LOANS_RECEIVABLE": Decimal("-10000")})
        self.assertEqual(total_effect(internal, external), Decimal("0"))

    def test_many_sided_manual_journal_requires_explicit_pairs(self):
        journal = batch(
            "MANUAL-JOURNAL-1",
            LedgerTransaction(
                transaction_key="MANUAL-JOURNAL-1-T1",
                debit_ledger_key="CASH",
                credit_ledger_key="LOAN_PRINCIPAL_CONTROL",
                money=inr("90"),
            ),
            LedgerTransaction(
                transaction_key="MANUAL-JOURNAL-1-T2",
                debit_ledger_key="BANK",
                credit_ledger_key="LOAN_PRINCIPAL_CONTROL",
                money=inr("10"),
            ),
            LedgerTransaction(
                transaction_key="MANUAL-JOURNAL-1-T3",
                debit_ledger_key="BANK",
                credit_ledger_key="INTEREST_INCOME",
                money=inr("40"),
            ),
            LedgerTransaction(
                transaction_key="MANUAL-JOURNAL-1-T4",
                debit_ledger_key="BANK",
                credit_ledger_key="FEE_INCOME",
                money=inr("10"),
            ),
        )
        internal, external, _ = fold_effects(journal)
        self.assertEqual(len(journal.transactions), 4)
        self.assertEqual(internal["CASH"], Decimal("90"))
        self.assertEqual(internal["BANK"], Decimal("60"))
        self.assertEqual(internal["LOAN_PRINCIPAL_CONTROL"], Decimal("-100"))
        self.assertEqual(internal["INTEREST_INCOME"], Decimal("-40"))
        self.assertEqual(internal["FEE_INCOME"], Decimal("-10"))
        self.assertEqual(total_effect(internal, external), Decimal("0"))

    def test_whole_batch_reversal_neutralizes_internal_external_and_classified_effects(self):
        original = batch(
            "CREDIT-SALE-REVERSIBLE",
            AccountTransaction(
                transaction_key="CREDIT-SALE-REVERSIBLE-T1",
                ledger_key="SALES_REVENUE",
                external_account_key="CUSTOMER:ABC:RECEIVABLE",
                ledger_side=LedgerSide.CREDIT,
                classification=CUSTOMER_RECEIVABLE,
                money=inr("1000"),
            ),
            LedgerTransaction(
                transaction_key="CREDIT-SALE-REVERSIBLE-T2",
                debit_ledger_key="COST_OF_SALES",
                credit_ledger_key="INVENTORY",
                money=inr("700"),
            ),
        )
        reversal = original.reversed(
            batch_key="CREDIT-SALE-REVERSIBLE-REV",
            idempotency_key="scenario:CREDIT-SALE-REVERSIBLE:REV",
            effective_date=date(2026, 8, 8),
        )
        internal, external, classified = fold_effects(original, reversal)
        self.assertTrue(all(amount == 0 for amount in internal.values()))
        self.assertTrue(all(amount == 0 for amount in external.values()))
        self.assertTrue(all(amount == 0 for amount in classified.values()))
        self.assertEqual(total_effect(internal, external), Decimal("0"))


class SettlementInvariantTests(TestCase):
    def receipt_transaction(self) -> AccountTransaction:
        return AccountTransaction(
            transaction_key="RECEIPT-VALIDATION-T1",
            ledger_key="CASH",
            external_account_key="CUSTOMER:ABC:RECEIVABLE",
            ledger_side=LedgerSide.DEBIT,
            classification=CUSTOMER_RECEIVABLE,
            money=inr("600"),
        )

    def test_allocation_cannot_exceed_the_financial_transaction(self):
        with self.assertRaises(DomainValidationError):
            AccountSettlement(
                settlement_key="OVER-ALLOCATED",
                account_transaction=self.receipt_transaction(),
                allocations=(
                    OpenItemAllocation(
                        open_item_key="INVOICE-1",
                        external_account_key="CUSTOMER:ABC:RECEIVABLE",
                        money=inr("601"),
                    ),
                ),
            )

    def test_allocation_cannot_cross_external_accounts(self):
        with self.assertRaises(DomainValidationError):
            AccountSettlement(
                settlement_key="CROSS-ACCOUNT",
                account_transaction=self.receipt_transaction(),
                allocations=(
                    OpenItemAllocation(
                        open_item_key="INVOICE-OTHER",
                        external_account_key="CUSTOMER:OTHER:RECEIVABLE",
                        money=inr("100"),
                    ),
                ),
            )
