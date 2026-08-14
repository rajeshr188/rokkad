from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.service_modules.repayment_workflow import (
    RepaymentWorkflowService,
)


class RepaymentWorkflowServiceTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.tenant_apps.girvi.service_modules.repayment_workflow.build_repayment_preview")
    def test_build_preview_delegates_to_selector(self, preview_mock):
        loan = SimpleNamespace(pk=1)
        expected = SimpleNamespace(suggested_interest_amount=10)
        preview_mock.return_value = expected

        result = RepaymentWorkflowService.build_preview(loan, loan_kind="taken")

        self.assertEqual(result, expected)
        preview_mock.assert_called_once_with(loan, loan_kind="taken")

    def test_initial_form_data_uses_preview_interest_amount(self):
        preview = SimpleNamespace(suggested_interest_amount=125)

        initial = RepaymentWorkflowService.initial_form_data(preview)

        self.assertEqual(initial["interest_amount"], 125)
        self.assertIn("payment_date", initial)

    def test_payment_options_builds_settlement_interest_and_principal_presets(self):
        preview = SimpleNamespace(
            suggested_total_amount=1100,
            suggested_interest_amount=100,
            settlement=SimpleNamespace(
                interest_due=100,
                principal_due=1000,
            ),
        )

        options = RepaymentWorkflowService.payment_options(preview)

        self.assertEqual([option["label"] for option in options], [
            "Exact settlement",
            "Interest only",
            "Principal only",
        ])
        self.assertEqual(options[0]["total_amount"], 1100)
        self.assertEqual(options[0]["interest_amount"], 100)
        self.assertEqual(options[1]["total_amount"], 100)
        self.assertEqual(options[1]["interest_amount"], 100)
        self.assertEqual(options[2]["total_amount"], 1000)
        self.assertEqual(options[2]["interest_amount"], 0)

    @patch("django.contrib.messages.success")
    @patch("django.contrib.messages.error")
    @patch("django.contrib.messages.warning")
    def test_emit_result_messages_dispatches_all_message_levels(
        self,
        warning_mock,
        error_mock,
        success_mock,
    ):
        request = self.factory.get("/girvi/loanpayment/1/create/")
        result = SimpleNamespace(
            warnings=["warn"],
            errors=["err"],
            success_message="ok",
        )

        RepaymentWorkflowService.emit_result_messages(request, result)

        warning_mock.assert_called_once_with(request, "warn")
        error_mock.assert_called_once_with(request, "err")
        success_mock.assert_called_once_with(request, "ok")
