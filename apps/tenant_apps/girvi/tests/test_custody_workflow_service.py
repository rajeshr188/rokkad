from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.custody_workflow import (
    CustodyWorkflowService,
)


class CustodyWorkflowServiceTests(SimpleTestCase):
    def test_gate_blocks_when_dues_not_clear(self):
        gate = CustodyWorkflowService.evaluate_release_with_return_gate(
            SimpleNamespace(is_released=False),
            checklist={"dues_clear": False, "needs_return": True},
        )

        self.assertFalse(gate.can_proceed)
        self.assertTrue(gate.redirect_to_checklist)
        self.assertIn("settlement dues", gate.block_message)

    def test_gate_redirects_to_release_create_when_no_return_needed(self):
        gate = CustodyWorkflowService.evaluate_release_with_return_gate(
            SimpleNamespace(is_released=False),
            checklist={"dues_clear": True, "needs_return": False},
        )

        self.assertTrue(gate.redirect_to_release_create)
        self.assertFalse(gate.can_proceed)

    def test_gate_allows_execution_when_return_needed_and_dues_clear(self):
        gate = CustodyWorkflowService.evaluate_release_with_return_gate(
            SimpleNamespace(is_released=False),
            checklist={"dues_clear": True, "needs_return": True},
        )

        self.assertTrue(gate.can_proceed)

    @patch("apps.tenant_apps.girvi.service_modules.custody_workflow.release_loan_with_custody_return")
    def test_execute_release_with_return_delegates(self, execute_mock):
        loan = SimpleNamespace(loan_id="GL-1")
        user = SimpleNamespace(username="demo")

        CustodyWorkflowService.execute_release_with_return(
            loan,
            release_date="2026-06-22",
            released_by="Owner",
            user=user,
        )

        execute_mock.assert_called_once_with(
            loan=loan,
            release_date="2026-06-22",
            released_by="Owner",
            user=user,
        )

    def test_build_release_custody_api_payload_matches_existing_shape(self):
        lender = SimpleNamespace(name="Lender A")
        items = [SimpleNamespace(repledged_to=SimpleNamespace(lender=lender))]
        queryset = MagicMock()
        queryset.__iter__.return_value = iter(items)
        queryset.exists.return_value = True
        queryset.count.return_value = 1
        loan = SimpleNamespace(loanitems=SimpleNamespace(filter=MagicMock(return_value=queryset)))

        payload = CustodyWorkflowService.build_release_custody_api_payload(loan)

        self.assertEqual(payload["can_release"], False)
        self.assertEqual(payload["needs_return"], True)
        self.assertEqual(payload["items_with_lender"], 1)
        self.assertEqual(payload["lenders"], ["Lender A"])
