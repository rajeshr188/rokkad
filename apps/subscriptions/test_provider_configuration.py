import json
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.platform_mail.models import Attempt, Delivery
from apps.platform_mail.services import dispatch_one, render_delivery
from apps.platform_mail.tests import MAIL_SETTINGS
from . import test_checkout as checkout_tests
from .checks import check_billing_configuration
from .models import Invoice, ProviderWebhookEvent
from .provider_configuration import provider_mode, require_invoice_mode
from .razorpay_service import client, RazorpayService
from .readiness import assess_billing_configuration, billing_evidence_inventory
from .recurring import provider_test_mode, recurring_provider_mode


class ProviderConfigurationTests(SimpleTestCase):
    def test_disabled_invalid_or_mismatched_mode_prevents_sdk_construction(self):
        for changes in ({"BILLING_PROVIDER_MODE": "disabled"}, {"BILLING_PROVIDER_MODE": "bad"},
                        {"BILLING_PROVIDER_MODE": "live"}, {"RAZORPAY_KEY_ID": "rzp_live_fixture"},
                        {"RAZORPAY_KEY_SECRET": ""}, {"RAZORPAY_KEY_ID": "rzp_test_"}):
            with self.subTest(changes=changes), override_settings(**changes), patch("razorpay.Client") as sdk:
                with self.assertRaises(ValidationError):
                    client()
                sdk.assert_not_called()
                self.assertFalse(RazorpayService.verify_payment_signature("order_a", "pay_a", "bad"))
                self.assertFalse(RazorpayService.verify_subscription_signature("sub_a", "pay_a", "bad"))

    def test_matching_live_mode_supported_but_test_only_operations_stay_restricted(self):
        self.assertEqual(provider_mode(), "test")
        with override_settings(BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture"):
            self.assertEqual(provider_mode(), "live")
            self.assertEqual(recurring_provider_mode(), "live")
            with self.assertRaises(PermissionDenied):
                provider_test_mode()
        with override_settings(BILLING_RECURRING_ENABLED=False):
            self.assertEqual(provider_test_mode(), "test")

    def test_report_is_offline_sanitized_and_never_claims_launch_readiness(self):
        with override_settings(RAZORPAY_KEY_SECRET="DO-NOT-PRINT", RAZORPAY_WEBHOOK_SECRET="PRIVATE-WEBHOOK"), patch("razorpay.Client") as sdk:
            report = assess_billing_configuration()
        sdk.assert_not_called()
        self.assertTrue(report["configuration_ready"])
        self.assertFalse(report["launch_ready"])
        self.assertTrue(report["live_recurring_supported"])
        for value in ("DO-NOT-PRINT", "PRIVATE-WEBHOOK", "rzp_test_fixture"):
            self.assertNotIn(value, json.dumps(report))

    def test_command_and_deployment_warning_distinguish_disabled_from_enabled(self):
        with override_settings(BILLING_PROVIDER_MODE="disabled", BILLING_CHECKOUT_ENABLED=False, BILLING_RECURRING_ENABLED=False):
            self.assertEqual(check_billing_configuration(None), [])
            with self.assertRaises(CommandError):
                call_command("check_billing_configuration", require_configured=True, stdout=StringIO())
        with override_settings(BILLING_PROVIDER_MODE="live", BILLING_RECURRING_ENABLED=True):
            self.assertEqual(check_billing_configuration(None)[0].id, "subscriptions.W001")


@override_settings(**MAIL_SETTINGS, BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture",
                   BILLING_CHECKOUT_ENABLED=True, RAZORPAY_KEY_SECRET="test-secret", RAZORPAY_WEBHOOK_SECRET="webhook-secret")
class BillingModeEvidenceTests(TestCase):
    setUp = checkout_tests.CheckoutTests.setUp
    order = checkout_tests.CheckoutTests.order
    payment = checkout_tests.CheckoutTests.payment
    confirm = checkout_tests.CheckoutTests.confirm
    webhook = checkout_tests.CheckoutTests.webhook

    def test_new_checkout_freezes_mode_and_cannot_replay_as_live(self):
        invoice = self.order()
        self.assertEqual(invoice.checkout_snapshot["provider_mode"], "test")
        with override_settings(BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture"):
            with self.assertRaises(ValidationError):
                self.order(request_key=invoice.checkout_key)
            with self.assertRaises(ValidationError):
                self.confirm(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "issued")

    def test_disabled_webhook_rejects_before_persisting_any_event(self):
        with override_settings(BILLING_PROVIDER_MODE="disabled"):
            self.assertEqual(self.webhook({"event": "payment.captured", "payload": {}}).status_code, 503)
        self.assertFalse(ProviderWebhookEvent.objects.exists())

    def test_legacy_mode_is_not_rewritten_and_live_recovery_fails_closed(self):
        invoice = self.order()
        # Unsaved historical representation; never rewrite immutable DB snapshots.
        invoice.checkout_snapshot = {k: v for k, v in invoice.checkout_snapshot.items() if k != "provider_mode"}
        self.assertEqual(require_invoice_mode(invoice), "test")
        with override_settings(BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture"), self.assertRaises(ValidationError):
            require_invoice_mode(invoice)

    def test_inventory_counts_missing_json_keys_and_never_emits_contacts(self):
        current = self.order()
        Invoice.objects.create(subscription=current.subscription, invoice_number="legacy-unknown",
            base_amount=1, gst_rate=0, invoice_date=current.invoice_date, due_date=current.due_date)
        report = billing_evidence_inventory()
        self.assertEqual(report["one_off_invoices_by_mode"]["test"], 1)
        self.assertEqual(report["unclassified_one_off_invoices"], 1)
        self.assertTrue(report["blockers"])
        self.assertNotIn("owner@example.test", json.dumps(report))
        with override_settings(BILLING_PROVIDER_MODE="live"):
            self.assertIn("another provider mode", billing_evidence_inventory()["blockers"][0])

    def test_test_receipts_are_labelled_and_cannot_enter_real_send(self):
        invoice = self.order()
        self.confirm(invoice)
        row = Delivery.objects.get(invoice=invoice)
        message = render_delivery(row)
        self.assertTrue(message["subject"].startswith("[TEST]"))
        self.assertIn("No real money was charged", message["text"])
        for mode in ("test", "live"):
            with override_settings(BILLING_PROVIDER_MODE=mode), patch("apps.platform_mail.transport.send_ses") as send:
                with self.assertRaises(ValidationError):
                    dispatch_one(row.pk)
                send.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.status, "queued")
        self.assertFalse(Attempt.objects.exists())
        self.assertEqual(dispatch_one(row.pk, capture=True), "captured")

    def test_unclassified_receipts_are_not_sent(self):
        invoice = self.order()
        self.confirm(invoice)
        row = Delivery.objects.get(invoice=invoice)
        with override_settings(BILLING_PROVIDER_MODE="live"), patch("apps.subscriptions.provider_configuration.invoice_mode", return_value=None), patch("apps.platform_mail.transport.send_ses") as send:
            with self.assertRaises(ValidationError):
                dispatch_one(row.pk)
            send.assert_not_called()
