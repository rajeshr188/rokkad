from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from moneyed import Money

from apps.tenant_apps.girvi.service_modules import payment_voucher_creation as svc


class PaymentVoucherCreationServiceTests(SimpleTestCase):
    def _user(self):
        return SimpleNamespace(username="tester")

    def test_given_loan_receipt_uses_receipt_direction(self):
        loan = SimpleNamespace(pk=1)
        user = self._user()

        with patch.object(svc, "create_payment_voucher", return_value="payment") as create:
            result = svc.create_given_loan_receipt_payment(
                loan,
                amount=Decimal("100.00"),
                principal=Money(80, "INR"),
                interest=Money(20, "INR"),
                reference_number="REC-1",
                is_final=True,
                create_release=True,
                created_by=user,
            )

        self.assertEqual(result, "payment")
        create.assert_called_once()
        kwargs = create.call_args.kwargs
        self.assertEqual(create.call_args.args[0], loan)
        self.assertEqual(kwargs["direction"], "RECEIPT")
        self.assertEqual(kwargs["payment_type"], "RECEIPT")
        self.assertEqual(kwargs["total_amount"], Money(Decimal("100.00"), "INR"))
        self.assertTrue(kwargs["is_final_payment"])
        self.assertTrue(kwargs["create_release"])

    def test_given_loan_disbursal_uses_payment_direction(self):
        loan = SimpleNamespace(pk=1, get_loan_amount_with_currency=Money(500, "INR"))
        user = self._user()

        with patch.object(svc, "create_payment_voucher", return_value="payment") as create:
            result = svc.create_given_loan_disbursal_payment(
                loan,
                reference_number="DISB-1",
                created_by=user,
            )

        self.assertEqual(result, "payment")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["direction"], "PAYMENT")
        self.assertEqual(kwargs["payment_type"], "DISBURSAL")
        self.assertEqual(kwargs["principal_amount"], Money(500, "INR"))

    def test_given_loan_release_defaults_principal_and_interest(self):
        loan = SimpleNamespace(
            pk=1,
            outstanding_principal=Money(300, "INR"),
            interest_due=lambda: Decimal("25.00"),
        )
        user = self._user()

        with patch.object(svc, "create_payment_voucher", return_value="payment") as create:
            result = svc.create_given_loan_release_payment(loan, created_by=user)

        self.assertEqual(result, "payment")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["direction"], "RECEIPT")
        self.assertEqual(kwargs["payment_type"], "RECEIPT")
        self.assertEqual(kwargs["principal_amount"], Money(300, "INR"))
        self.assertEqual(kwargs["interest_amount"], Money(Decimal("25.00"), "INR"))
        self.assertEqual(kwargs["total_amount"], Money(Decimal("325.00"), "INR"))

    def test_taken_loan_repayment_uses_payment_direction(self):
        loan = SimpleNamespace(pk=1)
        user = self._user()

        with patch.object(svc, "create_payment_voucher", return_value="payment") as create:
            result = svc.create_taken_loan_repayment_payment(
                loan,
                amount=Decimal("200.00"),
                created_by=user,
            )

        self.assertEqual(result, "payment")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["direction"], "PAYMENT")
        self.assertEqual(kwargs["payment_type"], "RECEIPT")
        self.assertEqual(kwargs["total_amount"], Money(Decimal("200.00"), "INR"))

    def test_created_by_is_required(self):
        with self.assertRaises(ValidationError):
            svc.create_given_loan_receipt_payment(SimpleNamespace(), amount=10)
