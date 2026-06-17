from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.forms import LoanItemForm


class LoanItemRateValidationTests(SimpleTestCase):
    def _form_data(self, **overrides):
        data = {
            "itemdesc": "Ring",
            "itemtype": "Gold",
            "quantity": "1",
            "weight": "10.000",
            "purity": "75.00",
            "loanamount": "1000.00",
            "interestrate": "2.00",
        }
        data.update(overrides)
        return data

    @patch("apps.tenant_apps.girvi.forms.RateCacheService.get_rate_or_none", return_value=None)
    def test_missing_rate_reports_setup_error(self, _mock_rate):
        form = LoanItemForm(data=self._form_data())

        self.assertFalse(form.is_valid())
        self.assertIn("rate is not configured", form.errors["__all__"][0])

    @patch(
        "apps.tenant_apps.girvi.forms.RateCacheService.get_rate_or_none",
        return_value=Decimal("200.00"),
    )
    def test_configured_rate_allows_collateral_value_check(self, _mock_rate):
        form = LoanItemForm(data=self._form_data(loanamount="1000.00"))

        self.assertTrue(form.is_valid(), form.errors)
