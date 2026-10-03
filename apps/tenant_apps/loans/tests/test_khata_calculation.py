from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain.khata import (
    Terms, DrawPosition, KhataCalculationError, anniversary, calculate_interest,
    available_draw, withdraw, revise_limit,
)


class KhataCalculationTests(SimpleTestCase):
    def quote(self, through, *, opened=date(2026, 10, 10), terms=None, frequency="MONTHLY"):
        return calculate_interest(opened_on=opened, through=through,
            terms=terms or (Terms(opened, "10000000", "1"),), frequency=frequency)

    def test_monthly_rate_is_independent_of_collection_frequency(self):
        monthly = self.quote(date(2027, 10, 10))
        annual = self.quote(date(2027, 10, 10), frequency="ANNUAL")
        self.assertEqual([p.charge for p in monthly], [Decimal("100000")] * 12)
        self.assertEqual(sum(p.charge for p in annual), Decimal("1200000"))
        self.assertEqual({p.due_on for p in annual}, {date(2027, 10, 10)})
        self.assertEqual(monthly[0].due_on, date(2026, 11, 10))

    def test_annual_early_closure_only_four_months(self):
        periods = self.quote(date(2027, 2, 10), frequency="ANNUAL")
        self.assertEqual(sum(p.charge for p in periods), Decimal("400000"))
        self.assertEqual(len(periods), 4)

    def test_opening_minimum_even_same_day_without_becoming_due_early(self):
        for day in (date(2026, 10, 10), date(2026, 10, 11), date(2026, 11, 9)):
            with self.subTest(day=day):
                period = self.quote(day)[0]
                self.assertEqual(period.charge, Decimal("100000"))
                self.assertEqual(period.due_on, date(2026, 11, 10))
        self.assertEqual(self.quote(date(2026, 10, 10))[0].segments, ())

    def test_partial_month_after_minimum_uses_actual_anniversary_days(self):
        period = self.quote(date(2026, 12, 20))[-1]
        self.assertEqual(period.charge, Decimal("32258.06"))
        self.assertEqual(period.segments[0].period_days, 31)

    def test_midperiod_change_and_opening_floor(self):
        start = date(2026, 4, 10)
        terms = (Terms(start, "10000000", "1"), Terms(date(2026, 4, 25), "15000000", "1", 2))
        full = self.quote(date(2026, 5, 10), opened=start, terms=terms)[0]
        self.assertEqual(full.charge, Decimal("125000"))
        early = self.quote(date(2026, 4, 30), opened=start, terms=terms)[0]
        self.assertEqual(early.actual_charge, Decimal("75000"))
        self.assertEqual(early.minimum_adjustment, Decimal("25000"))
        self.assertEqual(early.charge, Decimal("100000"))

    def test_reduction_and_rate_change_do_not_restart_minimum(self):
        start = date(2026, 4, 10)
        terms = (Terms(start, "10000000", "1"), Terms(date(2026, 5, 25), "5000000", "2", 2))
        periods = self.quote(date(2026, 5, 26), opened=start, terms=terms)
        self.assertEqual(periods[-1].charge, Decimal("51612.90"))
        self.assertEqual(periods[-1].minimum_adjustment, 0)

    def test_anniversaries_clamp_and_restore_including_leap_day(self):
        for year, feb_day in ((2026, 28), (2028, 29)):
            start = date(year, 1, 31)
            self.assertEqual(anniversary(start, 1), date(year, 2, feb_day))
            self.assertEqual(anniversary(start, 2), date(year, 3, 31))
        self.assertEqual(anniversary(date(2024, 2, 29), 12), date(2025, 2, 28))
        self.assertEqual(anniversary(date(2024, 2, 29), 48), date(2028, 2, 29))

    def test_revision_on_boundary_and_same_day_order(self):
        start = date(2026, 4, 10)
        terms = (Terms(start, "10000000", "1"), Terms(date(2026, 5, 10), "15000000", "1", 2),
                 Terms(date(2026, 5, 10), "20000000", "1", 3))
        periods = self.quote(date(2026, 6, 10), opened=start, terms=terms)
        self.assertEqual([p.charge for p in periods], [Decimal("100000"), Decimal("200000")])
        self.assertEqual(periods[-1].segments[0].terms.revision, 3)

    def test_opening_day_reduction_preserves_original_floor(self):
        start = date(2026, 4, 10)
        periods = self.quote(date(2026, 5, 10), opened=start,
            terms=(Terms(start, "10000000", "1"), Terms(start, "5000000", "1", 2)))
        self.assertEqual(periods[0].charge, Decimal("100000"))

    def test_exact_segments_round_once_and_annual_sums_months(self):
        start = date(2026, 4, 10)
        terms = tuple(Terms(start + timedelta(days=i), "1", "1", i + 1) for i in range(30))
        periods = self.quote(date(2026, 5, 10), opened=start, terms=terms)
        self.assertEqual(len(periods[0].segments), 30)
        self.assertEqual(periods[0].charge, Decimal("0.01"))
        annual = self.quote(date(2027, 4, 10), opened=start, terms=(Terms(start, "1", "0.5"),), frequency="ANNUAL")
        self.assertEqual(sum(p.charge for p in annual), Decimal("0.12"))

    def test_invalid_inputs_fail_explicitly(self):
        for value in (0, -1, "NaN", "Infinity", 1.1, "0.001"):
            with self.subTest(value=value), self.assertRaises(KhataCalculationError):
                Terms(date(2026, 1, 1), value, "1")
        for rate in ("-1", "NaN", "0.0000001"):
            with self.assertRaises(KhataCalculationError):
                Terms(date(2026, 1, 1), "1", rate)
        with self.assertRaises(KhataCalculationError):
            self.quote(date(2026, 10, 9))
        with self.assertRaises(KhataCalculationError):
            self.quote(date(2026, 11, 10), frequency="WEEKLY")
        with self.assertRaises(KhataCalculationError):
            self.quote(date(2026, 11, 10), terms=(Terms(date(2026, 10, 10), "1", "1", 2), Terms(date(2026, 10, 11), "1", "1", 1)))

    def test_unused_entitlement_reduces_and_never_replenishes_by_repayment(self):
        partial = revise_limit(DrawPosition("10000000", "6000000", "4000000"), new_limit="8000000")
        self.assertEqual(partial, DrawPosition("8000000", "6000000", "2000000"))
        full = revise_limit(DrawPosition("10000000", "10000000", "0"), new_limit="8000000", principal_repayment="2000000")
        self.assertEqual(full, DrawPosition("8000000", "8000000", "0"))
        increased = revise_limit(full, new_limit="15000000")
        self.assertEqual(increased.unused, Decimal("7000000"))
        with self.assertRaises(KhataCalculationError):
            revise_limit(full, new_limit="7000000")
        with self.assertRaises(KhataCalculationError):
            revise_limit(full, new_limit="8000000", principal_repayment="1")

    def test_withdrawal_limited_by_both_entitlement_and_ltv(self):
        initial = DrawPosition("10000000", "0", "10000000")
        self.assertEqual(available_draw(initial, collateral_value="1000000", ltv="0.75"), Decimal("750000"))
        after = withdraw(initial, value="750000", collateral_value="1000000", ltv="0.75")
        self.assertEqual(after.principal, Decimal("750000"))
        self.assertEqual(after.unused, Decimal("9250000"))
        with self.assertRaises(KhataCalculationError):
            withdraw(after, value="0.01", collateral_value="1000000", ltv="0.75")
        self.assertEqual(available_draw(after, collateral_value="900000", ltv="0.75"), 0)

    def test_ltv_floor_never_overstates_paise(self):
        position = DrawPosition("10", "0", "10")
        self.assertEqual(available_draw(position, collateral_value="1.01", ltv="0.75"), Decimal("0.75"))
        with self.assertRaises(KhataCalculationError):
            available_draw(position, collateral_value="1", ltv="1.01")
