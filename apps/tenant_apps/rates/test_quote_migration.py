"""Real upgrade rehearsal, confined to Django's disposable test database."""
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.rates.services import withdraw_quote


class QuoteMigrationTests(TransactionTestCase):
    def test_existing_values_dates_and_unknown_authors_are_preserved(self):
        before = [("rates", "0002_enable_workspace_rls")]
        after = [("rates", "0003_rate_effective_at_rate_is_withdrawal_rate_reason_and_more")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            old_apps = executor.loader.project_state(before).apps
            owner = get_user_model().objects.create_user(username="quote-upgrade-owner")
            workspace = Company.objects.create(name="Upgrade", schema_name="quote-upgrade", owner=owner, creator=owner)
            Membership.objects.create(user=owner, company=workspace, role=Role.objects.get_or_create(name="Owner")[0])
            old_time = datetime(2025, 1, 2, 10, 15, tzinfo=timezone.utc)
            with workspace_context(workspace.pk):
                source = old_apps.get_model("rates", "RateSource").objects.create(workspace_id=workspace.pk, name="Old market", location="Local", tax_included=True)
                quote = old_apps.get_model("rates", "Rate").objects.create(workspace_id=workspace.pk, rate_source_id=source.pk, metal="Silver", purity="22k", buying_rate=0, selling_rate=1)
                old_apps.get_model("rates", "Rate").objects.filter(pk=quote.pk).update(timestamp=old_time)
        finally:
            MigrationExecutor(connection).migrate(after)
        with workspace_context(workspace.pk):
            current = Rate.objects.get(pk=quote.pk)
            self.assertEqual(current.effective_at, old_time)
            self.assertEqual(current.timestamp, old_time)
            self.assertEqual(current.buying_rate, 0)
            self.assertEqual(current.purity, "22k")
            self.assertIsNone(current.recorded_by_id)
            self.assertEqual(current.source_snapshot["name"], "Old market")
            self.assertTrue(current.source_snapshot["legacy"])
            withdrawal = withdraw_quote(workspace=workspace, actor=owner, quote_id=current.pk, reason="Legacy quote has invalid basis")
            self.assertTrue(withdrawal.is_withdrawal)
            self.assertEqual(withdrawal.buying_rate, 0)
