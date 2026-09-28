from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
import hashlib
import hmac
import json
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.platform_mail.models import Delivery
from apps.tenancy.context import workspace_context
from .billing import effective_billing_state
from .checkout import _apply_capture, handle_provider_event
from .models import (Invoice, Payment, Plan, RecurringAgreement, RecurringAgreementEvent, RecurringCycle,
                     RecurringPlanBinding, Subscription, SubscriptionEntitlement, SubscriptionEvent)
from .razorpay_service import BillingProviderError, RazorpayService
from .recurring import _offer
from .recurring_cycles import _valid_period, record_paid_cycle, reconcile_cycle
from .recovery import process_refund_webhook
from .reviews import resolve_billing_review
from .views import razorpay_webhook


class CycleFixture:
    def setUp(self):
        with transaction.atomic():
            self.owner = get_user_model().objects.create_user(username="cycle-owner", email="cycle@example.test")
            self.other = get_user_model().objects.create_user(username="cycle-other")
            self.workspace = Company.all_objects.create(name="Cycle TEST", schema_name="cycle", owner=self.owner, creator=self.owner)
            Membership.objects.create(company=self.workspace, user=self.owner, role=Role.objects.get_or_create(name="Owner")[0])
            self.plan = Plan.objects.create(name="Cycle TEST", tier="starter", price="1499.00", yearly_price="14990.00",
                                           description="Test", max_users=6)
            self.plan.refresh_from_db()
            self.binding = RecurringPlanBinding.objects.create(plan=self.plan, mode=getattr(self, "provider_mode", "test"), provider_plan_id="plan_cycle",
                snapshot=_offer(self.plan, "monthly", mode=getattr(self, "offer_mode", "test")), actor=self.owner, reason="Verified fixture")
            self.now = timezone.now().replace(microsecond=0)
            self.agreement = RecurringAgreement.objects.create(workspace=self.workspace, binding=self.binding,
                actor=self.owner, request_key=uuid4(), state="verified", provider_subscription_id="sub_cycle",
                provider_status="active", verified_at=self.now, created_at=self.now-timedelta(days=100),
                request_snapshot={"plan_id": "plan_cycle", "quantity": 1, "total_count": 12, "customer_notify": False,
                                  "notes": {"workspace_id": str(self.workspace.pk), "rokkad_attempt": "fixture"}})
        self.provider_agreement = {**self.agreement.request_snapshot, "id": "sub_cycle", "entity": "subscription",
                                   "status": "active", "has_scheduled_changes": False}
        self.provider_plan = {"id": "plan_cycle", "entity": "plan", "period": "monthly", "interval": 1,
                              "item": {"amount": self.binding.snapshot["amount"], "currency": "INR"}}
        self.invoices, self.payments = {}, {}
        self.add_cycle("one", self.now-timedelta(days=45), self.now-timedelta(days=15))
        self.add_cycle("two", self.now-timedelta(days=15), self.now+timedelta(days=15))
        for method, effect in [
            ("get_invoice", lambda identity: deepcopy(self.invoices[identity])),
            ("get_payment_status", lambda identity: deepcopy(self.payments[identity])),
            ("get_subscription", lambda identity: deepcopy(self.provider_agreement)),
            ("get_plan", lambda identity: deepcopy(self.provider_plan)),
        ]:
            patch.object(RazorpayService, method, side_effect=effect).start()
        self.addCleanup(patch.stopall)

    def add_cycle(self, suffix, start, end, amount=None):
        amount = self.binding.snapshot["amount"] if amount is None else amount
        self.invoices["inv_"+suffix] = {"id": "inv_"+suffix, "entity": "invoice", "subscription_id": "sub_cycle",
            "order_id": "order_"+suffix, "payment_id": "pay_"+suffix, "status": "paid", "amount": amount,
            "amount_paid": amount, "amount_due": 0, "currency": "INR", "billing_start": int(start.timestamp()),
            "billing_end": int(end.timestamp()), "paid_at": int(min(start, self.now).timestamp()),
            "line_items": [{"type": "plan", "quantity": 1, "amount": amount, "currency": "INR"}]}
        self.payments["pay_"+suffix] = {"id": "pay_"+suffix, "entity": "payment", "invoice_id": "inv_"+suffix,
            "order_id": "order_"+suffix, "amount": amount, "currency": "INR", "status": "captured",
            "amount_refunded": 0, "method": "card"}

    def record(self, suffix="two"):
        return record_paid_cycle(agreement_id=self.agreement.pk, provider_invoice_id="inv_"+suffix)

    def webhook(self, event_type="subscription.charged", suffix="two", event_id="evt_cycle", signature=None):
        data = {"event": event_type, "payload": {"subscription": {"entity": {"id": "sub_cycle"}},
            "payment": {"entity": deepcopy(self.payments["pay_"+suffix])}}}
        body = json.dumps(data).encode()
        signed = signature or hmac.new(b"webhook-fixture", body, hashlib.sha256).hexdigest()
        return razorpay_webhook(RequestFactory().post("/subscriptions/webhook/razorpay/", body,
            content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=signed, HTTP_X_RAZORPAY_EVENT_ID=event_id))


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture",
                   RAZORPAY_WEBHOOK_SECRET="webhook-fixture", BILLING_RECURRING_ENABLED=False, BILLING_TAX_RATE="18")
class RecurringCycleTests(CycleFixture, TestCase):
    def test_initial_and_renewal_record_exact_periods_and_one_receipt_each(self):
        first = self.record("one")
        sub = Subscription.objects.get(company=self.workspace)
        self.assertEqual(sub.end_date, first.period_end)
        self.assertFalse(effective_billing_state(sub).commercially_available)
        second = self.record()
        sub.refresh_from_db()
        self.assertEqual(sub.end_date, second.period_end)
        self.assertTrue(effective_billing_state(sub).commercially_available)
        self.assertFalse(sub.auto_renew)
        self.assertEqual(Invoice.objects.count(), 2)
        self.assertEqual(Payment.objects.count(), 2)
        self.assertEqual(Delivery.objects.filter(status="queued").count(), 2)
        self.assertEqual(SubscriptionEntitlement.objects.get(subscription=sub, feature_code="workspace.max_members").value, "6")

    def test_signed_webhook_replay_and_capture_with_new_event_id_are_idempotent(self):
        self.assertEqual(self.webhook().status_code, 200)
        sub = Subscription.objects.get(company=self.workspace)
        end, revision = sub.end_date, sub.updated_at
        self.assertEqual(self.webhook().status_code, 200)
        self.assertEqual(self.webhook(event_id="evt_duplicate").status_code, 200)
        self.assertEqual(self.webhook(event_type="payment.captured", event_id="evt_capture").status_code, 200)
        sub.refresh_from_db()
        self.assertEqual((sub.end_date, sub.updated_at), (end, revision))
        for model in [Invoice, Payment, RecurringCycle, Delivery]:
            self.assertEqual(model.objects.count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="recurring.cycle_paid").count(), 1)

    def test_forged_event_and_conflicting_reused_event_id_grant_nothing_extra(self):
        self.assertEqual(self.webhook(signature="forged").status_code, 400)
        self.assertFalse(RecurringCycle.objects.exists())
        self.assertEqual(self.webhook().status_code, 200)
        self.assertEqual(self.webhook(suffix="one").status_code, 400)
        self.assertEqual(RecurringCycle.objects.count(), 1)

    def test_delayed_old_cycle_does_not_shorten_or_reactivate_access(self):
        latest = self.record()
        sub = Subscription.objects.get(company=self.workspace)
        Subscription.objects.filter(pk=sub.pk).update(status="cancelled")
        older = self.record("one")
        sub.refresh_from_db()
        self.assertEqual(sub.end_date, latest.period_end)
        self.assertEqual(sub.status, "cancelled")
        self.assertEqual(older.access_action, "retained")
        self.record()
        sub.refresh_from_db()
        self.assertEqual(sub.status, "cancelled")

    def test_authorization_failures_and_terminal_lifecycle_only_record_observations(self):
        events = {"subscription.authenticated": "authenticated", "subscription.pending": "pending",
                  "subscription.halted": "halted", "subscription.cancelled": "cancelled",
                  "subscription.completed": "completed"}
        for event, status in events.items():
            self.provider_agreement["status"] = status
            self.assertEqual(self.webhook(event_type=event, event_id=event).status_code, 200)
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Delivery.objects.exists())
        self.assertFalse(RecurringAgreementEvent.objects.exclude(actor=None).exists())
        cycle = self.record()
        sub = cycle.invoice.subscription
        for event, status in events.items():
            self.provider_agreement["status"] = status
            response = self.webhook(event_type=event, event_id=event+"again")
            self.assertEqual(response.status_code, 200 if status in {"cancelled", "completed"} else 500)
        sub.refresh_from_db()
        self.assertEqual(sub.end_date, cycle.period_end)
        self.assertEqual(sub.status, "active")

    def test_pending_halted_and_recovery_keep_paid_access_until_verified_capture(self):
        from .access_policy import workspace_activity
        initial = self.record()
        before = Subscription.objects.values().get()
        entitlements = list(SubscriptionEntitlement.objects.order_by("pk").values())
        for state in ("pending", "halted", "active"):
            self.provider_agreement["status"] = state
            self.provider_agreement.update(current_start=int(initial.period_end.timestamp()),
                current_end=int((initial.period_end+timedelta(days=30)).timestamp()))
            event = "subscription.activated" if state == "active" else "subscription."+state
            self.assertEqual(self.webhook(event_type=event, event_id="recovery_"+state).status_code, 200)
            self.assertEqual(Subscription.objects.values().get(), before)
            self.assertEqual(list(SubscriptionEntitlement.objects.order_by("pk").values()), entitlements)
            self.agreement.refresh_from_db()
            self.assertEqual(self.agreement.provider_status, state)
            for offset, expected in ((timedelta(seconds=-1), "full"), (timedelta(0), "grace"),
                                     (timedelta(days=7), "read_only")):
                self.assertEqual(workspace_activity(self.workspace, at=initial.period_end+offset).mode, expected)
        self.add_cycle("recovered", initial.period_end, initial.period_end+timedelta(days=30))
        self.assertEqual(self.webhook(suffix="recovered", event_id="recovery_capture").status_code, 200)
        self.assertEqual(RecurringCycle.objects.get(provider_invoice_id="inv_recovered").access_action, "review")
        self.assertEqual(Subscription.objects.values().get(), before)
        self.assertEqual(self.webhook(suffix="recovered", event_id="recovery_capture_replay").status_code, 200)
        for model in (Invoice, Payment, RecurringCycle, Delivery):
            self.assertEqual(model.objects.count(), 2)

    def test_delayed_pending_event_observes_current_provider_status_without_regression(self):
        self.record()
        before = Subscription.objects.values().get()
        self.provider_agreement["status"] = "active"
        self.assertEqual(self.webhook(event_type="subscription.pending", event_id="late_pending").status_code, 200)
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.provider_status, "active")
        self.assertEqual(Subscription.objects.values().get(), before)
        self.assertEqual(self.agreement.events.filter(event_type="provider.observed").get().detail["provider_status"], "active")

    def test_wrong_invoice_payment_and_plan_dimensions_fail_closed(self):
        invoice_bad = [{"subscription_id": "sub_else"}, {"status": "issued"}, {"amount": 1},
                       {"amount_paid": 1}, {"amount_due": 1}, {"currency": "USD"}, {"order_id": "order_else"},
                       {"billing_start": None}, {"billing_end": 0}, {"line_items": []},
                       {"line_items": [{"type": "invoice", "quantity": 1, "amount": 176882, "currency": "INR"}]}]
        payment_bad = [{"id": "pay_else"}, {"invoice_id": "inv_else"}, {"status": "authorized"},
                       {"amount": 1}, {"currency": "USD"}, {"amount_refunded": 100}, {"amount": True}]
        for target, mutations in [(self.invoices["inv_two"], invoice_bad), (self.payments["pay_two"], payment_bad),
                                  (self.provider_agreement, [{"notes": {}}, {"plan_id": "plan_else"}, {"quantity": 2}]),
                                  (self.provider_plan["item"], [{"amount": 1}, {"currency": "USD"}])]:
            original = deepcopy(target)
            for mutation in mutations:
                with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                    target.update(mutation)
                    self.record()
                target.clear()
                target.update(deepcopy(original))
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(RecurringCycle.objects.exists())

    def test_unpaid_renewal_recovery_explains_status_and_preserves_existing_access(self):
        cycle = self.record()
        subscription = cycle.invoice.subscription
        before = (subscription.status, subscription.end_date, subscription.updated_at)
        self.add_cycle("unpaid", self.now+timedelta(days=15), self.now+timedelta(days=45))
        self.invoices["inv_unpaid"].update(status="issued", payment_id=None, paid_at=None,
                                          amount_paid=0, amount_due=176882)
        counts = {model: model.objects.count() for model in
                  (RecurringCycle, Invoice, Payment, Delivery, RecurringAgreementEvent, SubscriptionEvent)}
        with workspace_context(self.workspace.pk), patch.object(RazorpayService, "get_payment_status") as remote:
            with self.assertRaisesMessage(ValidationError, "Razorpay has not marked this invoice as paid"):
                reconcile_cycle(workspace=self.workspace, actor=self.owner, agreement_id=self.agreement.pk,
                                provider_invoice_id="inv_unpaid", reason="Inspect pending renewal")
            remote.assert_not_called()
        subscription.refresh_from_db()
        self.assertEqual((subscription.status, subscription.end_date, subscription.updated_at), before)
        for model, count in counts.items():
            self.assertEqual(model.objects.count(), count)

    def test_future_paid_period_records_money_without_changing_existing_access(self):
        from django.template.loader import render_to_string
        current = self.record()
        subscription = current.invoice.subscription
        before = (subscription.status, subscription.plan_id, subscription.end_date, subscription.updated_at,
                  subscription.auto_renew)
        entitlements = list(SubscriptionEntitlement.objects.filter(subscription=subscription).values())
        self.add_cycle("future", self.now+timedelta(days=15), self.now+timedelta(days=45))
        future = self.record("future")
        subscription.refresh_from_db()
        self.assertEqual((subscription.status, subscription.plan_id, subscription.end_date,
                          subscription.updated_at, subscription.auto_renew), before)
        self.assertEqual(list(SubscriptionEntitlement.objects.filter(subscription=subscription).values()), entitlements)
        self.assertEqual(future.access_action, "review")
        self.assertEqual(future.invoice.checkout_snapshot["access_review_reason"], "future_period")
        self.assertEqual(future.period_start, self.now+timedelta(days=15))
        self.assertEqual(future.period_end, self.now+timedelta(days=45))
        self.assertEqual(Payment.objects.get(invoice=future.invoice).status, "captured")
        self.assertEqual(Delivery.objects.count(), 2)
        html = render_to_string("subscriptions/emails/subscription_confirmation.html", {"invoice": future.invoice})
        self.assertIn("will not activate automatically", html)
        with patch("apps.subscriptions.recurring_cycles.timezone.now", return_value=self.now+timedelta(days=16)):
            self.assertEqual(self.record("future").pk, future.pk)
        subscription.refresh_from_db()
        self.assertEqual((subscription.status, subscription.plan_id, subscription.end_date,
                          subscription.updated_at, subscription.auto_renew), before)
        self.assertEqual(Delivery.objects.count(), 2)

    def test_first_future_payment_creates_only_inactive_financial_parent(self):
        self.add_cycle("future", self.now+timedelta(days=60), self.now+timedelta(days=90))
        future = self.record("future")
        subscription = future.invoice.subscription
        self.assertEqual((subscription.status, subscription.end_date, subscription.trial_end_date,
                          subscription.auto_renew), ("past_due", self.now, None, False))
        self.assertFalse(effective_billing_state(subscription).commercially_available)
        self.assertFalse(SubscriptionEntitlement.objects.exists())
        # Held money must not become evidence of already-granted future access.
        started = self.record()
        subscription.refresh_from_db()
        self.assertEqual(started.access_action, "applied")
        self.assertEqual(subscription.end_date, started.period_end)

    def test_held_cycle_cannot_bypass_review_of_overlapping_manual_access(self):
        subscription = Subscription.objects.create(company=self.workspace, plan=self.plan, status="active", auto_renew=False)
        before = (subscription.end_date, subscription.updated_at)
        self.add_cycle("future", self.now+timedelta(days=60), self.now+timedelta(days=90))
        self.assertEqual(self.record("future").access_action, "review")
        self.assertEqual(self.record().access_action, "review")
        subscription.refresh_from_db()
        self.assertEqual((subscription.end_date, subscription.updated_at), before)

    def test_future_signed_replay_and_refund_never_grant_access(self):
        self.add_cycle("future", self.now+timedelta(days=1), self.now+timedelta(days=31))
        for event_id in ("evt_future", "evt_future", "evt_future_new"):
            self.assertEqual(self.webhook(suffix="future", event_id=event_id).status_code, 200)
        future = RecurringCycle.objects.get()
        refund = {"id": "rfnd_future", "payment_id": "pay_future", "status": "processed", "amount": 176882, "currency": "INR"}
        self.payments["pay_future"].update(status="refunded", amount_refunded=176882)
        with patch.object(RazorpayService, "get_refund", return_value=refund):
            process_refund_webhook({"payload": {"refund": {"entity": refund}}})
        with patch("apps.subscriptions.recurring_cycles.timezone.now", return_value=self.now+timedelta(days=2)):
            self.assertEqual(self.record("future").pk, future.pk)
        self.assertEqual(Subscription.objects.get().status, "past_due")
        self.assertFalse(SubscriptionEntitlement.objects.exists())
        for model in (Invoice, Payment, RecurringCycle, Delivery):
            self.assertEqual(model.objects.count(), 1)

    def test_future_cycle_overlap_and_receipt_failure_remain_atomic(self):
        self.add_cycle("future", self.now+timedelta(days=1), self.now+timedelta(days=31))
        with patch("apps.subscriptions.recurring_cycles.send_checkout_receipt", side_effect=ValidationError("Queue unavailable")):
            with self.assertRaises(ValidationError):
                self.record("future")
        for model in (Subscription, Invoice, Payment, RecurringCycle, Delivery):
            self.assertFalse(model.objects.exists())
        self.record("future")
        self.add_cycle("overlap", self.now+timedelta(days=2), self.now+timedelta(days=32))
        with self.assertRaises(ValidationError):
            self.record("overlap")
        self.assertEqual(RecurringCycle.objects.count(), 1)

    def test_impossible_periods_and_future_payment_timestamps_are_rejected(self):
        for start, end in [(self.now-timedelta(days=1), self.now+timedelta(days=90)),
                           (self.now+timedelta(days=1), self.now+timedelta(days=90)),
                           (self.now-timedelta(days=200), self.now-timedelta(days=170))]:
            self.add_cycle("invalid", start, end)
            with self.assertRaises(ValidationError):
                self.record("invalid")
        self.assertFalse(RecurringCycle.objects.exists())
        self.add_cycle("future", self.now+timedelta(days=1), self.now+timedelta(days=31))
        self.invoices["inv_future"]["paid_at"] = int((self.now+timedelta(days=1)).timestamp())
        with self.assertRaises(ValidationError):
            self.record("future")
        self.assertFalse(RecurringCycle.objects.exists())

    def test_same_or_overlapping_period_with_another_identity_is_rejected(self):
        self.record()
        for offset in [0, 1]:
            self.add_cycle("overlap", self.now-timedelta(days=15-offset), self.now+timedelta(days=15+offset))
            with self.assertRaises(ValidationError):
                self.record("overlap")
        self.assertEqual(RecurringCycle.objects.count(), 1)

    def test_provider_outage_and_atomic_receipt_failure_retry_cleanly(self):
        with patch.object(RazorpayService, "get_invoice", side_effect=BillingProviderError("Temporary unavailable")):
            with self.assertRaises(BillingProviderError):
                self.record()
        with patch("apps.subscriptions.recurring_cycles.send_checkout_receipt", side_effect=ValidationError("Local failure")):
            with self.assertRaises(ValidationError):
                self.record()
        for model in [Subscription, Invoice, Payment, RecurringCycle, Delivery]:
            self.assertFalse(model.objects.exists())
        self.record()
        self.assertEqual(Delivery.objects.count(), 1)

    def test_owner_recovery_works_with_new_creation_disabled_and_rejects_wrong_workspace(self):
        with workspace_context(self.workspace.pk):
            with self.assertRaises(PermissionDenied):
                reconcile_cycle(workspace=self.workspace, actor=self.other, agreement_id=self.agreement.pk,
                                provider_invoice_id="inv_two", reason="Not owner")
            cycle = reconcile_cycle(workspace=self.workspace, actor=self.owner, agreement_id=self.agreement.pk,
                                    provider_invoice_id="inv_two", reason="Missing webhook")
            self.assertEqual(cycle.access_action, "applied")
        with override_settings(RAZORPAY_KEY_ID="rzp_live_fixture"), self.assertRaises(PermissionDenied):
            self.record("one")

    def test_full_refund_preserves_newer_term_and_replay_cannot_restore_refunded_access(self):
        old, latest = self.record("one"), self.record()
        refund = {"id": "rfnd_cycle", "payment_id": "pay_one", "status": "processed", "amount": 176882, "currency": "INR"}
        self.payments["pay_one"].update(status="refunded", amount_refunded=176882)
        with patch.object(RazorpayService, "get_refund", return_value=refund):
            process_refund_webhook({"payload": {"refund": {"entity": refund}}})
        self.record("one")
        sub = Subscription.objects.get(company=self.workspace)
        self.assertEqual(sub.end_date, latest.period_end)
        self.assertEqual(Payment.objects.get(invoice=old.invoice).status, "refunded")
        self.provider_agreement["status"] = "cancelled"
        with workspace_context(self.workspace.pk), patch.object(RazorpayService, "get_refund", return_value=refund), \
                self.assertRaises(ValidationError):
            resolve_billing_review(workspace=self.workspace, actor=self.owner, invoice_id=old.invoice_id,
                action="end_access", reason="An older refunded cycle cannot end newer paid access", revision=sub.updated_at.isoformat())
        self.assertEqual(Delivery.objects.count(), 2)

    def test_late_closed_agreement_records_money_but_cannot_change_access(self):
        RecurringAgreement.objects.filter(pk=self.agreement.pk).update(provider_status="cancelled", closed_at=self.now)
        cycle = self.record()
        self.assertEqual(cycle.access_action, "review")
        self.assertEqual(Subscription.objects.get(company=self.workspace).status, "past_due")
        self.assertEqual(Payment.objects.count(), 1)

    def test_archived_workspace_is_not_reactivated_and_suspension_is_preserved(self):
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state="ARCHIVED")
        self.assertEqual(self.record().access_action, "review")
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.lifecycle_state, "ARCHIVED")

    def test_existing_expired_manual_term_can_receive_first_recurring_cycle(self):
        sub = Subscription.objects.create(company=self.workspace, plan=self.plan, status="active", auto_renew=False)
        Subscription.objects.filter(pk=sub.pk).update(end_date=self.now-timedelta(days=20))
        self.assertEqual(self.record().access_action, "applied")

    def test_final_cycle_replay_is_allowed_but_an_extra_invoice_exceeds_contract(self):
        initial = self.record()
        before = Subscription.objects.values().get()
        end = initial.period_end
        for number in range(2, 13):
            self.add_cycle(f"cycle{number}", end, end+timedelta(days=30))
            final = self.record(f"cycle{number}")
            end = final.period_end
        self.provider_agreement.update(status="completed", paid_count=12, remaining_count=0, charge_at=None)
        self.assertEqual(self.record("cycle12").pk, final.pk)
        self.add_cycle("extra", end, end+timedelta(days=30))
        with self.assertRaisesMessage(ValidationError, "cycle count is exhausted"):
            self.record("extra")
        self.assertEqual(Subscription.objects.values().get(), before)
        for model in (Invoice, Payment, RecurringCycle, Delivery):
            self.assertEqual(model.objects.count(), 12)

    def annual_agreement(self, *, created_at=None):
        binding = RecurringPlanBinding.objects.create(plan=self.plan, mode=getattr(self, "provider_mode", "test"), provider_plan_id="plan_annual",
            snapshot=_offer(self.plan, "yearly"), actor=self.owner, reason="Annual fixture")
        RecurringAgreement.objects.filter(pk=self.agreement.pk).update(provider_status="cancelled", closed_at=self.now)
        agreement = RecurringAgreement.objects.create(workspace=self.workspace, binding=binding, actor=self.owner,
            request_key=uuid4(), state="verified", provider_subscription_id="sub_annual", verified_at=self.now,
            created_at=created_at or self.now-timedelta(days=100), provider_status="active",
            request_snapshot={**self.agreement.request_snapshot, "plan_id": "plan_annual"})
        self.provider_agreement.update(id="sub_annual", plan_id="plan_annual", status="active")
        self.provider_plan.update(id="plan_annual", period="yearly")
        self.provider_plan["item"]["amount"] = 1768820
        return agreement

    def test_annual_provider_period_and_frozen_offer_ignore_later_catalog_prices(self):
        agreement = self.annual_agreement()
        self.add_cycle("year", self.now-timedelta(days=10), self.now+timedelta(days=355), amount=1768820)
        self.invoices["inv_year"]["subscription_id"] = "sub_annual"
        Plan.objects.filter(pk=self.plan.pk).update(price=999, yearly_price=999)
        cycle = record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id="inv_year")
        self.assertEqual(str(cycle.invoice.total_amount), "17688.20")
        self.assertEqual(cycle.period_end-cycle.period_start, timedelta(days=365))
        self.assertEqual(cycle.access_action, "applied")
        self.add_cycle("nextyear", self.now+timedelta(days=355), self.now+timedelta(days=720), amount=1768820)
        self.invoices["inv_nextyear"]["subscription_id"] = "sub_annual"
        future = record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id="inv_nextyear")
        self.assertEqual(future.access_action, "review")
        self.assertEqual(str(future.invoice.total_amount), "17688.20")
        self.assertEqual(Subscription.objects.get(company=self.workspace).end_date, cycle.period_end)

    def test_actual_annual_midnight_boundary_recovers_once_with_exact_paid_dates(self):
        start = datetime.fromtimestamp(1790537928, tz=dt_timezone.utc)
        end = datetime.fromtimestamp(1822069800, tz=dt_timezone.utc)
        paid_at = datetime.fromtimestamp(1790537950, tz=dt_timezone.utc)
        agreement = self.annual_agreement(created_at=start-timedelta(minutes=2))
        self.add_cycle("annualmidnight", start, end, amount=1768820)
        self.invoices["inv_annualmidnight"].update(subscription_id="sub_annual", paid_at=int(paid_at.timestamp()))
        with workspace_context(self.workspace.pk), patch("apps.subscriptions.recurring_cycles.timezone.now", return_value=paid_at):
            for _ in range(2):
                cycle = reconcile_cycle(workspace=self.workspace, actor=self.owner, agreement_id=agreement.pk,
                    provider_invoice_id="inv_annualmidnight", reason="Annual provider recovery")
        self.assertEqual((cycle.period_start, cycle.period_end, cycle.access_action), (start, end, "applied"))
        sub = Subscription.objects.get(company=self.workspace)
        self.assertEqual((sub.status, sub.end_date), ("active", end))
        self.assertEqual(str(cycle.invoice.total_amount), "17688.20")
        self.assertEqual(SubscriptionEntitlement.objects.get(subscription=sub, feature_code="workspace.max_members").value, "6")
        for model in (Invoice, Payment, RecurringCycle, Delivery):
            self.assertEqual(model.objects.count(), 1)

    def test_future_short_annual_period_records_money_but_replay_does_not_apply_access(self):
        start = datetime.fromtimestamp(1790537928, tz=dt_timezone.utc)
        end = datetime.fromtimestamp(1822069800, tz=dt_timezone.utc)
        paid_at = start-timedelta(days=1)
        agreement = self.annual_agreement(created_at=paid_at-timedelta(minutes=2))
        self.add_cycle("heldannual", start, end, amount=1768820)
        self.invoices["inv_heldannual"].update(subscription_id="sub_annual", paid_at=int(paid_at.timestamp()))
        with patch("apps.subscriptions.recurring_cycles.timezone.now", return_value=paid_at):
            cycle = record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id="inv_heldannual")
        before = Subscription.objects.values().get()
        self.assertEqual((cycle.access_action, before["status"], before["end_date"]), ("review", "past_due", paid_at))
        self.assertEqual(cycle.invoice.checkout_snapshot["access_review_reason"], "future_period")
        with patch("apps.subscriptions.recurring_cycles.timezone.now", return_value=start+timedelta(seconds=1)):
            record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id="inv_heldannual")
        self.assertEqual(Subscription.objects.values().get(), before)
        self.assertFalse(SubscriptionEntitlement.objects.exists())
        for model in (Invoice, Payment, RecurringCycle, Delivery):
            self.assertEqual(model.objects.count(), 1)

    def test_short_annual_wrong_boundary_grants_nothing(self):
        start = datetime.fromtimestamp(1790537928, tz=dt_timezone.utc)
        end = datetime.fromtimestamp(1822069800, tz=dt_timezone.utc)
        agreement = self.annual_agreement(created_at=start-timedelta(minutes=2))
        for invalid_end in (end-timedelta(seconds=1), end+timedelta(seconds=1), end-timedelta(days=1)):
            self.add_cycle("shortannual", start, invalid_end, amount=1768820)
            self.invoices["inv_shortannual"].update(subscription_id="sub_annual", paid_at=int(start.timestamp()))
            with patch("apps.subscriptions.recurring_cycles.timezone.now", return_value=start), self.assertRaises(ValidationError):
                record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id="inv_shortannual")
        for model in (Subscription, Invoice, Payment, RecurringCycle, Delivery):
            self.assertFalse(model.objects.exists())

    def test_annual_calendar_edges_are_bounded_and_independent_of_display_timezone(self):
        ist = ZoneInfo("Asia/Kolkata")
        cases = [("2026-09-28T23:59:59", "2027-09-28T00:00:00"),
                 ("2028-02-29T12:00:00", "2029-02-28T00:00:00"),
                 ("2027-09-28T12:00:00", "2028-09-28T00:00:00"),
                 ("2026-12-31T12:00:00", "2027-12-31T00:00:00")]
        with timezone.override("America/New_York"):
            for left, right in cases:
                start, end = (datetime.fromisoformat(value).replace(tzinfo=ist) for value in (left, right))
                with self.subTest(start=start):
                    self.assertTrue(_valid_period(start, end, "yearly"))
                    self.assertFalse(_valid_period(start, end, "monthly"))
                    self.assertFalse(_valid_period(start, start+timedelta(days=364), "yearly"))
                    self.assertFalse(_valid_period(start, start+timedelta(days=367), "yearly"))
        # Wrong calendar day even though only a fraction below the duration floor.
        self.assertFalse(_valid_period(datetime(2026, 9, 28, tzinfo=ist),
                                      datetime(2027, 9, 27, 23, 59, tzinfo=ist), "yearly"))

    def test_suspension_and_explicit_entitlement_override_survive_renewal(self):
        first = self.record("one")
        grant = SubscriptionEntitlement.objects.get(subscription=first.invoice.subscription, feature_code="workspace.max_members")
        grant.source, grant.value, grant.override_actor, grant.override_reason = "override", "9", self.owner, "Existing approved capacity"
        grant.save()
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state="SUSPENDED")
        second = self.record()
        self.assertEqual(second.access_action, "applied")
        grant.refresh_from_db()
        self.assertEqual(grant.value, "9")
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.lifecycle_state, "SUSPENDED")

    def test_recurring_expiry_uses_existing_grace_then_read_only(self):
        from .access_policy import workspace_activity
        cycle = self.record()
        for offset, mode in [(timedelta(seconds=-1), "full"), (timedelta(0), "grace"),
                             (timedelta(days=7), "read_only")]:
            self.assertEqual(workspace_activity(self.workspace, at=cycle.period_end+offset).mode, mode)
        self.assertEqual(Subscription.objects.get(company=self.workspace).status, "active")

    def test_receipt_describes_recurring_period_without_claiming_one_off_purchase(self):
        from django.template.loader import render_to_string
        cycle = self.record()
        html = render_to_string("subscriptions/emails/subscription_confirmation.html", {"invoice": cycle.invoice})
        self.assertIn("paid recurring billing period", html)
        self.assertNotIn("one-off purchase", html)
        self.assertNotIn("Automatic renewal has not been enabled", html)

    def test_database_rejects_linking_another_workspaces_agreement_to_paid_invoice(self):
        cycle = self.record()
        other_workspace = Company.all_objects.create(name="Other cycle", schema_name="guard_cycle", owner=self.other, creator=self.other)
        Membership.objects.create(company=other_workspace, user=self.other, role=Role.objects.get(name="Owner"))
        other_agreement = RecurringAgreement.objects.create(workspace=other_workspace, binding=self.binding,
            actor=self.other, request_key=uuid4(), request_snapshot={}, created_at=self.now)
        with self.assertRaisesMessage(DatabaseError, "must match its Workspace"), transaction.atomic():
            RecurringCycle.objects.create(agreement=other_agreement, invoice=cycle.invoice, provider_invoice_id="inv_misbound",
                period_start=cycle.period_start, period_end=cycle.period_end, evidence=cycle.evidence, access_action="applied")

    def test_recovery_rejects_another_workspace_before_provider_reads(self):
        other_workspace = Company.all_objects.create(name="Other cycle", schema_name="other_cycle", owner=self.other, creator=self.other)
        Membership.objects.create(company=other_workspace, user=self.other, role=Role.objects.get(name="Owner"))
        with workspace_context(other_workspace.pk), patch.object(RazorpayService, "get_invoice") as remote:
            with self.assertRaises(ValidationError):
                reconcile_cycle(workspace=other_workspace, actor=self.other, agreement_id=self.agreement.pk,
                    provider_invoice_id="inv_two", reason="Wrong Workspace")
            remote.assert_not_called()

    def test_manual_capture_cannot_treat_a_recurring_invoice_as_a_new_term(self):
        cycle = self.record()
        with self.assertRaises(ValidationError):
            _apply_capture(invoice_id=cycle.invoice_id, payment=self.payments["pay_two"])
        self.assertEqual(RecurringCycle.objects.count(), 1)

    def test_database_protects_cycle_invoice_payment_and_workspace_links(self):
        cycle = self.record()
        mutations = [lambda: RecurringCycle.objects.filter(pk=cycle.pk).update(period_end=self.now),
                     lambda: RecurringCycle.objects.filter(pk=cycle.pk).delete(),
                     lambda: Payment.objects.filter(invoice_id=cycle.invoice_id).update(amount=1),
                     lambda: Payment.objects.filter(invoice_id=cycle.invoice_id).delete(),
                     lambda: Invoice.objects.filter(pk=cycle.invoice_id).update(status="issued")]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(DatabaseError), transaction.atomic():
                mutation()


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture", BILLING_TAX_RATE="18")
class ConcurrentCycleTests(CycleFixture, TransactionTestCase):
    def test_concurrent_callbacks_under_restricted_role_record_once(self):
        self._concurrent_record_once()

    def test_concurrent_future_callbacks_under_restricted_role_record_money_once(self):
        self.add_cycle("two", self.now+timedelta(days=1), self.now+timedelta(days=31))
        self._concurrent_record_once()
        self.assertEqual(RecurringCycle.objects.get().access_action, "review")
        self.assertEqual(Subscription.objects.get().status, "past_due")
        self.assertFalse(SubscriptionEntitlement.objects.exists())

    def _concurrent_record_once(self):
        role = connection.ops.quote_name("cycle_test_"+uuid4().hex)
        with connection.cursor() as c:
            c.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            c.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            c.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            c.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        barrier = Barrier(2)
        def run():
            close_old_connections()
            try:
                with connection.cursor() as c:
                    c.execute(f"SET ROLE {role}")
                barrier.wait(timeout=10)
                return self.record().pk
            finally:
                connections.close_all()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: run(), range(2)))
            self.assertEqual(results[0], results[1])
            self.assertEqual(RecurringCycle.objects.count(), 1)
            self.assertEqual(Delivery.objects.count(), 1)
            with connection.cursor() as c:
                c.execute(f"SET ROLE {role}")
            with self.assertRaises(DatabaseError), transaction.atomic():
                RecurringCycle.objects.update(evidence={})
        finally:
            with connection.cursor() as c:
                c.execute("RESET ROLE")
                c.execute(f"DROP OWNED BY {role}")
                c.execute(f"DROP ROLE {role}")
