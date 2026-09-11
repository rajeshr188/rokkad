import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import connection, connections, DatabaseError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.forms.models import model_to_dict
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context, current_workspace_id
from apps.tenant_apps.loans.models import LoanMonitoringPolicy, LoanRiskSnapshot, PawnLoan
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio_summary
from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot, reassess_pawn_loans_batch
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.loans.web.economic_forms import LoanMonitoringPolicyForm
from apps.tenant_apps.rates.models import Rate


class MonitoringConcurrencyTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:10]
        self.actor = get_user_model().objects.create_user(username=f"monitor-race-{suffix}")
        self.tenant = Company.objects.create(name=f"Monitor race {suffix}", schema_name=f"monitor-race-{suffix}", owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            fixtures.CollateralReappraisalTests.make_loan(self)

    def test_competing_amendments_create_one_successor(self):
        barrier = Barrier(2)
        def amend(limit):
            try:
                barrier.wait(timeout=10)
                with workspace_context(self.tenant.pk):
                    values = model_to_dict(self.policy, fields=LoanMonitoringPolicyForm.Meta.fields)
                    values.update(license=None, supersedes=self.policy, effective_from=self.today,
                                  amendment_reason="Reviewed freshness", rate_freshness_days=limit)
                    return create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **values).pk
            except ValidationError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(amend, (8, 9)))
        self.assertEqual(sum(result is not None for result in results), 1)
        with workspace_context(self.tenant.pk):
            self.assertEqual(LoanMonitoringPolicy.objects.filter(workspace=self.tenant).count(), 2)

    def test_competing_batches_skip_locked_loans_and_keep_one_snapshot(self):
        barrier = Barrier(2)
        def refresh(_):
            try:
                barrier.wait(timeout=10)
                with workspace_context(self.tenant.pk):
                    return reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=1)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(refresh, (1, 2)))
        self.assertEqual(sum(result["current"] for result in results), 1)
        with workspace_context(self.tenant.pk):
            self.assertEqual(LoanRiskSnapshot.objects.filter(loan=self.loan).count(), 1)

    def test_restricted_committed_invalidation_and_foreign_scope_denial(self):
        foreign = Company.objects.create(name=uuid.uuid4().hex, schema_name=uuid.uuid4().hex, owner=self.actor, creator=self.actor)
        with workspace_context(foreign.pk):
            values = model_to_dict(self.policy, exclude=("id", "workspace", "license", "created_by", "supersedes"))
            foreign_policy = LoanMonitoringPolicy.objects.create(workspace=foreign, **values)
        with workspace_context(self.tenant.pk):
            snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        role = connection.ops.quote_name("monitor_commit_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with workspace_context(self.tenant.pk):
                with connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL ROLE {role}")
                self.assertFalse(LoanMonitoringPolicy.objects.filter(pk=foreign_policy.pk).exists())
                self.assertEqual(get_risk_portfolio_summary().loan_count, 1)
                bad = LoanMonitoringPolicy(workspace=self.tenant, version=2, supersedes_id=foreign_policy.pk,
                    effective_from=self.today, compliance_profile="bad", ltv_warning_ratio="0.7",
                    ltv_breach_ratio="0.8", ltv_critical_ratio="0.9", created_by=self.actor, amendment_reason="bad linkage")
                with self.assertRaises(DatabaseError), transaction.atomic():
                    bad.save_base(raw=True, force_insert=True)
                Rate.objects.create(rate_source=self.source, buying_rate=3400, selling_rate=3500)
            self.assertIsNone(current_workspace_id())
            with workspace_context(self.tenant.pk):
                snapshot.refresh_from_db()
                self.assertEqual(snapshot.status, "STALE")
            with workspace_context(foreign.pk):
                with connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL ROLE {role}")
                self.assertEqual(get_risk_portfolio_summary().loan_count, 0)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_upgrade_preserves_policy_and_invalidates_projection(self):
        with workspace_context(self.tenant.pk):
            snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
            other = PawnLoan.objects.create(workspace=self.tenant, license=self.loan.license,
                series=self.loan.series, borrower=self.loan.borrower, product_version=self.loan.product_version,
                loan_number=uuid.uuid4().hex, principal_amount=1000, monthly_interest_rate=2)
            failed = LoanRiskSnapshot.objects.create(workspace=self.tenant, loan=other,
                as_of_date=self.today, status="ERROR", error_message="First assessment failed")
            original = (self.policy.rate_freshness_days, self.policy.effective_from, self.policy.created_by_id)
        targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate([("loans", "0005_pawnreleasebatch_pawnreleasebatchline_and_more")])
        finally:
            MigrationExecutor(connection).migrate(targets)
        with workspace_context(self.tenant.pk):
            self.policy.refresh_from_db()
            snapshot.refresh_from_db()
            self.assertEqual((self.policy.rate_freshness_days, self.policy.effective_from, self.policy.created_by_id), original)
            self.assertIsNone(self.policy.supersedes_id)
            self.assertEqual(snapshot.status, "STALE")
            failed.refresh_from_db()
            self.assertEqual(failed.status, "ERROR")
            self.assertEqual(failed.error_message, "First assessment failed")
