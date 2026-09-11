from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from contextlib import nullcontext

from django.test import SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.loans.models import LoanRiskSnapshot
from apps.tenant_apps.loans.services.risk_snapshots import (
    RiskSnapshotRefreshError,
    _persist_transitions,
    _snapshot_values,
    reassess_pawn_loans_batch,
)


class RiskOrchestrationBoundaryTests(SimpleTestCase):
    def test_batch_size_is_bounded_before_database_work(self):
        with self.assertRaisesMessage(RiskSnapshotRefreshError, "Batch size"):
            reassess_pawn_loans_batch(workspace_id=1, as_of_date=__import__("datetime").date.today(), batch_size=1001)

    @patch(
        "apps.tenant_apps.loans.services.risk_snapshots.current_tenant_workspace_id",
        return_value=2,
    )
    def test_batch_rejects_cross_tenant_workspace_before_selection(self, _workspace):
        with self.assertRaisesMessage(RiskSnapshotRefreshError, "active tenant"):
            reassess_pawn_loans_batch(
                workspace_id=1,
                as_of_date=date(2026, 8, 13),
            )

    def test_batch_uses_skip_locked_and_active_loan_scope(self):
        queryset = MagicMock()
        queryset.filter.return_value = queryset
        queryset.exclude.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.values_list.return_value.__getitem__.return_value = ()
        manager = MagicMock()
        manager.select_for_update.return_value = queryset
        snapshot_manager = MagicMock()
        snapshot_manager.filter.return_value.values.return_value = "current-loan-subquery"
        with patch(
            "apps.tenant_apps.loans.services.risk_snapshots.current_tenant_workspace_id",
            return_value=5,
        ), patch(
            "apps.tenant_apps.loans.services.risk_snapshots.PawnLoan.objects",
            manager,
        ), patch(
            "apps.tenant_apps.loans.services.risk_snapshots.LoanRiskSnapshot.objects",
            snapshot_manager,
        ), patch(
            "apps.tenant_apps.loans.services.risk_snapshots.transaction.atomic",
            return_value=nullcontext(),
        ), patch("apps.tenant_apps.loans.services.risk_snapshots._require_active_workspace"):

            result = reassess_pawn_loans_batch(
                workspace_id=5,
                as_of_date=date(2026, 8, 13),
                batch_size=50,
            )

        manager.select_for_update.assert_called_once_with(skip_locked=True, of=("self",))
        queryset.filter.assert_called_once_with(workspace_id=5, state="ACTIVE")
        queryset.exclude.assert_called_once_with(pk__in="current-loan-subquery")
        self.assertEqual(result, {"selected": 0, "current": 0, "errors": []})

    def test_identical_transition_refresh_uses_one_idempotent_trigger(self):
        transition = SimpleNamespace(
            event_type="SEVERITY_CHANGED",
            old_value="LOW",
            new_value="MEDIUM",
        )
        snapshot = SimpleNamespace(
            workspace_id=5,
            loan_id=8,
            as_of_date=date(2026, 8, 13),
            policy_identity="monitoring-policy:4",
            status="CURRENT",
        )
        manager = MagicMock()
        manager.get_or_create.return_value = (SimpleNamespace(), False)
        with patch(
            "apps.tenant_apps.loans.services.risk_snapshots.detect_risk_transitions",
            return_value=(transition,),
        ), patch(
            "apps.tenant_apps.loans.services.risk_snapshots.LoanRiskEvent.objects",
            manager,
        ), patch(
            "apps.tenant_apps.loans.services.risk_alerts.sync_risk_alerts",
        ):
            for _ in range(2):
                _persist_transitions(
                    snapshot,
                    {"assessment_fingerprint": "old"},
                    {"assessment_fingerprint": "new"},
                )

        first = manager.get_or_create.call_args_list[0].kwargs["trigger_key"]
        second = manager.get_or_create.call_args_list[1].kwargs["trigger_key"]
        self.assertEqual(first, second)

    def test_snapshot_values_preserve_selector_authority_and_provenance(self):
        assessed_at = timezone.make_aware(datetime(2026, 8, 13, 10, 30))
        exposure = SimpleNamespace(
            total_economic_exposure=Decimal("1250.00"),
            due_now=SimpleNamespace(total=Decimal("300.00")),
            overdue=SimpleNamespace(total=Decimal("125.00")),
            ltv_basis_label="Economic exposure",
        )
        delinquency = SimpleNamespace(
            assessment=SimpleNamespace(days_past_due=7)
        )
        collateral = SimpleNamespace(
            eligible_collateral_value=Decimal("2000.00"),
            ltv=SimpleNamespace(ltv_ratio=Decimal("0.625"), exposure=Decimal("1250"), headroom=Decimal("350"), full_shortfall=Decimal("0"), status="WITHIN_LIMIT", blockers=()),
            compliance_profile="loan-policy-snapshot:91",
            items=(
                SimpleNamespace(collateral_item_id=8, appraisal_id=31, rate_id=12, rate_effective_at=assessed_at, appraisal_effective_at=assessed_at, rate_status="CURRENT", appraisal_status="CURRENT", blocker_messages=()),
                SimpleNamespace(collateral_item_id=7, appraisal_id=30, rate_id=12, rate_effective_at=assessed_at, appraisal_effective_at=assessed_at, rate_status="CURRENT", appraisal_status="CURRENT", blocker_messages=()),
            ),
        )
        assessment = SimpleNamespace(
            days_to_maturity=20,
            performance_class="WATCH",
            severity="MEDIUM",
            action_hint="CONTACT",
            flags=("DPD",),
            explanations=("Past due",),
            policy_identity="monitoring-policy:4",
            fingerprint="a" * 64,
        )

        values = _snapshot_values(
            workspace_id=5,
            as_of_date=date(2026, 8, 13),
            exposure=exposure,
            delinquency=delinquency,
            collateral=collateral,
            assessment=assessment,
            input_fingerprint="b" * 64,
            assessed_at=assessed_at,
        )

        self.assertEqual(values["exposure"], exposure.total_economic_exposure)
        self.assertEqual(values["due"], exposure.due_now.total)
        self.assertEqual(values["overdue"], exposure.overdue.total)
        self.assertEqual(values["days_past_due"], 7)
        self.assertEqual(values["collateral_value"], Decimal("2000.00"))
        self.assertEqual(values["ltv_ratio"], Decimal("0.625"))
        self.assertEqual(values["status"], LoanRiskSnapshot.Status.CURRENT)
        self.assertEqual(values["source_provenance"]["appraisal_ids"], [30, 31])
        self.assertEqual(values["source_provenance"]["valuation_rate_ids"], [12])
        self.assertEqual(values["source_provenance"]["collateral_item_ids"], [7, 8])
        self.assertEqual(values["source_provenance"]["coverage"]["basis"], "Economic exposure")
