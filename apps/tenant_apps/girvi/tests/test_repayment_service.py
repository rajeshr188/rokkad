from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.repayment import (
    GivenLoanRepaymentService,
    RepaymentCommand,
    TakenLoanRepaymentService,
)


class GivenLoanRepaymentServiceTests(SimpleTestCase):
    def _cleaned_data(self, **overrides):
        data = {
            "total_amount": Decimal("1000.00"),
            "interest_amount": Decimal("100.00"),
            "payment_date": datetime(2026, 4, 6, 10, 30),
            "payment_method": "CASH",
            "reference_number": "REF-1",
            "description": "test receipt",
            "is_final_payment": True,
        }
        data.update(overrides)
        return data

    @patch("apps.tenant_apps.girvi.service_modules.repayment.GivenLoanPostingService")
    @patch("apps.tenant_apps.girvi.service_modules.repayment.InterestAccrualService.execute")
    @patch("apps.tenant_apps.girvi.service_modules.repayment.CompanyPreferences")
    def test_execute_runs_catchup_accrual_before_repayment_posting(
        self,
        mock_preferences,
        mock_accrue,
        mock_posting_service,
    ):
        loan = SimpleNamespace(pk=1, loan_id="GL-001")
        user = SimpleNamespace(id=1, profile=SimpleNamespace(workspace="workspace"))
        payment = SimpleNamespace(payment_id="PAY-1")
        mock_preferences.return_value = SimpleNamespace(loan_catchup_on_receipt=True)
        mock_accrue.return_value = SimpleNamespace(success=True, message="ok")
        mock_posting_service.return_value.post_repayment.return_value = (payment, True)

        result = GivenLoanRepaymentService.execute(
            RepaymentCommand(
                loan=loan,
                cleaned_data=self._cleaned_data(),
                created_by=user,
            )
        )

        self.assertTrue(result.accounting_posted)
        self.assertEqual(result.payment, payment)
        self.assertEqual(result.success_message, "Payment PAY-1 recorded and posted to accounting.")

        mock_accrue.assert_called_once()
        accrual_command = mock_accrue.call_args.args[0]
        self.assertEqual(accrual_command.loan, loan)
        self.assertEqual(accrual_command.trigger_source, "RECEIPT")
        self.assertTrue(accrual_command.post_to_accounting)

        payload = mock_posting_service.return_value.post_repayment.call_args.args[1]
        self.assertEqual(payload["principal_amount"], Decimal("900.00"))
        self.assertNotIn("create_release", payload)

    @patch("apps.tenant_apps.girvi.service_modules.repayment.GivenLoanPostingService")
    @patch("apps.tenant_apps.girvi.service_modules.repayment.CompanyPreferences")
    @patch("apps.tenant_apps.girvi.service_modules.repayment.logger.exception")
    def test_execute_warns_when_posting_fails(
        self,
        _mock_logger_exception,
        mock_preferences,
        mock_posting_service,
    ):
        loan = SimpleNamespace(pk=1, loan_id="GL-001")
        user = SimpleNamespace(id=1)
        mock_preferences.return_value = SimpleNamespace(loan_catchup_on_receipt=False)
        mock_posting_service.return_value.post_repayment.side_effect = RuntimeError("boom")

        result = GivenLoanRepaymentService.execute(
            RepaymentCommand(
                loan=loan,
                cleaned_data=self._cleaned_data(),
                created_by=user,
            )
        )

        self.assertFalse(result.accounting_posted)
        self.assertEqual(result.success_message, "")
        self.assertEqual(result.warnings, ["Payment saved but accounting posting failed: boom"])


class TakenLoanRepaymentServiceTests(SimpleTestCase):
    def test_execute_creates_payment_and_posts_voucher(self):
        payment = SimpleNamespace(payment_id="TPAY-1")
        loan = MagicMock()
        loan.create_payment.return_value = payment
        user = SimpleNamespace(id=1)
        cleaned_data = {
            "total_amount": Decimal("800.00"),
            "interest_amount": Decimal("80.00"),
            "payment_date": datetime(2026, 4, 6, 10, 30),
            "payment_method": "BANK",
            "reference_number": "BANK-1",
            "description": "taken repayment",
            "is_final_payment": True,
        }

        with patch(
            "apps.tenant_apps.girvi.service_modules.repayment.post_payment_voucher"
        ) as mock_post:
            result = TakenLoanRepaymentService.execute(
                RepaymentCommand(
                    loan=loan,
                    cleaned_data=cleaned_data,
                    created_by=user,
                )
            )

        self.assertTrue(result.accounting_posted)
        self.assertEqual(result.payment, payment)
        self.assertEqual(result.success_message, "Payment TPAY-1 recorded and posted to accounting.")
        loan.create_payment.assert_called_once_with(
            amount=Decimal("800.00"),
            payment_date=datetime(2026, 4, 6, 10, 30),
            payment_method="BANK",
            reference_number="BANK-1",
            interest=Decimal("80.00"),
            principal=Decimal("720.00"),
            description="taken repayment",
            is_final=True,
            created_by=user,
        )
        mock_post.assert_called_once_with(payment, user)
