from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.custody_tracking import (
    GivenLoanReleaseMixin,
    ItemCustodyStatus,
    TakenLoanCollateralMixin,
)
from apps.tenant_apps.girvi.service_modules.custody import (
    return_all_items_from_taken_loan,
)


class FakeCollateralQuerySet(list):
    def exists(self):
        return bool(self)


class CustodyReturnReleaseTests(SimpleTestCase):
    def test_return_all_items_from_taken_loan_returns_each_matching_item(self):
        item = MagicMock(itemdesc="Ring")
        loan = MagicMock()
        loan.loanitems.filter.return_value = [item]
        taken_loan = MagicMock()
        taken_loan.lender.name = "Lender A"
        user = MagicMock()

        with patch(
            "apps.tenant_apps.girvi.service_modules.custody.transaction.atomic",
            return_value=nullcontext(),
        ):
            result = return_all_items_from_taken_loan(
                loan=loan,
                taken_loan=taken_loan,
                user=user,
            )

        loan.loanitems.filter.assert_called_once_with(
            repledged_to=taken_loan,
            custody_status=ItemCustodyStatus.WITH_LENDER,
        )
        item.return_from_lender.assert_called_once_with(
            user=user,
            notes="Bulk return from Lender A",
        )
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.errors, [])

    def test_return_all_items_from_taken_loan_collects_item_errors(self):
        item = MagicMock(itemdesc="Chain")
        item.return_from_lender.side_effect = ValidationError("not with lender")
        loan = MagicMock()
        loan.loanitems.filter.return_value = [item]
        taken_loan = MagicMock()
        taken_loan.lender.name = "Lender A"

        with patch(
            "apps.tenant_apps.girvi.service_modules.custody.transaction.atomic",
            return_value=nullcontext(),
        ):
            result = return_all_items_from_taken_loan(
                loan=loan,
                taken_loan=taken_loan,
                user=MagicMock(),
            )

        self.assertEqual(result.returned_count, 0)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Chain", result.errors[0])
        self.assertIn("not with lender", result.errors[0])

    def test_taken_loan_return_all_collateral_returns_current_collateral_items(self):
        item_one = MagicMock()
        item_two = MagicMock()
        user = MagicMock()

        class TakenLoanWithCollateral(TakenLoanCollateralMixin):
            @property
            def collateral_items(self):
                return [item_one, item_two]

        with patch(
            "apps.tenant_apps.girvi.models.custody_tracking.transaction.atomic",
            return_value=nullcontext(),
        ):
            TakenLoanWithCollateral().return_all_collateral(
                user=user,
                notes="Closing lender loan",
            )

        item_one.return_from_lender.assert_called_once_with(user, "Closing lender loan")
        item_two.return_from_lender.assert_called_once_with(user, "Closing lender loan")

    def test_taken_loan_can_close_requires_no_active_collateral(self):
        class TakenLoanWithCollateral(TakenLoanCollateralMixin):
            @property
            def collateral_items(self):
                return FakeCollateralQuerySet([MagicMock()])

        can_close, message = TakenLoanWithCollateral().can_close()

        self.assertFalse(can_close)
        self.assertIn("collateral items must be returned", message)

    def test_given_loan_can_release_blocks_items_still_with_lender(self):
        item = MagicMock()
        item.repledged_to.lender.name = "Lender A"

        class GivenLoanWithCustody(GivenLoanReleaseMixin):
            def get_items_by_custody(self):
                return {ItemCustodyStatus.WITH_LENDER: [item]}

        can_release, message = GivenLoanWithCustody().can_release()

        self.assertFalse(can_release)
        self.assertIn("currently with lender", message)
        self.assertIn("Lender A", message)

    def test_release_with_return_workflow_returns_lender_items_then_releases_vault_items(self):
        with_lender = MagicMock()
        in_vault = MagicMock()
        release = MagicMock()
        user = MagicMock()

        class GivenLoanWithCustody(GivenLoanReleaseMixin):
            loan_id = "GL-1"

            def get_items_by_custody(self):
                return {
                    ItemCustodyStatus.WITH_LENDER: [with_lender],
                    ItemCustodyStatus.IN_VAULT: [in_vault],
                }

            def create_release(self, **kwargs):
                self.release_kwargs = kwargs
                return release

        loan = GivenLoanWithCustody()

        with patch(
            "apps.tenant_apps.girvi.models.custody_tracking.transaction.atomic",
            return_value=nullcontext(),
        ):
            result = loan.release_with_return_workflow(
                release_date="2026-06-20",
                released_by="Owner",
                created_by=user,
            )

        self.assertIs(result, release)
        with_lender.return_from_lender.assert_called_once_with(
            user=user,
            notes="Returned for GivenLoan GL-1 release",
        )
        in_vault.release_to_customer.assert_called_once_with(user=user)
        self.assertEqual(
            loan.release_kwargs,
            {
                "release_date": "2026-06-20",
                "released_by": "Owner",
                "created_by": user,
            },
        )
