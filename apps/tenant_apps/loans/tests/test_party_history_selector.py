from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.loans.selectors.party_history import (
    get_party_pawn_loan_history_summary,
)


class PartyPawnLoanHistorySelectorTests(SimpleTestCase):
    @patch("apps.tenant_apps.loans.selectors.party_history.reverse", return_value="/loan/")
    @patch("apps.tenant_apps.loans.selectors.party_history.get_pawn_loan_balance", autospec=True)
    @patch("apps.tenant_apps.loans.selectors.party_history.PawnLoan.objects.filter")
    def test_total_includes_every_active_loan_independently_of_display_limit(
        self, filter_loans, get_balance, reverse
    ):
        loans = [SimpleNamespace(
            pk=pk, workspace=SimpleNamespace(slug="alpha"),
            loan_number=f"PL-{pk:03}", loan_date="2026-09-28",
            state=PawnLoanState.ACTIVE.value, collateral_items_count=1,
            get_state_display=lambda: "Active",
        ) for pk in range(1, 26)]
        filter_loans.return_value.select_related.return_value.annotate.return_value.order_by.return_value = loans
        get_balance.side_effect = lambda pk, **kwargs: SimpleNamespace(
            total_due=Decimal(pk) + Decimal("0.25"),
            principal_outstanding=Decimal(pk), interest_outstanding=Decimal("0.25"),
        )
        for limit in (20, 1, 0, 30):
            with self.subTest(limit=limit):
                result = get_party_pawn_loan_history_summary(SimpleNamespace(pk=3), limit=limit)
                self.assertEqual(result["counts"]["active_loans"], 25)
                self.assertEqual(result["counts"]["active_outstanding"], Decimal("331.25"))
                self.assertEqual([row.pk for row in result["active_loans"]], list(range(1, 26))[:limit])

    @patch("apps.tenant_apps.loans.selectors.party_history.reverse", return_value="/loan/")
    @patch("apps.tenant_apps.loans.selectors.party_history.get_pawn_loan_balance", autospec=True)
    @patch("apps.tenant_apps.loans.selectors.party_history.PawnLoan.objects.filter")
    def test_draft_approved_and_closed_do_not_add_principal_to_total(
        self, filter_loans, get_balance, reverse
    ):
        states = ("DRAFT", "APPROVED", "ACTIVE", "CLOSED")
        loans = [SimpleNamespace(
            pk=pk, workspace=SimpleNamespace(slug="alpha"), loan_number=f"PL-{pk}",
            loan_date="2026-09-28", state=state, collateral_items_count=1,
            get_state_display=lambda: "Status",
        ) for pk, state in enumerate(states, 1)]
        filter_loans.return_value.select_related.return_value.annotate.return_value.order_by.return_value = loans
        get_balance.return_value = SimpleNamespace(total_due=Decimal("42.50"))
        result = get_party_pawn_loan_history_summary(SimpleNamespace(pk=3), limit=1)
        self.assertEqual(result["counts"]["active_outstanding"], Decimal("42.50"))
        self.assertEqual(result["counts"]["active_loans"], 3)
        self.assertEqual(result["counts"]["closed_loans"], 1)
        self.assertEqual(result["active_loans"][0].status, "Status")
        self.assertIsNone(result["active_loans"][0].total_outstanding)
        self.assertEqual(get_balance.call_args.args, (3,))
        self.assertEqual(get_balance.call_count, 1)

    @patch("apps.tenant_apps.loans.selectors.party_history.reverse")
    @patch("apps.tenant_apps.loans.selectors.party_history.get_pawn_loan_balance", autospec=True)
    @patch("apps.tenant_apps.loans.selectors.party_history.PawnLoan.objects.filter")
    def test_uses_loans_balance_for_active_party_loan(
        self, filter_loans, get_balance, reverse
    ):
        loan = SimpleNamespace(
            pk=8,
            workspace=SimpleNamespace(slug="alpha"),
            loan_number="PL-008",
            loan_date="2026-08-16",
            state=PawnLoanState.ACTIVE.value,
            collateral_items_count=2,
            get_state_display=lambda: "Active",
        )
        filter_loans.return_value.select_related.return_value.annotate.return_value.order_by.return_value = [loan]
        get_balance.return_value = SimpleNamespace(
            total_due=Decimal("125.00"),
            principal_outstanding=Decimal("100.00"),
            interest_outstanding=Decimal("25.00"),
        )
        reverse.side_effect = lambda name, kwargs: f"/w/{kwargs['workspace_slug']}/{name}/{kwargs['pk']}"

        result = get_party_pawn_loan_history_summary(SimpleNamespace(pk=3))

        filter_loans.assert_called_once_with(borrower=SimpleNamespace(pk=3))
        self.assertEqual(result["counts"]["active_loans"], 1)
        self.assertEqual(result["counts"]["active_outstanding"], Decimal("125.00"))
        self.assertEqual(result["active_loans"][0].loan_id, "PL-008")

    @patch("apps.tenant_apps.loans.selectors.party_history.reverse")
    @patch("apps.tenant_apps.loans.selectors.party_history.get_pawn_loan_balance", autospec=True)
    @patch("apps.tenant_apps.loans.selectors.party_history.PawnLoan.objects.filter")
    def test_draft_does_not_claim_posted_outstanding(
        self, filter_loans, get_balance, reverse
    ):
        loan = SimpleNamespace(
            pk=9,
            workspace=SimpleNamespace(slug="alpha"),
            loan_number="PL-009",
            loan_date="2026-08-16",
            state=PawnLoanState.DRAFT.value,
            collateral_items_count=1,
            get_state_display=lambda: "Draft",
        )
        filter_loans.return_value.select_related.return_value.annotate.return_value.order_by.return_value = [loan]
        reverse.return_value = "/loan/9"

        result = get_party_pawn_loan_history_summary(SimpleNamespace(pk=4))

        get_balance.assert_not_called()
        self.assertIsNone(result["active_loans"][0].total_outstanding)
        self.assertEqual(result["counts"]["active_outstanding"], Decimal("0"))
