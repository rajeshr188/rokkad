from datetime import date
from decimal import Decimal
from django.test import SimpleTestCase
from apps.tenant_apps.loans.web.interest_help import calculate_example, InterestExampleForm


class InterestExampleTests(SimpleTestCase):
    def example(self, **values):
        return calculate_example(**(dict(principal=10000, monthly_rate=3, start=date(2024,1,31),
            end=date(2024,3,1), method="STARTED_WEEKS", cutoff=15, lower_fraction=Decimal(".5"), advance_periods=1) | values))

    def test_calendar_clamping_leap_year_and_credit(self):
        result = self.example()
        self.assertEqual([(r["days"],r["elapsed"]) for r in result["rows"]], [(29,29),(29,2)])
        self.assertEqual(result["total"], Decimal("372.41"))
        self.assertEqual(result["additional"], Decimal("72.41"))

    def test_first_month_is_full_even_at_same_day_closure(self):
        for method in ("FULL_MONTH", "SLAB", "STARTED_WEEKS", "ACTUAL_DAYS"):
            result = self.example(end=date(2024,1,31), method=method, advance_periods=0)
            self.assertEqual(result["additional"], 300)

    def test_bounded_dates_and_decimal_inputs(self):
        with self.assertRaises(ValueError): self.example(end=date(2030,1,1))
        form = InterestExampleForm(dict(principal="NaN", monthly_rate=3, start="2024-01-31", end="2024-02-01",
            method="STARTED_WEEKS", cutoff=15, lower_fraction=".5", advance_periods=1))
        self.assertFalse(form.is_valid())
