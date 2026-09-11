from decimal import Decimal
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.loans.selectors.workspace_dashboard import (
    get_workspace_pawn_loan_dashboard_summary,
)


class WorkspacePawnLoanDashboardSelectorTests(SimpleTestCase):
    @patch("apps.tenant_apps.loans.selectors.workspace_dashboard.current_tenant_workspace_id", return_value=7)
    @patch("apps.tenant_apps.loans.selectors.workspace_dashboard.get_pawn_loan_balance", autospec=True)
    @patch("apps.tenant_apps.loans.selectors.workspace_dashboard.PawnLoan.objects.filter")
    def test_uses_active_canonical_balances_and_closed_progress(self, filter_loans, get_balance, context):
        active = SimpleNamespace(pk=1, state=PawnLoanState.ACTIVE.value)
        closed = SimpleNamespace(pk=2, state=PawnLoanState.CLOSED.value)
        draft = SimpleNamespace(pk=3, state=PawnLoanState.DRAFT.value)
        filter_loans.return_value.order_by.return_value = [active, closed, draft]
        get_balance.return_value = SimpleNamespace(
            total_due=Decimal("150.00"),
            interest_outstanding=Decimal("20.00"),
        )
        workspace = SimpleNamespace(pk=7)

        with patch("django.utils.timezone.localdate", return_value=date(2026, 9, 8)):
            result = get_workspace_pawn_loan_dashboard_summary(workspace=workspace)

        filter_loans.assert_called_once_with(workspace=workspace)
        get_balance.assert_called_once_with(active.pk, as_of_date=date(2026, 9, 8))
        self.assertEqual(result["loan_count"], 1)
        self.assertEqual(result["total_loan_amount"], Decimal("150.00"))
        self.assertEqual(result["total_interest"], Decimal("20.00"))
        self.assertEqual(result["loan_progress"], 50.0)
        self.assertEqual(result["pawn_loan_counts"]["draft"], 1)
        self.assertEqual(result["sunken"], {"loan_count": 0})

    def test_incomplete_balances_never_expose_partial_money_as_total(self):
        from apps.tenant_apps.loans.selectors.balances import PawnLoanBalanceSelectorError
        prefix = "apps.tenant_apps.loans.selectors.workspace_dashboard."
        for failures in (1, 2):
            with self.subTest(failures=failures), patch(prefix + "current_tenant_workspace_id", return_value=7), patch(prefix + "PawnLoan.objects.filter") as query, patch(prefix + "get_pawn_loan_balance") as balance:
                query.return_value.order_by.return_value = [SimpleNamespace(pk=n, state="ACTIVE") for n in (1, 2)]
                balance.side_effect = [SimpleNamespace(total_due=Decimal("100"), interest_outstanding=Decimal("10"))] * (2-failures) + [PawnLoanBalanceSelectorError("invalid evidence")] * failures
                result = get_workspace_pawn_loan_dashboard_summary(workspace=SimpleNamespace(pk=7))
                self.assertFalse(result["totals_complete"])
                self.assertEqual(result["unavailable_balance_count"], failures)
                self.assertEqual(result["loan_count"], 2)
                self.assertIsNone(result["total_loan_amount"])
                self.assertIsNone(result["total_interest"])

    def test_empty_workspace_has_complete_zero_totals(self):
        prefix = "apps.tenant_apps.loans.selectors.workspace_dashboard."
        with patch(prefix + "current_tenant_workspace_id", return_value=7), patch(prefix + "PawnLoan.objects.filter") as query:
            query.return_value.order_by.return_value = []
            result = get_workspace_pawn_loan_dashboard_summary(workspace=SimpleNamespace(pk=7))
        self.assertTrue(result["totals_complete"])
        self.assertEqual(result["total_loan_amount"], Decimal("0"))

    def test_wrong_context_fails_before_query(self):
        prefix = "apps.tenant_apps.loans.selectors.workspace_dashboard."
        for context in (None, 8):
            with patch(prefix + "current_tenant_workspace_id", return_value=context), patch(prefix + "PawnLoan.objects.filter") as query:
                with self.assertRaises(ValueError):
                    get_workspace_pawn_loan_dashboard_summary(workspace=SimpleNamespace(pk=7))
                query.assert_not_called()
