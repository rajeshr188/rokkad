from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from moneyed import Money

from apps.tenant_apps.girvi.service_modules.loan_posting import GivenLoanPostingService


class GivenLoanPostingServiceTests(TestCase):
    def _fake_user(self):
        return SimpleNamespace(username="tester")

    def _fake_loan(self):
        loan = SimpleNamespace(
            loan_id="GL-001",
            pk=1,
            create_payment=MagicMock(return_value=SimpleNamespace(payment_id="PAY-123")),
            outstanding_principal=Money(0, "INR"),
            interest_due=MagicMock(return_value=Money(0, "INR")),
        )
        return loan

    def test_post_repayment_uses_adapter_when_reference_number_present(self):
        loan = self._fake_loan()
        payload = {
            "total_amount": 100,
            "interest_amount": 10,
            "principal_amount": 90,
            "payment_date": "2026-06-15",
            "payment_method": "CASH",
            "reference_number": "REF-001",
            "description": "Test repayment",
            "is_final_payment": True,
        }
        fake_payment = SimpleNamespace(payment_id="PAY-REF")

        with patch(
            "apps.tenant_apps.girvi.service_modules.loan_posting.create_and_post_voucher_for_doc",
            return_value=(fake_payment, True),
        ) as mock_create:
            payment, created = GivenLoanPostingService().post_repayment(
                loan, payload, self._fake_user()
            )

        self.assertEqual(payment, fake_payment)
        self.assertTrue(created)
        mock_create.assert_called_once()

    def test_post_repayment_posts_using_post_payment_voucher_when_no_reference_number(self):
        loan = self._fake_loan()
        loan.create_payment.return_value = SimpleNamespace(payment_id="PAY-001")
        payload = {
            "total_amount": 100,
            "interest_amount": 10,
            "principal_amount": 90,
            "payment_date": "2026-06-15",
            "payment_method": "CASH",
            "reference_number": "",
            "description": "Test repayment",
            "is_final_payment": False,
        }
        user = self._fake_user()

        with patch(
            "apps.tenant_apps.girvi.service_modules.loan_posting.post_payment_voucher"
        ) as mock_post:
            payment, created = GivenLoanPostingService().post_repayment(
                loan, payload, user
            )

        self.assertEqual(payment.payment_id, "PAY-001")
        self.assertTrue(created)
        mock_post.assert_called_once_with(payment, user)

    def test_post_release_returns_none_false_when_outstanding_is_zero(self):
        loan = SimpleNamespace(
            loan_id="GL-001",
            outstanding_principal=Money(0, "INR"),
            interest_due=MagicMock(return_value=Money(0, "INR")),
        )
        release = SimpleNamespace(
            loan=loan,
            pk=1,
            release_date="2026-06-15",
            release_id="REL-001",
        )

        payment, created = GivenLoanPostingService().post_release(release, self._fake_user())

        self.assertIsNone(payment)
        self.assertFalse(created)

    def test_post_auction_recovery_returns_existing_payment_when_marker_exists(self):
        class FakeGivenLoan:
            def __init__(self):
                self.loan_id = "GL-001"
                self.pk = 1
                self.create_payment = MagicMock(return_value=SimpleNamespace(payment_id="PAY-EXIST"))

        loan = FakeGivenLoan()
        existing_payment = SimpleNamespace(payment_id="PAY-EXIST")

        with patch(
            "apps.tenant_apps.girvi.service_modules.loan_posting.GivenLoan",
            FakeGivenLoan,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.loan_posting.find_payment_by_marker",
            return_value=existing_payment,
        ):
            payment, created = GivenLoanPostingService().post_auction_recovery(
                loan, 100, self._fake_user()
            )

        self.assertEqual(payment, existing_payment)
        self.assertFalse(created)

    def test_post_sale_recovery_creates_and_posts_payment_when_no_existing_marker(self):
        class FakeGivenLoan:
            def __init__(self):
                self.loan_id = "GL-001"
                self.pk = 1
                self.create_payment = MagicMock(return_value=SimpleNamespace(payment_id="PAY-NEW"))

        loan = FakeGivenLoan()
        payment_obj = loan.create_payment.return_value

        with patch(
            "apps.tenant_apps.girvi.service_modules.loan_posting.GivenLoan",
            FakeGivenLoan,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.loan_posting.find_payment_by_marker",
            return_value=None,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.loan_posting.post_payment_voucher"
        ) as mock_post:
            payment, created = GivenLoanPostingService().post_sale_recovery(
                loan, 250, self._fake_user()
            )

        self.assertEqual(payment, payment_obj)
        self.assertTrue(created)
        mock_post.assert_called_once_with(
            payment_obj,
            self._fake_user(),
            voucher_type_override="GIVENLOAN_SOLD",
        )
