from django.test import SimpleTestCase

from apps.tenant_apps.loans.services.risk_snapshots import RiskSnapshotRefreshError, reassess_pawn_loans_batch


class RiskOrchestrationBoundaryTests(SimpleTestCase):
    def test_batch_size_is_bounded_before_database_work(self):
        with self.assertRaisesMessage(RiskSnapshotRefreshError, "Batch size"):
            reassess_pawn_loans_batch(workspace_id=1, as_of_date=__import__("datetime").date.today(), batch_size=1001)
