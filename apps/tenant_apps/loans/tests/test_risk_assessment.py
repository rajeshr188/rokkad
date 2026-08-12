from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from apps.tenant_apps.loans.domain.risk import RiskPolicy, assess_pawn_loan_risk
from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment


class RiskAssessmentTests(SimpleTestCase):
    policy = RiskPolicy("policy-v1", 30, 1, 90, Decimal("0.70"), Decimal("0.75"), Decimal("0.90"))

    def assess(self, **overrides):
        values = dict(as_of_date=date(2026, 8, 11), maturity_date=date(2026, 9, 10), days_past_due=0, ltv_ratio=Decimal("0.60"), policy=self.policy)
        values.update(overrides)
        return assess_pawn_loan_risk(**values)

    def test_thresholds_are_explainable_and_composable(self):
        result = self.assess(days_past_due=90, ltv_ratio=Decimal("0.91"), accounting_variance=True)
        self.assertEqual(result.performance_class, "SUBSTANDARD")
        self.assertEqual(result.severity, "CRITICAL")
        self.assertIn("DPD_SUBSTANDARD", result.flags)
        self.assertIn("LTV_CRITICAL", result.flags)
        self.assertIn("ACCOUNTING_VARIANCE", result.flags)
        self.assertEqual(len(result.flags), len(result.explanations))

    def test_missing_valuation_is_not_healthy(self):
        result = self.assess(ltv_ratio=None, valuation_blockers=("STALE_RATE",))
        self.assertIn("VALUATION_UNKNOWN", result.flags)
        self.assertEqual(result.severity, "HIGH")

    def test_cure_and_fingerprint_are_deterministic(self):
        first = self.assess(days_past_due=0, ltv_ratio=Decimal("0.60"), maturity_date=date(2027, 8, 11))
        second = self.assess(days_past_due=0, ltv_ratio=Decimal("0.60"), maturity_date=date(2027, 8, 11))
        self.assertEqual(first.flags, ())
        self.assertEqual(first.severity, "LOW")
        self.assertEqual(first.fingerprint, second.fingerprint)

    def test_maturity_and_ltv_edges(self):
        self.assertIn("MATURITY_APPROACHING", self.assess().flags)
        self.assertIn("LTV_WARNING", self.assess(ltv_ratio=Decimal("0.70")).flags)
        self.assertNotIn("LTV_BREACH", self.assess(ltv_ratio=Decimal("0.75")).flags)
        self.assertIn("LTV_BREACH", self.assess(ltv_ratio=Decimal("0.750001")).flags)

    @patch("apps.tenant_apps.loans.selectors.risk.get_pawn_loan_collateral_valuation")
    @patch("apps.tenant_apps.loans.selectors.risk.get_pawn_loan_delinquency")
    @patch("apps.tenant_apps.loans.selectors.risk.resolve_monitoring_policy")
    @patch("apps.tenant_apps.loans.selectors.risk._active_schedule_as_of")
    @patch("apps.tenant_apps.loans.selectors.risk.PawnLoan.objects.get")
    @patch("apps.tenant_apps.loans.selectors.risk.current_tenant_workspace_id", return_value=7)
    def test_selector_uses_schedule_maturity_not_nonexistent_loan_field(
        self, _workspace, get_loan, active_schedule, resolve_policy,
        delinquency, collateral,
    ):
        loan = SimpleNamespace(pk=11, license_id=3)
        get_loan.return_value = loan
        active_schedule.return_value = SimpleNamespace(maturity_date=date(2026, 12, 31))
        resolve_policy.return_value = SimpleNamespace(
            pk=2, version=1, compliance_profile="pilot",
            maturity_warning_days=30, dpd_watch_threshold=1,
            dpd_substandard_threshold=90, ltv_warning_ratio=Decimal("0.70"),
            ltv_breach_ratio=Decimal("0.80"), ltv_critical_ratio=Decimal("0.90"),
        )
        delinquency.return_value = SimpleNamespace(
            assessment=SimpleNamespace(days_past_due=0), overdue_variance=False
        )
        collateral.return_value = SimpleNamespace(
            ltv=SimpleNamespace(ltv_ratio=Decimal("0.60"), blockers=())
        )

        result = get_pawn_loan_risk_assessment(11, as_of_date=date(2026, 8, 12))

        self.assertEqual(result.days_to_maturity, 141)
