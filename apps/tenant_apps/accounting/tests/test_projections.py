from datetime import date
from decimal import Decimal
from unittest import TestCase

from apps.tenant_apps.accounting.domain import (
    AccountClassificationSnapshot,
    AccountPurpose,
    AccountTransaction,
    DomainValidationError,
    LedgerDefinition,
    LedgerSide,
    LedgerTransaction,
    MonetaryAmount,
    PostingAccountKind,
    ReportingClass,
    TransactionBatch,
    project_external_account_balances,
    project_financial_statements,
    project_internal_ledger_balances,
    project_journal_lines,
    project_trial_balance,
    reconcile_external_classifications,
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


CUSTOMER_AR_V1 = AccountClassificationSnapshot(
    version_key="CUSTOMER-AR-V1",
    purpose=AccountPurpose.CUSTOMER_RECEIVABLE,
    reporting_class=ReportingClass.ASSET,
    reporting_ledger_key="ACCOUNTS_RECEIVABLE",
    normal_side=LedgerSide.DEBIT,
)


def ledger(key: str, reporting_class: ReportingClass, normal_side: LedgerSide):
    return LedgerDefinition(
        ledger_key=key,
        reporting_class=reporting_class,
        normal_side=normal_side,
    )


LEDGERS = {
    "CASH": ledger("CASH", ReportingClass.ASSET, LedgerSide.DEBIT),
    "SALES_REVENUE": ledger(
        "SALES_REVENUE", ReportingClass.REVENUE, LedgerSide.CREDIT
    ),
    "COST_OF_SALES": ledger(
        "COST_OF_SALES", ReportingClass.EXPENSE, LedgerSide.DEBIT
    ),
    "INVENTORY": ledger("INVENTORY", ReportingClass.ASSET, LedgerSide.DEBIT),
    "ACCOUNTS_RECEIVABLE": ledger(
        "ACCOUNTS_RECEIVABLE", ReportingClass.ASSET, LedgerSide.DEBIT
    ),
    "SUSPENSE": ledger("SUSPENSE", ReportingClass.ASSET, LedgerSide.DEBIT),
}


def batch(key: str, *transactions) -> TransactionBatch:
    return TransactionBatch(
        batch_key=key,
        book_key="BOOK-INR",
        idempotency_key=f"projection:{key}",
        effective_date=date(2026, 8, 7),
        transactions=tuple(transactions),
    )


def credit_sale() -> TransactionBatch:
    return batch(
        "CREDIT-SALE-1",
        AccountTransaction(
            transaction_key="CREDIT-SALE-1-REVENUE",
            ledger_key="SALES_REVENUE",
            external_account_key="CUSTOMER:ABC:RECEIVABLE",
            ledger_side=LedgerSide.CREDIT,
            classification=CUSTOMER_AR_V1,
            money=inr("1000"),
        ),
        LedgerTransaction(
            transaction_key="CREDIT-SALE-1-COST",
            debit_ledger_key="COST_OF_SALES",
            credit_ledger_key="INVENTORY",
            money=inr("700"),
        ),
    )


def customer_receipt() -> TransactionBatch:
    return batch(
        "CUSTOMER-RECEIPT-1",
        AccountTransaction(
            transaction_key="CUSTOMER-RECEIPT-1-T1",
            ledger_key="CASH",
            external_account_key="CUSTOMER:ABC:RECEIVABLE",
            ledger_side=LedgerSide.DEBIT,
            classification=CUSTOMER_AR_V1,
            money=inr("400"),
        ),
    )


def by_key(rows):
    return {row.key: row for row in rows}


class JournalProjectionTests(TestCase):
    def test_each_atomic_transaction_projects_exactly_two_conventional_lines(self):
        lines = project_journal_lines((credit_sale(),))
        self.assertEqual(len(lines), 4)
        revenue_lines = [
            line for line in lines if line.transaction_key == "CREDIT-SALE-1-REVENUE"
        ]
        self.assertEqual(len(revenue_lines), 2)
        self.assertEqual(
            {line.account_kind for line in revenue_lines},
            {
                PostingAccountKind.INTERNAL_LEDGER,
                PostingAccountKind.EXTERNAL_ACCOUNT,
            },
        )
        self.assertEqual(
            sum((line.signed_base_amount for line in revenue_lines), Decimal("0")),
            Decimal("0"),
        )
        external = next(
            line
            for line in revenue_lines
            if line.account_kind is PostingAccountKind.EXTERNAL_ACCOUNT
        )
        self.assertEqual(external.side, LedgerSide.DEBIT)
        self.assertEqual(external.classification_version_key, "CUSTOMER-AR-V1")

    def test_internal_and_external_statements_do_not_duplicate_each_other(self):
        batches = (credit_sale(), customer_receipt())
        internal = by_key(project_internal_ledger_balances(batches))
        external = by_key(project_external_account_balances(batches))
        self.assertEqual(internal["SALES_REVENUE"].signed_base_amount, Decimal("-1000"))
        self.assertEqual(internal["CASH"].signed_base_amount, Decimal("400"))
        self.assertEqual(
            external["CUSTOMER:ABC:RECEIVABLE"].signed_base_amount,
            Decimal("600"),
        )
        self.assertNotIn("ACCOUNTS_RECEIVABLE", internal)


class TrialBalanceAndStatementTests(TestCase):
    def test_trial_balance_counts_internal_and_classified_external_sides_once(self):
        trial = project_trial_balance(
            (credit_sale(), customer_receipt()), ledger_definitions=LEDGERS
        )
        rows = by_key(trial.rows)
        self.assertEqual(trial.signed_total, Decimal("0"))
        self.assertEqual(rows["ACCOUNTS_RECEIVABLE"].signed_base_amount, Decimal("600"))
        self.assertEqual(rows["CASH"].signed_base_amount, Decimal("400"))
        self.assertEqual(rows["INVENTORY"].signed_base_amount, Decimal("-700"))
        self.assertEqual(rows["COST_OF_SALES"].signed_base_amount, Decimal("700"))
        self.assertEqual(rows["SALES_REVENUE"].signed_base_amount, Decimal("-1000"))

    def test_balance_sheet_closes_current_profit_into_current_period_result(self):
        statements = project_financial_statements(
            (credit_sale(), customer_receipt()), ledger_definitions=LEDGERS
        )
        profit_rows = by_key(statements.profit_and_loss_rows)
        balance_rows = by_key(statements.balance_sheet_rows)
        self.assertEqual(profit_rows["SALES_REVENUE"].natural_base_amount, Decimal("1000"))
        self.assertEqual(profit_rows["COST_OF_SALES"].natural_base_amount, Decimal("700"))
        self.assertEqual(statements.current_period_result, Decimal("300"))
        self.assertEqual(
            balance_rows["CURRENT_PERIOD_RESULT"].natural_base_amount,
            Decimal("300"),
        )
        self.assertEqual(statements.balance_sheet_signed_total, Decimal("0"))

    def test_missing_internal_ledger_definition_fails_closed(self):
        incomplete = {key: value for key, value in LEDGERS.items() if key != "CASH"}
        with self.assertRaises(DomainValidationError):
            project_trial_balance(
                (credit_sale(), customer_receipt()), ledger_definitions=incomplete
            )


class ClassificationReconciliationTests(TestCase):
    def test_external_detail_plus_direct_internal_effect_equals_trial_balance_row(self):
        direct_adjustment = batch(
            "AR-DIRECT-ADJUSTMENT",
            LedgerTransaction(
                transaction_key="AR-DIRECT-ADJUSTMENT-T1",
                debit_ledger_key="ACCOUNTS_RECEIVABLE",
                credit_ledger_key="SUSPENSE",
                money=inr("25"),
            ),
        )
        reconciliations = reconcile_external_classifications(
            (credit_sale(), customer_receipt(), direct_adjustment),
            ledger_definitions=LEDGERS,
        )
        self.assertEqual(len(reconciliations), 1)
        reconciliation = reconciliations[0]
        self.assertEqual(reconciliation.external_account_total, Decimal("600"))
        self.assertEqual(reconciliation.direct_internal_ledger_total, Decimal("25"))
        self.assertEqual(reconciliation.trial_balance_total, Decimal("625"))
        self.assertEqual(reconciliation.difference, Decimal("0"))

    def test_posted_classification_is_stable_after_later_reclassification(self):
        later_classification = AccountClassificationSnapshot(
            version_key="CUSTOMER-OTHER-RECEIVABLE-V2",
            purpose=AccountPurpose.CUSTOMER_RECEIVABLE,
            reporting_class=ReportingClass.ASSET,
            reporting_ledger_key="OTHER_RECEIVABLES",
            normal_side=LedgerSide.DEBIT,
        )
        later_sale = batch(
            "CREDIT-SALE-2",
            AccountTransaction(
                transaction_key="CREDIT-SALE-2-REVENUE",
                ledger_key="SALES_REVENUE",
                external_account_key="CUSTOMER:ABC:RECEIVABLE",
                ledger_side=LedgerSide.CREDIT,
                classification=later_classification,
                money=inr("200"),
            ),
        )
        trial = project_trial_balance(
            (credit_sale(), later_sale), ledger_definitions=LEDGERS
        )
        rows = by_key(trial.rows)
        self.assertEqual(rows["ACCOUNTS_RECEIVABLE"].signed_base_amount, Decimal("1000"))
        self.assertEqual(rows["OTHER_RECEIVABLES"].signed_base_amount, Decimal("200"))
        self.assertEqual(rows["SALES_REVENUE"].signed_base_amount, Decimal("-1200"))

    def test_reversal_removes_statement_and_reconciliation_effects(self):
        original = credit_sale()
        reversal = original.reversed(
            batch_key="CREDIT-SALE-1-REV",
            idempotency_key="projection:CREDIT-SALE-1:REV",
            effective_date=date(2026, 8, 8),
        )
        trial = project_trial_balance(
            (original, reversal), ledger_definitions=LEDGERS
        )
        reconciliations = reconcile_external_classifications(
            (original, reversal), ledger_definitions=LEDGERS
        )
        self.assertEqual(trial.rows, ())
        self.assertEqual(reconciliations[0].external_account_total, Decimal("0"))
        self.assertEqual(reconciliations[0].difference, Decimal("0"))
