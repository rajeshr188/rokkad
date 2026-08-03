from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.dea.facade import LoanPostingPrerequisites
from apps.tenant_apps.loans.services.accounting_readiness import (
    PawnLoanAccountingNotReadyError,
    assess_pawn_loan_accounting_readiness,
    require_pawn_loan_accounting_readiness,
)


class PawnLoanAccountingReadinessTests(SimpleTestCase):
    def setUp(self):
        self.loan = SimpleNamespace(pk=29, borrower=SimpleNamespace(pk=31))
        self.effective_date = date(2026, 8, 3)

    @patch("apps.tenant_apps.loans.services.accounting_readiness.reverse")
    @patch(
        "apps.tenant_apps.loans.services.accounting_readiness.dea_facade.get_loan_posting_prerequisites"
    )
    def test_returns_precise_actionable_blockers_for_missing_setup(self, prerequisites, reverse):
        reverse.side_effect = lambda route, args=(): f"/{route}/{'/'.join(map(str, args))}"
        prerequisites.return_value = LoanPostingPrerequisites(
            None, None, None, None, None, None, None, None
        )

        readiness = assess_pawn_loan_accounting_readiness(
            self.loan,
            effective_date=self.effective_date,
            requires_fee_income=True,
        )

        self.assertFalse(readiness.ready)
        self.assertEqual(
            [blocker.code for blocker in readiness.blockers],
            [
                "OPEN_ACCOUNTING_PERIOD_REQUIRED",
                "FUNDING_CASH_ACCOUNT_REQUIRED",
                "LOAN_PRINCIPAL_CONTROL_REQUIRED",
                "BORROWER_LOAN_CONTROL_REQUIRED",
                "BORROWER_RECEIVABLE_REQUIRED",
                "INTEREST_INCOME_ACCOUNT_REQUIRED",
                "FEE_INCOME_ACCOUNT_REQUIRED",
            ],
        )
        self.assertTrue(all(blocker.action_url for blocker in readiness.blockers))
        borrower_blocker = readiness.blockers[4]
        self.assertEqual(borrower_blocker.action_label, "Set up borrower accounting")
        self.assertIn("29", borrower_blocker.action_url)
        prerequisites.assert_called_once_with(
            party=self.loan.borrower,
            effective_date=self.effective_date,
            requires_fee_income=True,
        )

    @patch(
        "apps.tenant_apps.loans.services.accounting_readiness.dea_facade.get_loan_posting_prerequisites"
    )
    def test_ready_when_required_prerequisites_exist(self, prerequisites):
        prerequisites.return_value = LoanPostingPrerequisites(
            object(), object(), object(), object(), True, object(), object(), object()
        )

        readiness = require_pawn_loan_accounting_readiness(
            self.loan,
            effective_date=self.effective_date,
        )

        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.blockers, ())

    @patch(
        "apps.tenant_apps.loans.services.accounting_readiness.dea_facade.get_loan_posting_prerequisites"
    )
    def test_fee_mapping_is_not_required_until_a_fee_applies(self, prerequisites):
        prerequisites.return_value = LoanPostingPrerequisites(
            object(), object(), object(), object(), None, object(), object(), object()
        )

        readiness = assess_pawn_loan_accounting_readiness(
            self.loan,
            effective_date=self.effective_date,
            requires_fee_income=False,
        )

        self.assertTrue(readiness.ready)

    @patch(
        "apps.tenant_apps.loans.services.accounting_readiness.dea_facade.get_loan_posting_prerequisites"
    )
    def test_accrual_repayment_requires_interest_receivable(self, prerequisites):
        prerequisites.return_value = LoanPostingPrerequisites(
            object(), object(), object(), object(), None, object(), object(), None
        )

        readiness = assess_pawn_loan_accounting_readiness(
            self.loan,
            effective_date=self.effective_date,
            requires_interest_receivable=True,
        )

        self.assertEqual(
            [blocker.code for blocker in readiness.blockers],
            ["INTEREST_RECEIVABLE_ACCOUNT_REQUIRED"],
        )

    @patch(
        "apps.tenant_apps.loans.services.accounting_readiness.dea_facade.get_loan_posting_prerequisites"
    )
    def test_require_fails_closed_with_the_full_readiness_result(self, prerequisites):
        prerequisites.return_value = LoanPostingPrerequisites(
            None, object(), object(), object(), True, object(), object(), object()
        )

        with self.assertRaises(PawnLoanAccountingNotReadyError) as raised:
            require_pawn_loan_accounting_readiness(
                self.loan,
                effective_date=self.effective_date,
            )

        self.assertEqual(
            raised.exception.readiness.blockers[0].code,
            "OPEN_ACCOUNTING_PERIOD_REQUIRED",
        )

    def test_selector_uses_only_the_public_dea_facade(self):
        selector_source = (
            Path(__file__).parents[1] / "services" / "accounting_readiness.py"
        ).read_text(encoding="utf-8")

        self.assertIn("from apps.tenant_apps.dea import facade as dea_facade", selector_source)
        self.assertNotIn("apps.tenant_apps.dea.models", selector_source)
        self.assertNotIn("apps.tenant_apps.dea.posting", selector_source)
        self.assertNotIn("apps.tenant_apps.dea.services", selector_source)
