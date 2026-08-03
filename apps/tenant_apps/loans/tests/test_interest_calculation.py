from decimal import Decimal

from django.test import SimpleTestCase

from apps.tenant_apps.loans.services import (
    PawnInterestError,
    calculate_accrual_interest,
)


class PawnInterestCalculationTests(SimpleTestCase):
    def test_retains_precision_then_rounds_half_up_to_currency_quantum(self):
        unrounded, recognized = calculate_accrual_interest(
            calculation_base=Decimal("1000.01"),
            monthly_interest_rate=Decimal("1.333333"),
            period_fraction=Decimal("0.5"),
            currency_quantum=Decimal("0.01"),
        )

        self.assertEqual(unrounded, Decimal("6.66673166665"))
        self.assertEqual(recognized, Decimal("6.67"))

    def test_rejects_invalid_period_fraction(self):
        with self.assertRaises(PawnInterestError):
            calculate_accrual_interest(
                calculation_base=Decimal("1000"),
                monthly_interest_rate=Decimal("2"),
                period_fraction=Decimal("0"),
                currency_quantum=Decimal("0.01"),
            )
