from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.flows import GivenLoanFlow, TakenLoanFlow, build_runtime_loan_flow
from apps.tenant_apps.girvi.models import (
    LoanLifecycleState,
    TakenLoanLifecycleState,
)
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
    def __init__(self, status, loan_type="Given"):
        self.status = status
        self.loan_type = loan_type

    def save(self, *args, **kwargs):
        return None


class _DummyUser:
    pass


class TransitionCommandRegistryTests(SimpleTestCase):
    def test_transition_command_lookup(self):
        self.assertIs(get_transition_command_class("approve_loan"), GenericForwardTransitionCommand)
        self.assertIs(get_transition_command_class("disburse_loan"), DisburseTransitionCommand)
        self.assertIs(get_transition_command_class("complete_auction"), MarkAuctionedTransitionCommand)
        self.assertIs(get_transition_command_class("mark_sold"), MarkSoldTransitionCommand)
        self.assertIs(get_transition_command_class("undo_disbursal"), UndoDisburseTransitionCommand)
        self.assertIs(get_transition_command_class("undo_release"), UndoReleaseTransitionCommand)
        self.assertIs(get_transition_command_class("undo_repledge"), UndoRepledgeTransitionCommand)

    def test_registry_binds_command_classes_for_core_transitions(self):
        self.assertIs(TRANSITION_REGISTRY["approve_loan"].command_class, GenericForwardTransitionCommand)
        self.assertIs(TRANSITION_REGISTRY["disburse_loan"].command_class, DisburseTransitionCommand)
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

    def test_mark_overdue_rejects_current_loan_before_tenure_end(self):
        loan = _DummyLoan(LoanLifecycleState.ACTIVE_CURRENT)
        loan.loan_date = datetime(2026, 6, 1)
        loan.tenure = 3

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "mark_overdue",
            marked_by="collector",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("maturity has not passed", result.message)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_CURRENT)

    @patch("apps.tenant_apps.girvi.flows.evaluate_overdue_policy")
    def test_mark_overdue_allows_undersecured_loan_before_maturity(self, mock_policy):
        mock_policy.return_value = SimpleNamespace(
            maturity_date=datetime(2026, 9, 1).date(),
            is_overdue=True,
        )
        loan = _DummyLoan(LoanLifecycleState.ACTIVE_CURRENT)

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "mark_overdue",
            marked_by="collector",
        )

        self.assertTrue(result.success)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_OVERDUE)

    @patch("apps.tenant_apps.girvi.flows.evaluate_overdue_policy")
    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_mark_npa_rejects_when_collateral_covers_settlement(
        self,
        _mock_permission,
        mock_policy,
    ):
        mock_policy.return_value = SimpleNamespace(is_npa=False)
        loan = _DummyLoan(LoanLifecycleState.ACTIVE_OVERDUE)

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "mark_npa",
            marked_by="collector",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("settlement amount is covered", result.message)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_OVERDUE)

    @patch("apps.tenant_apps.girvi.flows.evaluate_overdue_policy")
    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_mark_npa_allows_undersecured_loan(self, _mock_permission, mock_policy):
        mock_policy.return_value = SimpleNamespace(is_npa=True)
        loan = _DummyLoan(LoanLifecycleState.ACTIVE_OVERDUE)

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "mark_npa",
            marked_by="collector",
        )

        self.assertTrue(result.success)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_NPA)

    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_write_off_rejects_missing_reason(self, _mock_permission):
        loan = _DummyLoan(LoanLifecycleState.ACTIVE_NPA)
        loan.outstanding_amount = Decimal("100.00")

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "write_off_loan",
            written_off_by="manager",
            reason="",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("reason is required", result.message)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_NPA)

    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_write_off_rejects_fully_settled_loan(self, _mock_permission):
        loan = _DummyLoan(LoanLifecycleState.AUCTION_COMPLETE)
        loan.outstanding_amount = Decimal("0.00")

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "write_off_loan",
            written_off_by="manager",
            reason="approved loss decision",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("must be closed, not written off", result.message)
        self.assertEqual(loan.status, LoanLifecycleState.AUCTION_COMPLETE)

    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_write_off_requires_adjustment_document_for_residual_balance(self, _mock_permission):
        loan = _DummyLoan(LoanLifecycleState.AUCTION_COMPLETE)
        loan.outstanding_amount = Decimal("100.00")

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "write_off_loan",
            written_off_by="manager",
            reason="approved loss decision",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("requires an explicit settlement adjustment document", result.message)
        self.assertEqual(loan.status, LoanLifecycleState.AUCTION_COMPLETE)

    def test_cure_to_current_rejects_when_balance_outstanding(self):
        loan = _DummyLoan(LoanLifecycleState.ACTIVE_OVERDUE)
        loan.outstanding_amount = Decimal("1.00")

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "cure_to_current",
            cured_by="collector",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("dues are outstanding", result.message)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_OVERDUE)

    @patch("apps.tenant_apps.girvi.flows.has_permission", return_value=True)
    def test_request_renewal_rejects_already_released_loan(self, _mock_has_permission):
        loan = _DummyLoan(LoanLifecycleState.ACTIVE_CURRENT)
        loan.is_released = True

        result = LoanTransitionService(loan, _DummyUser(), tenant=None).execute(
            "request_renewal",
            requested_by="collector",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("Released loans cannot be renewed", result.message)
        self.assertEqual(loan.status, LoanLifecycleState.ACTIVE_CURRENT)

    def test_build_runtime_flow_routes_approved_status_to_v2(self):
        flow = build_runtime_loan_flow(
            _DummyLoan(LoanLifecycleState.APPROVED),
            _DummyUser(),
            tenant=None,
        )
        self.assertIsInstance(flow, GivenLoanFlow)

    def test_build_runtime_flow_routes_taken_loan_to_minimal_flow(self):
        flow = build_runtime_loan_flow(
            _DummyLoan(TakenLoanLifecycleState.DRAFT, loan_type="Taken"),
            _DummyUser(),
            tenant=None,
        )
        self.assertIsInstance(flow, TakenLoanFlow)

