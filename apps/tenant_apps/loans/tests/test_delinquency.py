from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain.delinquency import UnpaidObligation, calculate_delinquency


class DelinquencyCalculationTests(SimpleTestCase):
    def row(self, due, amount="100"):
        return UnpaidObligation(due, Decimal(amount), Decimal("0"))

    def test_due_today_is_current_and_not_overdue(self):
        result = calculate_delinquency([self.row(date(2026, 8, 11))], as_of_date=date(2026, 8, 11))
        self.assertEqual(result.days_past_due, 0)
        self.assertEqual(result.dpd_bucket, "CURRENT")
        self.assertEqual(result.due, Decimal("100"))
        self.assertEqual(result.overdue, Decimal("0"))

    def test_boundaries_and_grace_do_not_change_regulatory_dpd(self):
        due = date(2026, 1, 1)
        expected = {1: "DPD_1_29", 29: "DPD_1_29", 30: "DPD_30_59", 59: "DPD_30_59", 60: "DPD_60_89", 89: "DPD_60_89", 90: "DPD_90_PLUS"}
        for dpd, bucket in expected.items():
            with self.subTest(dpd=dpd):
                result = calculate_delinquency([self.row(due)], as_of_date=date(2026, 1, 1).fromordinal(due.toordinal() + dpd), operational_grace_days=3)
                self.assertEqual(result.days_past_due, dpd)
                self.assertEqual(result.dpd_bucket, bucket)
                self.assertEqual(result.escalation_eligible, dpd > 3)

    def test_partial_payment_keeps_oldest_due_until_fully_cured(self):
        rows = [self.row(date(2026, 6, 1), "1"), self.row(date(2026, 7, 1), "100")]
        result = calculate_delinquency(rows, as_of_date=date(2026, 8, 1))
        self.assertEqual(result.oldest_unpaid_due_date, date(2026, 6, 1))
        cured = calculate_delinquency([self.row(date(2026, 6, 1), "0"), rows[1]], as_of_date=date(2026, 8, 1))
        self.assertEqual(cured.oldest_unpaid_due_date, date(2026, 7, 1))

    def test_full_cure_returns_current(self):
        result = calculate_delinquency([self.row(date(2026, 1, 1), "0")], as_of_date=date(2026, 8, 1))
        self.assertEqual(result.days_past_due, 0)
        self.assertFalse(result.escalation_eligible)
