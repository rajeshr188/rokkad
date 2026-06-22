from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState
from apps.tenant_apps.girvi.policies import (
    assert_can_create_release,
    assert_can_record_repayment,
    assert_loan_transition_allowed,
    assert_loan_header_editable,
    can_create_release,
    can_edit_loan_header,
    can_execute_transition,
)


class GirviPolicyTests(SimpleTestCase):
    def test_draft_and_approved_loan_headers_are_editable(self):
        self.assertTrue(can_edit_loan_header(SimpleNamespace(status=LoanLifecycleState.DRAFT)))
        self.assertTrue(
            can_edit_loan_header(SimpleNamespace(status=LoanLifecycleState.APPROVED))
        )

    def test_active_and_closed_loan_headers_are_immutable(self):
        self.assertFalse(
            can_edit_loan_header(SimpleNamespace(status=LoanLifecycleState.ACTIVE_CURRENT))
        )
        with self.assertRaises(ValidationError):
            assert_loan_header_editable(
                SimpleNamespace(loan_id="GL-001", status=LoanLifecycleState.CLOSED)
            )

    @patch("apps.tenant_apps.girvi.service_modules.custody.build_release_readiness_checklist")
    def test_release_policy_returns_checklist_blockers(self, mock_checklist):
        mock_checklist.return_value = {
            "can_release": False,
            "blockers": ["Outstanding dues"],
        }

        allowed, blockers = can_create_release(SimpleNamespace(loan_id="GL-002"))

        self.assertFalse(allowed)
        self.assertEqual(blockers, ["Outstanding dues"])

    @patch("apps.tenant_apps.girvi.service_modules.custody.build_release_readiness_checklist")
    def test_assert_can_create_release_raises_from_policy(self, mock_checklist):
        mock_checklist.return_value = {
            "can_release": False,
            "blockers": ["Collateral with lender"],
        }

        with self.assertRaises(ValidationError):
            assert_can_create_release(SimpleNamespace(loan_id="GL-003"))

    def test_repayment_policy_blocks_given_loan_in_closed_status(self):
        with self.assertRaises(ValidationError):
            assert_can_record_repayment(
                SimpleNamespace(loan_id="GL-004", status=LoanLifecycleState.CLOSED),
                loan_kind="given",
            )

    def test_repayment_policy_allows_active_given_loan(self):
        assert_can_record_repayment(
            SimpleNamespace(
                loan_id="GL-005",
                status=LoanLifecycleState.ACTIVE_CURRENT,
            ),
            loan_kind="given",
        )

    def test_repayment_policy_blocks_taken_loan_when_released(self):
        with self.assertRaises(ValidationError):
            assert_can_record_repayment(
                SimpleNamespace(loan_id="TL-001", is_released=True),
                loan_kind="taken",
            )

    def test_can_execute_transition_denies_missing_transition(self):
        fake_flow = SimpleNamespace()
        with patch(
            "apps.tenant_apps.girvi.flows.build_runtime_loan_flow",
            return_value=fake_flow,
        ):
            allowed, message = can_execute_transition(
                SimpleNamespace(loan_id="GL-006"),
                "does_not_exist",
            )

        self.assertFalse(allowed)
        self.assertIn("not available", message)

    def test_assert_loan_transition_allowed_raises_when_cannot_proceed(self):
        transition = SimpleNamespace(can_proceed=lambda: False)
        fake_flow = SimpleNamespace(mark_overdue=transition)
        with patch(
            "apps.tenant_apps.girvi.flows.build_runtime_loan_flow",
            return_value=fake_flow,
        ):
            with self.assertRaises(ValidationError):
                assert_loan_transition_allowed(
                    SimpleNamespace(loan_id="GL-007"),
                    "mark_overdue",
                )
