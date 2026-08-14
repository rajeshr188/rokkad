from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models import GivenLoan, TakenLoan


class LoanModelSelectorDelegationTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.selectors.loan_interest_due")
    def test_interest_due_delegates_to_selector(self, mock_selector):
        loan = GivenLoan()
        mock_selector.return_value = Decimal("25.00")

        result = loan.interest_due()

        self.assertEqual(result, Decimal("25.00"))
        mock_selector.assert_called_once_with(loan, None)

    @patch("apps.tenant_apps.girvi.selectors.loan_total_receipt_payments")
    def test_get_total_payments_delegates_to_selector(self, mock_selector):
        loan = GivenLoan()
        mock_selector.return_value = Decimal("80.00")

        result = loan.get_total_payments()

        self.assertEqual(result, Decimal("80.00"))
        mock_selector.assert_called_once_with(loan)

    @patch("apps.tenant_apps.girvi.selectors.loan_interest_accrued_gross")
    def test_interest_accrued_gross_delegates_to_selector(self, mock_selector):
        loan = GivenLoan()
        mock_selector.return_value = Decimal("15.00")

        result = loan.interest_accrued_gross()

        self.assertEqual(result, Decimal("15.00"))
        mock_selector.assert_called_once_with(loan, None)

    @patch("apps.tenant_apps.girvi.selectors.given_loan_amount")
    def test_given_loan_amount_delegates_to_selector(self, mock_selector):
        loan = GivenLoan()
        mock_selector.return_value = Decimal("1000.00")

        result = loan.get_loan_amount

        self.assertEqual(result, Decimal("1000.00"))
        mock_selector.assert_called_once_with(loan)

    @patch("apps.tenant_apps.girvi.selectors.taken_loan_interest_amount")
    def test_taken_loan_interest_delegates_to_selector(self, mock_selector):
        loan = TakenLoan()
        mock_selector.return_value = Decimal("35.00")

        result = loan.get_interest_amount

        self.assertEqual(result, Decimal("35.00"))
        mock_selector.assert_called_once_with(loan)
