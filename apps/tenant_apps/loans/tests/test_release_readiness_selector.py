from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
    PawnLoanState,
    ValuationMethod,
)
from apps.tenant_apps.loans.selectors import calculate_pawn_loan_release_readiness
from apps.tenant_apps.rates.facade import RATE_FOUND, RATE_MISSING


class PawnLoanReleaseReadinessTests(SimpleTestCase):
    as_of_date = date(2026, 8, 3)

    def test_calculated_appraisal_and_lower_of_both_snapshot_inputs(self):
        item = self._item(1, appraisal="48000", net_weight="9", purity="91.6")
        expected = {
            ValuationMethod.CALCULATED_METAL_VALUE: Decimal("49464.00"),
            ValuationMethod.LATEST_APPRAISAL: Decimal("48000.00"),
            ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL: Decimal("48000.00"),
        }

        for method, amount in expected.items():
            with self.subTest(method=method):
                readiness = self._calculate(
                    items=(item,),
                    selected=(1,),
                    policy=self._policy(method),
                )
                snapshot = readiness.item_valuations[0]
                self.assertTrue(readiness.ready)
                self.assertEqual(snapshot.valuation_amount, amount)
                self.assertEqual(snapshot.net_weight, Decimal("9"))
                self.assertEqual(snapshot.purity_percentage, Decimal("91.6"))
                self.assertEqual(snapshot.latest_appraised_value, Decimal("48000.00"))
                if method != ValuationMethod.LATEST_APPRAISAL:
                    self.assertEqual(snapshot.rate_id, 71)
                    self.assertEqual(snapshot.rate_per_unit, Decimal("6000"))
                    self.assertEqual(snapshot.calculated_metal_value, Decimal("49464.00"))
                    self.assertEqual(snapshot.rate_source_name, "Market feed")

    def test_partial_release_settles_dues_then_reduces_principal_to_ltv(self):
        readiness = self._calculate(
            items=(
                self._item(1, appraisal="10000"),
                self._item(2, appraisal="50000"),
            ),
            selected=(1,),
            policy=self._policy(ValuationMethod.LATEST_APPRAISAL),
            balance=self._balance(principal="50000", interest="2000", fees="500"),
        )

        self.assertTrue(readiness.ready)
        self.assertFalse(readiness.is_full_release)
        self.assertEqual(readiness.selected_collateral_value, Decimal("10000.00"))
        self.assertEqual(readiness.retained_collateral_value, Decimal("50000.00"))
        self.assertEqual(readiness.fees_and_interest_settlement, Decimal("2500.00"))
        self.assertEqual(readiness.principal_reduction_required, Decimal("10000.00"))
        self.assertEqual(readiness.minimum_settlement, Decimal("12500.00"))
        self.assertEqual(
            readiness.principal_after_minimum_settlement,
            Decimal("40000.00"),
        )
        self.assertEqual(readiness.retained_ltv_after_minimum_settlement, Decimal("0.8"))

    def test_ltv_boundary_rounds_allowed_principal_down(self):
        readiness = self._calculate(
            items=(
                self._item(1, appraisal="10000"),
                self._item(2, appraisal="50000.01"),
            ),
            selected=(1,),
            policy=self._policy(ValuationMethod.LATEST_APPRAISAL),
            balance=self._balance(principal="40000.01"),
        )

        self.assertEqual(readiness.retained_collateral_value, Decimal("50000.01"))
        self.assertEqual(readiness.principal_reduction_required, Decimal("0.01"))
        self.assertLessEqual(
            readiness.retained_ltv_after_minimum_settlement,
            Decimal("0.80"),
        )

    def test_full_release_requires_the_entire_balance(self):
        readiness = self._calculate(
            items=(self._item(1, appraisal="60000"),),
            selected=(1,),
            policy=self._policy(ValuationMethod.LATEST_APPRAISAL),
            balance=self._balance(principal="50000", interest="1000", fees="250"),
        )

        self.assertTrue(readiness.is_full_release)
        self.assertEqual(readiness.retained_collateral_value, Decimal("0.00"))
        self.assertEqual(readiness.principal_reduction_required, Decimal("50000.00"))
        self.assertEqual(readiness.minimum_settlement, Decimal("51250.00"))
        self.assertIsNone(readiness.retained_ltv_after_minimum_settlement)

    def test_previously_released_items_are_not_retained_security(self):
        readiness = self._calculate(
            items=(
                self._item(1, appraisal="10000"),
                self._item(
                    2,
                    appraisal=None,
                    custody=CollateralCustodyState.WITH_CUSTOMER,
                ),
            ),
            selected=(1,),
            policy=self._policy(ValuationMethod.LATEST_APPRAISAL),
            balance=self._balance(principal="5000"),
        )

        self.assertTrue(readiness.ready)
        self.assertTrue(readiness.is_full_release)
        self.assertEqual(readiness.retained_item_ids, ())
        self.assertEqual(readiness.retained_collateral_value, Decimal("0.00"))

    def test_lender_held_released_and_unknown_items_fail_closed(self):
        readiness = self._calculate(
            items=(
                self._item(
                    1,
                    appraisal="10000",
                    custody=CollateralCustodyState.WITH_FUNDING_LENDER,
                ),
                self._item(
                    2,
                    appraisal="10000",
                    custody=CollateralCustodyState.WITH_CUSTOMER,
                ),
            ),
            selected=(1, 2, 999),
            policy=self._policy(ValuationMethod.LATEST_APPRAISAL),
        )

        self.assertFalse(readiness.ready)
        self.assertEqual(
            {blocker.code for blocker in readiness.blockers},
            {
                "COLLATERAL_NOT_FOUND",
                "COLLATERAL_WITH_FUNDING_LENDER",
                "COLLATERAL_ALREADY_RELEASED",
            },
        )
        self.assertIsNone(readiness.minimum_settlement)

    def test_missing_rate_appraisal_and_posting_readiness_are_actionable(self):
        missing_rate = lambda **_kwargs: SimpleNamespace(
            status=RATE_MISSING,
            rate=None,
        )
        readiness = calculate_pawn_loan_release_readiness(
            self._loan(),
            collateral_items=(self._item(1, appraisal=None),),
            balance=self._balance(posting_ready=False),
            policy_snapshot=self._policy(
                ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL
            ),
            selected_item_ids=(1,),
            as_of_date=self.as_of_date,
            rate_resolver=missing_rate,
        )

        self.assertEqual(
            {blocker.code for blocker in readiness.blockers},
            {
                "ACCOUNTING_NOT_READY",
                "METAL_RATE_MISSING_RATE",
                "LATEST_APPRAISAL_REQUIRED",
            },
        )
        self.assertIsNone(readiness.item_valuations[0].valuation_amount)

    def test_selector_uses_rates_public_facade_not_rate_models(self):
        source = (
            Path(__file__).parents[1] / "selectors" / "release_readiness.py"
        ).read_text(encoding="utf-8")

        self.assertIn("apps.tenant_apps.rates.facade", source)
        self.assertNotIn("apps.tenant_apps.rates.models", source)

    def _calculate(self, *, items, selected, policy, balance=None):
        return calculate_pawn_loan_release_readiness(
            self._loan(),
            collateral_items=items,
            balance=balance or self._balance(),
            policy_snapshot=policy,
            selected_item_ids=selected,
            as_of_date=self.as_of_date,
            rate_resolver=self._rate_resolver,
        )

    def _loan(self):
        return SimpleNamespace(pk=91, state=PawnLoanState.ACTIVE.value)

    def _policy(self, method):
        return SimpleNamespace(
            valuation_method=method.value,
            maximum_ltv_ratio=Decimal("0.80"),
            currency_quantum=Decimal("0.01"),
        )

    def _balance(
        self,
        *,
        principal="10000",
        interest="0",
        fees="0",
        posting_ready=True,
    ):
        return SimpleNamespace(
            principal_outstanding=Decimal(principal),
            interest_outstanding=Decimal(interest),
            fees_outstanding=Decimal(fees),
            posting_ready=posting_ready,
        )

    def _item(
        self,
        pk,
        *,
        appraisal,
        net_weight="10",
        purity="100",
        custody=CollateralCustodyState.IN_VAULT,
    ):
        return SimpleNamespace(
            pk=pk,
            description=f"Item {pk}",
            metal="GOLD",
            net_weight=Decimal(net_weight),
            purity_percentage=Decimal(purity),
            latest_appraised_value=(Decimal(appraisal) if appraisal is not None else None),
            custody_state=custody.value,
        )

    def _rate_resolver(self, **_kwargs):
        return SimpleNamespace(
            status=RATE_FOUND,
            rate=SimpleNamespace(
                pk=71,
                buying_rate=Decimal("6000"),
                timestamp=datetime(2026, 8, 3, 10, 0),
                rate_source="Market feed",
            ),
        )
