from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django import forms
from django.test import SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.girvi.service_modules.loan_form_validation import (
    LoanFormValidationService,
)


class LoanFormValidationServiceTests(SimpleTestCase):
    def test_validate_not_future_rejects_future_date(self):
        with self.assertRaises(forms.ValidationError):
            LoanFormValidationService.validate_not_future(
                timezone.now() + timedelta(days=1)
            )

    def test_validate_series_active_adds_error_for_inactive_series(self):
        form = SimpleNamespace(add_error=MagicMock())
        series = SimpleNamespace(is_active=False)

        LoanFormValidationService.validate_series_active(form, series)

        form.add_error.assert_called_once()

    @patch("apps.tenant_apps.girvi.service_modules.loan_form_validation.assert_loan_header_editable")
    def test_validate_loan_form_checks_header_editable_and_series(self, header_mock):
        form = SimpleNamespace(instance=SimpleNamespace(pk=1), add_error=MagicMock())
        cleaned_data = {"series": SimpleNamespace(is_active=False)}

        result = LoanFormValidationService.validate_loan_form(form, cleaned_data)

        self.assertIs(result, cleaned_data)
        header_mock.assert_called_once_with(form.instance)
        form.add_error.assert_called_once()

    def test_validate_loan_renewal_requires_positive_topup(self):
        form = SimpleNamespace(add_error=MagicMock())
        cleaned_data = {"mode": "TOPUP_RENEW", "requested_extra_amount": 0}

        LoanFormValidationService.validate_loan_renewal(form, cleaned_data)

        form.add_error.assert_called_once_with(
            "requested_extra_amount",
            "Top-Up mode requires a positive extra amount.",
        )

    def test_validate_storage_box_range_rejects_reverse_range(self):
        with self.assertRaises(forms.ValidationError):
            LoanFormValidationService.validate_storage_box_range(
                start_loan=SimpleNamespace(loan_id="GL-010"),
                end_loan=SimpleNamespace(loan_id="GL-001"),
            )
