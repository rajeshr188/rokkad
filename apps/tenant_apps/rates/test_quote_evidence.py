from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.testing import WorkspaceTestCase

from apps.tenant_apps.rates.facade import get_latest_commodity_valuation_rate, get_workspace_rate_dashboard_summary
from apps.tenant_apps.rates.forms import RateForm
from apps.tenant_apps.rates.models import Rate, RateSource
from apps.tenant_apps.rates.services import record_quote, withdraw_quote
from apps.tenant_apps.rates.views import rate_create, rate_update, rate_delete, ratesource_delete


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class QuoteEvidenceTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "quote-evidence"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.actor = get_user_model().objects.create_user(username="quote-evidence-owner")
        tenant.name = "Quote evidence"
        tenant.owner = tenant.creator = cls.actor
        tenant.save()
        Membership.objects.create(user=cls.actor, company=tenant, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        self.source = RateSource.objects.create(name="Market", location="Local")
        self.at = timezone.now() - timedelta(days=2)
        self.values = dict(rate_source=self.source, metal="Gold", currency="INR", purity="24k",
                           buying_rate=Decimal("7000"), selling_rate=Decimal("7100"), effective_at=self.at)

    def record(self, **changes):
        return record_quote(workspace=self.tenant, actor=self.actor, values={**self.values, **changes})

    def lookup(self, **kwargs):
        return get_latest_commodity_valuation_rate(commodity_code="GOLD", **kwargs)

    def request(self, data):
        request = RequestFactory().post("/rates/", data)
        request.user = self.actor
        request.workspace = self.tenant
        return request

    def test_effective_time_not_entry_time_controls_selection_and_future_exclusion(self):
        current = self.record()
        self.record(effective_at=self.at - timedelta(days=1), buying_rate=Decimal("6000"))
        self.record(effective_at=timezone.now() + timedelta(days=1), buying_rate=Decimal("8000"))
        self.assertEqual(self.lookup().rate.pk, current.pk)
        self.assertEqual(self.lookup(as_of=self.at).rate.pk, current.pk)
        self.assertIsNone(self.lookup(as_of=self.at - timedelta(days=2)).rate)
        self.assertEqual(get_workspace_rate_dashboard_summary()["gold_rate"].pk, current.pk)

    def test_latest_effective_quote_across_sources_is_deterministic(self):
        self.record()
        second = RateSource.objects.create(name="Second", location="Other")
        winner = self.record(rate_source=second)
        self.assertEqual(self.lookup().rate.pk, winner.pk)

    def test_correction_and_withdrawal_preserve_history_actor_and_dates(self):
        original = self.record()
        corrected = record_quote(workspace=self.tenant, actor=self.actor, supersedes_id=original.pk,
                                 values={**self.values, "buying_rate": Decimal("7200"), "reason": "Transposed price"})
        original.refresh_from_db()
        self.assertEqual(original.buying_rate, Decimal("7000"))
        self.assertEqual(corrected.supersedes_id, original.pk)
        self.assertEqual(corrected.recorded_by, self.actor)
        self.assertEqual(corrected.effective_at, original.effective_at)
        self.assertGreater(corrected.timestamp, original.timestamp)
        self.assertEqual(self.lookup(as_of=self.at).rate.pk, corrected.pk)
        withdrawn = withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=corrected.pk, reason="Unverified source")
        self.assertTrue(withdrawn.is_withdrawal)
        self.assertEqual(withdrawn.supersedes_id, corrected.pk)
        self.assertIsNone(self.lookup().rate)
        self.assertEqual(Rate.objects.filter(workspace=self.tenant).count(), 3)

    def test_withdrawal_can_fall_back_to_an_earlier_independent_quote(self):
        older = self.record()
        later = self.record(effective_at=self.at + timedelta(days=1))
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=later.pk, reason="Wrong quote")
        self.assertEqual(self.lookup().rate.pk, older.pk)

    def test_stale_correction_and_blank_reason_fail_without_new_rows(self):
        original = self.record()
        with self.assertRaises(ValidationError):
            record_quote(workspace=self.tenant, actor=self.actor, supersedes_id=original.pk, values=self.values)
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=original.pk, reason="Wrong quote")
        with self.assertRaises(ValidationError):
            record_quote(workspace=self.tenant, actor=self.actor, supersedes_id=original.pk, values={**self.values, "reason": "Late correction"})
        self.assertEqual(Rate.objects.filter(workspace=self.tenant).count(), 2)

    def test_model_and_database_reject_mutating_or_removing_quotes(self):
        quote = self.record()
        with self.assertRaises(ValidationError):
            quote.save()
        with self.assertRaises(ValidationError):
            quote.delete()
        for operation in (lambda: Rate.objects.filter(pk=quote.pk).update(buying_rate=1),
                          lambda: Rate.objects.filter(pk=quote.pk).delete()):
            with self.assertRaises(DatabaseError), transaction.atomic():
                operation()
        with self.assertRaises(ProtectedError):
            self.source.delete()

    def test_prices_require_positive_values_and_silver_requires_pure_basis(self):
        for changes in ({"buying_rate": "0"}, {"selling_rate": "-1"}, {"metal": "Silver", "purity": "22k"}):
            with self.subTest(changes=changes):
                form = RateForm(data={**self.values, "rate_source": self.source.pk, **changes})
                self.assertFalse(form.is_valid())
                with self.assertRaises(ValidationError):
                    self.record(**changes)
        silver = self.record(metal="Silver")
        self.assertEqual(silver.get_purity_display(), "Pure metal (100%)")

    def test_source_snapshot_survives_source_edits(self):
        quote = self.record()
        self.source.name = "Renamed"
        self.source.tax_included = True
        self.source.save()
        quote.refresh_from_db()
        self.assertEqual(quote.source_snapshot, {"name": "Market", "location": "Local", "tax_included": False})

    def test_service_requires_actor_permission_and_workspace(self):
        other = Company.objects.create(name="Other", schema_name="other-quotes", owner=self.actor, creator=self.actor)
        for workspace, actor in ((self.tenant, None), (other, self.actor)):
            with self.assertRaises(PermissionDenied):
                record_quote(workspace=workspace, actor=actor, values=self.values)
        self.assertFalse(Rate.objects.filter(workspace=self.tenant).exists())

    def test_ui_correction_withdrawal_and_protected_source(self):
        data = {**self.values, "rate_source": self.source.pk}
        self.assertEqual(rate_create(self.request(data)).status_code, 302)
        original = Rate.objects.get(workspace=self.tenant)
        response = rate_update(self.request({**data, "buying_rate": "7250", "reason": "Correct amount"}), original.pk)
        self.assertEqual(response.status_code, 302)
        corrected = Rate.objects.get(supersedes=original)
        self.assertIn(str(corrected.pk), response.url)
        response = rate_delete(self.request({"reason": "Unreliable price"}), corrected.pk)
        self.assertEqual(response.status_code, 302)
        response = ratesource_delete(self.request({}), self.source.pk)
        self.assertContains(response, "must remain in history")
