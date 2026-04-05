from contextlib import nullcontext
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.flows import GivenLoanFlowV2, build_runtime_loan_flow
from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState, LoanStatus
from apps.tenant_apps.girvi.service_modules.transitions import LoanTransitionService
from apps.tenant_apps.girvi.transitions.commands import (
    DisburseTransitionCommand,
    GenericForwardTransitionCommand,
    MarkAuctionedTransitionCommand,
    MarkSoldTransitionCommand,
    UndoDisburseTransitionCommand,
    UndoReleaseTransitionCommand,
    UndoRepledgeTransitionCommand,
    get_transition_command_class,
)
from apps.tenant_apps.girvi.transition_registry import TRANSITION_REGISTRY


class _DummyLoan:
    def __init__(self, status):
        self.status = status

    def save(self, *args, **kwargs):
        return None


class _DummyUser:
    pass


class TransitionCommandRegistryTests(SimpleTestCase):
    def test_transition_command_lookup(self):
        self.assertIs(get_transition_command_class("approve"), GenericForwardTransitionCommand)
        self.assertIs(get_transition_command_class("disburse"), DisburseTransitionCommand)
        self.assertIs(get_transition_command_class("mark_auctioned"), MarkAuctionedTransitionCommand)
        self.assertIs(get_transition_command_class("mark_sold"), MarkSoldTransitionCommand)
        self.assertIs(get_transition_command_class("undo_disburse"), UndoDisburseTransitionCommand)
        self.assertIs(get_transition_command_class("undo_release"), UndoReleaseTransitionCommand)
        self.assertIs(get_transition_command_class("undo_repledge"), UndoRepledgeTransitionCommand)

    def test_registry_binds_command_classes_for_core_transitions(self):
        self.assertIs(TRANSITION_REGISTRY["approve"].command_class, GenericForwardTransitionCommand)
        self.assertIs(TRANSITION_REGISTRY["disburse"].command_class, DisburseTransitionCommand)
        self.assertIs(TRANSITION_REGISTRY["undo_release"].command_class, UndoReleaseTransitionCommand)
        self.assertIs(TRANSITION_REGISTRY["undo_repledge"].command_class, UndoRepledgeTransitionCommand)

    def test_transition_service_routes_new_keys_to_v2_flow(self):
        loan = _DummyLoan(LoanLifecycleState.DRAFT)
        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "submit_for_approval"
        )

        self.assertTrue(result.success)
        self.assertEqual(loan.status, LoanLifecycleState.PENDING_APPROVAL)

    @patch(
        "apps.tenant_apps.girvi.transitions.commands.transaction.atomic",
        side_effect=lambda: nullcontext(),
    )
    @patch("apps.tenant_apps.girvi.service_modules.payment.record_loan_disbursal")
    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_transition_service_routes_draft_to_active_current_v2_journey(
        self,
        _mock_has_permission,
        mock_record_disbursal,
        _mock_atomic,
    ):
        payment = type("Payment", (), {"payment_id": "DIS-001"})()
        mock_record_disbursal.return_value = (payment, True)
        loan = _DummyLoan(LoanLifecycleState.DRAFT)

        service = LoanTransitionService(loan, _DummyUser(), tenant=None)

        submit_result = service.execute("submit_for_approval")
        self.assertTrue(submit_result.success)
        self.assertEqual(loan.status, LoanLifecycleState.PENDING_APPROVAL)

        approve_result = service.execute("approve_loan", approved_by="checker")
        self.assertTrue(approve_result.success)
        self.assertEqual(loan.status, LoanLifecycleState.APPROVED)

        disburse_result = service.execute("disburse_loan", disbursed_by="cashier")
        self.assertTrue(disburse_result.success)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_CURRENT)
        self.assertTrue(disburse_result.created)
        self.assertIn("DIS-001", disburse_result.message)
        mock_record_disbursal.assert_called_once_with(loan, service.user)

    @patch(
        "apps.tenant_apps.girvi.transitions.commands.transaction.atomic",
        side_effect=lambda: nullcontext(),
    )
    @patch("apps.tenant_apps.girvi.service_modules.payment.record_loan_disbursal")
    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_transition_service_accepts_legacy_approval_aliases_for_v2_states(
        self,
        _mock_has_permission,
        mock_record_disbursal,
        _mock_atomic,
    ):
        payment = type("Payment", (), {"payment_id": "DIS-LEGACY"})()
        mock_record_disbursal.return_value = (payment, True)
        loan = _DummyLoan(LoanLifecycleState.PENDING_APPROVAL)
        service = LoanTransitionService(loan, _DummyUser(), tenant=None)

        approve_result = service.execute("approve", approved_by="checker")
        self.assertTrue(approve_result.success)
        self.assertEqual(loan.status, LoanLifecycleState.APPROVED)

        disburse_result = service.execute("disburse", disbursed_by="cashier")
        self.assertTrue(disburse_result.success)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_CURRENT)
        mock_record_disbursal.assert_called_once_with(loan, service.user)

    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_request_closure_returns_error_result_when_balance_outstanding(
        self,
        _mock_has_permission,
    ):
        loan = _DummyLoan(LoanLifecycleState.ACTIVE_CURRENT)
        loan.outstanding_amount = 100

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "request_closure",
            requested_by="collector",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("Loan must be fully settled before closure request.", result.message)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_CURRENT)

    def test_build_runtime_flow_routes_approved_status_to_v2(self):
        flow = build_runtime_loan_flow(
            _DummyLoan(LoanStatus.APPROVED),
            _DummyUser(),
            tenant=None,
        )
        self.assertIsInstance(flow, GivenLoanFlowV2)
