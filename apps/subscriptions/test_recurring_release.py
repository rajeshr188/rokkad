from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.tenancy.context import workspace_context
from .models import (BillingResolution, Invoice, Payment, RecurringAgreement, RecurringAgreementEvent,
                     Subscription, SubscriptionEntitlement)
from .razorpay_service import BillingProviderError, RazorpayService
from .recurring import create_agreement, reconcile_agreement
from .recurring_release import _collection, _invoice_ids, release_refunded_agreement
from .recurring_cycles import record_paid_cycle
from .recovery import process_refund_webhook
from .reviews import resolve_billing_review
from .test_recurring_cycles import CycleFixture


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture", BILLING_TAX_RATE="18",
                   BILLING_RECURRING_ENABLED=False)
class RecurringReleaseTests(CycleFixture, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.add_cycle("two", self.now-timedelta(days=1), self.now+timedelta(days=30))
        self.cycle = self.record()
        self.invoices.pop("inv_one")
        self.payments["pay_two"].update(status="refunded", amount_refunded=176882)
        self.refund = {"id": "rfnd_release", "payment_id": "pay_two", "status": "processed",
                       "amount": 176882, "currency": "INR"}
        patch.object(RazorpayService, "get_refund", side_effect=lambda _: deepcopy(self.refund)).start()
        process_refund_webhook({"payload": {"refund": {"entity": self.refund}}})
        self.provider_agreement.update(status="cancelled", charge_at=None, paid_count=1)
        with workspace_context(self.workspace.pk):
            resolve_billing_review(workspace=self.workspace, actor=self.owner, invoice_id=self.cycle.invoice_id,
                action="end_access", reason="Refunded term reviewed", revision=Subscription.objects.get().updated_at.isoformat())
        self.before = Subscription.objects.values().get()
        self.entitlements = list(SubscriptionEntitlement.objects.order_by("pk").values())
        self.listing = patch.object(RazorpayService, "get_subscription_invoices", side_effect=lambda _, skip=0:
            self.collection(list(self.invoices.values())[skip:skip+100])).start()
        self.attempts = [deepcopy(self.payments["pay_two"])]
        patch.object(RazorpayService, "get_order_payments", side_effect=lambda _: self.collection(self.attempts)).start()

    @staticmethod
    def collection(rows):
        return {"entity": "collection", "count": len(rows), "items": deepcopy(rows)}

    def release(self, **changes):
        args = dict(workspace_id=self.workspace.pk, actor=self.owner, agreement_id=self.agreement.pk,
                    revision=self.before["updated_at"].isoformat(), reason="Reviewed fully refunded mandate")
        args.update(changes)
        return release_refunded_agreement(**args)

    def test_release_replay_preserves_access_evidence_and_closed_history(self):
        with patch.object(RazorpayService, "create_subscription") as create, patch.object(RazorpayService, "cancel_subscription") as cancel:
            event = self.release()
            create.assert_not_called()
            cancel.assert_not_called()
        self.assertEqual(event.detail["cycles"][0]["refunds"], ["rfnd_release"])
        self.assertIsNotNone(RecurringAgreement.objects.get().closed_at)
        with patch.object(RazorpayService, "get_subscription", side_effect=BillingProviderError("offline")):
            self.assertEqual(self.release(revision="old replay").pk, event.pk)
        self.record()
        self.assertEqual(Subscription.objects.values().get(), self.before)
        self.assertEqual(list(SubscriptionEntitlement.objects.order_by("pk").values()), self.entitlements)
        self.assertEqual(self.agreement.events.filter(event_type="reservation.released").count(), 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            RecurringAgreement.objects.filter(pk=self.agreement.pk).update(closed_at=None)
        with override_settings(BILLING_RECURRING_ENABLED=True):
            result = reconcile_agreement(workspace_id=self.workspace.pk, actor=self.owner,
                agreement_id=self.agreement.pk, provider_subscription_id="sub_cycle", reason="Historical replay")
        self.assertIsNotNone(result.closed_at)

    def test_pending_or_terminal_mismatch_keeps_reservation(self):
        for changes in ({"status": "active"}, {"charge_at": 123}, {"paid_count": 2}, {"paid_count": True}):
            original = deepcopy(self.provider_agreement)
            self.provider_agreement.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.release()
            self.provider_agreement = original
        self.assertIsNone(RecurringAgreement.objects.get().closed_at)

    def test_unpaid_missing_foreign_and_duplicate_invoices_block_release(self):
        original = deepcopy(self.invoices)
        for rows in ([], [dict(self.invoices["inv_two"], status="issued")],
                     [dict(self.invoices["inv_two"], subscription_id="sub_other")],
                     [self.invoices["inv_two"], self.invoices["inv_two"]]):
            with self.subTest(rows=rows), patch.object(RazorpayService, "get_subscription_invoices",
                    side_effect=lambda _, skip=0: self.collection(rows if skip == 0 else [])), self.assertRaises(ValidationError):
                self.release()
        self.invoices = original
        self.assertIsNone(RecurringAgreement.objects.get().closed_at)

    def test_unsettled_additional_order_attempt_blocks_release(self):
        for status in ("created", "authorized", "captured", "refunded"):
            self.attempts = [deepcopy(self.payments["pay_two"]), {"id": "pay_extra", "order_id": "order_two", "status": status}]
            with self.subTest(status=status), self.assertRaises(ValidationError):
                self.release()
        self.attempts[-1]["status"] = "failed"
        self.release()

    def test_provider_refund_or_local_refund_mismatch_blocks_release(self):
        for changes in ({"amount": 1}, {"status": "pending"}, {"payment_id": "pay_other"}):
            original = deepcopy(self.refund)
            self.refund.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.release()
            self.refund = original
        Payment.objects.filter(invoice=self.cycle.invoice).update(refund_amount=0)
        with self.assertRaises(ValidationError):
            self.release()

    def test_authority_revision_mode_and_local_decision_required(self):
        with self.assertRaises(PermissionDenied):
            self.release(actor=self.other)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.release()
        self.owner.is_active = True
        self.owner.save(update_fields=["is_active"])
        with override_settings(RAZORPAY_KEY_ID="rzp_live_fixture"), self.assertRaises(PermissionDenied):
            self.release()
        for args in ({"agreement_id": 999999}, {"revision": "stale"}, {"reason": ""}):
            with self.subTest(args=args), self.assertRaises(ValidationError):
                self.release(**args)
        Subscription.objects.filter(pk=self.before["id"]).update(status="active")
        with self.assertRaises(ValidationError):
            self.release()

    def test_provider_outage_and_changed_local_state_do_not_release(self):
        with patch.object(RazorpayService, "get_order_payments", side_effect=BillingProviderError("offline")):
            with self.assertRaises(BillingProviderError):
                self.release()
        def changed(_):
            Subscription.objects.filter(pk=self.before["id"]).update(status="active")
            return self.collection(self.attempts)
        with patch.object(RazorpayService, "get_order_payments", side_effect=changed), self.assertRaises(ValidationError):
            self.release()
        self.assertIsNone(RecurringAgreement.objects.get().closed_at)

    def test_audit_failure_rolls_back_release(self):
        with patch.object(RecurringAgreementEvent.objects, "create", side_effect=RuntimeError("audit failure")):
            with self.assertRaises(RuntimeError):
                self.release()
        self.assertIsNone(RecurringAgreement.objects.get().closed_at)

    def test_another_paid_invoice_blocks_release_even_with_cancelled_access(self):
        invoice = Invoice.objects.create(subscription_id=self.before["id"], invoice_number="other-paid",
            base_amount=1, gst_rate=0, status="paid", invoice_date=self.now.date(), due_date=self.now.date())
        with self.assertRaisesMessage(ValidationError, "Other paid invoices"):
            self.release()
        self.assertEqual(Invoice.objects.get(pk=invoice.pk).status, "paid")
        self.assertIsNone(RecurringAgreement.objects.get().closed_at)

    def test_missing_access_decision_and_scheduled_creation_keep_reservation(self):
        with patch.object(BillingResolution.objects, "filter") as resolutions:
            resolutions.return_value.first.return_value = None
            with self.assertRaisesMessage(ValidationError, "completed access review"):
                self.release()
        with patch.object(RecurringAgreement.objects, "select_related") as agreements:
            self.agreement.request_snapshot["start_at"] = int(self.now.timestamp())
            agreements.return_value.filter.return_value.first.return_value = self.agreement
            with self.assertRaisesMessage(ValidationError, "Scheduled authorization"):
                self.release()
        self.assertIsNone(RecurringAgreement.objects.get().closed_at)

    def test_scan_requires_final_empty_page_and_rejects_malformed_collection(self):
        rows = [self.invoices["inv_two"], dict(self.invoices["inv_two"], id="inv_three")]
        with patch.object(RazorpayService, "get_subscription_invoices",
                side_effect=lambda _, skip=0: self.collection(rows[skip:skip+1])) as listing:
            self.assertEqual(_invoice_ids(self.agreement), {"inv_two", "inv_three"})
            self.assertEqual([call.kwargs["skip"] for call in listing.call_args_list], [0, 1, 2])
        for value in ({}, {"entity": "collection", "count": 2, "items": []},
                      {"entity": "collection", "count": True, "items": [{}]}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                _collection(value)

    def test_new_agreement_gets_exact_shorter_period_and_old_replay_cannot_restore_access(self):
        self.release()
        def create(payload):
            return {**payload, "id": "sub_replacement", "entity": "subscription", "status": "created",
                    "has_scheduled_changes": False}
        with override_settings(BILLING_RECURRING_ENABLED=True), patch.object(RazorpayService, "create_subscription", side_effect=create):
            new = create_agreement(workspace_id=self.workspace.pk, actor=self.owner, binding_id=self.binding.pk,
                                   total_count=2, request_key=uuid4())
        self.assertEqual(Subscription.objects.values().get(), self.before)
        old_provider = deepcopy(self.provider_agreement)
        self.provider_agreement = {**new.request_snapshot, "id": new.provider_subscription_id,
                                   "entity": "subscription", "status": "active", "has_scheduled_changes": False}
        # New period ends before the old refunded end date, but is actually due.
        new_start = timezone.now().replace(microsecond=0)
        self.add_cycle("replacement", new_start, new_start+timedelta(days=28))
        self.invoices["inv_replacement"]["subscription_id"] = new.provider_subscription_id
        cycle = record_paid_cycle(agreement_id=new.pk, provider_invoice_id="inv_replacement")
        self.assertEqual(cycle.access_action, "applied")
        after = Subscription.objects.values().get()
        self.assertEqual(after["end_date"], new_start+timedelta(days=28))
        self.assertEqual(after["status"], "active")
        self.provider_agreement = old_provider
        self.record()
        self.release(revision="historical retry")
        self.assertEqual(Subscription.objects.values().get(), after)
        self.assertIsNone(RecurringAgreement.objects.get(pk=new.pk).closed_at)
