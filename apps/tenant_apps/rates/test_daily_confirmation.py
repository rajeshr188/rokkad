from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, transaction
from django.db import connection
from django.test import TestCase
from django.test import RequestFactory
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.rates import test_quote_evidence as fixtures
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.rates.services import confirm_quote_unchanged


class DailyConfirmationTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.QuoteEvidenceTests.setup_tenant.__func__)
    setUp = fixtures.QuoteEvidenceTests.setUp
    record = fixtures.QuoteEvidenceTests.record

    @classmethod
    def get_test_schema_name(cls):
        return "daily-confirmation"

    def confirm(self, quote, **changes):
        values = dict(workspace=self.tenant, actor=self.actor, quote_id=quote.pk)
        values.update(changes)
        return confirm_quote_unchanged(**values)

    def test_confirmation_is_new_dated_actor_evidence_and_repeat_is_idempotent(self):
        original = self.record()
        current = self.confirm(original)
        self.assertNotEqual(current.pk, original.pk)
        self.assertEqual(current.confirmed_from_id, original.pk)
        self.assertEqual(current.recorded_by, self.actor)
        self.assertEqual(current.buying_rate, original.buying_rate)
        self.assertEqual(timezone.localdate(current.effective_at), timezone.localdate())
        self.assertIsNone(current.supersedes_id)
        original.refresh_from_db()
        self.assertEqual(original.effective_at, self.at)
        self.assertEqual(self.confirm(original).pk, current.pk)
        self.assertEqual(self.confirm(current).pk, current.pk)
        self.assertEqual(Rate.objects.count(), 2)

    def test_cannot_confirm_stale_page_or_foreign_or_missing_user(self):
        original = self.record()
        self.record(buying_rate=7200, effective_at=timezone.now())
        with self.assertRaisesMessage(ValidationError, "quote changed"):
            self.confirm(original)
        with self.assertRaises(PermissionDenied):
            self.confirm(original, actor=None)
        with self.assertRaises(ValidationError):
            self.confirm(original, quote_id=9999999)

    def test_confirmation_retains_database_immutability_and_value_guard(self):
        original = self.record()
        current = self.confirm(original)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Rate.objects.filter(pk=current.pk).update(buying_rate=1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            Rate.objects.bulk_create([Rate(workspace=self.tenant, rate_source=self.source,
                confirmed_from=original, recorded_by=self.actor, buying_rate=1, selling_rate=2,
                effective_at=timezone.now())])

    def test_next_day_can_confirm_again_without_rewriting_prior_confirmation(self):
        original = self.record()
        first = self.confirm(original)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=1)):
            second = self.confirm(first)
        self.assertEqual(second.confirmed_from_id, first.pk)
        self.assertEqual(Rate.objects.count(), 3)

    def test_confirmation_endpoint_requires_post(self):
        from apps.tenant_apps.rates.views import rate_confirm_unchanged
        quote = self.record()
        request = RequestFactory().get("/")
        request.user, request.workspace = self.actor, self.tenant
        self.assertEqual(rate_confirm_unchanged(request, quote.pk).status_code, 405)
        self.assertEqual(Rate.objects.count(), 1)

    def test_confirmation_attributes_the_actual_staff_user_not_workspace_owner(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Membership, Role
        original = self.record()
        staff = get_user_model().objects.create_user(username="daily-confirming-admin")
        Membership.objects.create(user=staff, company=self.tenant, role=Role.objects.get_or_create(name="Admin")[0])
        confirmed = self.confirm(original, actor=staff)
        self.assertEqual(confirmed.recorded_by, staff)
        self.assertNotEqual(confirmed.recorded_by_id, self.tenant.owner_id)


class DailyConfirmationIsolationTests(TestCase):
    def test_foreign_confirmation_source_is_blocked_under_restricted_rls_role(self):
        import uuid
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company, Membership, Role
        from apps.tenancy.context import workspace_context
        from apps.tenant_apps.rates.models import RateSource
        from apps.tenant_apps.rates.services import record_quote
        actor = get_user_model().objects.create_user(username="daily-isolation-owner")
        records = []
        for suffix in ("a", "b"):
            workspace = Company.objects.create(name=suffix, schema_name="daily-isolation-" + suffix, owner=actor, creator=actor)
            Membership.objects.create(user=actor, company=workspace, role=Role.objects.get_or_create(name="Owner")[0])
            with workspace_context(workspace.pk):
                source = RateSource.objects.create(name="Market", location="Local")
                quote = record_quote(workspace=workspace, actor=actor, values=dict(rate_source=source,
                    metal="Gold", currency="INR", purity="24k", buying_rate=10, selling_rate=11,
                    effective_at=timezone.now() - timedelta(days=1)))
            records.append((workspace, source, quote))
        role = connection.ops.quote_name("daily_guard_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            workspace, source, original = records[0]
            foreign = records[1][2]
            with workspace_context(workspace.pk):
                self.assertFalse(Rate.objects.filter(pk=foreign.pk).exists())
                with self.assertRaises(ValidationError):
                    confirm_quote_unchanged(workspace=workspace, actor=actor, quote_id=foreign.pk)
                with self.assertRaises(DatabaseError), transaction.atomic():
                    Rate.objects.bulk_create([Rate(workspace=workspace, rate_source=source,
                        confirmed_from_id=foreign.pk, recorded_by=actor, buying_rate=10, selling_rate=11)])
                confirmed = confirm_quote_unchanged(workspace=workspace, actor=actor, quote_id=original.pk)
                self.assertEqual(confirmed.confirmed_from_id, original.pk)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
