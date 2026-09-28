import json
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.orgs.audit import AuditLog
from apps.platform_mail.models import Attempt, Delivery, Suppression
from apps.platform_mail.rehearsal import dispatch_test_receipt, preview_test_receipt, require_rehearsal_runtime
from apps.platform_mail.services import dispatch_one, recipient_hash
from apps.platform_mail.tests import MAIL_SETTINGS
from apps.platform_mail.transport import TransportFailure
from apps.subscriptions import test_checkout as checkout_tests


@override_settings(BILLING_REHEARSAL=True, BILLING_PROVIDER_MODE="test",
                   RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture")
class ReceiptRuntimeTests(SimpleTestCase):
    @patch("apps.platform_mail.rehearsal.connection")
    def test_runtime_requires_exact_isolated_database_loopback_and_restricted_role(self, connection):
        name = "rokkad_baseline_rehearsal_billing_receipt"
        connection.settings_dict = {"NAME": name, "HOST": "127.0.0.1"}
        cursor = connection.cursor.return_value.__enter__.return_value
        with override_settings(REHEARSAL_DATABASE_NAME=name):
            cursor.fetchone.return_value = (name, False, False)
            require_rehearsal_runtime()
            for observed in [(name, True, False), (name, False, True), ("production", False, False)]:
                cursor.fetchone.return_value = observed
                with self.assertRaises(PermissionDenied):
                    require_rehearsal_runtime()
            for field, value in [("HOST", "remote-db"), ("NAME", "production")]:
                with patch.dict(connection.settings_dict, {field: value}), self.assertRaises(PermissionDenied):
                    require_rehearsal_runtime()
        with override_settings(REHEARSAL_DATABASE_NAME="production"), self.assertRaises(PermissionDenied):
            require_rehearsal_runtime()
        with override_settings(BILLING_REHEARSAL=False), self.assertRaises(PermissionDenied):
            require_rehearsal_runtime()
        with override_settings(BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture"), self.assertRaises(PermissionDenied):
            require_rehearsal_runtime()


@override_settings(**MAIL_SETTINGS, BILLING_CHECKOUT_ENABLED=True,
                   BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_SECRET="test-secret",
                   RAZORPAY_WEBHOOK_SECRET="webhook-secret")
class ReceiptRehearsalTests(TestCase):
    order = checkout_tests.CheckoutTests.order
    payment = checkout_tests.CheckoutTests.payment
    confirm = checkout_tests.CheckoutTests.confirm

    def setUp(self):
        checkout_tests.CheckoutTests.setUp(self)
        self.owner.email = "receipt-test@rokkad.com"
        self.owner.save(update_fields=["email"])
        self.invoice = self.order()
        self.confirm(self.invoice)
        self.row = Delivery.objects.get(invoice=self.invoice)
        self.arguments = dict(actor=self.owner, recipient=self.owner.email, reference="RECEIPT-TEST-001")
        self.runtime = patch("apps.platform_mail.rehearsal.require_rehearsal_runtime").start()

    def test_preview_is_read_only_labelled_and_does_not_print_recipient(self):
        before = list(Delivery.objects.values())
        audits = AuditLog.objects.count()
        with patch("apps.platform_mail.transport.send_ses") as send:
            row, message = preview_test_receipt(self.row.pk, **self.arguments)
            output = StringIO()
            call_command("rehearse_billing_receipt", delivery=str(row.pk), actor_id=self.owner.pk,
                         recipient=self.owner.email, reference="RECEIPT-TEST-001", stdout=output)
            send.assert_not_called()
        self.assertTrue(message["subject"].startswith("[TEST]"))
        self.assertIn("No real money was charged", message["text"])
        self.assertTrue(json.loads(output.getvalue())["preview_only"])
        self.assertNotIn(self.owner.email, output.getvalue())
        self.assertEqual(before, list(Delivery.objects.values()))
        self.assertEqual(audits, AuditLog.objects.count())
        self.assertFalse(Attempt.objects.exists())

    def test_one_send_records_attempt_and_audit_and_replay_does_not_resend(self):
        with patch("apps.platform_mail.transport.send_ses", return_value="ses-receipt") as send:
            self.assertEqual(dispatch_test_receipt(self.row.pk, **self.arguments), "accepted")
            self.assertEqual(dispatch_test_receipt(self.row.pk, **self.arguments), "accepted")
            send.assert_called_once()
            self.assertEqual(send.call_args.args[0]["recipient"], self.owner.email)
        self.assertEqual(Attempt.objects.get().provider_message_id, "ses-receipt")
        audit = AuditLog.objects.get(action="EMAIL_TEST_SEND")
        self.assertEqual(audit.data["recipient_hash"], recipient_hash(self.owner.email))
        self.assertNotIn(self.owner.email, json.dumps(audit.data))

    def test_normal_dispatch_still_refuses_test_receipt(self):
        with patch("apps.platform_mail.transport.send_ses") as send, self.assertRaises(ValidationError):
            dispatch_one(self.row.pk)
        send.assert_not_called()
        self.assertFalse(Attempt.objects.exists())

    def test_mismatched_recipient_fictional_recipient_reference_and_mode_are_rejected(self):
        for arguments in [dict(self.arguments, recipient="other@rokkad.com"),
                          dict(self.arguments, recipient="owner@example.test"),
                          dict(self.arguments, reference="contact@example.com")]:
            with patch("apps.platform_mail.transport.send_ses") as send, self.assertRaises(ValidationError):
                dispatch_test_receipt(self.row.pk, **arguments)
            send.assert_not_called()
        with patch("apps.platform_mail.rehearsal.invoice_mode", return_value="live"), self.assertRaises(ValidationError):
            preview_test_receipt(self.row.pk, **self.arguments)
        self.assertFalse(Attempt.objects.exists())

    def test_foreign_owner_and_changed_delivery_destination_are_rejected(self):
        from django.contrib.auth import get_user_model
        other = get_user_model().objects.create_user(username="receipt-other")
        with self.assertRaises(PermissionDenied):
            preview_test_receipt(self.row.pk, **dict(self.arguments, actor=other))
        Delivery.objects.filter(pk=self.row.pk).update(recipient="other@rokkad.com")
        with self.assertRaises(ValidationError):
            preview_test_receipt(self.row.pk, **dict(self.arguments, recipient="other@rokkad.com"))

    def test_suppression_and_paused_transport_are_preserved(self):
        with override_settings(PLATFORM_EMAIL_ENABLED=False), self.assertRaises(ValidationError):
            dispatch_test_receipt(self.row.pk, **self.arguments)
        Suppression.objects.create(recipient_hash=recipient_hash(self.owner.email), reason="complaint")
        with patch("apps.platform_mail.transport.send_ses") as send, self.assertRaises(ValidationError):
            dispatch_test_receipt(self.row.pk, **self.arguments)
        send.assert_not_called()
        self.assertFalse(Attempt.objects.exists())

    def test_uncertain_outcome_and_throttling_do_not_automatically_retry(self):
        with patch("apps.platform_mail.transport.send_ses", side_effect=TransportFailure("uncertain", outcome="unknown")) as send:
            self.assertEqual(dispatch_test_receipt(self.row.pk, **self.arguments), "unknown")
            self.assertEqual(dispatch_test_receipt(self.row.pk, **self.arguments), "unknown")
            send.assert_called_once()
        # A mistakenly requeued attempted rehearsal is still refused.
        Delivery.objects.filter(pk=self.row.pk).update(status="queued")
        with self.assertRaises(ValidationError):
            dispatch_test_receipt(self.row.pk, **self.arguments)

    def test_throttling_leaves_failed_evidence_without_requeue(self):
        with patch("apps.platform_mail.transport.send_ses", side_effect=TransportFailure("ses_throttled", retryable=True)):
            self.assertEqual(dispatch_test_receipt(self.row.pk, **self.arguments), "failed")
        self.row.refresh_from_db()
        self.assertEqual(self.row.attempt_count, 1)

    def test_audit_failure_rolls_back_claim_before_network(self):
        with patch.object(AuditLog, "log", side_effect=DatabaseError("audit unavailable")), patch("apps.platform_mail.transport.send_ses") as send:
            with self.assertRaises(DatabaseError):
                dispatch_test_receipt(self.row.pk, **self.arguments)
            send.assert_not_called()
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, "queued")
        self.assertEqual(self.row.attempt_count, 0)
        self.assertFalse(Attempt.objects.exists())
