from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant_apps.girvi.transitions.commands import (
    DisburseTransitionCommand,
    GenericForwardTransitionCommand,
    MarkAuctionedTransitionCommand,
    MarkSoldTransitionCommand,
    UndoReleaseTransitionCommand,
)
from apps.tenant_apps.girvi.models import LoanLifecycleState
from apps.tenant_apps.girvi.transitions.payloads import CancelPayload
from apps.tenant_apps.girvi.transitions.payloads import MarkAuctionedPayload
from apps.tenant_apps.girvi.transitions.payloads import MarkSoldPayload
from apps.tenant_apps.girvi.transitions.types import TransitionResult


class TransitionCommandBehaviorTests(TestCase):
    def _loan(self, status=LoanLifecycleState.ACTIVE_CURRENT):
        return SimpleNamespace(
            status=status,
            pk=1,
            release=SimpleNamespace(delete=lambda: None),
            payments=SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(delete=lambda: None)),
        )

    def test_disburse_command_success_with_created_voucher(self):
        loan = self._loan(status=LoanLifecycleState.ACTIVE_CURRENT)
        cmd = DisburseTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = LoanLifecycleState.ACTIVE_CURRENT

        payment = SimpleNamespace(payment_id="PV-001")
        with patch(
            "apps.tenant_apps.girvi.service_modules.payment.record_loan_disbursal",
            return_value=(payment, True),
        ):
            result = cmd.execute(transition_method)

        self.assertIsInstance(result, TransitionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.level, "success")
        self.assertTrue(result.created)
        self.assertEqual(result.payment, payment)

    def test_disburse_command_idempotent_existing_voucher(self):
        loan = self._loan(status=LoanLifecycleState.ACTIVE_CURRENT)
        cmd = DisburseTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = LoanLifecycleState.ACTIVE_CURRENT

        payment = SimpleNamespace(payment_id="PV-EXIST")
        with patch(
            "apps.tenant_apps.girvi.service_modules.payment.record_loan_disbursal",
            return_value=(payment, False),
        ):
            result = cmd.execute(transition_method)

        self.assertTrue(result.success)
        self.assertEqual(result.level, "success")
        self.assertFalse(result.created)
        self.assertEqual(result.payment, payment)
        self.assertIn("already recorded", result.message)

    def test_disburse_command_returns_error_when_posting_fails(self):
        loan = self._loan(status=LoanLifecycleState.ACTIVE_CURRENT)
        cmd = DisburseTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = LoanLifecycleState.ACTIVE_CURRENT

        with patch(
            "apps.tenant_apps.girvi.service_modules.payment.record_loan_disbursal",
            side_effect=Exception("posting failed"),
        ):
            result = cmd.execute(transition_method)

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("posting failed", result.message)

    @patch("apps.tenant_apps.girvi.transitions.commands.post_auction_recovery_for_transition")
    def test_mark_auctioned_posts_recovery_voucher(self, mock_post_auction):
        loan = self._loan(status=LoanLifecycleState.AUCTION_IN_PROGRESS)
        cmd = MarkAuctionedTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)
        mock_post_auction.return_value = (SimpleNamespace(payment_id="AUC-001"), True)

        called = {"ok": False}

        def transition_method(**_payload):
            called["ok"] = True
            loan.status = LoanLifecycleState.AUCTION_COMPLETE

        payload = MarkAuctionedPayload(auctioned_by="auditor", amount=100)
        result = cmd.execute(transition_method, payload=payload)
        self.assertTrue(called["ok"])
        self.assertTrue(result.success)
        self.assertEqual(result.level, "success")
        self.assertIn("posted", result.message)
        mock_post_auction.assert_called_once_with(loan, payload.amount, cmd.user)

    def test_mark_auctioned_requires_positive_recovery_amount(self):
        loan = self._loan(status=LoanLifecycleState.AUCTION_IN_PROGRESS)
        cmd = MarkAuctionedTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = LoanLifecycleState.AUCTION_COMPLETE

        payload = MarkAuctionedPayload(auctioned_by="auditor", amount=0)
        result = cmd.execute(transition_method, payload=payload)

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("greater than zero", result.message)

    @patch("apps.tenant_apps.girvi.transitions.commands.create_girvi_reminder_batch")
    def test_mark_auctioned_creates_notify_v2_auction_notice_for_borrower(
        self,
        mock_create_notice,
    ):
        borrower = SimpleNamespace(name="Asha")
        loan = self._loan(status=LoanLifecycleState.AUCTION_IN_PROGRESS)
        loan.borrower = borrower
        loan.loan_id = "GL-001"

        cmd = MarkAuctionedTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = LoanLifecycleState.AUCTION_COMPLETE

        payload = MarkAuctionedPayload(auctioned_by="auditor", amount=100)
        with patch(
            "apps.tenant_apps.girvi.transitions.commands.post_auction_recovery_for_transition"
        ) as mock_post_auction:
            mock_post_auction.return_value = (
                SimpleNamespace(payment_id="AUC-002"),
                True,
            )
            result = cmd.execute(transition_method, payload=payload)

        self.assertTrue(result.success)
        mock_create_notice.assert_called_once()
        self.assertEqual(
            mock_create_notice.call_args.kwargs["event_key"],
            "loan.auction_notice_due",
        )
        self.assertEqual(mock_create_notice.call_args.kwargs["loans"], [loan])
        self.assertIn("Auction notice", result.message)

    @patch("apps.tenant_apps.girvi.transitions.commands.LoanChangeLog.objects.create")
    @patch("apps.tenant_apps.girvi.transitions.commands.ContentType.objects.get_for_model")
    @patch(
        "apps.tenant_apps.girvi.transitions.commands.create_girvi_reminder_batch",
        side_effect=Exception("notify unavailable"),
    )
    def test_auction_notice_failure_records_visible_change_log(
        self,
        _mock_create_notice,
        mock_content_type,
        mock_log_create,
    ):
        borrower = SimpleNamespace(name="Asha")
        loan = self._loan(status=LoanLifecycleState.AUCTION_IN_PROGRESS)
        loan.borrower = borrower
        loan.loan_id = "GL-001"
        mock_content_type.return_value = SimpleNamespace(pk=44)
        user = SimpleNamespace(pk=7)

        cmd = MarkAuctionedTransitionCommand(loan=loan, user=user, tenant=None)

        def transition_method(**_payload):
            loan.status = LoanLifecycleState.AUCTION_COMPLETE

        payload = MarkAuctionedPayload(auctioned_by="auditor", amount=100)
        with patch(
            "apps.tenant_apps.girvi.transitions.commands.post_auction_recovery_for_transition"
        ) as mock_post_auction:
            mock_post_auction.return_value = (
                SimpleNamespace(payment_id="AUC-003"),
                True,
            )
            result = cmd.execute(transition_method, payload=payload)

        self.assertTrue(result.success)
        mock_log_create.assert_called_once()
        self.assertEqual(
            mock_log_create.call_args.kwargs["metadata"]["event"],
            "auction_notice_failed",
        )
        self.assertIn("notify unavailable", mock_log_create.call_args.kwargs["notes"])

    @patch("apps.tenant_apps.girvi.transitions.commands.post_sale_recovery_for_transition")
    def test_mark_sold_posts_recovery_voucher(self, mock_post_sale):
        loan = self._loan(status=LoanLifecycleState.AUCTION_IN_PROGRESS)
        cmd = MarkSoldTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)
        mock_post_sale.return_value = (SimpleNamespace(payment_id="SOLD-001"), True)

        def transition_method(**_payload):
            loan.status = LoanLifecycleState.AUCTION_COMPLETE

        result = cmd.execute(
            transition_method,
            payload=MarkSoldPayload(sold_by="checker", amount=250),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.level, "success")
        self.assertIn("posted", result.message)
        mock_post_sale.assert_called_once_with(loan, 250, cmd.user)

    def test_undo_release_returns_error_on_validation_exception(self):
        loan = self._loan(status=LoanLifecycleState.CLOSED)
        cmd = UndoReleaseTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            raise ValidationError("cannot reverse")

        result = cmd.execute(transition_method)
        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("cannot reverse", result.message)

    def test_generic_forward_command_accepts_typed_payload(self):
        loan = self._loan(status="Approved")
        cmd = GenericForwardTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)
        captured = {}

        def transition_method(**kwargs):
            captured.update(kwargs)

        payload = CancelPayload(cancelled_by="alice", reason="duplicate")
        result = cmd.execute(transition_method, payload=payload)

        self.assertTrue(result.success)
        self.assertEqual(captured["cancelled_by"], "alice")
        self.assertEqual(captured["reason"], "duplicate")

    def test_generic_forward_command_rejects_untyped_payload(self):
        loan = self._loan(status="Approved")
        cmd = GenericForwardTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**kwargs):
            return kwargs

        with self.assertRaises(TypeError):
            cmd.execute(transition_method, payload={"cancelled_by": "alice"})
