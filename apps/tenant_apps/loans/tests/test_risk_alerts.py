from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.models import LoanRiskAlert, LoanRiskSnapshot
from apps.tenant_apps.loans.services.risk_alerts import _active_kinds, _alert_kind, _can_resolve, _severity


class RiskAlertProjectionTests(SimpleTestCase):
    def test_watch_classification_does_not_defer_overdue_collection_attention(self):
        from datetime import date
        from decimal import Decimal
        from apps.tenant_apps.loans.domain.risk import RiskPolicy, assess_pawn_loan_risk
        policy = RiskPolicy("watch-seven", 30, 7, 60, Decimal(".7"), Decimal(".8"), Decimal(".9"))
        common = dict(as_of_date=date(2026, 10, 16), maturity_date=date(2027, 1, 1),
            ltv_ratio=Decimal(".5"), policy=policy)
        first = assess_pawn_loan_risk(days_past_due=1, **common)
        self.assertEqual((first.performance_class, first.severity), ("STANDARD", "LOW"))
        self.assertIn(LoanRiskAlert.Kind.DPD_WORSENING,
            _active_kinds(SimpleNamespace(status="CURRENT", days_past_due=1, flags=first.flags)))
        self.assertEqual(assess_pawn_loan_risk(days_past_due=7, **common).performance_class, "WATCH")
        substandard = assess_pawn_loan_risk(days_past_due=60, **common)
        self.assertEqual(_severity(LoanRiskAlert.Kind.DPD_WORSENING,
            SimpleNamespace(flags=substandard.flags)), "CRITICAL")

    def transition(self, event_type, old=None, new=None):
        return SimpleNamespace(event_type=event_type, old_value=old, new_value=new)

    def test_material_entry_transitions_map_to_staff_alerts(self):
        self.assertEqual(
            _alert_kind(self.transition("DELINQUENCY_ENTERED")),
            LoanRiskAlert.Kind.DPD_WORSENING,
        )
        self.assertEqual(
            _alert_kind(self.transition("LTV_BREACH_ENTERED")),
            LoanRiskAlert.Kind.LTV_BREACH,
        )
        self.assertEqual(
            _alert_kind(self.transition("MATURITY_WARNING_ENTERED")),
            LoanRiskAlert.Kind.MATURITY,
        )
        self.assertEqual(
            _alert_kind(self.transition("ASSESSMENT_ERROR_ENTERED")),
            LoanRiskAlert.Kind.ASSESSMENT_FAILURE,
        )

    def test_only_worsening_dpd_bucket_changes_create_alert_work(self):
        worse = self.transition(
            "DPD_BUCKET_CHANGED",
            {"bucket": "DPD_1_29"},
            {"bucket": "DPD_30_59"},
        )
        improved = self.transition(
            "DPD_BUCKET_CHANGED",
            {"bucket": "DPD_60_89"},
            {"bucket": "DPD_30_59"},
        )
        self.assertEqual(_alert_kind(worse), LoanRiskAlert.Kind.DPD_WORSENING)
        self.assertIsNone(_alert_kind(improved))

    def test_current_snapshot_state_controls_automatic_resolution(self):
        snapshot = SimpleNamespace(
            days_past_due=2,
            flags=["LTV_BREACH", "MATURITY_APPROACHING"],
            status=LoanRiskSnapshot.Status.ERROR,
        )
        self.assertEqual(
            _active_kinds(snapshot),
            set(LoanRiskAlert.Kind.values),
        )

    def test_unknown_or_failed_evidence_cannot_resolve_existing_risk(self):
        for status in ("ERROR", "STALE"):
            snapshot = SimpleNamespace(status=status, days_past_due=0, ltv_ratio=None, flags=[])
            self.assertTrue(all(not _can_resolve(kind, snapshot) for kind in LoanRiskAlert.Kind.values))
        unknown = SimpleNamespace(status="CURRENT", days_past_due=None, ltv_ratio=None, flags=["VALUATION_UNKNOWN"])
        self.assertFalse(_can_resolve(LoanRiskAlert.Kind.DPD_WORSENING, unknown))
        self.assertFalse(_can_resolve(LoanRiskAlert.Kind.LTV_BREACH, unknown))

    def test_alert_severity_uses_its_own_condition(self):
        snapshot = SimpleNamespace(flags=["LTV_CRITICAL", "MATURITY_APPROACHING"])
        self.assertEqual(_severity(LoanRiskAlert.Kind.LTV_BREACH, snapshot), "CRITICAL")
        self.assertEqual(_severity(LoanRiskAlert.Kind.MATURITY, snapshot), "MEDIUM")
        snapshot.flags = ["DPD_SUBSTANDARD", "PAST_MATURITY"]
        self.assertEqual(_severity(LoanRiskAlert.Kind.DPD_WORSENING, snapshot), "CRITICAL")
        self.assertEqual(_severity(LoanRiskAlert.Kind.MATURITY, snapshot), "HIGH")
