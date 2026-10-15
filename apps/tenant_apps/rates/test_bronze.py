"""Bronze uses ordinary scoped quote evidence, not a new pricing subsystem."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import override_settings

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.rates import test_quote_evidence as fixtures
from apps.tenant_apps.rates import test_reference_ui as ui
from apps.tenant_apps.rates.facade import get_latest_commodity_valuation_rate, get_workspace_rate_dashboard_summary
from apps.tenant_apps.rates.forms import RateForm
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.rates.services import confirm_quote_unchanged, record_quote, withdraw_quote


class BronzeQuoteTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.QuoteEvidenceTests.setup_tenant.__func__)
    setUp = fixtures.QuoteEvidenceTests.setUp
    record = fixtures.QuoteEvidenceTests.record

    @classmethod
    def get_test_schema_name(cls):
        return "bronze-quote"

    def test_bronze_selection_correction_and_withdrawal_retain_source_history(self):
        quote = self.record(metal="Bronze", buying_rate=Decimal("0.60"), selling_rate=Decimal("0.75"))
        lookup = lambda: get_latest_commodity_valuation_rate(commodity_code=" bronze ")
        self.assertEqual(lookup().rate.pk, quote.pk)
        self.assertEqual(quote.get_purity_display(), "Bronze reference grade (100%)")
        self.assertEqual(get_workspace_rate_dashboard_summary()["bronze_rate"].pk, quote.pk)
        self.assertIsNone(get_workspace_rate_dashboard_summary()["gold_rate"])
        corrected = record_quote(workspace=self.tenant, actor=self.actor, supersedes_id=quote.pk,
            values={**self.values, "metal": "Bronze", "buying_rate": Decimal("0.65"),
                    "selling_rate": Decimal("0.75"), "reason": "Fictional source correction"})
        self.assertEqual(lookup().rate.pk, corrected.pk)
        quote.refresh_from_db()
        self.assertEqual(quote.buying_rate, Decimal("0.60"))
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=corrected.pk, reason="Fictional quote withdrawn")
        self.assertIsNone(lookup().rate)

    def test_bronze_requires_positive_prices_and_reference_grade(self):
        for changes in ({"purity": "22k"}, {"buying_rate": "0"}, {"selling_rate": "-1"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.record(metal="Bronze", **changes)
        form = RateForm(data={**self.values, "rate_source": self.source.pk, "metal": "Bronze"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn("bronze", form.fields["purity"].help_text)

    def test_bronze_daily_confirmation_is_actor_attributed_and_repeat_safe(self):
        original = self.record(metal="Bronze", buying_rate=Decimal("0.60"), selling_rate=Decimal("0.75"))
        current = confirm_quote_unchanged(workspace=self.tenant, actor=self.actor, quote_id=original.pk)
        self.assertEqual(current.confirmed_from_id, original.pk)
        self.assertEqual(current.recorded_by, self.actor)
        self.assertEqual(current.buying_rate, original.buying_rate)
        self.assertEqual(confirm_quote_unchanged(workspace=self.tenant, actor=self.actor, quote_id=original.pk).pk, current.pk)
        self.assertEqual(get_latest_commodity_valuation_rate(commodity_code="BRONZE").rate.pk, current.pk)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class BronzeRateUiTests(WorkspaceTestCase):
    setup_tenant = classmethod(ui.RateReferenceUiTests.setup_tenant.__func__)
    setUp = ui.RateReferenceUiTests.setUp
    url = ui.RateReferenceUiTests.url

    @classmethod
    def get_test_schema_name(cls):
        return "bronze-reference-ui"

    def test_bronze_entry_list_confirmation_and_latest_price_are_available(self):
        from django.utils import timezone
        from datetime import timedelta
        response = self.client.post(self.url("rate_create"), {
            "rate_source": self.source.pk, "metal": "Bronze", "currency": "INR", "purity": "24k",
            "buying_rate": "0.60", "selling_rate": "0.75",
            "effective_at": (timezone.now() - timedelta(days=1)).isoformat(),
        })
        self.assertEqual(response.status_code, 302)
        quote = Rate.objects.get(metal="Bronze")
        page = self.client.get(self.url("rate_list"), {"metal": "Bronze"})
        self.assertContains(page, "Bronze reference grade (100%)")
        self.assertContains(page, "Confirm bronze price unchanged for today")
        self.assertContains(page, "not a pure-copper price")
        response = self.client.post(self.url("rate_confirm_unchanged", pk=quote.pk))
        self.assertEqual(response.status_code, 302)
        latest = self.client.get(self.url("historical_rate"))
        self.assertContains(latest, "Bronze")
