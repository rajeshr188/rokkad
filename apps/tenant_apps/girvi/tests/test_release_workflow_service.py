from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.release_workflow import (
    ReleaseWorkflowService,
)


class ReleaseWorkflowServiceTests(SimpleTestCase):
    def _loan(self):
        return SimpleNamespace(pk=42, loan_id="GL-42", borrower="Demo")

    def _user(self):
        return SimpleNamespace(username="demo-user")

    def test_build_preview_returns_none_without_required_inputs(self):
        self.assertIsNone(ReleaseWorkflowService.build_preview(None, user=self._user()))
        self.assertIsNone(ReleaseWorkflowService.build_preview(self._loan(), user=None))

    @patch("apps.tenant_apps.girvi.service_modules.release_workflow.ReleaseLifecycleService.execute")
    def test_submit_returns_success_shape(self, execute_mock):
        loan = self._loan()
        execute_mock.return_value = SimpleNamespace(
            success=True,
            release=SimpleNamespace(loan=loan),
            message="Release created",
            warnings=["Loan has no outstanding balance."],
        )

        result = ReleaseWorkflowService.submit(
            loan=loan,
            release_date=datetime(2026, 4, 1, 10, 0),
            released_by=loan.borrower,
            user=self._user(),
            checklist={"can_release": True, "blockers": []},
        )

        self.assertTrue(result.success)
        self.assertEqual(result.message, "Release created")
        self.assertEqual(result.warnings, ["Loan has no outstanding balance."])

    def test_submit_returns_blockers_when_checklist_not_ready(self):
        result = ReleaseWorkflowService.submit(
            loan=self._loan(),
            release_date=datetime(2026, 4, 1, 10, 0),
            released_by="Demo",
            user=self._user(),
            checklist={
                "can_release": False,
                "blockers": ["Loan has outstanding dues"],
            },
        )

        self.assertFalse(result.success)
        self.assertIn("Loan has outstanding dues", result.blocker_messages)
        self.assertEqual(result.execution_error, "Release checklist is not ready.")
