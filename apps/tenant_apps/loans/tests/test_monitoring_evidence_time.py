"""Assessment-time boundaries using actual quote/appraisal and worker records."""
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import CollateralAppraisal, LoanRiskEvent, LoanRiskSnapshot
from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio_summary, snapshot_is_current
from apps.tenant_apps.loans.services.risk_snapshots import (
    RiskSnapshotRefreshError, refresh_loan_risk_snapshot, reassess_pawn_loans_batch,
)
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.rates.models import Rate


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MonitoringEvidenceTimeTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)

    @classmethod
    def get_test_schema_name(cls):
        return "monitoring-evidence-time"

    def setUp(self):
        self.instant = timezone.make_aware(datetime.combine(timezone.localdate(), time(10)))
        clock = patch("django.utils.timezone.now", return_value=self.instant)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.quote_count = 0

    def make_loan(self, method):
        fixtures.CollateralReappraisalTests.make_loan(self, method=method)

    def make_quote(self, amount, effective_at, **changes):
        self.quote_count += 1
        with patch("django.utils.timezone.now", return_value=self.instant - timedelta(minutes=self.quote_count)):
            return Rate.objects.create(rate_source=self.source, buying_rate=amount,
                selling_rate=amount, effective_at=effective_at, **changes)

    def valuation(self, day=None):
        return get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=day or self.today)

    def test_live_rate_ignores_later_today_quote(self):
        self.make_loan("CALCULATED_METAL_VALUE")
        current = self.make_quote(3000, self.instant - timedelta(hours=1))
        self.make_quote(9000, self.instant + timedelta(hours=6))
        valuation = self.valuation()
        self.assertEqual(valuation.items[0].rate_id, current.pk)
        self.assertEqual(valuation.eligible_collateral_value, Decimal("3000"))

    def test_live_appraisal_ignores_later_today_approval(self):
        self.make_loan("LATEST_APPRAISAL")
        current = fixtures.CollateralReappraisalTests.reassess(self, appraised_value=Decimal("2500"))
        CollateralAppraisal.objects.create(workspace=self.tenant, collateral_item=self.item,
            version=3, supersedes=current, effective_at=self.instant + timedelta(hours=6),
            appraised_value=9000, method="EXTERNAL_REPORT", status="APPROVED",
            evidence_reference="Fictional future-effective inspection", review_notes="Timing fixture",
            created_by=self.actor)
        valuation = self.valuation()
        self.assertEqual(valuation.items[0].appraisal_id, current.pk)
        self.assertEqual(valuation.eligible_collateral_value, Decimal("2500"))

    def test_evidence_effective_exactly_now_is_eligible_and_dated_reports_use_day_end(self):
        self.make_loan("CALCULATED_METAL_VALUE")
        yesterday = self.instant - timedelta(days=1)
        earlier = self.make_quote(2500, yesterday - timedelta(hours=1))
        day_end = self.make_quote(2600, yesterday + timedelta(hours=6))
        exact = self.make_quote(3000, self.instant)
        self.assertEqual(self.valuation().items[0].rate_id, exact.pk)
        dated = self.valuation(yesterday.date())
        self.assertEqual(dated.items[0].rate_id, day_end.pk)
        self.assertNotEqual(dated.items[0].rate_id, earlier.pk)
        self.assertEqual(timezone.localtime(dated.evidence_at).time(), time.max)

    def test_saved_assessment_expires_and_worker_picks_up_scheduled_quote(self):
        self.make_loan("CALCULATED_METAL_VALUE")
        self.make_quote(3000, self.instant - timedelta(hours=1))
        future_at = self.instant + timedelta(hours=6)
        future = self.make_quote(1500, future_at)
        financial_before = list(self.loan.loan_events.values_list("pk", "payload_fingerprint"))
        snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        self.assertEqual(snapshot.collateral_value, Decimal("3000"))
        self.assertEqual(parse_datetime(snapshot.source_provenance["valuation"]["evidence_at"]), self.instant)
        self.assertEqual(parse_datetime(snapshot.source_provenance["valuation"]["next_evidence_at"]), future_at)
        self.assertTrue(snapshot_is_current(snapshot, self.today))
        self.assertEqual(get_risk_portfolio_summary().current_count, 1)
        self.clock.return_value = future_at
        self.assertFalse(snapshot_is_current(snapshot, self.today))
        summary = get_risk_portfolio_summary()
        self.assertEqual((summary.current_count, summary.stale_count), (0, 1))
        self.assertEqual(get_dashboard_health_summary(workspace=self.tenant)["current_count"], 0)
        result = reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today)
        self.assertEqual(result, {"selected": 1, "current": 1, "errors": []})
        snapshot.refresh_from_db()
        self.assertTrue(snapshot_is_current(snapshot, self.today))
        self.assertEqual(snapshot.collateral_value, Decimal("1500"))
        self.assertEqual(snapshot.source_provenance["valuation_rate_ids"], [future.pk])
        self.assertEqual(financial_before, list(self.loan.loan_events.values_list("pk", "payload_fingerprint")))

    def test_scheduled_appraisal_expires_saved_result_without_another_write(self):
        self.make_loan("LATEST_APPRAISAL")
        current = fixtures.CollateralReappraisalTests.reassess(self)
        future_at = self.instant + timedelta(hours=6)
        future = CollateralAppraisal.objects.create(workspace=self.tenant, collateral_item=self.item,
            version=3, supersedes=current, effective_at=future_at, appraised_value=1500,
            method="EXTERNAL_REPORT", status="APPROVED", evidence_reference="Fictional scheduled inspection",
            review_notes="Timing fixture", created_by=self.actor)
        snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        self.assertEqual(snapshot.collateral_value, Decimal("2500"))
        self.clock.return_value = future_at
        self.assertFalse(snapshot_is_current(snapshot, self.today))
        self.assertEqual(get_risk_portfolio_summary().stale_count, 1)
        result = reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today)
        self.assertEqual(result["current"], 1)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.source_provenance["appraisal_ids"], [future.pk])

    def test_only_relevant_evidence_schedules_expiry(self):
        self.make_loan("CALCULATED_METAL_VALUE")
        self.make_quote(3000, self.instant - timedelta(hours=1))
        self.make_quote(9000, self.instant + timedelta(hours=1), currency="USD")
        self.make_quote(9000, self.instant + timedelta(hours=2), purity="22k")
        fixtures.CollateralReappraisalTests.reassess(self)
        self.assertIsNone(self.valuation().next_evidence_at)

    def test_crossing_scheduled_evidence_before_commit_discards_result(self):
        self.make_loan("CALCULATED_METAL_VALUE")
        self.make_quote(3000, self.instant - timedelta(hours=1))
        future_at = self.instant + timedelta(hours=6)
        self.make_quote(1500, future_at)
        from apps.tenant_apps.loans.services import risk_snapshots

        for name in ("get_pawn_loan_risk_assessment", "_persist_transitions"):
            original = getattr(risk_snapshots, name)
            self.clock.return_value = self.instant

            def cross_boundary(*args, **kwargs):
                result = original(*args, **kwargs)
                self.clock.return_value = future_at
                return result

            with self.subTest(stage=name), patch.object(risk_snapshots, name, side_effect=cross_boundary):
                with self.assertRaisesMessage(RiskSnapshotRefreshError, "became effective"):
                    refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
            self.assertFalse(LoanRiskSnapshot.objects.filter(loan=self.loan).exists())
            self.assertFalse(LoanRiskEvent.objects.filter(loan=self.loan).exists())

    def test_explicit_cutoff_rejects_naive_wrong_day_and_future_live_instants(self):
        self.make_loan("CALCULATED_METAL_VALUE")
        for instant in (self.instant.replace(tzinfo=None), self.instant - timedelta(days=1),
                        self.instant + timedelta(hours=1)):
            with self.subTest(instant=instant), self.assertRaisesMessage(ValueError, "Evidence cutoff"):
                get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today, evidence_at=instant)
