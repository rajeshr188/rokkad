from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.tenancy.context import workspace_context, current_workspace_id
from .models import Invoice, Payment, PaymentRefund, Subscription, SubscriptionEvent
from .razorpay_service import RazorpayService
from .recovery import reconcile_payment
from . import test_checkout as checkout_tests


@override_settings(RAZORPAY_KEY_SECRET="test-secret", RAZORPAY_WEBHOOK_SECRET="webhook-secret")
class RecoveryTests(TestCase):
    setUp = checkout_tests.CheckoutTests.setUp
    order = checkout_tests.CheckoutTests.order
    confirm = checkout_tests.CheckoutTests.confirm
    payment = checkout_tests.CheckoutTests.payment
    webhook = checkout_tests.CheckoutTests.webhook

    def refund(self, invoice, amount=None, refund_id="rfnd_test"):
        return {"id": refund_id, "payment_id": "pay_test", "amount": amount or invoice.checkout_snapshot["amount"],
                "currency": "INR", "status": "processed", "created_at": 1700000000}

    def recover(self, invoice, refund=None, apply=True):
        payment = self.payment(invoice, status="refunded" if refund and refund["amount"] == invoice.checkout_snapshot["amount"] else "captured")
        with workspace_context(self.workspace.pk), patch.object(RazorpayService, "get_payment_status", return_value=payment), patch.object(RazorpayService, "get_refund", return_value=refund):
            return reconcile_payment(workspace=self.workspace, actor=self.owner, invoice_id=invoice.pk,
                                     payment_id="pay_test", refund_id=refund["id"] if refund else None,
                                     reason="Reviewed provider dashboard", apply=apply)

    def test_check_is_read_only_and_apply_recovers_missing_confirmation(self):
        invoice = self.order()
        self.assertFalse(self.recover(invoice, apply=False)["applied"])
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(SubscriptionEvent.objects.exists())
        self.recover(invoice)
        self.recover(invoice)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="checkout.completed").count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="payment.reconciled").count(), 2)

    def test_stale_invoice_remains_blocked_without_rewriting_snapshot(self):
        invoice = self.order()
        newer = self.order()
        self.confirm(newer)
        with self.assertRaises(ValidationError):
            self.recover(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "issued")

    def test_partial_then_full_refunds_preserve_terms_and_do_not_double_count(self):
        invoice = self.order()
        self.confirm(invoice)
        term = Subscription.objects.get().end_date
        first = self.refund(invoice, 100)
        self.recover(invoice, first)
        self.recover(invoice, first)
        self.assertEqual(Payment.objects.get().refund_amount, Decimal("1"))
        self.assertEqual(Payment.objects.get().status, "captured")
        second = self.refund(invoice, invoice.checkout_snapshot["amount"] - 100, "rfnd_second")
        self.recover(invoice, second)
        self.assertEqual(Payment.objects.get().refund_amount, invoice.total_amount)
        self.assertEqual(Payment.objects.get().status, "refunded")
        self.assertEqual(PaymentRefund.objects.count(), 2)
        self.assertEqual(Subscription.objects.get().end_date, term)
        self.assertEqual(Subscription.objects.get().status, "active")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="refund.recorded").count(), 2)

    def test_refund_mismatches_and_pending_status_fail_closed(self):
        invoice = self.order()
        self.confirm(invoice)
        for change in ({"currency": "USD"}, {"payment_id": "pay_other"}, {"status": "pending"}, {"amount": -1}):
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.recover(invoice, {**self.refund(invoice), **change})
        self.assertFalse(PaymentRefund.objects.exists())

    def test_refund_total_cannot_exceed_payment_and_identity_cannot_change(self):
        invoice = self.order()
        self.confirm(invoice)
        self.recover(invoice, self.refund(invoice))
        for refund in (self.refund(invoice, 100), self.refund(invoice, 100, "rfnd_extra")):
            with self.assertRaises(ValidationError):
                self.recover(invoice, refund)
        self.assertEqual(PaymentRefund.objects.count(), 1)

    def test_unrecorded_capture_cannot_be_invented_from_refund(self):
        invoice = self.order()
        with self.assertRaises(ValidationError):
            self.recover(invoice, self.refund(invoice))
        self.assertFalse(Payment.objects.exists())

    def test_saved_refund_is_immutable(self):
        invoice = self.order()
        self.confirm(invoice)
        self.recover(invoice, self.refund(invoice))
        with self.assertRaises(DatabaseError), transaction.atomic():
            PaymentRefund.objects.update(amount=1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PaymentRefund.objects.all().delete()

    def test_webhook_fetches_exact_refund_and_late_capture_cannot_change_it(self):
        invoice = self.order()
        self.confirm(invoice)
        refund = self.refund(invoice)
        data = {"event": "refund.processed", "payload": {"refund": {"entity": refund}}}
        with patch.object(RazorpayService, "get_refund", return_value=refund), patch.object(RazorpayService, "get_payment_status", return_value=self.payment(invoice, status="refunded")):
            self.assertEqual(self.webhook(data).status_code, 200)
            self.assertEqual(self.webhook(data, "another-delivery").status_code, 200)
        captured = {"event": "payment.captured", "payload": {"payment": {"entity": self.payment(invoice)}}}
        self.assertEqual(self.webhook(captured, "late-capture").status_code, 200)
        self.assertEqual(Payment.objects.get().status, "refunded")
        self.assertEqual(PaymentRefund.objects.count(), 1)

    def test_authorization_precedes_provider_io(self):
        invoice = self.order()
        with patch.object(RazorpayService, "get_payment_status") as fetch:
            with self.assertRaises(PermissionDenied):
                reconcile_payment(workspace=self.workspace, actor=self.owner, invoice_id=invoice.pk,
                                  payment_id="pay_test", reason="Review", apply=True)
            fetch.assert_not_called()

    def test_cross_workspace_invoice_is_rejected_before_fetch(self):
        from apps.orgs.models import Company, Membership, Role
        invoice = self.order()
        other = Company.all_objects.create(name="Other recovery", schema_name="other-recovery", owner=self.owner, creator=self.owner)
        Membership.objects.create(company=other, user=self.owner, role=Role.objects.get(name="Owner"))
        with workspace_context(other.pk), patch.object(RazorpayService, "get_payment_status") as fetch:
            with self.assertRaises(ValidationError):
                reconcile_payment(workspace=other, actor=self.owner, invoice_id=invoice.pk,
                                  payment_id="pay_test", reason="Review", apply=True)
            fetch.assert_not_called()

    def test_audit_failure_rolls_back_refund_and_projection(self):
        invoice = self.order()
        self.confirm(invoice)
        with patch("apps.subscriptions.recovery.SubscriptionEvent.objects.create", side_effect=ValidationError("Audit failed")):
            with self.assertRaises(ValidationError):
                self.recover(invoice, self.refund(invoice))
        self.assertFalse(PaymentRefund.objects.exists())
        self.assertEqual(Payment.objects.get().refund_amount, 0)

    def test_command_check_is_read_only_and_cleans_context(self):
        invoice = self.order()
        with patch.object(RazorpayService, "get_payment_status", return_value=self.payment(invoice)):
            out = StringIO()
            call_command("reconcile_subscription_payment", workspace_id=self.workspace.pk, actor_id=self.owner.pk,
                         invoice_id=invoice.pk, payment_id="pay_test", reason="Review", stdout=out)
        self.assertIn('"applied": false', out.getvalue())
        self.assertFalse(Payment.objects.exists())
        self.assertIsNone(current_workspace_id())

    def test_owner_recovery_http_and_method_boundary(self):
        invoice = self.order()
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:invoice-reconcile", kwargs={"workspace_slug": self.workspace.slug, "pk": invoice.pk})
        self.assertEqual(self.client.get(url).status_code, 405)
        with patch.object(RazorpayService, "get_payment_status", return_value=self.payment(invoice)):
            response = self.client.post(url, {"payment_id": "pay_test", "reason": "Review", "action": "apply"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Payment.objects.count(), 1)

    @override_settings(STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_refund_is_visible_on_owner_invoice(self):
        invoice = self.order()
        self.confirm(invoice)
        self.recover(invoice, self.refund(invoice))
        self.client.force_login(self.owner)
        response = self.client.get(reverse("workspace_subscriptions:invoice-detail", kwargs={
            "workspace_slug": self.workspace.slug, "pk": invoice.pk,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fully refunded: access remains unchanged pending owner review.")
        self.assertContains(response, "Check provider records")


class ConcurrentRefundTests(TransactionTestCase):
    order = checkout_tests.CheckoutTests.order
    payment = checkout_tests.CheckoutTests.payment

    def setUp(self):
        with transaction.atomic():
            checkout_tests.CheckoutTests.setUp(self)

    def test_duplicate_refunds_are_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        from .checkout import _apply_capture
        from .recovery import _record_refund
        invoice = self.order()
        payment = self.payment(invoice)
        with patch("apps.subscriptions.notifications.send_checkout_receipt"):
            _apply_capture(invoice_id=invoice.pk, payment=payment)
        refund = {"id": "rfnd_concurrent", "payment_id": payment["id"], "amount": payment["amount"],
                  "currency": "INR", "status": "processed"}
        barrier = Barrier(2)

        def record():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return _record_refund(invoice_id=invoice.pk, payment=payment, refund=refund).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: record(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(PaymentRefund.objects.count(), 1)
        self.assertEqual(Payment.objects.get().refund_amount, invoice.total_amount)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="refund.recorded").count(), 1)
