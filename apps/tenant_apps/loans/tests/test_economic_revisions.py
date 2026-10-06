"""Database upgrade and competing same-day policy edits."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import historical_migration_database
from apps.tenant_apps.loans.models import PawnLoanEconomicPolicy, PawnMetalInterestRatePolicy
from apps.tenant_apps.loans.services import create_pawn_economic_configuration


class EconomicRevisionDatabaseTests(TransactionTestCase):
    maxDiff = None
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username=uuid.uuid4().hex)
        self.workspace = Company.objects.create(name="Policy revisions", schema_name=uuid.uuid4().hex,
            owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.workspace,
            role=Role.objects.get_or_create(name="Owner")[0])

    def configure(self, ltv):
        return create_pawn_economic_configuration(workspace=self.workspace, actor=self.actor,
            valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal(ltv),
            gold_monthly_interest_rate=Decimal("2"), silver_monthly_interest_rate=Decimal("4"),
            effective_from=date(2026, 9, 25))

    def test_concurrent_first_configurations_allocate_distinct_atomic_revisions(self):
        barrier = Barrier(2)

        def save(ltv):
            try:
                with workspace_context(self.workspace.pk):
                    barrier.wait(timeout=10)
                    result = self.configure(ltv)
                    return (result.economic_policy.revision, result.gold_rate_policy.revision,
                            result.silver_rate_policy.revision)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(save, ("0.80", "0.95")))
        self.assertEqual(sorted(results), [(1, 1, 1), (2, 2, 2)])
        with workspace_context(self.workspace.pk):
            self.assertEqual(PawnLoanEconomicPolicy.objects.count(), 2)
            self.assertEqual(PawnMetalInterestRatePolicy.objects.count(), 4)

    def test_populated_upgrade_preserves_policy_values_and_ids(self):
        with workspace_context(self.workspace.pk):
            configuration = self.configure("0.80")
        old = [("loans", "0024_disbursal_schedule_identity")]
        membership = Membership.objects.get(company=self.workspace, user=self.actor)
        with historical_migration_database(self, old, [membership, configuration.economic_policy,
            configuration.gold_rate_policy, configuration.silver_rate_policy]) as (target, old_apps):
            names = ("PawnLoanEconomicPolicy", "PawnMetalInterestRatePolicy")
            originals = {name: list(old_apps.get_model("loans", name).objects.using(target.alias).order_by("pk").values()) for name in names}
            after = [("loans", "0025_same_day_economic_policy_revisions")]
            executor = MigrationExecutor(target)
            executor.migrate(after)
            apps = executor.loader.project_state(after).apps
            for name in names:
                rows = list(apps.get_model("loans", name).objects.using(target.alias).order_by("pk").values())
                self.assertTrue(all(row.pop("revision") == 1 for row in rows))
                self.assertEqual(rows, originals[name])
        with workspace_context(self.workspace.pk):
            self.assertEqual(self.configure("0.95").economic_policy.revision, 2)
