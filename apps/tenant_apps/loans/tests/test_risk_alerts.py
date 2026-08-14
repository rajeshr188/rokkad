from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.models import LoanRiskAlert, LoanRiskSnapshot
from apps.tenant_apps.loans.services.risk_alerts import _active_kinds, _alert_kind


class RiskAlertProjectionTests(SimpleTestCase):
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
