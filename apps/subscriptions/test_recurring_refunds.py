from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.tenancy.context import workspace_context
from .models import BillingResolution, Invoice, Payment, RecurringAgreement, Subscription
from .razorpay_service import BillingProviderError, RazorpayService
from .recovery import process_refund_webhook
from .reviews import resolve_billing_review
from .test_recurring_cycles import CycleFixture


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture", BILLING_TAX_RATE="18")
class RecurringRefundReviewTests(CycleFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.cycle = self.record()
        self.refund = {"id": "rfnd_review", "payment_id": "pay_two", "status": "processed",
                       "amount": 176882, "currency": "INR"}
        self.payments["pay_two"].update(status="refunded", amount_refunded=176882)
        self.refund_read = patch.object(RazorpayService, "get_refund", side_effect=lambda _: dict(self.refund)).start()
        process_refund_webhook({"payload": {"refund": {"entity": self.refund}}})
        self.provider_agreement["status"] = "cancelled"
        self.before = Subscription.objects.values().get()

    def decide(self, **changes):
        args = dict(workspace=self.workspace, actor=self.owner, invoice_id=self.cycle.invoice_id,
                    action="end_access", reason="Reviewed full Test Mode refund",
                    revision=Subscription.objects.get().updated_at.isoformat())
        args.update(changes)
        with workspace_context(self.workspace.pk):
            return resolve_billing_review(**args)

    def test_exact_current_refund_ends_access_once_preserves_dates_and_reservation(self):
        result = self.decide()
        subscription = Subscription.objects.get()
        self.assertEqual(subscription.status, "cancelled")
        self.assertEqual(subscription.end_date, self.before["end_date"])
        self.assertEqual(result.evidence["refund_ids"], ["rfnd_review"])
        self.assertIsNone(RecurringAgreement.objects.get().closed_at)
        self.assertEqual(self.agreement.events.filter(event_type="refund.access_reviewed").count(), 1)
        with patch.object(RazorpayService, "get_invoice", side_effect=BillingProviderError("offline")):
            self.assertEqual(self.decide(revision="stale retry").pk, result.pk)
        self.record()
        self.assertEqual(Subscription.objects.get().status, "cancelled")
        self.assertEqual(BillingResolution.objects.count(), 1)
        self.assertEqual(Invoice.objects.count(), 1)
        with self.assertRaises(ValidationError):
            self.decide(action="retain_access")

    def test_retain_access_never_changes_subscription_or_issues_provider_mutation(self):
        self.provider_agreement["status"] = "active"
        with patch.object(RazorpayService, "cancel_subscription") as cancel:
            self.decide(action="retain_access")
            cancel.assert_not_called()
        self.assertEqual(Subscription.objects.values().get(), self.before)

    def test_active_collection_and_stale_revision_block_access_end(self):
        for status in ("created", "authenticated", "active", "pending", "halted", "paused"):
            self.provider_agreement["status"] = status
            with self.subTest(status=status), self.assertRaisesMessage(ValidationError, "Stop future renewals"):
                self.decide()
        self.provider_agreement["status"] = "cancelled"
        with self.assertRaisesMessage(ValidationError, "changed during review"):
            self.decide(revision="outdated")
        self.assertFalse(BillingResolution.objects.exists())
        self.assertEqual(Subscription.objects.values().get(), self.before)

    def test_partial_mismatched_or_unverified_refunds_cannot_decide(self):
        for changes in ({"amount_refunded": 100}, {"status": "captured"}, {"invoice_id": "inv_other"}):
            payment = dict(self.payments["pay_two"])
            self.payments["pay_two"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.decide(action="retain_access")
            self.payments["pay_two"] = payment
        for changes in ({"amount": 100}, {"status": "pending"}, {"currency": "USD"}, {"payment_id": "pay_other"}):
            refund = dict(self.refund)
            self.refund.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.decide()
            self.refund = refund
        self.assertEqual(Subscription.objects.values().get(), self.before)
        self.assertFalse(BillingResolution.objects.exists())

    def test_future_paid_hold_prevents_ending_current_refunded_access(self):
        self.add_cycle("future", self.cycle.period_end, self.cycle.period_end+timedelta(days=30))
        future = self.record("future")
        self.assertEqual(future.access_action, "review")
        with self.assertRaisesMessage(ValidationError, "other paid periods"):
            self.decide()
        self.assertEqual(Subscription.objects.values().get(), self.before)

    def test_old_term_cannot_end_newer_paid_access(self):
        self.add_cycle("newer", self.cycle.period_end, self.cycle.period_end+timedelta(days=30))
        # A provider period that has really become due, represented by this unit fixture.
        with patch("apps.subscriptions.recurring_cycles.timezone.now", return_value=self.cycle.period_end+timedelta(days=1)):
            self.record("newer")
            newer = Subscription.objects.values().get()
            with self.assertRaises(ValidationError):
                self.decide()
            self.assertEqual(Subscription.objects.values().get(), newer)

    def test_authority_mode_and_recorded_evidence_boundaries(self):
        with self.assertRaises(PermissionDenied):
            self.decide(actor=self.other)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.decide()
        self.owner.is_active = True
        self.owner.save(update_fields=["is_active"])
        with override_settings(RAZORPAY_KEY_ID="rzp_live_fixture"), self.assertRaises(PermissionDenied):
            self.decide()
        for changes in ({"invoice_id": self.cycle.invoice_id+999}, {"action": "returned_payment"}, {"reason": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.decide(**changes)
        Payment.objects.filter(invoice=self.cycle.invoice).update(refund_amount=0)
        with self.assertRaisesMessage(ValidationError, "recorded full-refund"):
            self.decide()

    def test_provider_outage_and_terminal_regression_preserve_access(self):
        with patch.object(RazorpayService, "get_refund", side_effect=BillingProviderError("offline")):
            with self.assertRaises(BillingProviderError):
                self.decide()
        RecurringAgreement.objects.filter(pk=self.agreement.pk).update(provider_status="cancelled")
        self.provider_agreement["status"] = "active"
        with self.assertRaisesMessage(ValidationError, "terminal state"):
            self.decide(action="retain_access")
        self.assertFalse(BillingResolution.objects.exists())
        self.assertEqual(Subscription.objects.values().get(), self.before)

    def test_local_failure_rolls_back_access_and_resolution(self):
        with patch("apps.subscriptions.recurring_access.BillingResolution.objects.create", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.decide()
        self.assertEqual(Subscription.objects.values().get(), self.before)
        self.assertFalse(BillingResolution.objects.exists())

    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                                 "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_owner_can_review_refunded_future_hold_without_granting_access(self):
        self.add_cycle("future", self.cycle.period_end, self.cycle.period_end+timedelta(days=30))
        held = self.record("future")
        self.refund.update(id="rfnd_future", payment_id="pay_future")
        self.payments["pay_future"].update(status="refunded", amount_refunded=176882)
        process_refund_webhook({"payload": {"refund": {"entity": self.refund}}})
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:resolve-review", kwargs={"workspace_slug": self.workspace.slug,
                                                                         "pk": held.invoice_id})
        response = self.client.post(url, {"decision": "retain_access", "reason": "Future period fully returned",
            "revision": Subscription.objects.get().updated_at.isoformat()}, follow=True)
        self.assertContains(response, "Billing review decision recorded")
        self.assertEqual(Subscription.objects.values().get(), self.before)
        dashboard = self.client.get(reverse("workspace_subscriptions:recurring", kwargs={"workspace_slug": self.workspace.slug}))
        self.assertContains(dashboard, "Refund reviewed:")
        self.assertNotContains(dashboard, "Payments awaiting access review")
        from .recurring_access import apply_held_period
        with workspace_context(self.workspace.pk), patch("django.utils.timezone.now", return_value=held.period_start+timedelta(seconds=1)):
            with self.assertRaises(ValidationError):
                apply_held_period(workspace=self.workspace, actor=self.owner, cycle_id=held.pk,
                    revision=Subscription.objects.get().updated_at.isoformat(), reason="Refund must prevent application")
