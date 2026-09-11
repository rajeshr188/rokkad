import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import CollateralAppraisal
from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures


class ReappraisalConcurrencyTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:10]
        self.actor = get_user_model().objects.create_user(username=f"appraisal-race-{suffix}")
        self.tenant = Company.objects.create(name="Appraisal race", schema_name=f"appraisal-race-{suffix}", owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            fixtures.CollateralReappraisalTests.make_loan(self)

    def test_competing_reviews_preserve_one_successor(self):
        barrier = Barrier(2)

        def review(amount):
            try:
                barrier.wait(timeout=10)
                with workspace_context(self.tenant.pk):
                    return record_collateral_reappraisal(loan_id=self.loan.pk, item_id=self.item.pk, actor=self.actor,
                        appraised_value=amount, method="PHYSICAL_INSPECTION", evidence_reference="Inspection 1",
                        review_notes="Reviewed condition", expected_version=1).pk
            except ValidationError:
                return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(review, (2500, 2600)))
        self.assertEqual(sum(result is not None for result in results), 1)
        with workspace_context(self.tenant.pk):
            self.assertEqual(CollateralAppraisal.objects.filter(collateral_item=self.item).count(), 2)

    def test_upgrade_preserves_appraisal_and_invalidates_saved_assessment(self):
        with workspace_context(self.tenant.pk):
            snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
            self.assertEqual(snapshot.status, "CURRENT")
            original_value, original_date = self.original.appraised_value, self.original.effective_at
        before = [("loans", "0005_pawnreleasebatch_pawnreleasebatchline_and_more")]
        after = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            MigrationExecutor(connection).migrate(before)
        finally:
            MigrationExecutor(connection).migrate(after)
        with workspace_context(self.tenant.pk):
            self.original.refresh_from_db()
            snapshot.refresh_from_db()
            self.assertEqual(self.original.appraised_value, original_value)
            self.assertEqual(self.original.effective_at, original_date)
            self.assertEqual(self.original.created_by_id, self.actor.pk)
            self.assertEqual(snapshot.status, "STALE")
