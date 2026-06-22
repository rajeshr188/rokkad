from datetime import datetime
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.girvi.services import InterestCalculationService


class InterestCalculationPolicyTests(SimpleTestCase):
    def _aware(self, value):
        return timezone.make_aware(value, timezone.get_current_timezone())

    def test_policy_is_minimum_month_partial_full_with_grace(self):
        policy = InterestCalculationService.policy()

        self.assertEqual(policy["code"], "MINIMUM_MONTH_PARTIAL_FULL_WITH_3_DAY_GRACE")
        self.assertEqual(policy["grace_days_in_new_month"], 3)
        self.assertIn("minimum first-month charge", policy["description"])

    def test_months_between_applies_minimum_first_month_charge(self):
        start = self._aware(datetime(2026, 1, 15, 10, 0))
        end = self._aware(datetime(2026, 1, 16, 10, 0))

        self.assertEqual(InterestCalculationService.months_between(start, end), 1)
        self.assertEqual(
            InterestCalculationService.interest_due(Decimal("125.00"), start, end),
            Decimal("125.00"),
        )

    def test_months_between_counts_exact_month_boundary(self):
        start = self._aware(datetime(2026, 1, 15, 10, 0))
        end = self._aware(datetime(2026, 2, 15, 10, 0))

        self.assertEqual(InterestCalculationService.months_between(start, end), 1)
        self.assertEqual(
            InterestCalculationService.interest_due(Decimal("125.00"), start, end),
            Decimal("125.00"),
        )

    def test_months_between_counts_partial_month_as_full_after_grace(self):
        start = self._aware(datetime(2026, 1, 15, 10, 0))
        end = self._aware(datetime(2026, 3, 20, 9, 0))

        self.assertEqual(InterestCalculationService.months_between(start, end), 3)
        self.assertEqual(
            InterestCalculationService.interest_due(Decimal("125.00"), start, end),
            Decimal("375.00"),
        )

    def test_months_between_does_not_add_partial_month_in_first_three_calendar_days(self):
        start = self._aware(datetime(2026, 1, 1, 10, 0))
        end = self._aware(datetime(2026, 4, 3, 9, 0))

        self.assertEqual(InterestCalculationService.months_between(start, end), 3)
        self.assertEqual(
            InterestCalculationService.interest_due(Decimal("125.00"), start, end),
            Decimal("375.00"),
        )
