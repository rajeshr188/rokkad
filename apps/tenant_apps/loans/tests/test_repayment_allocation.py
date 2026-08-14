from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services import (
    PawnRepaymentError,
    allocate_repayment,
    record_pawn_loan_repayment,
)


class PawnRepaymentAllocationTests(TestCase):
    def setUp(self):
        self.balance = SimpleNamespace(
            fees_outstanding=Decimal("100.00"),
            overdue_interest_outstanding=Decimal("200.00"),
            current_interest_outstanding=Decimal("300.00"),
            principal_outstanding=Decimal("1000.00"),
        )

    def test_allocates_fees_overdue_current_then_principal(self):
        allocation = allocate_repayment(self.balance, Decimal("750.00"))

        self.assertEqual(allocation.fees, Decimal("100.00"))
        self.assertEqual(allocation.overdue_interest, Decimal("200.00"))
        self.assertEqual(allocation.current_interest, Decimal("300.00"))
        self.assertEqual(allocation.principal, Decimal("150.00"))
        self.assertEqual(allocation.interest, Decimal("500.00"))

    def test_rejects_overpayment_and_nonpositive_amounts(self):
        with self.assertRaises(PawnRepaymentError):
            allocate_repayment(self.balance, Decimal("1600.01"))
        with self.assertRaises(PawnRepaymentError):
            allocate_repayment(self.balance, Decimal("0.00"))

    def test_repayment_command_scopes_same_loan_identifier_to_active_workspace(self):
        queryset = MagicMock()
        queryset.select_for_update.return_value.select_related.return_value = queryset
        queryset.get.side_effect = [PawnLoan.DoesNotExist, PawnLoan.DoesNotExist]

        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.current_tenant_workspace_id",
            side_effect=[101, 202],
        ), patch(
            "apps.tenant_apps.loans.services.pawn_repayment.PawnLoan.objects",
            queryset,
        ):
            for request_key in ("workspace-101", "workspace-202"):
                with self.assertRaises(PawnRepaymentError):
                    record_pawn_loan_repayment(
                        7,
                        amount=Decimal("100.00"),
                        request_key=request_key,
                    )

        self.assertEqual(
            [call.kwargs for call in queryset.get.call_args_list],
            [
                {"pk": 7, "workspace_id": 101},
                {"pk": 7, "workspace_id": 202},
            ],
        )
