from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.services import PawnRepaymentError, allocate_repayment


class PawnRepaymentAllocationTests(SimpleTestCase):
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
