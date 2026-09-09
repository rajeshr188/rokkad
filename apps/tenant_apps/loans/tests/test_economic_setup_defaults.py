from decimal import Decimal

from django.test import SimpleTestCase

from apps.orgs.models import Company
from apps.tenant_apps.loans.forms import PawnEconomicConfigurationForm, PawnFeePolicyForm


class EconomicSetupDefaultsTests(SimpleTestCase):
    def test_new_forms_offer_requested_values_without_database_writes(self):
        workspace = Company(pk=1)
        economics = PawnEconomicConfigurationForm(workspace=workspace)
        self.assertEqual(economics["gold_monthly_interest_rate"].value(), Decimal("2"))
        self.assertEqual(economics["silver_monthly_interest_rate"].value(), Decimal("4"))
        fee = PawnFeePolicyForm(workspace=workspace)
        self.assertEqual(fee["code"].value(), "DOCUMENT_CHARGE")
        self.assertEqual(fee["name"].value(), "Document charge")
        self.assertEqual(fee["calculation_type"].value(), "FIXED")
        self.assertEqual(fee["value"].value(), Decimal("10"))
        self.assertTrue(fee["deducted_at_disbursal"].value())

    def test_entered_values_override_starters_and_blanks_do_not_become_charges(self):
        fee = PawnFeePolicyForm(workspace=Company(pk=1), data={
            "license": "", "code": "CUSTOM", "name": "Custom fee",
            "calculation_type": "FIXED", "value": "25", "effective_from": "2026-09-09",
        })
        self.assertTrue(fee.is_valid(), fee.errors)
        self.assertEqual(fee.cleaned_data["value"], Decimal("25"))
        self.assertFalse(fee.cleaned_data["deducted_at_disbursal"])
        blank = PawnFeePolicyForm(workspace=Company(pk=1), data={})
        self.assertFalse(blank.is_valid())
        self.assertIn("value", blank.errors)
        economics = PawnEconomicConfigurationForm(workspace=Company(pk=1), data={
            "gold_monthly_interest_rate": "3", "silver_monthly_interest_rate": "5",
        })
        self.assertEqual(economics["gold_monthly_interest_rate"].value(), "3")
        self.assertEqual(economics["silver_monthly_interest_rate"].value(), "5")
