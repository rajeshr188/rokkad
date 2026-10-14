from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.loans.services.risk_jobs import reassess_pawn_loans_pass
from apps.tenant_apps.loans.services.risk_snapshots import (
    RiskSnapshotRefreshError, refresh_loan_risk_snapshot,
    rebuild_current_risk_snapshots, reassess_pawn_loans_batch,
)


class LiveRiskBoundaryTests(SimpleTestCase):
    def test_non_today_service_calls_reject_before_source_selection(self):
        for days in (-1, 1):
            day = timezone.localdate() + timedelta(days=days)
            with patch("apps.tenant_apps.loans.services.risk_snapshots.current_tenant_workspace_id", return_value=5):
                for action in (
                    lambda: refresh_loan_risk_snapshot(8, as_of_date=day),
                    lambda: rebuild_current_risk_snapshots(as_of_date=day),
                    lambda: reassess_pawn_loans_batch(workspace_id=5, as_of_date=day),
                    lambda: reassess_pawn_loans_pass(workspace_id=5, as_of_date=day),
                ):
                    with self.subTest(days=days, action=action), self.assertRaisesMessage(
                        RiskSnapshotRefreshError, "only be refreshed for today"
                    ):
                        action()
