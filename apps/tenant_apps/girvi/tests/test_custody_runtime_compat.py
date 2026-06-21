from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.custody_tracking import (
    ItemCustodyQuerySet,
    RepledgeHistory,
    TakenLoanCollateralMixin,
)


class CustodyRuntimeCompatibilityTests(SimpleTestCase):
    def test_collateral_items_uses_active_loan_item_model_from_app_registry(self):
        loan_item_model = MagicMock()
        loan = TakenLoanCollateralMixin()

        with patch(
            "apps.tenant_apps.girvi.models.custody_tracking.apps.get_model",
            return_value=loan_item_model,
        ) as get_model:
            result = loan.collateral_items

        self.assertIs(result, loan_item_model.objects.filter.return_value)
        get_model.assert_called_once_with("girvi", "LoanItem")
        loan_item_model.objects.filter.assert_called_once_with(
            repledged_to=loan,
            custody_status="with_lender",
        )

    def test_collateral_summary_uses_borrower_on_current_given_loan(self):
        borrower = object()
        item = MagicMock()
        item.loan.borrower = borrower
        item.current_value.return_value = Decimal("1200.00")

        class LoanWithCollateral(TakenLoanCollateralMixin):
            @property
            def collateral_items(self):
                return [item]

        summary = LoanWithCollateral().collateral_summary

        self.assertEqual(summary[borrower]["count"], 1)
        self.assertEqual(summary[borrower]["value"], Decimal("1200.00"))

    def test_repledge_history_string_uses_lender_name_attribute(self):
        history = RepledgeHistory()
        history._state.fields_cache["loan_item"] = MagicMock(itemdesc="Ring")
        history._state.fields_cache["taken_loan"] = MagicMock()
        history.taken_loan.lender.name = "Lender A"
        history.returned_at = None

        self.assertEqual(str(history), "Ring -> Lender A (Active)")

    def test_item_custody_queryset_by_customer_uses_current_borrower_field(self):
        queryset = ItemCustodyQuerySet(model=MagicMock())
        queryset.filter = MagicMock(return_value="filtered")
        customer = object()

        result = queryset.by_customer(customer)

        self.assertEqual(result, "filtered")
        queryset.filter.assert_called_once_with(loan__borrower=customer)
