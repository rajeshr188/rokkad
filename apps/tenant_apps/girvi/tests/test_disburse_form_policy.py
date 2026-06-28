from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.forms import DisburseLoanForm


class DisburseLoanFormPolicyTests(SimpleTestCase):
    def _workspace(self):
        return SimpleNamespace(id=1)

    def _loan(self, amount=Decimal("1000.00")):
        return SimpleNamespace(get_loan_amount=amount)

    @patch("apps.tenant_apps.girvi.forms.CompanyPreferences")
    def test_rejects_deductions_when_policy_disabled(self, mock_prefs):
        mock_prefs.return_value = SimpleNamespace(
            loan_disbursal_deductions_enabled=False,
            loan_interest_deduction=True,
            loan_minimum_document_charge=Decimal("0.00"),
        )

        form = DisburseLoanForm(
            data={
                "disbursed_by": "cashier",
                "upfront_interest_deduction": "20.00",
                "document_charge": "0.00",
            },
            loan=self._loan(),
            workspace=self._workspace(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Disbursal deductions are disabled by policy", str(form.errors))

    @patch("apps.tenant_apps.girvi.forms.CompanyPreferences")
    def test_enforces_minimum_document_charge_when_enabled(self, mock_prefs):
        mock_prefs.return_value = SimpleNamespace(
            loan_disbursal_deductions_enabled=True,
            loan_interest_deduction=True,
            loan_minimum_document_charge=Decimal("25.00"),
        )

        form = DisburseLoanForm(
            data={
                "disbursed_by": "cashier",
                "upfront_interest_deduction": "0.00",
                "document_charge": "10.00",
            },
            loan=self._loan(),
            workspace=self._workspace(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Document charge must be at least 25.00", str(form.errors))

    @patch("apps.tenant_apps.girvi.forms.CompanyPreferences")
    def test_rejects_interest_deduction_when_interest_policy_disabled(self, mock_prefs):
        mock_prefs.return_value = SimpleNamespace(
            loan_disbursal_deductions_enabled=True,
            loan_interest_deduction=False,
            loan_minimum_document_charge=Decimal("5.00"),
        )

        form = DisburseLoanForm(
            data={
                "disbursed_by": "cashier",
                "upfront_interest_deduction": "15.00",
                "document_charge": "5.00",
            },
            loan=self._loan(),
            workspace=self._workspace(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("Interest deduction is disabled by policy", str(form.errors))

    @patch("apps.tenant_apps.girvi.forms.CompanyPreferences")
    def test_builds_net_disbursal_preview_when_policy_valid(self, mock_prefs):
        mock_prefs.return_value = SimpleNamespace(
            loan_disbursal_deductions_enabled=True,
            loan_interest_deduction=True,
            loan_minimum_document_charge=Decimal("25.00"),
        )

        form = DisburseLoanForm(
            data={
                "disbursed_by": "cashier",
                "upfront_interest_deduction": "100.00",
                "document_charge": "25.00",
            },
            loan=self._loan(amount=Decimal("1000.00")),
            workspace=self._workspace(),
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.disbursal_preview["net_disbursal_amount"], Decimal("875.00"))
