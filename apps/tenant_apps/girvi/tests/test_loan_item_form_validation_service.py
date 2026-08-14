from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from django import forms
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.loan_item_form_validation import (
    LoanItemFormValidationService,
)


class LoanItemFormValidationServiceTests(SimpleTestCase):
    def test_validate_collateral_value_requires_rate(self):
        with self.assertRaises(forms.ValidationError):
            LoanItemFormValidationService.validate_collateral_value(
                itemtype="Gold",
                loanamount=Decimal("1000.00"),
                weight=Decimal("10.000"),
                purity=Decimal("75.00"),
                rate=None,
            )

    def test_validate_collateral_value_rejects_loan_amount_above_value(self):
        with self.assertRaises(forms.ValidationError):
            LoanItemFormValidationService.validate_collateral_value(
                itemtype="Gold",
                loanamount=Decimal("1000.00"),
                weight=Decimal("1.000"),
                purity=Decimal("75.00"),
                rate=Decimal("100.00"),
            )

    def test_validate_collateral_value_skips_when_required_inputs_missing(self):
        LoanItemFormValidationService.validate_collateral_value(
            itemtype=None,
            loanamount=Decimal("1000.00"),
            weight=Decimal("1.000"),
            purity=Decimal("75.00"),
            rate=None,
        )

    def test_validate_initial_row_adds_errors_and_defaults(self):
        form = SimpleNamespace(add_error=MagicMock())
        cleaned_data = {
            "itemdesc": "",
            "weight": "",
            "loanamount": "",
            "interestrate": "",
            "quantity": "",
            "purity": "",
            "itemtype": "",
        }

        result = LoanItemFormValidationService.validate_initial_row(
            form,
            cleaned_data,
            row_has_user_input=True,
        )

        self.assertIs(result, cleaned_data)
        self.assertEqual(form.add_error.call_count, 4)
        self.assertEqual(cleaned_data["quantity"], 1)
        self.assertEqual(cleaned_data["purity"], 75)
        self.assertEqual(cleaned_data["itemtype"], "Gold")

    def test_validate_initial_row_leaves_blank_rows_untouched(self):
        form = SimpleNamespace(add_error=MagicMock())
        cleaned_data = {
            "itemdesc": "",
            "weight": "",
            "loanamount": "",
            "interestrate": "",
        }

        result = LoanItemFormValidationService.validate_initial_row(
            form,
            cleaned_data,
            row_has_user_input=False,
        )

        self.assertIs(result, cleaned_data)
        form.add_error.assert_not_called()
