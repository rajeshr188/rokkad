from decimal import Decimal

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    CollateralEconomicsError,
    CollateralMetal,
    CollateralTrancheInput,
    DisbursalFeeInput,
    FeeCalculationType,
    ValuationMethod,
    calculate_pawn_disbursal_economics,
)


class CollateralTrancheEconomicsTests(SimpleTestCase):
    def test_mixed_metals_reconcile_gross_interest_deductions_and_net_cash(self):
        result = calculate_pawn_disbursal_economics(
            (
                self._tranche("gold-ring", "GOLD", "5000", "2", "6000", "10000"),
                self._tranche("silver-item", "SILVER", "3000", "4", "100", "5000"),
            ),
            valuation_method=ValuationMethod.LATEST_APPRAISAL,
            maximum_ltv_ratio=Decimal("0.80"),
            advance_interest_periods=1,
            fees=(
                DisbursalFeeInput(
                    code="DOC",
                    name="Document fee",
                    calculation_type=FeeCalculationType.FIXED,
                    value=Decimal("50"),
                ),
            ),
        )

        self.assertEqual(result.gross_principal, Decimal("8000.00"))
        self.assertEqual(result.monthly_interest, Decimal("220.00"))
        self.assertEqual(result.effective_monthly_rate, Decimal("2.750000"))
        self.assertEqual(result.advance_interest, Decimal("220.00"))
        self.assertEqual(result.deducted_fees, Decimal("50.00"))
        self.assertEqual(result.net_disbursed, Decimal("7730.00"))

    def test_item_allocation_above_ltv_fails_with_item_reference(self):
        with self.assertRaisesRegex(
            CollateralEconomicsError,
            "gold-ring allocation 8500.00 exceeds its maximum 8000.00",
        ):
            calculate_pawn_disbursal_economics(
                (self._tranche("gold-ring", "GOLD", "8500", "2", "6000", "10000"),),
                valuation_method=ValuationMethod.LATEST_APPRAISAL,
                maximum_ltv_ratio=Decimal("0.80"),
            )

    def test_lower_of_both_uses_calculated_value_and_rounds_ltv_down(self):
        result = calculate_pawn_disbursal_economics(
            (self._tranche("ring", "GOLD", "8000", "2", "6000", "12000"),),
            valuation_method=ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL,
            maximum_ltv_ratio=Decimal("0.80"),
        )

        item = result.tranches[0]
        self.assertEqual(item.calculated_metal_value, Decimal("10992.00"))
        self.assertEqual(item.selected_value, Decimal("10992.00"))
        self.assertEqual(item.maximum_principal, Decimal("8793.60"))

    def test_percentage_fee_and_multiple_advance_periods_are_configurable(self):
        result = calculate_pawn_disbursal_economics(
            (self._tranche("ring", "GOLD", "5000", "2", "6000", "10000"),),
            valuation_method=ValuationMethod.LATEST_APPRAISAL,
            maximum_ltv_ratio=Decimal("0.80"),
            advance_interest_periods=2,
            fees=(
                DisbursalFeeInput(
                    code="PROC",
                    name="Processing fee",
                    calculation_type=FeeCalculationType.PERCENTAGE,
                    value=Decimal("1.5"),
                ),
            ),
        )

        self.assertEqual(result.advance_interest, Decimal("200.00"))
        self.assertEqual(result.deducted_fees, Decimal("75.00"))
        self.assertEqual(result.net_disbursed, Decimal("4725.00"))

    def test_missing_inputs_and_nonpositive_net_fail_closed(self):
        missing_rate = self._tranche("ring", "GOLD", "5000", "2", None, "10000")
        with self.assertRaisesRegex(CollateralEconomicsError, "a usable metal valuation rate"):
            calculate_pawn_disbursal_economics(
                (missing_rate,),
                valuation_method=ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL,
                maximum_ltv_ratio=Decimal("0.80"),
            )
        with self.assertRaisesRegex(CollateralEconomicsError, "positive net disbursal"):
            calculate_pawn_disbursal_economics(
                (self._tranche("ring", "GOLD", "100", "100", "6000", "10000"),),
                valuation_method=ValuationMethod.LATEST_APPRAISAL,
                maximum_ltv_ratio=Decimal("0.80"),
                advance_interest_periods=1,
            )

    @staticmethod
    def _tranche(reference, metal, principal, rate, metal_rate, appraisal):
        return CollateralTrancheInput(
            reference=reference,
            metal=CollateralMetal(metal),
            net_weight=Decimal("2"),
            purity_percentage=Decimal("91.6"),
            allocated_principal=Decimal(principal),
            monthly_interest_rate=Decimal(rate),
            metal_rate_per_unit=(Decimal(metal_rate) if metal_rate else None),
            latest_appraised_value=(Decimal(appraisal) if appraisal else None),
        )
