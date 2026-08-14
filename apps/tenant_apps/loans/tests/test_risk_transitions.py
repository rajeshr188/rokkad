from django.test import SimpleTestCase
from apps.tenant_apps.loans.domain.risk_transitions import detect_risk_transitions


class RiskTransitionTests(SimpleTestCase):
    def projection(self, **changes):
        value = {"status": "CURRENT", "days_past_due": 0, "performance_class": "STANDARD", "severity": "LOW", "policy_identity": "p1", "flags": (), "assessment_fingerprint": "a"}
        value.update(changes); return value

    def test_initial_and_repeated_assessment(self):
        current = self.projection()
        self.assertEqual(detect_risk_transitions(None, current)[0].event_type, "ASSESSMENT_INITIALIZED")
        self.assertEqual(detect_risk_transitions(current, current), ())

    def test_delinquency_entry_bucket_change_and_cure(self):
        current = self.projection()
        entered = self.projection(days_past_due=1, flags=("PAYMENT_OVERDUE",))
        self.assertIn("DELINQUENCY_ENTERED", [row.event_type for row in detect_risk_transitions(current, entered)])
        ninety = self.projection(days_past_due=90, performance_class="SUBSTANDARD", severity="CRITICAL", flags=("DPD_SUBSTANDARD",))
        self.assertIn("DPD_BUCKET_CHANGED", [row.event_type for row in detect_risk_transitions(entered, ninety)])
        self.assertIn("DELINQUENCY_CURED", [row.event_type for row in detect_risk_transitions(ninety, current)])

    def test_ltv_and_error_transitions_are_bidirectional(self):
        current = self.projection()
        breach = self.projection(severity="HIGH", flags=("LTV_BREACH",))
        self.assertIn("LTV_BREACH_ENTERED", [row.event_type for row in detect_risk_transitions(current, breach)])
        self.assertIn("LTV_BREACH_CURED", [row.event_type for row in detect_risk_transitions(breach, current)])
        error = self.projection(status="ERROR", severity="HIGH", flags=("VALUATION_UNKNOWN",))
        types = [row.event_type for row in detect_risk_transitions(current, error)]
        self.assertIn("ASSESSMENT_ERROR_ENTERED", types)
        self.assertIn("VALUATION_ERROR_ENTERED", types)
        self.assertIn("ASSESSMENT_ERROR_RECOVERED", [row.event_type for row in detect_risk_transitions(error, current)])
