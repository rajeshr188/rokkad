from decimal import Decimal
from django.test import SimpleTestCase
from apps.tenant_apps.loans.domain.ltv import calculate_ltv


class LtvCalculationTests(SimpleTestCase):
    def test_exact_limit_and_breach(self):
        exact = calculate_ltv(exposure="750", collateral_value="1000", allowed_ltv_ratio="0.75")
        self.assertEqual(exact.status, "WITHIN_LIMIT")
        self.assertEqual(exact.headroom, Decimal("0.00"))
        breach = calculate_ltv(exposure="751", collateral_value="1000", allowed_ltv_ratio="0.75")
        self.assertEqual(breach.status, "BREACH")
        self.assertEqual(breach.headroom, Decimal("-1.00"))

    def test_missing_or_blocked_value_is_unknown(self):
        missing = calculate_ltv(exposure="500", collateral_value=None, allowed_ltv_ratio="0.75")
        self.assertEqual(missing.status, "UNKNOWN")
        stale = calculate_ltv(exposure="500", collateral_value="1000", allowed_ltv_ratio="0.75", blockers=("STALE_RATE",))
        self.assertEqual(stale.status, "UNKNOWN")

    def test_full_shortfall_is_separate_from_policy_breach(self):
        result = calculate_ltv(exposure="1100", collateral_value="1000", allowed_ltv_ratio="0.75")
        self.assertEqual(result.full_shortfall, Decimal("100"))
        cured = calculate_ltv(exposure="700", collateral_value="1000", allowed_ltv_ratio="0.75")
        self.assertEqual(cured.status, "WITHIN_LIMIT")
