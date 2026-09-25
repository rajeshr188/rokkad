from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase

from apps.tenant_apps.loans.documents.display import collateral_description, display_money
from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder


class IndianDisplayTests(SimpleTestCase):
    def test_exact_decimal_grouping_and_paise(self):
        cases = {
            "0": "0", "999.5": "999.50", "1000": "1,000",
            "18600": "18,600", "160000": "1,60,000",
            "1234567.50": "12,34,567.50", "10000000": "1,00,00,000",
            "-123456789.01": "-12,34,56,789.01",
            "123456789012345678901.12": "12,34,56,78,90,12,34,56,78,901.12",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                amount = Decimal(value)
                self.assertEqual(display_money(amount, grouping=True), expected)
                self.assertEqual(PawnLoanDocumentProjectionBuilder._money(amount), "INR " + expected)
                self.assertEqual(amount, Decimal(value))

    def test_template_handles_unknown_and_does_not_change_form_value(self):
        template = Template('{% load loans_display %}{{ amount|indian_money }}|{{ unknown|default_if_none:"Unknown"|indian_money }}|{{ invalid|indian_money }}')
        self.assertEqual(template.render(Context({"amount": Decimal("123456.50"), "unknown": None,
                                                 "invalid": "<missing>"})),
                         "1,23,456.50|Unknown|&lt;missing&gt;")

    def test_descriptions_use_known_evidence_only(self):
        self.assertEqual(collateral_description({"description": "Gold bangles", "quantity": 2}), "Gold bangles (Qty 2)")
        self.assertEqual(collateral_description({"description": "Chain"}), "Chain")
        self.assertEqual(collateral_description({"description": "Chain", "quantity": None}), "Chain")

    def test_all_affected_app_templates_compile(self):
        for folder in ("loans", "party", "rates"):
            for path in (Path(settings.BASE_DIR) / "templates" / folder).rglob("*.html"):
                with self.subTest(path=path):
                    get_template(path.relative_to(Path(settings.BASE_DIR) / "templates").as_posix())
