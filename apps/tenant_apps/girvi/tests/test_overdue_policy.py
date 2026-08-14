from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.overdue_policy import evaluate_overdue_policy


class OverduePolicyTests(SimpleTestCase):
    def _loan(self, **overrides):
        data = {
            "loan_date": date(2026, 1, 1),
            "tenure": 3,
            "current_value": Decimal("1000.00"),
        }
        data.update(overrides)
        return SimpleNamespace(**data)

    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_maturity_before_today_is_overdue(self, mock_settlement):
        mock_settlement.return_value = SimpleNamespace(total_outstanding=Decimal("500.00"))

        policy = evaluate_overdue_policy(
            self._loan(current_value=Decimal("1000.00")),
            as_of_date=date(2026, 4, 2),
        )

        self.assertTrue(policy.maturity_expired)
        self.assertTrue(policy.is_overdue)
        self.assertFalse(policy.is_npa)

    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_settlement_above_current_value_is_overdue_and_npa(self, mock_settlement):
        mock_settlement.return_value = SimpleNamespace(total_outstanding=Decimal("1200.00"))

        policy = evaluate_overdue_policy(
            self._loan(current_value=Decimal("1000.00")),
            as_of_date=date(2026, 3, 1),
        )

        self.assertFalse(policy.maturity_expired)
        self.assertTrue(policy.undersecured)
        self.assertTrue(policy.is_overdue)
        self.assertTrue(policy.is_npa)

    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    def test_covered_settlement_is_not_npa(self, mock_settlement):
        mock_settlement.return_value = SimpleNamespace(total_outstanding=Decimal("900.00"))

        policy = evaluate_overdue_policy(
            self._loan(current_value=Decimal("1000.00")),
            as_of_date=date(2026, 3, 1),
        )

        self.assertFalse(policy.is_overdue)
        self.assertFalse(policy.is_npa)
