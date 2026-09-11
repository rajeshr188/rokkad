import hashlib
import hmac
import json
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from .checkout import create_checkout, confirm_checkout
from .models import Invoice, Payment, Plan, Subscription, SubscriptionEvent, ProviderWebhookEvent
from .razorpay_service import RazorpayService
from .views import OrderView, PaymentView, InvoicePDFView, razorpay_webhook


@override_settings(RAZORPAY_KEY_SECRET="test-secret", RAZORPAY_WEBHOOK_SECRET="webhook-secret")
class CheckoutTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="checkout-owner", email="owner@example.test")
        self.workspace = Company.all_objects.create(name="Checkout", schema_name="checkout", owner=self.owner, creator=self.owner)
        role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.create(company=self.workspace, user=self.owner, role=role)
        self.plan = Plan.objects.create(name="Checkout Plan", tier="starter", price=Decimal("100.01"), description="Test")
        self.factory = RequestFactory()
        self.order_mock = patch.object(RazorpayService, "create_order", side_effect=lambda **kw: {
            "id": "order_" + kw["receipt"], "amount": kw["amount"], "currency": kw["currency"],
        }).start()
        self.addCleanup(patch.stopall)

    def order(self, **kwargs):
        with workspace_context(self.workspace.pk):
            return create_checkout(workspace=self.workspace, actor=self.owner, plan_id=self.plan.pk,
                                   billing_cycle=kwargs.pop("billing_cycle", "monthly"),
                                   request_key=kwargs.pop("request_key", uuid4()), **kwargs)

    def payment(self, invoice, **changes):
        return {"id": "pay_test", "order_id": invoice.razorpay_order_id,
                "amount": invoice.checkout_snapshot["amount"], "currency": "INR", "status": "captured", **changes}

    def confirm(self, invoice, **changes):
        signature = hmac.new(b"test-secret", f"{invoice.razorpay_order_id}|pay_test".encode(), hashlib.sha256).hexdigest()
        with workspace_context(self.workspace.pk), patch.object(RazorpayService, "get_payment_status", return_value=self.payment(invoice, **changes)):
            return confirm_checkout(workspace=self.workspace, actor=self.owner, order_id=invoice.razorpay_order_id,
                                    payment_id="pay_test", signature=signature)

    def webhook(self, data, event_id="evt-test"):
        body = json.dumps(data).encode()
        signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
        return razorpay_webhook(self.factory.post("/webhook/", body, content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature, HTTP_X_RAZORPAY_EVENT_ID=event_id))

    def test_order_freezes_price_and_does_not_grant_trial_or_entitlements(self):
        invoice = self.order()
        self.assertEqual(invoice.checkout_snapshot["amount"], 11801)
        self.assertEqual(invoice.subscription.status, "past_due")
        self.assertIsNone(invoice.subscription.trial_end_date)
        self.assertFalse(invoice.subscription.entitlements.exists())

    def test_same_checkout_reuses_order(self):
        key = uuid4()
        first, second = self.order(request_key=key), self.order(request_key=key)
        self.assertEqual(first.pk, second.pk)
        self.order_mock.assert_called_once()
        with self.assertRaises(ValidationError):
            self.order(request_key=key, billing_cycle="yearly")

    def test_checkout_uses_frozen_catalog_and_preserves_billing_contact(self):
        from .models import BillingAccount
        BillingAccount.objects.create(company=self.workspace, contact_name="Accounts", billing_email="accounts@example.test")
        invoice = self.order()
        Plan.objects.filter(pk=self.plan.pk).update(price=999, max_users=999)
        self.confirm(invoice)
        self.assertEqual(invoice.billing_contact_email, "accounts@example.test")
        self.assertEqual(invoice.total_amount, Decimal("118.01"))
        self.assertNotEqual(invoice.subscription.entitlements.get(feature_code="workspace.max_members").value, "999")

    def test_receipt_scheduled_once_after_success_and_not_after_rollback(self):
        invoice = self.order()
        with patch("apps.subscriptions.notifications.send_mail") as mail:
            with self.captureOnCommitCallbacks(execute=True):
                self.confirm(invoice)
                self.confirm(invoice)
            mail.assert_called_once()
            self.assertEqual(mail.call_args.args[3], ["owner@example.test"])

    def test_real_http_order_and_confirmation(self):
        self.client.force_login(self.owner)
        kwargs = {"workspace_slug": self.workspace.slug}
        result = self.client.post(reverse("workspace_subscriptions:order-create", kwargs=kwargs),
            {"plan_id": self.plan.pk, "billing_cycle": "monthly", "checkout_key": str(uuid4())}, content_type="application/json")
        self.assertEqual(result.status_code, 200)
        invoice = Invoice.objects.get()
        signature = hmac.new(b"test-secret", f"{invoice.razorpay_order_id}|pay_test".encode(), hashlib.sha256).hexdigest()
        with patch.object(RazorpayService, "get_payment_status", return_value=self.payment(invoice)):
            result = self.client.post(reverse("workspace_subscriptions:payment-create", kwargs=kwargs), {
                "razorpay_order_id": invoice.razorpay_order_id, "razorpay_payment_id": "pay_test",
                "razorpay_signature": signature, "plan_id": 999999,
            }, content_type="application/json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(Subscription.objects.get().plan_id, self.plan.pk)

    def test_renewal_extends_once_and_active_plan_switch_is_rejected(self):
        invoice = self.order()
        self.confirm(invoice)
        previous = Subscription.objects.get().end_date
        renewal = self.order(billing_cycle="yearly")
        from .checkout import _apply_capture
        _apply_capture(invoice_id=renewal.pk, payment=self.payment(renewal, id="pay_renewal"))
        from dateutil.relativedelta import relativedelta
        self.assertEqual(Subscription.objects.get().end_date, previous + relativedelta(years=1))
        self.plan = Plan.objects.create(name="Other plan", tier="professional", price=Decimal("500"), description="Test")
        with self.assertRaises(ValidationError):
            self.order()

    def test_expired_paid_plan_can_purchase_new_term_without_replay_reactivation(self):
        from datetime import timedelta
        from django.utils import timezone
        from .billing import effective_billing_state
        first = self.order()
        self.confirm(first)
        Subscription.objects.filter(pk=first.subscription_id).update(end_date=timezone.now() - timedelta(days=1))
        self.confirm(first)
        self.assertFalse(effective_billing_state(Subscription.objects.get()).commercially_available)
        self.plan = Plan.objects.create(name="New term", tier="professional", price=Decimal("500"), description="Test")
        renewal = self.order()
        from .checkout import _apply_capture
        before = timezone.now()
        _apply_capture(invoice_id=renewal.pk, payment=self.payment(renewal, id="pay_new_term"))
        subscription = Subscription.objects.get()
        self.assertTrue(effective_billing_state(subscription).commercially_available)
        self.assertEqual(subscription.plan_id, self.plan.pk)
        self.assertGreater(subscription.end_date, before + timedelta(days=27))

    def test_invalid_signature_never_fetches_payment(self):
        invoice = self.order()
        with workspace_context(self.workspace.pk), patch.object(RazorpayService, "get_payment_status") as fetch:
            for signature in ("wrong", "\u20b9", None):
                with self.assertRaises(ValidationError):
                    confirm_checkout(workspace=self.workspace, actor=self.owner, order_id=invoice.razorpay_order_id,
                                     payment_id="pay_test", signature=signature)
            fetch.assert_not_called()

    def test_capture_is_atomic_and_replay_does_not_extend_access(self):
        invoice = self.order()
        self.confirm(invoice)
        subscription = Subscription.objects.get(pk=invoice.subscription_id)
        end = subscription.end_date
        self.assertEqual(subscription.status, "active")
        self.assertFalse(subscription.auto_renew)
        self.confirm(invoice)
        subscription.refresh_from_db()
        self.assertEqual(subscription.end_date, end)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="checkout.completed").count(), 1)

    def test_provider_amount_currency_order_and_capture_are_required(self):
        invoice = self.order()
        for change in ({"amount": 1}, {"currency": "USD"}, {"order_id": "another"},
                       {"status": "authorized"}, {"amount_refunded": 1}, {"id": "pay_other"}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.confirm(invoice, **change)
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(Subscription.objects.get().status, "past_due")

    def test_subscription_revision_prevents_old_order_overwriting_new_purchase(self):
        first, second = self.order(), self.order()
        self.confirm(second)
        with self.assertRaises(ValidationError):
            self.confirm(first)

    def test_service_rejects_missing_context_and_nonowner_before_provider_io(self):
        with self.assertRaises(PermissionDenied):
            create_checkout(workspace=self.workspace, actor=self.owner, plan_id=self.plan.pk,
                            billing_cycle="monthly", request_key=uuid4())
        outsider = get_user_model().objects.create_user(username="outsider")
        with workspace_context(self.workspace.pk), self.assertRaises(PermissionDenied):
            create_checkout(workspace=self.workspace, actor=outsider, plan_id=self.plan.pk,
                            billing_cycle="monthly", request_key=uuid4())
        self.order_mock.assert_not_called()

    def test_cross_workspace_confirmation_does_not_fetch_provider(self):
        invoice = self.order()
        other = Company.all_objects.create(name="Other", schema_name="other", owner=self.owner, creator=self.owner)
        Membership.objects.create(company=other, user=self.owner, role=Role.objects.get(name="Owner"))
        with workspace_context(other.pk), patch.object(RazorpayService, "get_payment_status") as fetch:
            with self.assertRaises(ValidationError):
                confirm_checkout(workspace=other, actor=self.owner, order_id=invoice.razorpay_order_id,
                                 payment_id="pay_test", signature="anything")
            fetch.assert_not_called()

    def test_frozen_evidence_rejects_queryset_rewrite(self):
        invoice = self.order()
        for changes in ({"checkout_snapshot": {}}, {"base_amount": 1}, {"razorpay_order_id": "changed"}):
            with self.assertRaises(DatabaseError), transaction.atomic():
                Invoice.objects.filter(pk=invoice.pk).update(**changes)

    def test_real_webhook_shape_replay_and_failed_attempt_after_capture(self):
        invoice = self.order()
        data = {"event": "payment.captured", "payload": {"payment": {"entity": self.payment(invoice)}}}
        self.assertEqual(self.webhook(data).status_code, 200)
        self.assertEqual(self.webhook(data).status_code, 200)
        self.confirm(invoice)
        self.assertEqual(self.webhook({"event": "payment.failed", "payload": {}}, "evt-failed").status_code, 200)
        self.assertEqual(Subscription.objects.get().status, "active")
        self.assertEqual(Payment.objects.count(), 1)

    def test_failed_webhook_rolls_back_and_retains_review_record(self):
        invoice = self.order()
        data = {"event": "payment.captured", "payload": {"payment": {"entity": self.payment(invoice)}}}
        with patch("apps.subscriptions.checkout.ensure_entitlements_for_subscription", side_effect=ValidationError("test")):
            self.assertEqual(self.webhook(data).status_code, 500)
        self.assertEqual(Subscription.objects.get().status, "past_due")
        self.assertEqual(ProviderWebhookEvent.objects.get().status, "failed")
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(self.webhook(data).status_code, 200)

    def test_webhook_identity_cannot_be_reused_with_new_body(self):
        self.assertEqual(self.webhook({"event": "payment.authorized"}).status_code, 200)
        self.assertEqual(self.webhook({"event": "payment.failed"}).status_code, 400)

    def test_missing_webhook_secret_fails_closed(self):
        with override_settings(RAZORPAY_WEBHOOK_SECRET=""):
            self.assertEqual(self.webhook({"event": "payment.authorized"}).status_code, 400)

    def test_post_view_methods_and_invoice_pdf(self):
        request = self.factory.post("/order/", json.dumps({"plan_id": self.plan.pk, "billing_cycle": "yearly", "checkout_key": str(uuid4())}), content_type="application/json")
        request.user, request.workspace = self.owner, self.workspace
        with workspace_context(self.workspace.pk):
            response = OrderView.as_view()(request)
            self.assertEqual(response.status_code, 200)
            bad = self.factory.post("/payment/", "[]", content_type="application/json")
            bad.user, bad.workspace = self.owner, self.workspace
            self.assertEqual(PaymentView.as_view()(bad).status_code, 400)
            invoice = Invoice.objects.get()
            download = self.factory.get("/invoice/pdf/")
            download.user, download.workspace = self.owner, self.workspace
            response = InvoicePDFView.as_view()(download, pk=invoice.pk)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(b"%PDF"))


    def test_global_webhook_route_requires_no_workspace_or_login(self):
        invoice = self.order()
        body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": self.payment(invoice)}}}).encode()
        signature = hmac.new(b"webhook-secret", body, hashlib.sha256).hexdigest()
        response = self.client.post("/subscriptions/webhook/razorpay/", body, content_type="application/json",
                                    HTTP_X_RAZORPAY_SIGNATURE=signature, HTTP_X_RAZORPAY_EVENT_ID="evt-global")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="checkout.completed").count(), 1)


class ConcurrentCheckoutTests(TransactionTestCase):
    order = CheckoutTests.order
    payment = CheckoutTests.payment

    def setUp(self):
        with transaction.atomic():
            CheckoutTests.setUp(self)

    def test_two_simultaneous_capture_callbacks_apply_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        from .checkout import _apply_capture

        invoice = self.order()
        payment = self.payment(invoice)
        barrier = Barrier(2)

        def capture():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return _apply_capture(invoice_id=invoice.pk, payment=payment).pk
            finally:
                connections.close_all()

        with patch("apps.subscriptions.notifications.send_checkout_receipt") as receipt:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: capture(), range(2)))
            receipt.assert_called_once_with(invoice.pk)
        self.assertEqual(results, [invoice.pk, invoice.pk])
        self.assertEqual(Payment.objects.count(), 1)

        self.assertEqual(SubscriptionEvent.objects.filter(event_type="checkout.completed").count(), 1)
