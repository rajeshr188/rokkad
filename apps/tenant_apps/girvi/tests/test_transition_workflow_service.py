from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.service_modules.transition_workflow import (
    TransitionWorkflowService,
)


class TransitionWorkflowServiceTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("apps.tenant_apps.girvi.service_modules.transition_workflow.get_transition_form_ui")
    @patch("apps.tenant_apps.girvi.service_modules.transition_workflow.get_transition_form_class")
    @patch("apps.tenant_apps.girvi.service_modules.transition_workflow.resolve_runtime_transition_name")
    @patch("apps.tenant_apps.girvi.service_modules.transition_workflow.normalize_transition_name")
    def test_resolve_transition_context_builds_expected_payload(
        self,
        normalize_mock,
        resolve_mock,
        form_class_mock,
        form_ui_mock,
    ):
        request = self.factory.get("/girvi/loan/1/transition/?transition=disburse")
        loan = SimpleNamespace(status="Approved")

        normalize_mock.return_value = "disburse"
        resolve_mock.return_value = "disburse_loan"
        form_class_mock.return_value = object()
        form_ui_mock.return_value = {"title": "Disburse"}

        context = TransitionWorkflowService.resolve_transition_context(loan, request)

        self.assertEqual(context["transition_name"], "disburse_loan")
        self.assertIn("status_label", context)
        self.assertIn("status_badge_class", context)
        self.assertIn("form_class", context)
        self.assertIn("transition_ui", context)

    @patch("apps.tenant_apps.girvi.service_modules.transition_workflow.assert_loan_transition_allowed")
    def test_assert_allowed_returns_none_when_policy_passes(self, assert_mock):
        result = TransitionWorkflowService.assert_allowed(
            SimpleNamespace(),
            "disburse_loan",
            user=SimpleNamespace(),
            workspace=SimpleNamespace(),
        )

        self.assertIsNone(result)
        assert_mock.assert_called_once()

    @patch("apps.tenant_apps.girvi.service_modules.transition_workflow.assert_loan_transition_allowed")
    def test_assert_allowed_returns_message_when_policy_fails(self, assert_mock):
        assert_mock.side_effect = ValidationError("Transition is blocked")

        result = TransitionWorkflowService.assert_allowed(
            SimpleNamespace(),
            "disburse_loan",
            user=SimpleNamespace(),
            workspace=SimpleNamespace(),
        )

        self.assertEqual(result, "Transition is blocked")
