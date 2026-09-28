import json
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.subscriptions import test_checkout as checkout_tests
from apps.subscriptions.models import Payment
from .events import reconcile_sqs_envelope
from .models import Attempt, Delivery, Suppression
from .operations import queue_health, suppress_recipient
from .services import dispatch_one, recipient_hash, retry_delivery
from . import tests as mail_tests


@override_settings(**mail_tests.MAIL_SETTINGS)
class OperationsTests(TestCase):
    setUp = mail_tests.DeliveryTests.setUp

    def test_deployment_operator_identity_is_required(self):
        for operator in (None, "", "private free text"):
            with self.assertRaises(ValidationError):
                suppress_recipient(operator=operator, recipient=self.row.recipient, reference="SUP-123")
        self.assertFalse(Suppression.objects.exists())

    def test_stop_request_audited_without_address_and_blocks_dispatch(self):
        suppression, created = suppress_recipient(operator="test-operator", recipient="  INVITEE@example.test ", reference="SUP-123")
        self.assertTrue(created)
        self.assertEqual(suppression.recipient_hash, recipient_hash(self.row.recipient))
        audit = AuditLog.objects.get(description="Platform mail recipient suppression requested")
        self.assertIsNone(audit.user)
        self.assertEqual(audit.data["operator"], "test-operator")
        self.assertIsNone(audit.company_id)
        self.assertNotIn(self.row.recipient, json.dumps(audit.data))
        with patch("apps.platform_mail.transport.send_ses") as send:
            self.assertEqual(dispatch_one(self.row.pk), "suppressed")
        send.assert_not_called()
        self.assertFalse(Attempt.objects.exists())
        with self.assertRaises(ValidationError):
            retry_delivery(self.row.pk, actor=self.owner)

    def test_preserves_existing_feedback_reason_and_rolls_back_if_audit_fails(self):
        row = Suppression.objects.create(recipient_hash=recipient_hash(self.row.recipient), reason="complaint")
        _, created = suppress_recipient(operator="test-operator", recipient=self.row.recipient, reference="SUP-124")
        row.refresh_from_db()
        self.assertFalse(created)
        self.assertEqual(row.reason, "complaint")
        with patch.object(AuditLog, "log", side_effect=DatabaseError), self.assertRaises(DatabaseError):
            suppress_recipient(operator="test-operator", recipient="new@example.test", reference="SUP-125")
        self.assertFalse(Suppression.objects.filter(recipient_hash=recipient_hash("new@example.test")).exists())

    def test_health_paused_backlog_and_expired_source_are_read_only(self):
        Delivery.objects.filter(pk=self.row.pk).update(available_at=timezone.now()-timedelta(hours=1),
                                                       expires_at=timezone.now()-timedelta(seconds=1))
        with override_settings(PLATFORM_EMAIL_ENABLED=False):
            report = queue_health()
        self.assertNotIn("overdue_queue", report["flags"])
        self.assertEqual(report["queued_source_problems"][0]["problem"], "expired")
        self.assertNotIn(self.row.recipient, json.dumps(report))
        self.assertNotIn(self.invitation.key, json.dumps(report))
        self.assertIn("overdue_queue", queue_health()["flags"])
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "queued")

    def test_health_alerts_for_uncertain_and_stale_without_replaying(self):
        Delivery.objects.filter(pk=self.row.pk).update(status="sending", updated_at=timezone.now()-timedelta(minutes=11))
        self.assertIn("stale_claim", queue_health()["flags"])
        Delivery.objects.filter(pk=self.row.pk).update(status="unknown")
        with self.assertRaises(CommandError):
            call_command("check_platform_mail_queue", require_healthy=True, stdout=StringIO(), stderr=StringIO())
        self.assertIn("uncertain_acceptance", queue_health()["flags"])
        self.assertFalse(Attempt.objects.exists())

    def test_operator_commands_hide_address_and_validate_reference(self):
        out = StringIO()
        with patch("sys.stdin", StringIO(self.row.recipient+"\n")):
            call_command("suppress_platform_mail", operator="test-operator", reference="SUP-126", recipient_stdin=True, stdout=out)
        self.assertNotIn(self.row.recipient, out.getvalue())
        with self.assertRaises(ValidationError):
            suppress_recipient(operator="test-operator", recipient=self.row.recipient, reference="request with private text")
        with self.assertRaises(CommandError):
            call_command("check_platform_mail_queue", since="not-a-date", stdout=StringIO())

    def test_rejected_feedback_is_not_acknowledged_and_fails_the_worker(self):
        with patch("apps.platform_mail.management.commands.receive_platform_mail_events.aws_client") as client:
            client.return_value.receive_message.return_value = {"Messages": [{"Body": "{}", "ReceiptHandle": "private"}]}
            with self.assertRaises(CommandError):
                call_command("receive_platform_mail_events", stdout=StringIO(), stderr=StringIO())
            client.return_value.delete_message.assert_not_called()


@override_settings(**mail_tests.MAIL_SETTINGS, BILLING_CHECKOUT_ENABLED=True,
                   BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_mockfixture",
                   RAZORPAY_KEY_SECRET="test-secret", RAZORPAY_WEBHOOK_SECRET="webhook-secret")
class ReceiptAcceptanceTests(TestCase):
    setUp = checkout_tests.CheckoutTests.setUp
    order = checkout_tests.CheckoutTests.order
    payment = checkout_tests.CheckoutTests.payment
    confirm = checkout_tests.CheckoutTests.confirm
    envelope = mail_tests.DeliveryTests.envelope

    def test_paid_invoice_to_rendered_receipt_delivery_and_replay(self):
        invoice = self.order()
        self.confirm(invoice)
        self.confirm(invoice)
        self.row = Delivery.objects.get(invoice=invoice)
        with override_settings(PLATFORM_EMAIL_ENABLED=False), patch("apps.platform_mail.transport.send_ses") as send:
            with self.assertRaises(ValidationError):
                dispatch_one(self.row.pk)
            send.assert_not_called()
        with patch("apps.platform_mail.transport.send_ses", return_value="ses-message-1") as send:
            self.assertEqual(dispatch_one(self.row.pk), "accepted")
            message = send.call_args.args[0]
            self.assertEqual(message["sender"], mail_tests.MAIL_SETTINGS["BILLING_EMAIL_SENDER"])
            self.assertEqual(message["reply_to"], "billing@rokkad.com")
            self.assertEqual(message["recipient"], "owner@example.test")
            self.assertIn(invoice.invoice_number, message["text"])
            self.assertIn("118.01", message["text"])
            event = self.envelope(attempt=Attempt.objects.get(delivery=self.row))
            self.assertTrue(reconcile_sqs_envelope(event))
            self.assertFalse(reconcile_sqs_envelope(event))
            self.assertEqual(dispatch_one(self.row.pk), "delivered")
            send.assert_called_once()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Delivery.objects.filter(invoice=invoice).count(), 1)
