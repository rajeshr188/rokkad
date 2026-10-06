"""Real upgrade rehearsal, confined to Django's disposable test database."""
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.testing import historical_migration_database


class QuoteMigrationTests(TransactionTestCase):
    def test_existing_values_dates_and_unknown_authors_are_preserved(self):
        before = [("rates", "0002_enable_workspace_rls")]
        after = [("rates", "0004_rate_daily_confirmation")]
        owner = get_user_model().objects.create_user(username="quote-upgrade-owner")
        workspace = Company.objects.create(name="Upgrade", schema_name="quote-upgrade", owner=owner, creator=owner)
        membership = Membership.objects.create(user=owner, company=workspace, role=Role.objects.get_or_create(name="Owner")[0])
        with historical_migration_database(self, before, [membership]) as (target, old_apps):
            old_time = datetime(2025, 1, 2, 10, 15, tzinfo=timezone.utc)
            old_rate = old_apps.get_model("rates", "Rate")
            source = old_apps.get_model("rates", "RateSource").objects.using(target.alias).create(workspace_id=workspace.pk, name="Old market", location="Local", tax_included=True)
            quote = old_rate.objects.using(target.alias).create(workspace_id=workspace.pk, rate_source_id=source.pk, metal="Silver", purity="22k", buying_rate=0, selling_rate=1)
            old_rate.objects.using(target.alias).filter(pk=quote.pk).update(timestamp=old_time)
            executor = MigrationExecutor(target)
            executor.migrate(after)
            rate = executor.loader.project_state(after).apps.get_model("rates", "Rate")
            current = rate.objects.using(target.alias).get(pk=quote.pk)
            self.assertEqual(current.effective_at, old_time)
            self.assertEqual(current.timestamp, old_time)
            self.assertEqual(current.buying_rate, 0)
            self.assertEqual(current.purity, "22k")
            self.assertIsNone(current.recorded_by_id)
            self.assertEqual(current.source_snapshot["name"], "Old market")
            self.assertTrue(current.source_snapshot["legacy"])
            # Verify the upgraded database guard can retain and withdraw an old
            # invalid quote. Ordinary command permission/RLS tests run separately.
            withdrawal = rate.objects.using(target.alias).create(workspace_id=workspace.pk,
                rate_source_id=source.pk, metal=current.metal, currency=current.currency,
                purity=current.purity, buying_rate=current.buying_rate, selling_rate=current.selling_rate,
                effective_at=current.effective_at, is_withdrawal=True, supersedes_id=current.pk,
                recorded_by_id=owner.pk, reason="Legacy quote has invalid basis")
            self.assertTrue(withdrawal.is_withdrawal)
            self.assertEqual(withdrawal.buying_rate, 0)
