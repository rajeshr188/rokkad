"""Fictional seller details and mocked payments; no provider or email requests."""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.platform_mail.models import Delivery
from apps.platform_mail.services import render_delivery
from apps.platform_mail.tests import MAIL_SETTINGS
from apps.tenancy.context import workspace_context
from . import test_checkout as checkout_tests
from . import recurring_owner
from .invoice_pdf import render_invoice_pdf
from .models import Invoice, RecurringPlanBinding
from .readiness import assess_billing_configuration
from .seller import live_seller, NO_GST_NOTE
from .test_recurring_owner import OwnerFixture

SELLER_SETTINGS = dict(BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture",
    RAZORPAY_KEY_SECRET="test-secret", RAZORPAY_WEBHOOK_SECRET="webhook-secret",
    BILLING_TAX_RATE="0", BILLING_SELLER_NAME="Fictional Seller",
    BILLING_SELLER_ADDRESS="1 Example Street\nExample City", BILLING_SELLER_TAX_STATUS="unregistered",
    BILLING_CHECKOUT_ENABLED=True, BILLING_RECURRING_ENABLED=False,
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})


@override_settings(**SELLER_SETTINGS)
class SellerConfigurationTests(SimpleTestCase):
    def test_live_readiness_requires_complete_explicit_unregistered_configuration(self):
        self.assertEqual(live_seller()["name"], "Fictional Seller")
        self.assertTrue(assess_billing_configuration()["configuration_ready"])
        for changes in ({"BILLING_SELLER_NAME": ""}, {"BILLING_SELLER_ADDRESS": ""},
                        {"BILLING_SELLER_TAX_STATUS": ""}, {"BILLING_SELLER_TAX_STATUS": "registered"},
                        {"BILLING_TAX_RATE": "18"}, {"BILLING_TAX_RATE": ""},
                        {"BILLING_TAX_RATE": "NaN"}, {"BILLING_TAX_RATE": "Infinity"},
                        {"BILLING_TAX_RATE": "-1"}, {"BILLING_TAX_RATE": "wrong"},
                        {"BILLING_SELLER_NAME": "Name\nInjected"}):
            with self.subTest(changes=changes), override_settings(**changes):
                with self.assertRaises(ValidationError):
                    live_seller()
                self.assertFalse(assess_billing_configuration()["configuration_ready"])

    def test_readiness_never_prints_the_seller_or_claims_launch_approval(self):
        report = assess_billing_configuration()
        self.assertNotIn("Fictional Seller", str(report))
        self.assertNotIn("Example Street", str(report))
        self.assertFalse(report["launch_ready"])

    def test_test_mode_still_requires_explicit_tax_without_requiring_a_seller(self):
        with override_settings(BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture",
                               BILLING_TAX_RATE="", BILLING_SELLER_NAME=""):
            self.assertFalse(assess_billing_configuration()["configuration_ready"])
            with override_settings(BILLING_TAX_RATE="18"):
                self.assertTrue(assess_billing_configuration()["configuration_ready"])


@override_settings(**SELLER_SETTINGS)
class SellerInvoiceTests(TestCase):
    setUp = checkout_tests.CheckoutTests.setUp
    order = checkout_tests.CheckoutTests.order
    payment = checkout_tests.CheckoutTests.payment
    confirm = checkout_tests.CheckoutTests.confirm

    def test_missing_seller_or_nonzero_tax_blocks_order_before_provider_call(self):
        for changes in ({"BILLING_SELLER_NAME": ""}, {"BILLING_TAX_RATE": "18"}):
            with override_settings(**changes), self.assertRaises(ValidationError):
                self.order()
        self.order_mock.assert_not_called()
        self.assertFalse(Invoice.objects.exists())

    def test_new_invoice_freezes_issuer_and_zero_tax_and_database_rejects_rewrite(self):
        invoice = self.order()
        self.assertEqual(invoice.billing_seller, live_seller())
        self.assertEqual(invoice.total_amount, Decimal("100.01"))
        self.assertEqual(invoice.checkout_snapshot["amount"], 10001)
        snapshot = deepcopy(invoice.checkout_snapshot)
        snapshot["seller"]["name"] = "Replacement Seller"
        with self.assertRaises(DatabaseError), transaction.atomic():
            Invoice.objects.filter(pk=invoice.pk).update(checkout_snapshot=snapshot)

    def test_confirmation_retry_and_rendering_keep_frozen_issuer_when_config_changes(self):
        invoice = self.order()
        with override_settings(BILLING_SELLER_NAME="Replacement Seller", BILLING_TAX_RATE="18",
                               BILLING_SELLER_TAX_STATUS=""):
            self.assertEqual(self.order(request_key=invoice.checkout_key).pk, invoice.pk)
            self.confirm(invoice)
            invoice.refresh_from_db()
            self.assertEqual(invoice.billing_seller["name"], "Fictional Seller")
            self.assertEqual(invoice.billing_tax_note, NO_GST_NOTE)
            self.assertEqual(invoice.total_amount, Decimal("100.01"))
            with override_settings(**MAIL_SETTINGS):
                message = render_delivery(Delivery.objects.get(invoice=invoice))
            self.assertIn("Fictional Seller", message["text"])
            self.assertIn(NO_GST_NOTE, message["text"])
            self.assertNotIn("Replacement Seller", message["text"])

    def test_html_and_pdf_show_same_saved_seller_and_no_gst_line(self):
        invoice = self.order()
        html = render_to_string("subscriptions/_seller.html", {"seller": invoice.billing_seller})
        self.assertIn("Fictional Seller", html)
        self.assertIn("Example City", html)
        with patch("reportlab.rl_config.pageCompression", 0):
            pdf = render_invoice_pdf(invoice)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(b"Fictional Seller", pdf)
        self.assertIn(NO_GST_NOTE.encode(), pdf)
        self.assertNotIn(b"GST \\(0", pdf)
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:invoice-detail", kwargs={"workspace_slug":self.workspace.slug,"pk":invoice.pk})
        page = self.client.get(url)
        self.assertContains(page, "Fictional Seller")
        self.assertContains(page, NO_GST_NOTE)
        self.assertNotContains(page, "GST (0")

    def test_historical_invoice_does_not_inherit_current_issuer_or_no_gst_claim(self):
        with override_settings(BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture", BILLING_TAX_RATE="18"):
            invoice = self.order()
        self.assertIsNone(invoice.billing_seller)
        self.assertEqual(invoice.billing_tax_note, "")
        with patch("reportlab.rl_config.pageCompression", 0):
            pdf = render_invoice_pdf(invoice)
        self.assertNotIn(b"Fictional Seller", pdf)
        self.assertNotIn(NO_GST_NOTE.encode(), pdf)
        self.assertIn(b"118.01", pdf)

    def test_checkout_page_blocks_invalid_live_configuration_and_shows_valid_seller(self):
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:checkout", kwargs={"workspace_slug":self.workspace.slug,"plan_id":self.plan.pk})
        self.assertContains(self.client.get(url), NO_GST_NOTE)
        with override_settings(BILLING_SELLER_NAME=""):
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_seller_text_is_escaped_and_conflicting_invoice_tax_fails_closed(self):
        with override_settings(BILLING_SELLER_NAME="Seller <script>text</script>"):
            invoice = self.order()
        html = render_to_string("subscriptions/_seller.html", {"seller": invoice.billing_seller})
        self.assertNotIn("<script>", html)
        invoice.gst_rate = Decimal("18")
        with self.assertRaises(ValidationError):
            render_invoice_pdf(invoice)


@override_settings(**{**SELLER_SETTINGS, "BILLING_CHECKOUT_ENABLED":False})
class SellerRecurringTests(OwnerFixture, TestCase):
    provider_mode = "live"
    offer_mode = "live"

    def test_cycle_inherits_binding_issuer_despite_current_profile_change(self):
        with override_settings(BILLING_SELLER_NAME="Replacement Seller", BILLING_TAX_RATE="18",
                               BILLING_SELLER_TAX_STATUS=""):
            cycle = self.record()
        self.assertEqual(cycle.invoice.billing_seller, self.binding.snapshot["seller"])
        self.assertEqual(cycle.invoice.total_amount, Decimal("1499.00"))
        self.assertEqual(cycle.invoice.billing_tax_note, NO_GST_NOTE)
        changed = deepcopy(self.binding.snapshot)
        changed["seller"]["name"] = "Replacement"
        with self.assertRaises(DatabaseError), transaction.atomic():
            RecurringPlanBinding.objects.filter(pk=self.binding.pk).update(snapshot=changed)

    @override_settings(BILLING_RECURRING_ENABLED=True)
    def test_current_seller_authorizes_and_changed_seller_blocks_new_consent(self):
        self.provider_agreement["status"] = "created"
        with workspace_context(self.workspace.pk):
            options = recurring_owner.authorization_options(**self.args())
        self.assertEqual(options["name"], "Rokkad")
        self.assertNotIn("amount", options)
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:recurring", kwargs={"workspace_slug":self.workspace.slug})
        self.assertContains(self.client.get(url), 'id="recurring-authorize"')
        self.assertContains(self.client.get(url), NO_GST_NOTE)
        with override_settings(BILLING_SELLER_NAME="Replacement"):
            with workspace_context(self.workspace.pk), self.assertRaises(ValidationError):
                recurring_owner.authorization_options(**self.args())
            self.assertNotContains(self.client.get(url), 'id="recurring-authorize"')
