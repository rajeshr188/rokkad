from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.repayment_form_validation import (
    RepaymentFormValidationService,
)


class RepaymentFormValidationServiceTests(SimpleTestCase):
    def _build_form(self, *, total, interest, loan=None):
        form = SimpleNamespace()
        form.cleaned_data = {
            "total_amount": total,
            "interest_amount": interest,
        }
        form.loan = loan
        form.add_error = MagicMock()
        return form

    def test_validate_form_rejects_interest_greater_than_total(self):
        form = self._build_form(total=Decimal("100.00"), interest=Decimal("101.00"))

        RepaymentFormValidationService.validate_form(form, loan_kind="given")

        form.add_error.assert_called_once_with(
            "interest_amount",
            "Interest portion cannot exceed total amount.",
        )

    @patch(
        "apps.tenant_apps.girvi.service_modules.repayment_form_validation.build_loan_settlement_balance"
    )
    def test_validate_form_rejects_total_above_outstanding(self, settlement_mock):
        settlement_mock.return_value = SimpleNamespace(
            total_outstanding=Decimal("500.00"),
            interest_due=Decimal("100.00"),
        )
        loan = SimpleNamespace(loan_id="GL-1")
        form = self._build_form(
            total=Decimal("501.00"),
            interest=Decimal("80.00"),
            loan=loan,
        )

        RepaymentFormValidationService.validate_form(form, loan_kind="given")

        settlement_mock.assert_called_once_with(loan, loan_kind="given")
        form.add_error.assert_called_once_with(
            "total_amount",
            "Payment amount cannot exceed outstanding amount 500.00.",
        )

    @patch(
        "apps.tenant_apps.girvi.service_modules.repayment_form_validation.build_loan_settlement_balance"
    )
    def test_validate_form_rejects_interest_above_outstanding_interest(self, settlement_mock):
        settlement_mock.return_value = SimpleNamespace(
            total_outstanding=Decimal("500.00"),
            interest_due=Decimal("90.00"),
        )
        loan = SimpleNamespace(loan_id="TL-1")
        form = self._build_form(
            total=Decimal("200.00"),
            interest=Decimal("91.00"),
            loan=loan,
        )

        RepaymentFormValidationService.validate_form(form, loan_kind="taken")

        settlement_mock.assert_called_once_with(loan, loan_kind="taken")
        form.add_error.assert_called_once_with(
            "interest_amount",
            "Interest portion cannot exceed outstanding interest 90.00.",
        )
