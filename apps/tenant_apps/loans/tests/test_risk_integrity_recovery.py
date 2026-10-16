from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import LoanRiskAlert, LoanRiskEvent, LoanRiskSnapshot
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.selectors.delinquency import get_pawn_loan_delinquency
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
from apps.tenant_apps.loans.selectors.obligation_state import calculate_obligation_state_as_of, get_active_repayment_schedule_as_of
from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot, RiskSnapshotRefreshError
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RiskIntegrityRecoveryTests(WorkspaceTestCase):
    get_test_schema_name = classmethod(lambda cls: "risk-integrity-recovery")
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)

    def setUp(self):
        fixtures.CollateralReappraisalTests.make_loan(self, method="LATEST_APPRAISAL")

    def refresh(self):
        return refresh_loan_risk_snapshot(self.loan.pk, as_of_date=timezone.localdate())

    def revalue(self, value):
        record_collateral_reappraisal(loan_id=self.loan.pk, item_id=self.item.pk, actor=self.actor,
            appraised_value=Decimal(value), method="PHYSICAL_INSPECTION", evidence_reference="Synthetic current inspection",
            review_notes="Test current condition", expected_version=self.item.appraisals.count())
        return self.refresh()

    def alert(self, kind="LTV_BREACH"):
        return LoanRiskAlert.objects.get(loan=self.loan, alert_kind=kind, status="OPEN")

    def test_worsening_keeps_one_open_alert_and_updates_its_severity(self):
        self.revalue("1400")
        alert = self.alert()
        self.assertEqual(alert.severity, "HIGH")
        source = alert.source_event_id
        last = LoanRiskEvent.objects.filter(loan=self.loan).latest("pk").pk
        self.revalue("1000")
        alert.refresh_from_db()
        self.assertEqual(alert.status, "OPEN")
        self.assertEqual(alert.severity, "CRITICAL")
        self.assertEqual(alert.source_event_id, source)
        self.assertFalse(LoanRiskEvent.objects.filter(loan=self.loan, pk__gt=last, event_type="LTV_BREACH_CURED").exists())
        self.revalue("1400")
        alert.refresh_from_db()
        self.assertEqual(alert.status, "OPEN")
        self.assertEqual(alert.severity, "HIGH")

    def test_unknown_valuation_retains_alert_until_known_recovery(self):
        self.revalue("1000")
        alert = self.alert()
        financial = list(self.loan.loan_events.values())
        last = LoanRiskEvent.objects.filter(loan=self.loan).latest("pk").pk
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=91)):
            snapshot = self.refresh()
            self.assertIn("VALUATION_UNKNOWN", snapshot.flags)
            alert.refresh_from_db()
            self.assertEqual((alert.status, alert.severity, alert.resolved_by_event_id), ("OPEN", "CRITICAL", None))
            self.assertFalse(LoanRiskEvent.objects.filter(loan=self.loan, pk__gt=last, event_type__endswith="_CURED").exists())
            self.revalue("4000")
        alert.refresh_from_db()
        self.assertEqual(alert.status, "RESOLVED")
        self.assertEqual(alert.resolved_by_event.event_type, "VALUATION_ERROR_CURED")
        self.assertEqual(list(self.loan.loan_events.values()), financial)

    def test_financial_integrity_failure_clears_unsafe_metrics_but_keeps_alerts(self):
        self.revalue("1000")
        alert = self.alert()
        financial = list(self.loan.loan_events.values())
        exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today)
        broken = replace(exposure, integrity_findings=("Obligation is over-allocated.",))
        with patch("apps.tenant_apps.loans.services.risk_snapshots.get_pawn_loan_exposure", return_value=broken):
            with self.assertRaisesMessage(RiskSnapshotRefreshError, "Financial evidence is inconsistent"):
                self.refresh()
            event_count = LoanRiskEvent.objects.filter(loan=self.loan).count()
            with self.assertRaises(RiskSnapshotRefreshError):
                self.refresh()
            self.assertEqual(LoanRiskEvent.objects.filter(loan=self.loan).count(), event_count)
        snapshot = LoanRiskSnapshot.objects.get(loan=self.loan)
        self.assertEqual(snapshot.status, "ERROR")
        self.assertEqual(snapshot.performance_class, "UNKNOWN")
        self.assertIsNone(snapshot.days_past_due)
        self.assertIsNone(snapshot.exposure)
        self.assertIsNone(snapshot.overdue)
        self.assertIsNone(snapshot.ltv_ratio)
        self.assertEqual(snapshot.source_provenance["financial"]["calculation_status"], "INCONSISTENT")
        alert.refresh_from_db()
        self.assertEqual((alert.status, alert.severity), ("OPEN", "CRITICAL"))
        failure = self.alert("ASSESSMENT_FAILURE")
        from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
        summary = get_dashboard_health_summary(workspace=self.tenant)
        self.assertEqual(summary["error_count"], 1)
        self.assertIsNone(summary["economic_exposure"])
        self.refresh()
        failure.refresh_from_db()
        self.assertEqual(failure.status, "RESOLVED")
        self.assertEqual(failure.resolved_by_event.event_type, "ASSESSMENT_ERROR_RECOVERED")
        self.assertEqual(self.alert().pk, alert.pk)
        self.revalue("4000")
        alert.refresh_from_db()
        self.assertEqual(alert.resolved_by_event.event_type, "LTV_CRITICAL_CURED")
        self.assertEqual(list(self.loan.loan_events.values()), financial)

    def test_missing_schedule_is_unknown_financial_evidence_on_live_paths(self):
        self.revalue("4000")
        with patch("apps.tenant_apps.loans.selectors.financial_inputs.get_active_repayment_schedule_as_of", return_value=None):
            exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today)
            self.assertTrue(any("no active repayment schedule" in finding for finding in exposure.integrity_findings))
            with self.assertRaisesMessage(ValueError, "no active repayment schedule"):
                get_pawn_loan_risk_assessment(self.loan.pk, as_of_date=self.today)
            collateral = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today, _exposure=exposure)
            self.assertEqual(collateral.eligible_collateral_value, Decimal("4000"))
            self.assertIsNone(collateral.ltv.ltv_ratio)
            self.assertIn("FINANCIAL_EVIDENCE_INCONSISTENT", collateral.ltv.blockers)
        with patch("apps.tenant_apps.loans.selectors.financial_inputs.get_active_repayment_schedule_as_of", return_value=None):
            with self.assertRaisesMessage(ValueError, "no active repayment schedule"):
                get_pawn_loan_delinquency(self.loan.pk, as_of_date=self.today)

    def test_overallocated_obligation_state_cannot_be_classified_as_valid_dpd(self):
        schedule = get_active_repayment_schedule_as_of(self.loan, self.today)
        state = calculate_obligation_state_as_of(schedule, self.today)
        invalid = replace(state, integrity_findings=("Obligation is over-allocated.",))
        with patch("apps.tenant_apps.loans.selectors.financial_inputs.calculate_obligation_state_as_of", return_value=invalid):
            with self.assertRaisesMessage(ValueError, "Delinquency evidence is inconsistent"):
                get_pawn_loan_delinquency(self.loan.pk, as_of_date=self.today)

    def test_identical_same_day_breach_recurs_as_a_new_incident(self):
        with patch("django.utils.timezone.now", return_value=timezone.now()):
            self.revalue("4000")
            first = self.revalue("1400")
            first_alert = self.alert()
            self.revalue("4000")
            first_alert.refresh_from_db()
            self.assertEqual(first_alert.status, "RESOLVED")
            self.assertIsNotNone(first_alert.resolved_by_event_id)
            second = self.revalue("1400")
            second_alert = self.alert()
            self.assertEqual(first.assessment_fingerprint, second.assessment_fingerprint)
            self.assertNotEqual(first_alert.pk, second_alert.pk)
            self.assertNotEqual(first_alert.source_event_id, second_alert.source_event_id)
            count = LoanRiskEvent.objects.filter(loan=self.loan).count()
            self.refresh()
            self.assertEqual(LoanRiskEvent.objects.filter(loan=self.loan).count(), count)
            self.assertEqual(self.alert().pk, second_alert.pk)

    def test_actual_payment_cures_dpd_with_linked_event(self):
        from apps.tenant_apps.loans.services import finalize_pawn_loan_accrual, record_pawn_loan_repayment
        from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=300)):
            snapshot = self.revalue("4000")
            self.assertGreater(snapshot.days_past_due, 0)
            alert = self.alert("DPD_WORSENING")
            for period in range(1, 13):
                finalize_pawn_loan_accrual(self.loan.pk, period_number=period, actor=self.actor)
            balance = get_servicing_position(self.loan, as_of_date=timezone.localdate()).balance
            record_pawn_loan_repayment(self.loan.pk, amount=balance.total_due,
                                      request_key="risk-dpd-cure", actor=self.actor)
            snapshot = self.refresh()
            self.assertEqual(snapshot.days_past_due, 0)
        alert.refresh_from_db()
        self.assertEqual(alert.status, "RESOLVED")
        self.assertEqual(alert.resolved_by_event.event_type, "DELINQUENCY_CURED")

    def test_retained_alert_can_clear_after_unknown_without_its_old_flags(self):
        self.revalue("1400")
        alert = self.alert()
        # Simulate a legacy retained open alert while the current projection's
        # old flags are absent. Resolution still needs today's own evidence.
        LoanRiskSnapshot.objects.filter(loan=self.loan).update(flags=[], ltv_ratio=None)
        self.revalue("4000")
        alert.refresh_from_db()
        self.assertEqual(alert.status, "RESOLVED")
        self.assertEqual(alert.resolved_by_event.event_type, "ALERT_CONDITION_CLEARED")
        self.assertEqual(alert.resolved_by_event.new_value["cleared"], True)
