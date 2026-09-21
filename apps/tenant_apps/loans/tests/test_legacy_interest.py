from datetime import date, datetime
from decimal import Decimal, localcontext

from django.test import SimpleTestCase

from apps.tenant_apps.loans.services.legacy_interest import aggregate_collection_interest, collection_calendar, collection_interest, round_rupees


class LegacyInterestTests(SimpleTestCase):
    def test_owner_january_10_examples_and_inclusive_boundaries(self):
        for end, months in (("2026-01-10", 0), ("2026-01-20", 0), ("2026-02-10", 0),
                            ("2026-02-11", 1), ("2026-02-20", 1), ("2026-03-10", 1), ("2026-03-11", 2)):
            with self.subTest(end=end):
                result = collection_interest(date(2026, 1, 10), date.fromisoformat(end), Decimal("200"))
                self.assertEqual(result["additional_months"], months)
                self.assertEqual(Decimal(result["additional_interest"]), 200 * months)
    def test_january_31_restores_original_day_after_short_month(self):
        for end, months, next_day in (("2026-02-28", 0, "2026-03-01"), ("2026-03-01", 1, "2026-04-01"),
                                      ("2026-03-31", 1, "2026-04-01"), ("2026-04-01", 2, "2026-05-01")):
            with self.subTest(end=end):
                result = collection_interest(date(2026, 1, 31), date.fromisoformat(end), Decimal("200"))
                self.assertEqual(result["additional_months"], months)
                self.assertEqual(result["next_increase_on"], next_day)
                self.assertEqual(Decimal(result["additional_interest"]), months * 200)

    def test_leap_year_and_year_rollover(self):
        self.assertEqual(collection_calendar(date(2024, 1, 31), date(2024, 2, 29))["additional_months"], 0)
        self.assertEqual(collection_calendar(date(2024, 1, 31), date(2024, 3, 1))["additional_months"], 1)
        self.assertEqual(collection_calendar(date(2024, 2, 29), date(2025, 3, 1))["next_increase_on"], "2025-03-30")
        self.assertEqual(collection_calendar(date(2025, 12, 31), date(2026, 2, 1))["additional_months"], 1)

    def test_owner_rounding_examples_are_independent_of_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            for amount, expected in (("148.20", "148"), ("148.50", "148"), ("148.80", "149"), ("149.50", "150")):
                self.assertEqual(round_rupees(Decimal(amount)), Decimal(expected))

    def test_fractional_aggregation_is_explicitly_unsupported(self):
        with self.assertRaisesRegex(ValueError, "aggregation"):
            collection_interest(date(2026, 1, 10), date(2026, 3, 11), Decimal("148.50"))

    def test_invalid_amounts_dates_and_overflow_fail_closed(self):
        for amount in (Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("1e16"), 200, "200"):
            with self.subTest(amount=str(amount)), self.assertRaises(ValueError):
                round_rupees(amount)
        for original, end in ((date(2026, 1, 2), date(2026, 1, 1)), (datetime(2026, 1, 1), date(2026, 2, 1)),
                              (date(1800, 1, 1), date(2026, 1, 1)), (date(9999, 12, 1), date(9999, 12, 31))):
            with self.subTest(original=original, end=end), self.assertRaises(ValueError):
                collection_calendar(original, end)

    def test_aggregate_rehearsal_rounds_once_after_months(self):
        for end, expected, raw in ((date(2026, 2, 10), "0", "0.00"),
                                   (date(2026, 2, 11), "148", "148.50"),
                                   (date(2026, 3, 11), "297", "297.00")):
            result = aggregate_collection_interest(date(2026, 1, 10), end, Decimal("148.50"))
            self.assertEqual(result["additional_interest"], expected)
            self.assertEqual(result["additional_interest_unrounded"], raw)
            self.assertEqual(result["rule"], "original-anniversary-upfront-inclusive/2")
        self.assertEqual(result["rounding_adjustment"], "0.00")

    def test_aggregate_keeps_calendar_and_whole_rupee_results_compatible(self):
        with localcontext() as context:
            context.prec = 2
            for end in (date(2026, 2, 28), date(2026, 3, 1), date(2026, 3, 31), date(2026, 4, 1)):
                original = collection_interest(date(2026, 1, 31), end, Decimal("200"))
                aggregate = aggregate_collection_interest(date(2026, 1, 31), end, Decimal("200"))
                for key in ("additional_interest", "additional_months", "next_increase_on"):
                    self.assertEqual(aggregate[key], original[key])

    def test_aggregate_invalid_money_and_total_overflow_fail_closed(self):
        for amount in (Decimal("NaN"), Decimal("-0.1"), "148.50", Decimal("1e16"), Decimal("9e15")):
            with self.subTest(amount=str(amount)), self.assertRaises(ValueError):
                aggregate_collection_interest(date(2026, 1, 10), date(2026, 3, 11), amount)
