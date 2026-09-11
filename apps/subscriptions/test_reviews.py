from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.tenancy.context import workspace_context
from . import test_recovery as recovery_tests
from .models import BillingResolution, Invoice, Payment, Subscription, SubscriptionEvent
from .razorpay_service import RazorpayService
from .reviews import resolve_billing_review


@override_settings(RAZORPAY_KEY_SECRET="test-secret", RAZORPAY_WEBHOOK_SECRET="webhook-secret",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BillingReviewTests(TestCase):
    setUp = recovery_tests.RecoveryTests.setUp
    order = recovery_tests.RecoveryTests.order
    confirm = recovery_tests.RecoveryTests.confirm
    payment = recovery_tests.RecoveryTests.payment
    refund = recovery_tests.RecoveryTests.refund
    recover = recovery_tests.RecoveryTests.recover

    def full_refund(self):
        invoice = self.order()
        self.confirm(invoice)
        self.recover(invoice, self.refund(invoice))
        return invoice

    def resolve(self, invoice, action="retain_access", **kwargs):
        with workspace_context(self.workspace.pk):
            return resolve_billing_review(workspace=self.workspace, actor=self.owner, invoice_id=invoice.pk,
                action=action, reason="Reviewed paid terms and provider records",
                revision=kwargs.pop("revision", Subscription.objects.get().updated_at.isoformat()), **kwargs)

    def test_retain_is_final_idempotent_and_preserves_term(self):
        invoice = self.full_refund()
        end = Subscription.objects.get().end_date
        first = self.resolve(invoice)
        self.assertEqual(self.resolve(invoice).pk, first.pk)
        self.assertEqual(Subscription.objects.get().status, "active")
        self.assertEqual(Subscription.objects.get().end_date, end)
        with self.assertRaises(ValidationError):
            self.resolve(invoice, "end_access")
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="billing.review.resolved").count(), 1)

    def test_end_current_refunded_term_cannot_be_undone_by_capture_replay(self):
        invoice = self.full_refund()
        revision = Subscription.objects.get().updated_at.isoformat()
        self.resolve(invoice, "end_access", revision=revision)
        self.assertEqual(Subscription.objects.get().status, "cancelled")
        self.resolve(invoice, "end_access", revision=revision)
        self.confirm(invoice)
        self.assertEqual(Subscription.objects.get().status, "cancelled")
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.lifecycle_state, "ACTIVE")

    def test_newer_purchase_and_future_renewal_are_not_cancelled(self):
        old = self.full_refund()
        newer = self.order()
        from .checkout import _apply_capture
        _apply_capture(invoice_id=newer.pk, payment=self.payment(newer, id="pay_newer"))
        with self.assertRaises(ValidationError):
            self.resolve(old, "end_access")
        from .recovery import _record_refund
        refund = {**self.refund(newer, refund_id="rfnd_newer"), "payment_id": "pay_newer"}
        _record_refund(invoice_id=newer.pk, payment=self.payment(newer, id="pay_newer"), refund=refund)
        with self.assertRaises(ValidationError):
            self.resolve(newer, "end_access")
        self.assertEqual(Subscription.objects.get().status, "active")

    def test_revision_and_full_refund_required(self):
        invoice = self.order()
        self.confirm(invoice)
        with self.assertRaises(ValidationError):
            self.resolve(invoice)
        self.recover(invoice, self.refund(invoice))
        with self.assertRaises(ValidationError):
            self.resolve(invoice, revision="outdated")
        self.assertFalse(BillingResolution.objects.exists())

    def test_missing_authority_and_cross_workspace_invoice_fail_closed(self):
        invoice = self.full_refund()
        with self.assertRaises(PermissionDenied):
            resolve_billing_review(workspace=self.workspace, actor=self.owner, invoice_id=invoice.pk,
                action="retain_access", reason="Review", revision="irrelevant")
        from apps.orgs.models import Company, Membership, Role
        other = Company.all_objects.create(name="Other review", schema_name="other-review", owner=self.owner, creator=self.owner)
        Membership.objects.create(company=other, user=self.owner, role=Role.objects.get(name="Owner"))
        with workspace_context(other.pk), self.assertRaises(ValidationError):
            resolve_billing_review(workspace=other, actor=self.owner, invoice_id=invoice.pk,
                action="retain_access", reason="Review", revision="irrelevant")

    def test_stale_return_records_fully_returned_money_without_granting_access(self):
        stale = self.order()
        newer = self.order()
        self.confirm(newer)
        before = Subscription.objects.get().updated_at
        payment = self.payment(stale, id="pay_stale", status="refunded")
        refund = {**self.refund(stale, refund_id="rfnd_stale"), "payment_id": "pay_stale"}
        with patch.object(RazorpayService, "get_payment_status", return_value=payment), patch.object(RazorpayService, "get_refund", return_value=refund):
            result = self.resolve(stale, "returned_payment", payment_id="pay_stale", refund_ids=["rfnd_stale"])
            self.assertEqual(self.resolve(stale, "returned_payment", payment_id="pay_stale", refund_ids=["rfnd_stale"]).pk, result.pk)
        self.assertEqual(Subscription.objects.get().updated_at, before)
        self.assertEqual(Payment.objects.get(invoice=stale).status, "refunded")
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="checkout.completed").count(), 1)

    def test_partial_refund_cannot_resolve_stale_payment(self):
        stale = self.order()
        self.confirm(self.order())
        payment = self.payment(stale, id="pay_stale")
        refund = {**self.refund(stale, amount=100), "payment_id": "pay_stale"}
        with patch.object(RazorpayService, "get_payment_status", return_value=payment), patch.object(RazorpayService, "get_refund", return_value=refund):
            with self.assertRaises(ValidationError):
                self.resolve(stale, "returned_payment", payment_id="pay_stale", refund_ids=[refund["id"]])
        self.assertFalse(Payment.objects.filter(invoice=stale).exists())

    def test_returned_payment_resolution_rolls_back_on_audit_failure(self):
        stale = self.order()
        self.confirm(self.order())
        payment = self.payment(stale, id="pay_stale", status="refunded")
        refund = {**self.refund(stale), "payment_id": "pay_stale"}
        with patch.object(RazorpayService, "get_payment_status", return_value=payment), patch.object(RazorpayService, "get_refund", return_value=refund), patch("apps.subscriptions.reviews.BillingResolution.objects.create", side_effect=ValidationError("Test failure")):
            with self.assertRaises(ValidationError):
                self.resolve(stale, "returned_payment", payment_id="pay_stale", refund_ids=[refund["id"]])
        stale.refresh_from_db()
        self.assertEqual(stale.status, "issued")
        self.assertFalse(Payment.objects.filter(invoice=stale).exists())

    def test_audit_failure_rolls_back_cancellation(self):
        invoice = self.full_refund()
        with patch("apps.subscriptions.reviews.BillingResolution.objects.create", side_effect=ValidationError("Test audit failure")):
            with self.assertRaises(ValidationError):
                self.resolve(invoice, "end_access")
        self.assertEqual(Subscription.objects.get().status, "active")
        self.assertFalse(SubscriptionEvent.objects.filter(event_type="refund.access_ended").exists())

    def test_resolution_evidence_is_immutable(self):
        self.resolve(self.full_refund())
        with self.assertRaises(DatabaseError), transaction.atomic():
            BillingResolution.objects.update(reason="changed")
        with self.assertRaises(DatabaseError), transaction.atomic():
            BillingResolution.objects.all().delete()

    def test_owner_queue_and_post_resolution(self):
        invoice = self.full_refund()
        self.client.force_login(self.owner)
        queue = reverse("workspace_subscriptions:reviews", kwargs={"workspace_slug": self.workspace.slug})
        self.assertContains(self.client.get(queue), invoice.invoice_number)
        url = reverse("workspace_subscriptions:resolve-review", kwargs={"workspace_slug": self.workspace.slug, "pk": invoice.pk})
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, {"decision": "retain_access", "reason": "Owner review", "revision": Subscription.objects.get().updated_at.isoformat()})
        self.assertEqual(response.status_code, 302)
        self.assertNotContains(self.client.get(queue), invoice.invoice_number)


@override_settings(RAZORPAY_KEY_SECRET="test-secret", RAZORPAY_WEBHOOK_SECRET="webhook-secret")
class ConcurrentReviewTests(TransactionTestCase):
    order = BillingReviewTests.order
    confirm = BillingReviewTests.confirm
    payment = BillingReviewTests.payment
    refund = BillingReviewTests.refund
    recover = BillingReviewTests.recover
    full_refund = BillingReviewTests.full_refund

    def setUp(self):
        with transaction.atomic():
            recovery_tests.RecoveryTests.setUp(self)

    def test_concurrent_final_decisions_are_applied_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        with patch("apps.subscriptions.notifications.send_checkout_receipt"):
            invoice = self.full_refund()
        revision = Subscription.objects.get().updated_at.isoformat()
        barrier = Barrier(2)

        def decide():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                with workspace_context(self.workspace.pk):
                    return resolve_billing_review(workspace=self.workspace, actor=self.owner, invoice_id=invoice.pk,
                        action="retain_access", reason="Concurrent review", revision=revision).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: decide(), range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(BillingResolution.objects.count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="billing.review.resolved").count(), 1)
