from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.tenant_apps.girvi.transitions.commands import (
    DisburseTransitionCommand,
    GenericForwardTransitionCommand,
    MarkAuctionedTransitionCommand,
    UndoReleaseTransitionCommand,
)
from apps.tenant_apps.girvi.transitions.payloads import CancelPayload
from apps.tenant_apps.girvi.transitions.payloads import MarkAuctionedPayload
from apps.tenant_apps.girvi.transitions.types import TransitionResult


class TransitionCommandBehaviorTests(TestCase):
    def _loan(self, status="Disbursed"):
        return SimpleNamespace(
            status=status,
            pk=1,
            release=SimpleNamespace(delete=lambda: None),
            payments=SimpleNamespace(filter=lambda **kwargs: SimpleNamespace(delete=lambda: None)),
        )

    def test_disburse_command_success_with_created_voucher(self):
        loan = self._loan(status="Disbursed")
        cmd = DisburseTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = "Disbursed"

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
        loan = self._loan(status="Disbursed")
        cmd = DisburseTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = "Disbursed"

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
        loan = self._loan(status="Disbursed")
        cmd = DisburseTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = "Disbursed"

        with patch(
            "apps.tenant_apps.girvi.service_modules.payment.record_loan_disbursal",
            side_effect=Exception("posting failed"),
        ):
            result = cmd.execute(transition_method)

        self.assertFalse(result.success)
        self.assertEqual(result.level, "error")
        self.assertIn("posting failed", result.message)

    def test_mark_auctioned_is_warning_transition(self):
        loan = self._loan(status="Defaulted")
        cmd = MarkAuctionedTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        called = {"ok": False}

        def transition_method(**_payload):
            called["ok"] = True

        payload = MarkAuctionedPayload(auctioned_by="auditor", amount=100)
        result = cmd.execute(transition_method, payload=payload)
        self.assertTrue(called["ok"])
        self.assertTrue(result.success)
        self.assertEqual(result.level, "warning")

    @patch("apps.tenant_apps.notify.services.create_loan_auction_notice")
    def test_mark_auctioned_creates_auction_notice_for_borrower(self, mock_create_notice):
        borrower = SimpleNamespace(name="Asha")
        loan = self._loan(status="Defaulted")
        loan.borrower = borrower
        loan.loan_id = "GL-001"

        cmd = MarkAuctionedTransitionCommand(loan=loan, user=SimpleNamespace(), tenant=None)

        def transition_method(**_payload):
            loan.status = "Auctioned"

        payload = MarkAuctionedPayload(auctioned_by="auditor", amount=100)
        result = cmd.execute(transition_method, payload=payload)

        self.assertTrue(result.success)
        mock_create_notice.assert_called_once()
        self.assertIn("Auction notice", result.message)

    def test_undo_release_returns_error_on_validation_exception(self):
        loan = self._loan(status="Released")
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
