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
        self.assertNotIn("VALUATION_ERROR_ENTERED", types)  # Failure does not establish a valuation state.
        self.assertIn("ASSESSMENT_ERROR_RECOVERED", [row.event_type for row in detect_risk_transitions(error, current)])

    def test_worsening_ltv_and_unknown_evidence_never_emit_cure(self):
        breach = self.projection(flags=("LTV_BREACH",))
        critical = self.projection(flags=("LTV_CRITICAL",))
        unknown = self.projection(flags=("VALUATION_UNKNOWN",), ltv_ratio=None)
        types = [row.event_type for row in detect_risk_transitions(breach, critical)]
        self.assertIn("LTV_CRITICAL_ENTERED", types)
        self.assertNotIn("LTV_BREACH_CURED", types)
        for new in (unknown, self.projection(status="ERROR", days_past_due=None)):
            self.assertFalse(any(row.event_type.endswith("_CURED") for row in detect_risk_transitions(critical, new)))

    def test_improved_critical_ltv_keeps_breach_but_records_threshold_recovery(self):
        old, new = self.projection(flags=("LTV_CRITICAL",)), self.projection(flags=("LTV_BREACH",))
        types = [row.event_type for row in detect_risk_transitions(old, new)]
        self.assertIn("LTV_CRITICAL_CURED", types)
        self.assertIn("LTV_BREACH_ENTERED", types)
        self.assertNotIn("LTV_BREACH_CURED", types)

    def test_unknown_dpd_and_outdated_error_cannot_cure_delinquency(self):
        overdue = self.projection(days_past_due=30)
        self.assertNotIn("DELINQUENCY_CURED", [row.event_type for row in detect_risk_transitions(
            overdue, self.projection(days_past_due=None))])
        self.assertNotIn("ASSESSMENT_ERROR_RECOVERED", [row.event_type for row in detect_risk_transitions(
            self.projection(status="ERROR"), self.projection(status="STALE"))])
