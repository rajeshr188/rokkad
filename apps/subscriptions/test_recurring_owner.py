from copy import deepcopy
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4
import hashlib
import hmac
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.tenancy.context import workspace_context
from . import recurring_owner as owner_actions
from .models import Invoice, Payment, RecurringAgreement, RecurringAgreementEvent, Subscription
from .razorpay_service import BillingProviderError, RazorpayService
from .test_recurring_cycles import CycleFixture


class OwnerFixture(CycleFixture):
    def args(self):
        return dict(workspace=self.workspace, actor=self.owner, agreement_id=self.agreement.pk)

    def signature(self, payment="pay_auth", subscription="sub_cycle"):
        return hmac.new(b"fixture", f"{payment}|{subscription}".encode(), hashlib.sha256).hexdigest()

    def saved_request(self):
        with patch.object(owner_actions, "_deliver_cancellation"), workspace_context(self.workspace.pk):
            return owner_actions.request_cancellation(**self.args())


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture",
                   BILLING_RECURRING_ENABLED=True, BILLING_TAX_RATE="18",
                   STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RecurringOwnerTests(OwnerFixture, TestCase):
    def test_callback_binds_signature_to_server_agreement_and_grants_nothing(self):
        with workspace_context(self.workspace.pk):
            for signature in [self.signature(subscription="sub_other"), "☃", "", None]:
                with self.assertRaises(ValidationError):
                    owner_actions.confirm_authorization(**self.args(), payment_id="pay_auth", signature=signature)
            for _ in range(2):
                owner_actions.confirm_authorization(**self.args(), payment_id="pay_auth", signature=self.signature())
        self.assertEqual(self.agreement.events.filter(event_type="authorization.verified").count(), 1)
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())

    @override_settings(BILLING_RECURRING_ENABLED=False)
    def test_pause_blocks_checkout_but_not_confirmation_refresh_or_cancellation(self):
        with workspace_context(self.workspace.pk):
            with self.assertRaises(PermissionDenied):
                owner_actions.authorization_options(**self.args())
            owner_actions.confirm_authorization(**self.args(), payment_id="pay_auth", signature=self.signature())
            owner_actions.refresh_agreement(**self.args())
            self.saved_request()

    def test_owner_workspace_and_mode_boundaries_before_provider_calls(self):
        with workspace_context(self.workspace.pk), patch.object(RazorpayService, "get_subscription") as remote:
            with self.assertRaises(PermissionDenied):
                owner_actions.refresh_agreement(**{**self.args(), "actor": self.other})
            with self.assertRaises(ValidationError):
                owner_actions.refresh_agreement(**{**self.args(), "agreement_id": self.agreement.pk + 100})
            with override_settings(RAZORPAY_KEY_ID="rzp_live_fixture"), self.assertRaises(PermissionDenied):
                owner_actions.request_cancellation(**self.args())
            remote.assert_not_called()

    def test_authorization_uses_frozen_identity_and_blocks_after_cancel_request(self):
        self.provider_agreement["status"] = "created"
        with workspace_context(self.workspace.pk):
            options = owner_actions.authorization_options(**self.args())
            self.assertEqual(options["subscription_id"], "sub_cycle")
            self.assertNotIn("amount", options)
            self.saved_request()
            with self.assertRaises(ValidationError):
                owner_actions.authorization_options(**self.args())

    def test_authorization_rechecks_existing_paid_time(self):
        self.record()
        self.provider_agreement["status"] = "created"
        with workspace_context(self.workspace.pk), self.assertRaisesMessage(ValidationError, "scheduled transition"):
            owner_actions.authorization_options(**self.args())

    def test_terminal_refresh_cannot_regress_and_paid_dates_never_change(self):
        cycle = self.record()
        original = cycle.invoice.subscription.end_date
        self.provider_agreement["status"] = "cancelled"
        with workspace_context(self.workspace.pk):
            owner_actions.refresh_agreement(**self.args())
            self.provider_agreement["status"] = "active"
            with self.assertRaises(ValidationError):
                owner_actions.refresh_agreement(**self.args())
            from .recurring_cycles import handle_subscription_event
            with self.assertRaises(ValidationError):
                handle_subscription_event({"event": "subscription.activated",
                                           "payload": {"subscription": {"entity": {"id": "sub_cycle"}}}})
        sub = Subscription.objects.get()
        self.assertEqual(sub.end_date, original)
        self.assertEqual(sub.status, "active")
        self.agreement.refresh_from_db()
        self.assertIsNone(self.agreement.closed_at)

    def test_cancel_request_rollback_does_not_contact_provider(self):
        with patch.object(owner_actions, "_deliver_cancellation") as send:
            with self.assertRaises(ValueError), workspace_context(self.workspace.pk):
                owner_actions.request_cancellation(**self.args())
                raise ValueError("rollback")
            send.assert_not_called()
        self.assertFalse(self.agreement.events.filter(event_type="cancel.requested").exists())

    def test_completed_agreement_keeps_paid_access_and_recoverable_final_invoice(self):
        from apps.platform_mail.models import Delivery
        from .models import RecurringCycle, SubscriptionEntitlement
        from .recurring import require_no_recurring_agreement
        initial = self.record()
        before = Subscription.objects.values().get()
        entitlements = list(SubscriptionEntitlement.objects.order_by("pk").values())
        self.add_cycle("final", initial.period_end, initial.period_end+timedelta(days=30))
        self.provider_agreement.update(status="completed", paid_count=12, remaining_count=0, charge_at=None)
        self.client.force_login(self.owner)
        kwargs = {"workspace_slug": self.workspace.slug, "agreement_id": self.agreement.pk}
        response = self.client.post(reverse("workspace_subscriptions:recurring-refresh", kwargs=kwargs), follow=True)
        self.assertContains(response, "Completed")
        self.assertContains(response, "This agreement has ended. Already-paid time is preserved.")
        self.assertNotContains(response, "I want to stop future renewals.")
        self.assertNotContains(response, 'id="recurring-authorize"')
        self.assertEqual(Subscription.objects.values().get(), before)
        for _ in range(2):
            response = self.client.post(reverse("workspace_subscriptions:recurring-recover", kwargs=kwargs),
                {"provider_invoice_id": "inv_final"}, follow=True)
            self.assertContains(response, "Payment recorded. Workspace access is unchanged")
        self.assertEqual(RecurringCycle.objects.get(provider_invoice_id="inv_final").access_action, "review")
        self.assertEqual(Subscription.objects.values().get(), before)
        self.assertEqual(list(SubscriptionEntitlement.objects.order_by("pk").values()), entitlements)
        for model in (Invoice, Payment, RecurringCycle, Delivery):
            self.assertEqual(model.objects.count(), 2)
        self.agreement.refresh_from_db()
        self.assertIsNone(self.agreement.closed_at)
        with workspace_context(self.workspace.pk), self.assertRaises(ValidationError):
            require_no_recurring_agreement(self.workspace)
        with workspace_context(self.workspace.pk), patch.object(RazorpayService, "cancel_subscription") as cancel:
            with self.assertRaisesMessage(ValidationError, "already ended"):
                owner_actions.request_cancellation(**self.args())
            cancel.assert_not_called()

    def test_owner_page_and_post_only_csrf_boundary(self):
        self.client.force_login(self.owner)
        kwargs = {"workspace_slug": self.workspace.slug}
        url = reverse("workspace_subscriptions:recurring", kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stop future renewals")
        self.assertContains(response, "INR 1768.82")
        cancel = reverse("workspace_subscriptions:recurring-cancel", kwargs={**kwargs, "agreement_id": self.agreement.pk})
        self.assertEqual(self.client.get(cancel).status_code, 405)
        self.client.post(cancel, {})
        self.assertFalse(self.agreement.events.filter(event_type="cancel.requested").exists())
        from django.test import Client
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        self.assertEqual(csrf_client.post(cancel, {"confirm_cancel": "yes"}).status_code, 403)
        self.client.force_login(self.other)
        self.assertNotEqual(self.client.get(url).status_code, 200)

    def test_known_invoice_recovery_uses_existing_paid_cycle_path(self):
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:recurring-recover", kwargs={"workspace_slug": self.workspace.slug,
                                                                            "agreement_id": self.agreement.pk})
        for _ in range(2):
            self.assertEqual(self.client.post(url, {"provider_invoice_id": "inv_two"}).status_code, 302)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

    def test_future_recovery_displays_held_payment_without_promising_activation(self):
        self.add_cycle("future", self.now+timedelta(days=1), self.now+timedelta(days=31))
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:recurring-recover", kwargs={"workspace_slug": self.workspace.slug,
                                                                            "agreement_id": self.agreement.pk})
        response = self.client.post(url, {"provider_invoice_id": "inv_future"}, follow=True)
        self.assertContains(response, "Payment recorded. Workspace access is unchanged")
        self.assertContains(response, "Payments awaiting access review")
        self.assertContains(response, "will not activate held access automatically")
        self.assertContains(response, "RCY-inv_future")
        self.assertEqual(Subscription.objects.get().status, "past_due")
        invoice_url = reverse("workspace_subscriptions:invoice-detail", kwargs={"workspace_slug": self.workspace.slug,
                                                                               "pk": Invoice.objects.get().pk})
        self.assertContains(self.client.get(invoice_url), "The period will not activate automatically")

    def test_collection_attention_guidance_uses_verified_status_and_preserves_access(self):
        self.record()
        before = Subscription.objects.values().get()
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:recurring-refresh", kwargs={"workspace_slug": self.workspace.slug,
                                                                          "agreement_id": self.agreement.pk})
        for state, message in (("pending", "Razorpay may retry the payment"),
                               ("halted", "Automatic collection has stopped")):
            self.provider_agreement["status"] = state
            response = self.client.post(url, follow=True)
            self.assertContains(response, message)
            self.assertContains(response, "Already-paid time is preserved")
            self.assertContains(response, "an unpaid invoice does not extend it")
            self.assertEqual(Subscription.objects.values().get(), before)
        self.provider_agreement["status"] = "active"
        response = self.client.post(url, follow=True)
        self.assertNotContains(response, "Automatic collection has stopped")
        self.assertNotContains(response, "Razorpay may retry the payment")
        self.assertEqual(Invoice.objects.count(), 1)

    def test_review_list_keeps_old_agreement_payments_visible_and_paginated(self):
        for suffix, offset in (("firstfuture", 1), ("nextfuture", 31)):
            self.add_cycle(suffix, self.now+timedelta(days=offset), self.now+timedelta(days=offset+30))
            self.record(suffix)
        RecurringAgreement.objects.filter(pk=self.agreement.pk).update(provider_status="cancelled", closed_at=self.now)
        RecurringAgreement.objects.create(workspace=self.workspace, binding=self.binding, actor=self.owner,
            request_key=uuid4(), request_snapshot={}, created_at=self.now+timedelta(seconds=1))
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:recurring", kwargs={"workspace_slug": self.workspace.slug})
        with patch("apps.subscriptions.recurring_views.Paginator", side_effect=lambda rows, size: Paginator(rows, 1)):
            first, second = self.client.get(url), self.client.get(url, {"review_page": 2})
        self.assertContains(first, "RCY-inv_nextfuture")
        self.assertNotContains(first, "RCY-inv_firstfuture")
        self.assertContains(first, "More reviews")
        self.assertContains(second, "RCY-inv_firstfuture")
        self.assertNotContains(second, "RCY-inv_nextfuture")


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture",
                   BILLING_RECURRING_ENABLED=False, BILLING_TAX_RATE="18")
class CancellationDeliveryTests(OwnerFixture, TransactionTestCase):
    def cancel_at_provider(self, identity):
        self.assertFalse(connection.in_atomic_block)
        self.assertTrue(self.agreement.events.filter(event_type="cancel.dispatched").exists())
        self.assertEqual(identity, "sub_cycle")
        self.provider_agreement["status"] = "cancelled"
        return deepcopy(self.provider_agreement)

    def test_committed_delivery_confirms_once_preserves_access_and_reservation(self):
        cycle = self.record()
        end = cycle.invoice.subscription.end_date
        with patch.object(RazorpayService, "cancel_subscription", side_effect=self.cancel_at_provider) as cancel:
            with workspace_context(self.workspace.pk):
                first = owner_actions.request_cancellation(**self.args())
                second = owner_actions.request_cancellation(**self.args())
                self.assertEqual(first.pk, second.pk)
                cancel.assert_not_called()
            cancel.assert_called_once()
            owner_actions.process_cancellation(request_id=first.pk)
            cancel.assert_called_once()
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.provider_status, "cancelled")
        self.assertIsNone(self.agreement.closed_at)
        sub = Subscription.objects.get()
        self.assertEqual((sub.status, sub.end_date), ("active", end))

    def test_timeout_is_unknown_and_recovery_fetches_without_repost(self):
        request = self.saved_request()
        with patch.object(RazorpayService, "cancel_subscription", side_effect=BillingProviderError("timeout")) as cancel:
            with self.assertRaises(BillingProviderError):
                owner_actions.process_cancellation(request_id=request.pk)
            self.assertTrue(self.agreement.events.filter(event_type="cancel.unknown").exists())
            owner_actions.process_cancellation(request_id=request.pk)
            cancel.assert_called_once()
            self.provider_agreement["status"] = "cancelled"
            owner_actions.process_cancellation(request_id=request.pk)
            cancel.assert_called_once()
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.provider_status, "cancelled")

    def test_local_persistence_failure_after_provider_success_never_reposts(self):
        request = self.saved_request()
        with patch.object(RazorpayService, "cancel_subscription", side_effect=self.cancel_at_provider) as cancel:
            with patch.object(owner_actions, "_observe", side_effect=DatabaseError("local failure")):
                with self.assertRaises(DatabaseError):
                    owner_actions.process_cancellation(request_id=request.pk)
            owner_actions.process_cancellation(request_id=request.pk)
            cancel.assert_called_once()

    def test_already_ended_provider_needs_no_cancellation_post(self):
        request = self.saved_request()
        self.provider_agreement["status"] = "completed"
        with patch.object(RazorpayService, "cancel_subscription") as cancel:
            owner_actions.process_cancellation(request_id=request.pk)
            cancel.assert_not_called()

    def test_invalid_remote_identity_cannot_cancel_another_agreement(self):
        request = self.saved_request()
        self.provider_agreement["id"] = "sub_other"
        with patch.object(RazorpayService, "cancel_subscription") as cancel:
            with self.assertRaises(ValidationError):
                owner_actions.process_cancellation(request_id=request.pk)
            cancel.assert_not_called()

    def test_concurrent_delivery_under_restricted_role_posts_once(self):
        request = self.saved_request()
        role = connection.ops.quote_name("cancel_test_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        entered, release = Event(), Event()
        def blocked_cancel(identity):
            entered.set()
            if not release.wait(timeout=15):
                raise AssertionError("Concurrent recovery did not finish")
            return self.cancel_at_provider(identity)
        def run():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {role}")
                return owner_actions.process_cancellation(request_id=request.pk).provider_status
            finally:
                connections.close_all()
        try:
            with patch.object(RazorpayService, "cancel_subscription", side_effect=blocked_cancel) as cancel:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    first = pool.submit(run)
                    try:
                        self.assertTrue(entered.wait(timeout=10))
                        self.assertEqual(pool.submit(run).result(timeout=10), "active")
                    finally:
                        release.set()
                    self.assertEqual(first.result(timeout=10), "cancelled")
                cancel.assert_called_once()
        finally:
            release.set()
            with connection.cursor() as cursor:
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
