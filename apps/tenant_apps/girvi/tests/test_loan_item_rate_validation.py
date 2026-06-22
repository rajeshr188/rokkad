from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.forms import LoanItemForm
from apps.tenant_apps.girvi.models import LoanItem


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

    def test_loan_item_model_blocks_edit_after_active_state(self):
        item = LoanItem(
            itemdesc="Ring",
            itemtype="Gold",
            quantity=1,
            weight=Decimal("10.000"),
            purity=Decimal("75.00"),
            loanamount=Decimal("1000.00"),
            interestrate=Decimal("2.00"),
        )
        item._state.fields_cache["loan"] = SimpleNamespace(
            status="ActiveCurrent",
            is_released=False,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Cannot modify LoanItem after loan approval/disbursal workflow has advanced.",
        ):
            item._assert_loan_items_editable()

    def test_loan_item_model_allows_draft_state(self):
        item = LoanItem(
            itemdesc="Ring",
            itemtype="Gold",
            quantity=1,
            weight=Decimal("10.000"),
            purity=Decimal("75.00"),
            loanamount=Decimal("1000.00"),
            interestrate=Decimal("2.00"),
        )
        item._state.fields_cache["loan"] = SimpleNamespace(
            status="Draft",
            is_released=False,
        )

        item._assert_loan_items_editable()
