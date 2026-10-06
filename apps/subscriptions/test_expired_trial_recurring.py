"""First paid recurring term after a trial, with mocked provider facts only."""
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, override_settings

from apps.platform_mail.models import Delivery
from .models import Invoice, Payment, Plan, RecurringCycle, Subscription, SubscriptionEntitlement, SubscriptionEvent
from .test_recurring_cycles import CycleFixture


@override_settings(BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture",
                   RAZORPAY_KEY_SECRET="fixture", RAZORPAY_WEBHOOK_SECRET="webhook-fixture",
                   BILLING_RECURRING_ENABLED=False, BILLING_TAX_RATE="0")
class ExpiredTrialRecurringTests(CycleFixture, TestCase):
    agreement_age = timedelta(hours=1)

    def setUp(self):
        super().setUp()
        self.trial_plan = Plan.objects.create(name="Original trial", price=0, trial_days=14, max_users=3)
        self.subscription = Subscription.objects.create(company=self.workspace, plan=self.trial_plan,
                                                       status="trial", auto_renew=False)
        self.trial_end = self.now - timedelta(days=1)
        Subscription.objects.filter(pk=self.subscription.pk).update(
            trial_end_date=self.trial_end, end_date=self.now+timedelta(days=60))
        self.start = self.now-timedelta(minutes=1)
        self.end = self.start+timedelta(days=30)
        self.add_cycle("pilot", self.start, self.end)

    def unchanged_review(self):
        before = Subscription.objects.values().get(pk=self.subscription.pk)
        cycle = self.record("pilot")
        self.assertEqual(cycle.access_action, "review")
        self.assertEqual(Subscription.objects.values().get(pk=self.subscription.pk), before)
        return cycle

    def test_expired_trial_switches_plan_on_capture_once_with_exact_dates_and_audit(self):
        before = Subscription.objects.values().get(pk=self.subscription.pk)
        cycle = self.record("pilot")
        self.subscription.refresh_from_db()
        self.assertEqual(cycle.access_action, "applied")
        self.assertEqual((self.subscription.status, self.subscription.plan_id, self.subscription.end_date),
                         ("active", self.plan.pk, self.end))
        self.assertEqual(self.subscription.trial_end_date, self.trial_end)
        self.assertEqual(self.subscription.start_date, before["start_date"])
        self.assertEqual(SubscriptionEntitlement.objects.get(subscription=self.subscription,
                         feature_code="workspace.max_members").value, "6")
        event = SubscriptionEvent.objects.get(event_type="recurring.payment")
        self.assertEqual(event.payload["trial_conversion"]["previous_plan_id"], self.trial_plan.pk)
        self.assertEqual(event.payload["trial_conversion"]["trial_end_date"], self.trial_end.isoformat())
        after = Subscription.objects.values().get(pk=self.subscription.pk)
        self.assertEqual(self.webhook(suffix="pilot", event_id="trial_replay").status_code, 200)
        self.assertEqual(Subscription.objects.values().get(pk=self.subscription.pk), after)
        for model in (Invoice, Payment, RecurringCycle, Delivery):
            self.assertEqual(model.objects.count(), 1)

    def test_unexpired_trial_and_period_overlapping_trial_preserve_access(self):
        for expiry in (self.now+timedelta(days=1), self.start+timedelta(seconds=1)):
            with self.subTest(expiry=expiry):
                # Each subcase uses a rollback so its immutable payment cannot mask the next.
                with transaction.atomic():
                    Subscription.objects.filter(pk=self.subscription.pk).update(trial_end_date=expiry)
                    self.unchanged_review()
                    transaction.set_rollback(True)

    def test_agreement_created_before_trial_end_cannot_convert(self):
        Subscription.objects.filter(pk=self.subscription.pk).update(
            trial_end_date=self.agreement.created_at+timedelta(seconds=1))
        self.unchanged_review()

    def test_same_plan_trial_default_end_is_not_treated_as_paid_time(self):
        Subscription.objects.filter(pk=self.subscription.pk).update(plan=self.plan)
        cycle = self.record("pilot")
        self.subscription.refresh_from_db()
        self.assertEqual((cycle.access_action, self.subscription.status, self.subscription.end_date),
                         ("applied", "active", self.end))

    def test_legacy_mandate_and_inactive_workspace_require_review(self):
        for change in ("legacy", "suspended", "archived"):
            with self.subTest(change=change), transaction.atomic():
                if change == "legacy":
                    Subscription.objects.filter(pk=self.subscription.pk).update(razorpay_subscription_id="sub_legacy")
                else:
                    type(self.workspace).all_objects.filter(pk=self.workspace.pk).update(lifecycle_state=change.upper())
                self.unchanged_review()
                transaction.set_rollback(True)

    def test_previous_invoice_requires_separate_review(self):
        Invoice.objects.create(subscription=self.subscription, invoice_number="old-draft", status="draft",
                               base_amount=1, gst_rate=0, invoice_date=self.now.date(), due_date=self.now.date())
        self.unchanged_review()

    def test_future_period_is_still_held_and_replay_cannot_convert(self):
        self.add_cycle("pilot", self.now+timedelta(days=2), self.now+timedelta(days=32))
        cycle = self.unchanged_review()
        self.assertEqual(cycle.invoice.checkout_snapshot["access_review_reason"], "future_period")
        before = Subscription.objects.values().get(pk=self.subscription.pk)
        with patch("apps.subscriptions.recurring_cycles.timezone.now", return_value=self.now+timedelta(days=3)):
            self.record("pilot")
        self.assertEqual(Subscription.objects.values().get(pk=self.subscription.pk), before)

    def test_cancelled_subscription_cannot_be_converted(self):
        Subscription.objects.filter(pk=self.subscription.pk).update(status="cancelled")
        self.unchanged_review()

    def test_over_capacity_trial_is_not_converted(self):
        with patch("apps.subscriptions.recurring_cycles.get_workspace_member_usage", return_value=7):
            self.unchanged_review()

    def test_receipt_failure_rolls_back_trial_conversion_and_financial_records(self):
        before = Subscription.objects.values().get(pk=self.subscription.pk)
        with patch("apps.subscriptions.recurring_cycles.send_checkout_receipt", side_effect=ValidationError("queue failed")):
            with self.assertRaises(ValidationError):
                self.record("pilot")
        self.assertEqual(Subscription.objects.values().get(pk=self.subscription.pk), before)
        for model in (Invoice, Payment, RecurringCycle, Delivery, SubscriptionEvent, SubscriptionEntitlement):
            self.assertFalse(model.objects.exists())


@override_settings(BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture",
                   BILLING_SELLER_NAME="Fictional Seller", BILLING_SELLER_ADDRESS="1 Example Street",
                   BILLING_SELLER_TAX_STATUS="unregistered")
class LiveExpiredTrialRecurringTests(ExpiredTrialRecurringTests):
    provider_mode = "live"
    offer_mode = "live"
