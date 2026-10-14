"""PW-02 durable capture, source safety, owner reviews and restricted-role tests."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
import time
import uuid
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, connections, close_old_connections, DatabaseError, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.platform_mail.models import Delivery as EmailDelivery
from apps.subscriptions.models import Invoice, Payment, Plan, Subscription, SubscriptionEvent
from apps.subscriptions.public_trial import start_public_trial, PUBLIC_TRIAL_TERMS
from apps.subscriptions.notifications import send_checkout_receipt
from apps.subscriptions import test_checkout as checkout_tests
from apps.subscriptions.test_recurring_cycles import CycleFixture
from apps.tenancy.context import workspace_context
from apps.platform_whatsapp.tests import EnrollmentFixture, INBOUND
from apps.platform_whatsapp.models import Contact, ConsentEvent, Delivery, Preference, SetupRequest
from apps.platform_whatsapp.intents import (review_setup, confirm_setup, preview_delivery,
    _capture_trial_started, _capture_paid_invoice)

STORAGE = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

@override_settings(**INBOUND, STORAGES=STORAGE, BILLING_ALLOW_TRIAL_START=True)
class SourceIntentTests(EnrollmentFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.owner.email = "pw02-owner@example.test"
        self.owner.save(update_fields=["email"])
        EmailAddress.objects.create(user=self.owner, email=self.owner.email, primary=True, verified=True)
        self.plan = Plan.objects.create(name="PW02 public trial", tier="starter", price=0, trial_days=30, max_users=6)

    def start(self):
        with override_settings(BILLING_PUBLIC_TRIAL_PLAN_ID=self.plan.pk), workspace_context(self.ws.pk):
            return start_public_trial(workspace=self.ws, actor=self.owner, plan_id=self.plan.pk,
                                      accepted_terms=PUBLIC_TRIAL_TERMS)

    def rows(self):
        with workspace_context(self.ws.pk):
            return list(Delivery.objects.all())

    def setup(self):
        review = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        return confirm_setup(actor=self.owner, token=review["token"])

    def test_paired_consented_trial_has_one_source_intent_and_no_email_or_network_send(self):
        self.paired()
        with patch("apps.platform_mail.transport.send_ses") as send:
            sub = self.start()
        send.assert_not_called()
        row = self.rows()[0]
        self.assertEqual(row.trial_event_id, SubscriptionEvent.objects.get(event_type="trial.started").pk)
        self.assertEqual(row.source_recorded_at, row.trial_event.created_at)
        self.assertTrue(row.capture_only)
        self.assertFalse(EmailDelivery.objects.exists())
        self.assertEqual(sub.status, "trial")
        self.assertFalse(Payment.objects.exists())

    def test_unpaired_or_unconsented_trial_still_starts_without_intent(self):
        contact, _ = self.enroll()
        self.consent(contact)
        self.start()
        self.assertFalse(self.rows())
        self.assertEqual(Subscription.objects.count(), 1)

    def test_unselected_subscription_category_creates_no_trial_intent(self):
        contact = self.paired()
        self.consent(contact, subscription=False)
        self.start()
        self.assertFalse(self.rows())

    def test_trial_source_and_intent_roll_back_together(self):
        self.paired()
        with self.assertRaises(RuntimeError), transaction.atomic():
            self.start()
            self.assertEqual(len(self.rows()), 1)
            raise RuntimeError("abort source transaction")
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(SubscriptionEvent.objects.exists())
        self.assertFalse(self.rows())

    def test_internal_intent_failure_uses_existing_source_transaction_recovery(self):
        self.paired()
        with patch("apps.platform_whatsapp.intents._capture", side_effect=RuntimeError("local write failure")):
            with self.assertRaises(RuntimeError):
                self.start()
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(self.rows())

    def test_trial_intent_replay_is_idempotent(self):
        self.paired()
        self.start()
        event = SubscriptionEvent.objects.get(event_type="trial.started")
        first = self.rows()[0]
        with transaction.atomic():
            again = _capture_trial_started(event)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(len(self.rows()), 1)

    def test_late_enrollment_cannot_backfill_old_trial(self):
        self.start()
        self.paired()
        with transaction.atomic():
            self.assertIsNone(_capture_trial_started(SubscriptionEvent.objects.get(event_type="trial.started")))
        self.assertFalse(self.rows())

    def test_setup_review_is_read_only_confirmation_is_idempotent(self):
        self.paired()
        review = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        self.assertFalse(self.rows())
        first = confirm_setup(actor=self.owner, token=review["token"])
        again = confirm_setup(actor=self.owner, token=review["token"])
        self.assertEqual(first.pk, again.pk)
        with workspace_context(self.ws.pk):
            self.assertEqual(SetupRequest.objects.count(), 1)
        self.assertFalse(Subscription.objects.exists())

    def test_setup_confirmation_and_source_roll_back_together(self):
        self.paired()
        review = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        with self.assertRaises(RuntimeError), transaction.atomic():
            confirm_setup(actor=self.owner, token=review["token"])
            raise RuntimeError("abort confirmation")
        self.assertFalse(self.rows())
        with workspace_context(self.ws.pk):
            self.assertFalse(SetupRequest.objects.exists())

    def test_setup_needs_current_pairing_and_its_own_category(self):
        with self.assertRaises(ValidationError):
            review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        contact = self.paired()
        self.consent(contact, setup=False)
        with self.assertRaises(ValidationError):
            review_setup(actor=self.owner, workspace_slug=self.ws.slug)

    def test_setup_review_rejects_forgery_expiry_and_different_actor(self):
        self.paired()
        review = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        with self.assertRaises(ValidationError):
            confirm_setup(actor=self.owner, token=review["token"]+"changed")
        with self.assertRaises(PermissionDenied):
            confirm_setup(actor=self.other, token=review["token"])
        with patch("django.core.signing.time.time", return_value=time.time()-601):
            old = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        with self.assertRaises(ValidationError):
            confirm_setup(actor=self.owner, token=old["token"])
        self.assertFalse(self.rows())

    def test_changed_choices_or_workspace_name_invalidates_setup_review(self):
        contact = self.paired()
        review = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        self.consent(contact)
        with self.assertRaises(ValidationError):
            confirm_setup(actor=self.owner, token=review["token"])
        review = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        Company.all_objects.filter(pk=self.ws.pk).update(name="Changed business")
        with self.assertRaises(ValidationError):
            confirm_setup(actor=self.owner, token=review["token"])

    def test_optout_invalidates_saved_preview_without_mutating_source(self):
        self.paired()
        row = self.setup()
        old = row.source_fingerprint
        self.post_payload(self.payload("STOP"))
        rendered = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        self.assertFalse(rendered["eligible"])
        self.assertFalse(rendered["can_send"])
        with workspace_context(self.ws.pk):
            self.assertEqual(Delivery.objects.get(pk=row.pk).source_fingerprint, old)
            self.assertEqual(SetupRequest.objects.count(), 1)

    def test_consent_off_then_on_does_not_revive_old_intent(self):
        contact = self.paired()
        row = self.setup()
        self.consent(contact, setup=False)
        self.consent(contact, setup=True)
        rendered = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        self.assertIn("contact_or_consent_changed", rendered["blockers"])

    def test_trial_conversion_or_changed_end_invalidates_preview(self):
        self.paired()
        sub = self.start()
        row = self.rows()[0]
        self.assertTrue(preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)["eligible"])
        Subscription.objects.filter(pk=sub.pk).update(trial_end_date=sub.trial_end_date+timedelta(days=1))
        result = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        self.assertIn("trial_no_longer_current", result["blockers"])
        Subscription.objects.filter(pk=sub.pk).update(status="active")
        self.assertFalse(preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)["eligible"])
        Subscription.objects.filter(pk=sub.pk).update(status="trial", trial_end_date=sub.trial_end_date, company=self.foreign)
        changed_scope = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        self.assertIn("trial_no_longer_current", changed_scope["blockers"])

    def test_changed_trial_source_is_detected_and_not_rendered_as_new_confirmation(self):
        self.paired()
        self.start()
        row = self.rows()[0]
        event = row.trial_event
        SubscriptionEvent.objects.filter(pk=event.pk).update(payload={**event.payload, "plan_id": self.plan.pk+1})
        result = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        self.assertIn("source_evidence_changed", result["blockers"])
        self.assertIn("source changed", result["body"])

    def test_owner_transfer_denies_old_owner_and_does_not_disclose_old_recipient_to_new(self):
        self.paired()
        row = self.setup()
        Membership.objects.create(user=self.other, company=self.ws, role=self.member_role)
        from apps.orgs.services.control_plane import transfer_workspace_ownership
        transfer_workspace_ownership(workspace=self.ws, new_owner=self.other, actor=self.owner,
            previous_owner_role=self.member_role, reason="Fictional transfer")
        with self.assertRaises(PermissionDenied):
            preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        with self.assertRaises(Delivery.DoesNotExist):
            preview_delivery(actor=self.other, workspace_slug=self.ws.slug, delivery_id=row.pk)

    def test_source_intents_are_immutable_under_restricted_role(self):
        self.paired()
        row = self.setup()
        with workspace_context(self.ws.pk):
            for mutation in (
                lambda: Delivery.objects.filter(pk=row.pk).update(capture_only=False),
                lambda: Delivery.objects.filter(pk=row.pk).update(recipient_phone="+919876543211"),
                lambda: Delivery.objects.filter(pk=row.pk).delete(),
                lambda: SetupRequest.objects.filter(pk=row.setup_request_id).update(contact_revision=99),
                lambda: SetupRequest.objects.filter(pk=row.setup_request_id).delete(),
            ):
                with self.subTest(mutation=mutation), self.assertRaises(DatabaseError), transaction.atomic():
                    mutation()

    def test_new_tables_have_forced_rls_and_foreign_source_links_fail(self):
        self.paired()
        row = self.setup()
        self.assertFalse(Delivery.objects.exists())
        self.assertFalse(SetupRequest.objects.exists())
        values = {f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields if not f.primary_key}
        values["workspace_id"] = self.foreign.pk
        with workspace_context(self.foreign.pk):
            self.assertFalse(Delivery.objects.filter(pk=row.pk).exists())
            with self.assertRaises(DatabaseError), transaction.atomic():
                Delivery.objects.bulk_create([Delivery(**values)])
        with connection.cursor() as c:
            c.execute("SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class WHERE relname IN (%s,%s)",
                      ("platform_whatsapp_delivery", "platform_whatsapp_setuprequest"))
            self.assertTrue(c.fetchone()[0])

    def test_global_trial_source_cannot_be_attached_to_another_workspace(self):
        self.paired()
        self.start()
        row = self.rows()[0]
        foreign_sub = Subscription.objects.create(company=self.foreign, plan=self.plan,
            status="trial", trial_end_date=timezone.now()+timedelta(days=30))
        foreign_event = SubscriptionEvent.objects.create(subscription=foreign_sub,
            event_type="trial.started", payload={"plan_id": self.plan.pk,
                "trial_end_date": foreign_sub.trial_end_date.isoformat()})
        values = {f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields if not f.primary_key}
        values.update(trial_event_id=foreign_event.pk, source_recorded_at=foreign_event.created_at)
        with workspace_context(self.ws.pk), self.assertRaisesMessage(DatabaseError,
                "Delivery source must match"), transaction.atomic():
            Delivery.objects.bulk_create([Delivery(**values)])

    def test_canonical_origin_missing_blocks_delivery_but_keeps_preview_relative(self):
        self.paired()
        row = self.setup()
        for origin in ("", "http://example.test", "https://example.test:invalid",
                       "https://example.test:0", "https://user:pass@example.test",
                       "https://example.test/path", "https://example.test?query=1"):
            with self.subTest(origin=origin), override_settings(PLATFORM_WHATSAPP_BASE_URL=origin):
                result = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
                self.assertIn("canonical_https_origin_unavailable", result["blockers"])
                self.assertTrue(result["link"].startswith("/w/"))
                self.assertFalse(result["can_send"])

    def test_setup_confirmation_ui_and_saved_message_review_are_explicit_posts(self):
        self.paired()
        response = self.client.post(self.url, {"action": "review_setup", "workspace_slug": self.ws.slug})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.rows())
        token = response.context["setup_review"]["token"]
        response = self.client.post(self.url, {"action": "confirm_setup", "token": token})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saved preview only")
        row = self.rows()[0]
        response = self.client.post(self.url, {"action": "delivery_preview",
            "workspace_slug": self.ws.slug, "delivery_id": row.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, row.recipient_phone)
        self.assertFalse(response.context["preview"]["can_send"])


class PaidFixture(EnrollmentFixture):
    def setUp(self):
        EnrollmentFixture.setUp(self)
        self.owner.email = "paid-owner@example.test"
        self.owner.save(update_fields=["email"])
        self.workspace = self.ws
        self.plan = Plan.objects.create(name="PW02 checkout", tier="starter", price=Decimal("100.01"))
        self.order_mock = patch("apps.subscriptions.razorpay_service.RazorpayService.create_order",
            side_effect=lambda **kw: {"id": "order_"+kw["receipt"], "amount": kw["amount"], "currency": kw["currency"]}).start()
        self.addCleanup(patch.stopall)

    order = checkout_tests.CheckoutTests.order
    payment = checkout_tests.CheckoutTests.payment
    confirm = checkout_tests.CheckoutTests.confirm

    def row(self):
        with workspace_context(self.ws.pk):
            return Delivery.objects.get()


@override_settings(**INBOUND, STORAGES=STORAGE, RAZORPAY_KEY_SECRET="test-secret")
class PaidIntentTests(PaidFixture, TestCase):
    def test_checkout_records_whatsapp_and_email_once_in_same_capture(self):
        self.paired()
        invoice = self.order()
        self.confirm(invoice)
        self.confirm(invoice)
        self.assertEqual(self.row().invoice_id, invoice.pk)
        self.assertEqual(EmailDelivery.objects.filter(invoice=invoice).count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

    def test_paid_capture_source_and_both_channels_roll_back_together(self):
        self.paired()
        invoice = self.order()
        with self.assertRaises(RuntimeError), transaction.atomic():
            self.confirm(invoice)
            raise RuntimeError("abort source")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "issued")
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(EmailDelivery.objects.exists())
        with workspace_context(self.ws.pk):
            self.assertFalse(Delivery.objects.exists())

    def test_local_whatsapp_write_failure_rolls_back_capture_without_provider_send(self):
        self.paired()
        invoice = self.order()
        with patch("apps.platform_whatsapp.intents._capture", side_effect=RuntimeError("local intent failure")):
            with self.assertRaises(RuntimeError):
                self.confirm(invoice)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "issued")
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(EmailDelivery.objects.exists())

    def test_authorized_or_failed_payment_does_not_create_receipts(self):
        self.paired()
        invoice = self.order()
        for status in ("authorized", "failed"):
            with self.assertRaises(ValidationError):
                self.confirm(invoice, status=status)
        self.assertFalse(EmailDelivery.objects.exists())
        with workspace_context(self.ws.pk):
            self.assertFalse(Delivery.objects.exists())

    def test_late_enrollment_and_email_retry_cannot_backfill_old_paid_intent(self):
        invoice = self.order()
        self.confirm(invoice)
        self.paired()
        send_checkout_receipt(invoice.pk)
        with transaction.atomic():
            self.assertIsNone(_capture_paid_invoice(invoice))
        with workspace_context(self.ws.pk):
            self.assertFalse(Delivery.objects.exists())
        self.assertEqual(EmailDelivery.objects.count(), 1)

    def test_email_receipt_call_without_new_capture_flag_does_not_generate_whatsapp(self):
        self.paired()
        invoice = self.order()
        with patch("apps.platform_whatsapp.intents._capture_paid_invoice") as capture:
            send_checkout_receipt(invoice.pk)
        capture.assert_not_called()

    def test_test_mode_receipt_is_labeled_and_not_access_activation(self):
        self.paired()
        invoice = self.order()
        self.confirm(invoice)
        row = self.row()
        result = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        self.assertTrue(result["body"].startswith("[TEST]"))
        self.assertIn("118.01", result["body"])
        self.assertNotIn("activated", result["body"])
        self.assertFalse(result["can_send"])

    def test_expiry_and_saved_provider_mode_cannot_be_changed(self):
        self.paired()
        self.confirm(self.order())
        row = self.row()
        with patch("apps.platform_whatsapp.intents.timezone.now", return_value=row.expires_at):
            result = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        self.assertIn("preview_expired", result["blockers"])
        with workspace_context(self.ws.pk), self.assertRaises(DatabaseError), transaction.atomic():
            Delivery.objects.filter(pk=row.pk).update(provider_mode="live")

    def test_unknown_provider_evidence_does_not_get_reclassified_as_live(self):
        self.paired()
        invoice = self.order()
        # The normal source always freezes mode. Exercise legacy/unclassified evidence separately.
        with patch("apps.platform_whatsapp.intents.invoice_mode", return_value=None):
            self.confirm(invoice)
        with workspace_context(self.ws.pk):
            self.assertFalse(Delivery.objects.exists())
        self.assertEqual(EmailDelivery.objects.count(), 1)

    def test_global_paid_source_cannot_be_attached_to_another_workspace(self):
        self.paired()
        self.confirm(self.order())
        row = self.row()
        owner, workspace = self.owner, self.workspace
        try:
            self.owner, self.workspace = self.other, self.foreign
            foreign_invoice = self.order()
            from apps.subscriptions.checkout import _apply_capture
            _apply_capture(invoice_id=foreign_invoice.pk,
                payment=self.payment(foreign_invoice, id="pay_foreign_source"))
        finally:
            self.owner, self.workspace = owner, workspace
        payment = Payment.objects.get(invoice=foreign_invoice)
        values = {f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields if not f.primary_key}
        values.update(invoice_id=foreign_invoice.pk, source_recorded_at=payment.created_at)
        with workspace_context(self.ws.pk), self.assertRaisesMessage(DatabaseError,
                "Delivery source must match"), transaction.atomic():
            Delivery.objects.bulk_create([Delivery(**values)])

    def test_paid_source_replay_uses_existing_intent(self):
        self.paired()
        invoice = self.order()
        self.confirm(invoice)
        first = self.row()
        with transaction.atomic():
            self.assertEqual(_capture_paid_invoice(invoice).pk, first.pk)
        self.assertEqual(self.row().pk, first.pk)


@override_settings(**INBOUND, STORAGES=STORAGE, RAZORPAY_KEY_ID="rzp_test_fixture",
                   RAZORPAY_KEY_SECRET="fixture", BILLING_TAX_RATE="18")
class RecurringIntentTests(CycleFixture, EnrollmentFixture, TestCase):
    def setUp(self):
        # Keep the established recurring price/period fixture, with restricted-role DML.
        role = connection.ops.quote_name("pw02_cycle_"+uuid.uuid4().hex)
        with connection.cursor() as c:
            c.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            c.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            c.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            c.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            c.execute(f"SET LOCAL ROLE {role}")
        CycleFixture.setUp(self)
        self.ws = self.workspace
        from django.urls import reverse
        self.callback = reverse("platform_whatsapp_webhook")
        self.client.force_login(self.owner)
        self.paired()

    def record(self, suffix="two"):
        from apps.subscriptions.recurring_cycles import record_paid_cycle
        return record_paid_cycle(agreement_id=self.agreement.pk, provider_invoice_id="inv_"+suffix)

    def test_recurring_capture_and_replay_preserve_period_and_both_receipts(self):
        cycle = self.record()
        sub = Subscription.objects.get(company=self.ws)
        original = (sub.status, sub.end_date, sub.updated_at)
        self.record()
        sub.refresh_from_db()
        self.assertEqual((sub.status, sub.end_date, sub.updated_at), original)
        with workspace_context(self.ws.pk):
            row = Delivery.objects.get()
            self.assertEqual(row.invoice_id, cycle.invoice_id)
        self.assertEqual(EmailDelivery.objects.count(), 1)

    def test_future_paid_cycle_preview_confirms_money_without_claiming_access(self):
        self.add_cycle("two", self.now+timedelta(days=1), self.now+timedelta(days=31))
        cycle = self.record()
        self.assertEqual(cycle.access_action, "review")
        with workspace_context(self.ws.pk):
            row = Delivery.objects.get()
        result = preview_delivery(actor=self.owner, workspace_slug=self.ws.slug, delivery_id=row.pk)
        self.assertIn("recorded payment", result["body"])
        self.assertNotIn("activated", result["body"])
        self.assertEqual(Subscription.objects.get(company=self.ws).status, "past_due")
        self.assertFalse(result["can_send"])

    def test_recurring_intent_failure_uses_existing_atomic_recovery(self):
        with patch("apps.platform_whatsapp.intents._capture", side_effect=RuntimeError("local persistence failure")):
            with self.assertRaises(RuntimeError):
                self.record()
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(EmailDelivery.objects.exists())
        with workspace_context(self.ws.pk):
            self.assertFalse(Delivery.objects.exists())


@override_settings(**INBOUND, STORAGES=STORAGE, RAZORPAY_KEY_SECRET="test-secret")
class ConcurrentIntentTests(PaidFixture, TransactionTestCase):
    def setUp(self):
        with transaction.atomic():
            PaidFixture.setUp(self)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_user")
                self.runtime_role = cursor.fetchone()[0]
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE " + connection.ops.quote_name(self.runtime_role))
        self.paired()

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            role = connection.ops.quote_name(self.runtime_role)
            cursor.execute("DROP OWNED BY " + role)
            cursor.execute("DROP ROLE " + role)
        super().tearDown()

    def concurrent(self, operation):
        barrier = Barrier(2)
        def execute(_):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET ROLE " + connection.ops.quote_name(self.runtime_role))
                barrier.wait(timeout=15)
                return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(execute, range(2)))

    def test_simultaneous_setup_confirmations_share_one_request_and_intent(self):
        review = review_setup(actor=self.owner, workspace_slug=self.ws.slug)
        results = self.concurrent(lambda: confirm_setup(actor=self.owner, token=review["token"]).pk)
        self.assertEqual(results[0], results[1])
        with workspace_context(self.ws.pk):
            self.assertEqual(SetupRequest.objects.count(), 1)
            self.assertEqual(Delivery.objects.count(), 1)
        self.assertFalse(EmailDelivery.objects.exists())

    def test_simultaneous_paid_callbacks_record_one_payment_and_both_receipts(self):
        from apps.subscriptions.checkout import _apply_capture
        invoice = self.order()
        payment = self.payment(invoice)
        results = self.concurrent(lambda: _apply_capture(invoice_id=invoice.pk, payment=payment).pk)
        self.assertEqual(results, [invoice.pk, invoice.pk])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(EmailDelivery.objects.filter(invoice=invoice).count(), 1)
        self.assertEqual(self.row().invoice_id, invoice.pk)
