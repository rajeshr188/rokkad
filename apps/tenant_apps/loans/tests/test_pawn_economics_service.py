from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch, ANY

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import CollateralMetal
from apps.tenant_apps.loans.services.pawn_economics import (
    resolve_pawn_draft_economics,
)


class PawnEconomicsResolutionTests(SimpleTestCase):
    @patch("apps.tenant_apps.loans.services.pawn_economics.resolve_pawn_loan_fee_policies", return_value=())
    @patch("apps.tenant_apps.loans.services.pawn_economics.get_origination_quote_rows")
    @patch("apps.tenant_apps.loans.services.pawn_economics.resolve_pawn_metal_interest_rate_policy")
    @patch("apps.tenant_apps.loans.services.pawn_economics.resolve_pawn_loan_economic_policy")
    def test_calculated_valuation_uses_current_24k_buying_rate(
        self,
        resolve_policy,
        resolve_rate,
        valuation_rate,
        _resolve_fees,
    ):
        resolve_policy.return_value = SimpleNamespace(
            valuation_method="CALCULATED_METAL_VALUE",
            maximum_ltv_ratio=Decimal("0.80"),
            advance_interest_periods=1,
        )
        resolve_rate.return_value = SimpleNamespace(
            monthly_interest_rate=Decimal("2")
        )
        valuation_rate.return_value = [{"metal": "GOLD", "usable": True, "fresh": True,
            "rate": SimpleNamespace(buying_rate=Decimal("7000")), "evidence": {"rate_id": 7}}]
        item = SimpleNamespace(
            metal=CollateralMetal.GOLD,
            net_weight=Decimal("10"),
            purity_percentage=Decimal("100"),
            allocated_principal=Decimal("50000"),
            latest_appraised_value=None,
        )

        resolved = resolve_pawn_draft_economics(
            workspace_id=1,
            license_id=2,
            as_of_date=date(2026, 8, 5),
            collateral=(item,),
        )

        tranche = resolved.economics.tranches[0]
        self.assertEqual(tranche.calculated_metal_value, Decimal("70000.00"))
        self.assertEqual(tranche.maximum_principal, Decimal("56000.00"))
        self.assertEqual(resolved.economics.net_disbursed, Decimal("49000.00"))
        valuation_rate.assert_called_once_with(
            workspace_id=1, loan_date=date(2026, 8, 5), metals=("GOLD",), at=ANY,
        )
