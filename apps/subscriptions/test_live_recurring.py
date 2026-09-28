"""Live-mode boundaries using fictional identities and mocked provider responses only."""
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.platform_mail.models import Delivery
from apps.platform_mail.services import dispatch_one, render_delivery
from apps.platform_mail.tests import MAIL_SETTINGS
from apps.tenancy.context import workspace_context
from . import recurring, recurring_owner as owner_actions
from . import test_recurring as creation_tests, test_recurring_owner as owner_tests
from . import test_recurring_cycles as cycle_tests, test_recurring_access as access_tests
from . import test_recurring_refunds as refund_tests
from .models import (Invoice, Payment, Plan, ProviderWebhookEvent, RecurringAgreement,
                     RecurringPlanBinding, Subscription)
from .razorpay_service import BillingProviderError, RazorpayService
from .recovery import process_refund_webhook
from .recurring_release import release_refunded_agreement


LIVE_SETTINGS = dict(BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture",
    RAZORPAY_KEY_SECRET="fixture", RAZORPAY_WEBHOOK_SECRET="webhook-fixture",
    BILLING_RECURRING_ENABLED=False, BILLING_CHECKOUT_ENABLED=False,
    BILLING_ALLOW_TRIAL_START=False, BILLING_TAX_RATE="18",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})


@override_settings(**{**LIVE_SETTINGS, "BILLING_RECURRING_ENABLED": True, "BILLING_TAX_RATE": "0",
    "BILLING_SELLER_NAME": "Fictional Seller", "BILLING_SELLER_ADDRESS": "1 Example Street",
    "BILLING_SELLER_TAX_STATUS": "unregistered"})
class LiveCreationTests(TransactionTestCase):
    expected_amount = 149900
    created_entity = creation_tests.RecurringAgreementTests.created_entity
    create = creation_tests.RecurringAgreementTests.create
    reconcile = creation_tests.RecurringAgreementTests.reconcile
    assert_no_access_granted = creation_tests.RecurringAgreementTests.assert_no_access_granted

    def setUp(self):
        with transaction.atomic():
            self.owner = get_user_model().objects.create_user(username="live-fixture-owner")
            self.admin = get_user_model().objects.create_user(username="live-fixture-admin", is_superuser=True)
            self.workspace = Company.all_objects.create(name="Fictional Workspace", schema_name="live_fixture",
                owner=self.owner, creator=self.owner)
            Membership.objects.create(company=self.workspace, user=self.owner,
                role=Role.objects.get_or_create(name="Owner")[0])
            self.plan = Plan.objects.create(name="Fictional offer", tier="starter", price="1499.00",
                yearly_price="14990.00", max_users=6, trial_days=0)
            self.plan.refresh_from_db()
        self.provider_plan = {"id": "plan_fixture", "entity": "plan", "period": "monthly", "interval": 1,
                              "item": {"amount": 149900, "currency": "INR"}}
        self.plan_read = patch.object(RazorpayService, "get_plan", side_effect=lambda _: deepcopy(self.provider_plan)).start()
        self.provider_create = patch.object(RazorpayService, "create_subscription", side_effect=self.created_entity).start()
        self.addCleanup(patch.stopall)
        with override_settings(BILLING_RECURRING_ENABLED=False):
            self.binding = recurring.bind_plan(actor=self.admin, plan_id=self.plan.pk, cycle="monthly",
                provider_plan_id="plan_fixture", reason="Mocked live offer", mode="live")
        self.plan_read.reset_mock()
        self.key = uuid4()

    test_committed_creation_replay_freezes_six_seats_without_access = (
        creation_tests.RecurringAgreementTests.test_verified_creation_replay_freezes_six_seats_and_grants_nothing)
    test_failed_local_commit_preserves_original_provider_attempt = (
        creation_tests.RecurringAgreementTests.test_persistence_failure_after_provider_success_leaves_durable_reservation)

    def test_timeout_recovery_works_while_new_authorizations_are_paused(self):
        self.provider_create.side_effect = BillingProviderError("Mocked timeout")
        with self.assertRaises(BillingProviderError):
            self.create()
        agreement = RecurringAgreement.objects.get(request_key=self.key)
        self.assertEqual(agreement.state, "unknown")
        with override_settings(BILLING_RECURRING_ENABLED=False):
            with self.assertRaises(PermissionDenied):
                self.create()
            self.assertEqual(self.reconcile(agreement).state, "verified")
        self.provider_create.assert_called_once()
        self.assert_no_access_granted()

    def test_live_schedule_and_configuration_reject_before_reserving_or_provider_calls(self):
        with self.assertRaisesMessage(ValidationError, "Scheduled live starts"):
            self.create(start_at=1900000000)
        for settings in ({"BILLING_RECURRING_ENABLED": False}, {"RAZORPAY_WEBHOOK_SECRET": ""},
                         {"BILLING_PROVIDER_MODE": "disabled"}, {"RAZORPAY_KEY_ID": "rzp_test_fixture"}):
            with self.subTest(settings=settings), override_settings(**settings), self.assertRaises(PermissionDenied):
                self.create()
        with override_settings(BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture"), \
                self.assertRaisesMessage(ValidationError, "another mode"):
            self.create()
        self.plan_read.assert_not_called()
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_test_evidence_blocks_new_creation_without_disabling_live_recovery(self):
        agreement = self.create()
        RecurringPlanBinding.objects.create(plan=self.plan, mode="test", provider_plan_id="plan_testfixture",
            snapshot=self.binding.snapshot, actor=self.admin, reason="Contamination fixture")
        with self.assertRaisesMessage(ValidationError, "another provider mode"):
            self.create(request_key=uuid4())
        self.assertEqual(self.reconcile(agreement).state, "verified")
        self.provider_create.assert_called_once()

    def test_unclassified_invoice_blocks_new_creation(self):
        subscription = Subscription.objects.create(company=self.workspace, plan=self.plan)
        Invoice.objects.create(subscription=subscription, invoice_number="unclassified", base_amount=1,
            gst_rate=0, invoice_date=subscription.start_date.date(), due_date=subscription.end_date.date())
        with self.assertRaisesMessage(ValidationError, "no verified mode"):
            self.create()
        self.plan_read.assert_not_called()
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_live_reservation_release_remains_unavailable(self):
        agreement = self.create()
        with self.assertRaises(PermissionDenied):
            release_refunded_agreement(workspace_id=self.workspace.pk, actor=self.owner,
                agreement_id=agreement.pk, revision="unused", reason="Mocked review")
        agreement.refresh_from_db()
        self.assertIsNone(agreement.closed_at)


@override_settings(**LIVE_SETTINGS)
class LiveOwnerAndCycleTests(owner_tests.OwnerFixture, TestCase):
    provider_mode = "live"
    annual_agreement = cycle_tests.RecurringCycleTests.annual_agreement
    test_annual_capture_uses_frozen_offer_and_holds_future_period = (
        cycle_tests.RecurringCycleTests.test_annual_provider_period_and_frozen_offer_ignore_later_catalog_prices)
    test_annual_midnight_boundary_recovery_preserves_exact_paid_dates = (
        cycle_tests.RecurringCycleTests.test_actual_annual_midnight_boundary_recovers_once_with_exact_paid_dates)
    test_callback_uses_server_identity_and_grants_no_access = (
        owner_tests.RecurringOwnerTests.test_callback_binds_signature_to_server_agreement_and_grants_nothing)
    test_pause_preserves_confirmation_refresh_and_cancel_request = (
        owner_tests.RecurringOwnerTests.test_pause_blocks_checkout_but_not_confirmation_refresh_or_cancellation)
    test_verified_cycles_preserve_exact_dates_and_queue_once = (
        cycle_tests.RecurringCycleTests.test_initial_and_renewal_record_exact_periods_and_one_receipt_each)
    test_signed_webhooks_and_capture_replays_apply_once = (
        cycle_tests.RecurringCycleTests.test_signed_webhook_replay_and_capture_with_new_event_id_are_idempotent)
    test_failed_collection_keeps_paid_access = (
        owner_tests.RecurringOwnerTests.test_collection_attention_guidance_uses_verified_status_and_preserves_access)
    test_future_recovery_keeps_access_held = (
        owner_tests.RecurringOwnerTests.test_future_recovery_displays_held_payment_without_promising_activation)

    @override_settings(BILLING_RECURRING_ENABLED=True)
    def test_historical_live_offer_without_seller_cannot_start_new_authorization(self):
        self.provider_agreement["status"] = "created"
        with workspace_context(self.workspace.pk), self.assertRaises(ValidationError):
            owner_actions.authorization_options(**self.args())
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:recurring", kwargs={"workspace_slug": self.workspace.slug})
        page = self.client.get(url)
        self.assertNotContains(page, 'id="recurring-authorize"')
        self.assertNotContains(page, "Test Mode")
        with override_settings(BILLING_RECURRING_ENABLED=False):
            self.assertNotContains(self.client.get(url), 'id="recurring-authorize"')

    def test_wrong_configured_mode_cannot_read_or_mutate_saved_live_agreement(self):
        with override_settings(BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture"), \
                patch.object(RazorpayService, "get_subscription") as subscription, \
                patch.object(RazorpayService, "get_invoice") as invoice:
            with workspace_context(self.workspace.pk):
                for action in (owner_actions.refresh_agreement, owner_actions.request_cancellation):
                    with self.assertRaises(ValidationError):
                        action(**self.args())
                with self.assertRaises(ValidationError):
                    self.record()
            subscription.assert_not_called()
            invoice.assert_not_called()
        self.assertFalse(Invoice.objects.exists())

    def test_forged_webhook_stores_nothing_and_matching_signature_still_checks_mode(self):
        self.assertEqual(self.webhook(signature="forged").status_code, 400)
        self.assertFalse(ProviderWebhookEvent.objects.exists())
        with override_settings(BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture"):
            self.assertEqual(self.webhook().status_code, 500)
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(ProviderWebhookEvent.objects.get().status, "failed")
        self.assertEqual(self.webhook().status_code, 200)
        self.assertEqual(Payment.objects.count(), 1)

    @override_settings(**MAIL_SETTINGS)
    def test_live_receipt_renders_saved_live_mode_and_dispatches_once_to_mock_transport(self):
        cycle = self.record()
        row = Delivery.objects.get(invoice=cycle.invoice)
        message = render_delivery(row)
        self.assertFalse(message["subject"].startswith("[TEST]"))
        self.assertNotIn("No real money was charged", message["text"])
        self.assertIn("1768.82", message["text"])
        with patch("apps.platform_mail.transport.send_ses", return_value="fictional-message") as send:
            self.assertEqual(dispatch_one(row.pk), "accepted")
            self.assertEqual(dispatch_one(row.pk), "accepted")
            send.assert_called_once()


@override_settings(**LIVE_SETTINGS)
class LiveCancellationTests(owner_tests.OwnerFixture, TransactionTestCase):
    provider_mode = "live"
    cancel_at_provider = owner_tests.CancellationDeliveryTests.cancel_at_provider
    test_committed_cancel_posts_once_and_preserves_paid_dates = (
        owner_tests.CancellationDeliveryTests.test_committed_delivery_confirms_once_preserves_access_and_reservation)
    test_unknown_cancel_uses_get_only_recovery = (
        owner_tests.CancellationDeliveryTests.test_timeout_is_unknown_and_recovery_fetches_without_repost)
    test_identity_conflict_never_cancels_another_mandate = (
        owner_tests.CancellationDeliveryTests.test_invalid_remote_identity_cannot_cancel_another_agreement)


@override_settings(**LIVE_SETTINGS)
class LiveHeldAccessTests(access_tests.HeldFixture, TestCase):
    provider_mode = "live"
    test_due_review_applies_once_without_rewriting_payment_evidence = (
        access_tests.HeldAccessTests.test_due_application_is_exact_audited_and_idempotent_after_refund_or_cancellation)
    test_future_expired_or_stale_review_cannot_change_access = (
        access_tests.HeldAccessTests.test_future_expired_and_stale_revision_leave_everything_unchanged)
    test_refunded_or_mismatched_provider_facts_block_application = (
        access_tests.HeldAccessTests.test_provider_refunds_identity_changes_and_outage_fail_closed)


@override_settings(**LIVE_SETTINGS)
class LiveRefundReviewTests(cycle_tests.CycleFixture, TestCase):
    provider_mode = "live"
    decide = refund_tests.RecurringRefundReviewTests.decide

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

    test_full_refund_review_ends_access_once_without_releasing_mandate = (
        refund_tests.RecurringRefundReviewTests.test_exact_current_refund_ends_access_once_preserves_dates_and_reservation)
    test_active_mandate_or_stale_revision_blocks_access_end = (
        refund_tests.RecurringRefundReviewTests.test_active_collection_and_stale_revision_block_access_end)
    test_partial_or_unverified_refunds_cannot_resolve_access = (
        refund_tests.RecurringRefundReviewTests.test_partial_mismatched_or_unverified_refunds_cannot_decide)
