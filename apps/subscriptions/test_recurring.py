from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from . import recurring
from .checkout import create_checkout
from .models import (Invoice, Payment, Plan, RecurringAgreement, RecurringAgreementEvent,
                     RecurringPlanBinding, Subscription, SubscriptionEntitlement)
from .razorpay_service import BillingProviderError, RazorpayService


@override_settings(BILLING_RECURRING_ENABLED=True, RAZORPAY_KEY_ID="rzp_test_fixture",
                   RAZORPAY_KEY_SECRET="fixture", BILLING_TAX_RATE="18")
class RecurringAgreementTests(TransactionTestCase):
    def setUp(self):
        with transaction.atomic():
            self.owner = get_user_model().objects.create_user(username="recurring-owner")
            self.admin = get_user_model().objects.create_user(username="recurring-admin", is_superuser=True)
            self.outsider = get_user_model().objects.create_user(username="recurring-outsider")
            self.workspace = Company.all_objects.create(name="Recurring", schema_name="recurring",
                owner=self.owner, creator=self.owner)
            role, _ = Role.objects.get_or_create(name="Owner")
            Membership.objects.create(company=self.workspace, user=self.owner, role=role)
            self.plan = Plan.objects.create(name="Recurring TEST", tier="starter", price=Decimal("1499"),
                yearly_price=Decimal("14990"), max_users=6, description="Test", trial_days=0)
        self.provider_plan = {"id": "plan_fixture", "entity": "plan", "period": "monthly", "interval": 1,
                              "item": {"amount": 176882, "currency": "INR"}}
        self.plan_read = patch.object(RazorpayService, "get_plan", side_effect=lambda _: deepcopy(self.provider_plan)).start()
        self.provider_create = patch.object(RazorpayService, "create_subscription", side_effect=self.created_entity).start()
        self.addCleanup(patch.stopall)
        self.binding = recurring.bind_plan(actor=self.admin, plan_id=self.plan.pk, cycle="monthly",
            provider_plan_id="plan_fixture", reason="Isolated test offer")
        self.key = uuid4()

    def created_entity(self, payload):
        # This read would see nothing if the durable attempt was rolled back/not saved.
        self.assertFalse(connection.in_atomic_block)
        self.assertTrue(RecurringAgreement.objects.filter(request_key=payload["notes"]["rokkad_attempt"]).exists())
        return {**deepcopy(payload), "id": "sub_fixture", "entity": "subscription", "status": "created",
                "has_scheduled_changes": False}

    def create(self, **changes):
        args = dict(workspace_id=self.workspace.pk, actor=self.owner, binding_id=self.binding.pk,
                    total_count=12, request_key=self.key)
        args.update(changes)
        return recurring.create_agreement(**args)

    def reconcile(self, agreement, entity=None, **changes):
        entity = entity or {**agreement.request_snapshot, "id": "sub_fixture", "entity": "subscription",
                            "status": "active", "has_scheduled_changes": False}
        args = dict(workspace_id=self.workspace.pk, actor=self.owner, agreement_id=agreement.pk,
                    provider_subscription_id="sub_fixture", reason="Locate uncertain attempt in provider")
        args.update(changes)
        with patch.object(RazorpayService, "get_subscription", return_value=entity):
            return recurring.reconcile_agreement(**args)

    def assert_no_access_granted(self):
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(SubscriptionEntitlement.objects.exists())
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_verified_creation_replay_freezes_six_seats_and_grants_nothing(self):
        agreement = self.create()
        self.assertEqual(self.create().pk, agreement.pk)
        self.provider_create.assert_called_once()
        self.assertEqual(agreement.state, "verified")
        self.assertEqual(self.binding.snapshot["amount"], getattr(self, "expected_amount", 176882))
        seats = next(x for x in self.binding.snapshot["entitlements"] if x["feature_code"] == "workspace.max_members")
        self.assertEqual(seats["value"], "6")
        self.assert_no_access_granted()
        with self.assertRaises(ValidationError):
            self.create(total_count=24)
        with self.assertRaises(ValidationError):
            self.create(request_key=uuid4())

    def test_timeout_preserves_attempt_blocks_repost_and_recovers_original(self):
        self.provider_create.side_effect = BillingProviderError("Simulated timeout")
        with self.assertRaises(BillingProviderError):
            self.create()
        agreement = RecurringAgreement.objects.get(request_key=self.key)
        self.assertEqual(agreement.state, "unknown")
        with self.assertRaises(ValidationError):
            self.create()
        with self.assertRaises(ValidationError):
            self.create(request_key=uuid4())
        with workspace_context(self.workspace.pk), self.assertRaises(ValidationError):
            create_checkout(workspace=self.workspace, actor=self.owner, plan_id=self.plan.pk,
                billing_cycle="monthly", request_key=uuid4())
        self.assertEqual(self.reconcile(agreement).state, "verified")
        self.assertEqual(self.create().pk, agreement.pk)
        self.provider_create.assert_called_once()
        self.assert_no_access_granted()

    def test_scheduled_attempt_freezes_date_and_replays_after_start_without_reposting(self):
        start = int(timezone.now().timestamp()) + 1800
        agreement = self.create(start_at=start)
        self.assertEqual(agreement.request_snapshot["start_at"], start)
        self.assertEqual(self.provider_create.call_args.args[0]["start_at"], start)
        for changed in (None, start+1):
            with self.assertRaises(ValidationError):
                self.create(start_at=changed)
        with patch.object(recurring.timezone, "now", return_value=timezone.now()+timedelta(hours=1)):
            self.assertEqual(self.create(start_at=start).pk, agreement.pk)
        self.provider_create.assert_called_once()
        self.assert_no_access_granted()

    def test_invalid_schedule_never_reserves_or_calls_provider(self):
        now = int(timezone.now().timestamp())
        for start in (True, False, "1800000000", 1.5, 0, -1, now, now-60, 10**30):
            with self.subTest(start=start), self.assertRaises(ValidationError):
                self.create(start_at=start)
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_provider_schedule_mismatch_preserves_attempt_and_requires_exact_recovery(self):
        start = int(timezone.now().timestamp()) + 1800
        original = self.created_entity
        self.provider_create.side_effect = lambda payload: {**original(payload), "start_at": start+1}
        with self.assertRaisesMessage(ValidationError, "scheduled start"):
            self.create(start_at=start)
        agreement = RecurringAgreement.objects.get()
        self.assertEqual(agreement.state, "unknown")
        with self.assertRaises(ValidationError):
            self.create(start_at=start)
        good = {**agreement.request_snapshot, "id": "sub_fixture", "entity": "subscription",
                "status": "authenticated", "has_scheduled_changes": False}
        for value in (None, str(start), True, start-1, start+1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.reconcile(agreement, {**good, "start_at": value})
        self.assertEqual(self.reconcile(agreement, good).state, "verified")
        self.provider_create.assert_called_once()
        self.assert_no_access_granted()

    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                                 "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_scheduled_owner_page_and_expired_authorization_preserve_access(self):
        from . import recurring_owner
        start = int(timezone.now().timestamp()) + 1800
        agreement = self.create(start_at=start)
        provider = {**agreement.request_snapshot, "id": "sub_fixture", "entity": "subscription",
                    "status": "created", "has_scheduled_changes": False}
        self.client.force_login(self.owner)
        url = reverse("workspace_subscriptions:recurring", kwargs={"workspace_slug": self.workspace.slug})
        response = self.client.get(url)
        self.assertContains(response, "Scheduled billing start:")
        self.assertContains(response, "refundable token payment")
        self.assertNotContains(response, "Payments start on authorization")
        self.assertContains(response, 'id="recurring-authorize"')
        with patch.object(RazorpayService, "get_subscription", return_value=provider):
            options = recurring_owner.authorization_options(workspace=self.workspace, actor=self.owner,
                                                             agreement_id=agreement.pk)
            self.assertEqual(options["subscription_id"], "sub_fixture")
            with patch.object(recurring.timezone, "now", return_value=timezone.now()+timedelta(hours=1)):
                with self.assertRaisesMessage(ValidationError, "scheduled start has passed"):
                    recurring_owner.authorization_options(workspace=self.workspace, actor=self.owner,
                                                          agreement_id=agreement.pk)
                response = self.client.get(url)
                self.assertContains(response, "scheduled start has passed")
                self.assertNotContains(response, 'id="recurring-authorize"')
        self.assert_no_access_granted()

    def test_scheduled_cycle_cannot_precede_frozen_start_and_future_capture_is_held(self):
        from .recurring_cycles import record_paid_cycle
        start = int(timezone.now().timestamp()) + 1800
        agreement = self.create(start_at=start)
        provider = {**agreement.request_snapshot, "id": "sub_fixture", "entity": "subscription",
                    "status": "active", "has_scheduled_changes": False}
        invoice = {"id": "inv_scheduled", "entity": "invoice", "subscription_id": "sub_fixture",
            "order_id": "order_scheduled", "payment_id": "pay_scheduled", "status": "paid",
            "amount": 176882, "amount_paid": 176882, "amount_due": 0, "currency": "INR",
            "billing_start": start-1, "billing_end": start+30*86400,
            "paid_at": int(timezone.now().timestamp()),
            "line_items": [{"type": "plan", "quantity": 1, "amount": 176882, "currency": "INR"}]}
        payment = {"id": "pay_scheduled", "entity": "payment", "invoice_id": "inv_scheduled",
            "order_id": "order_scheduled", "amount": 176882, "currency": "INR", "status": "captured",
            "amount_refunded": 0, "method": "card"}
        with patch.object(RazorpayService, "get_subscription", return_value=provider), \
                patch.object(RazorpayService, "get_invoice", return_value=invoice), \
                patch.object(RazorpayService, "get_payment_status", return_value=payment):
            with self.assertRaises(ValidationError):
                record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id=invoice["id"])
            self.assert_no_access_granted()
            invoice["billing_start"] = start
            cycle = record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id=invoice["id"])
            self.assertEqual(cycle.access_action, "review")
            self.assertEqual(cycle.invoice.checkout_snapshot["access_review_reason"], "future_period")
            self.assertEqual(int(cycle.period_start.timestamp()), start)
            self.assertEqual(record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id=invoice["id"]).pk, cycle.pk)
            self.assertEqual(Payment.objects.count(), 1)

    def test_persistence_failure_after_provider_success_leaves_durable_reservation(self):
        with patch.object(recurring, "_record_provider", side_effect=DatabaseError("Local commit failure")):
            with self.assertRaises(DatabaseError):
                self.create()
        agreement = RecurringAgreement.objects.get(request_key=self.key)
        self.assertEqual(agreement.state, "creating")
        self.assertTrue(agreement.events.filter(event_type="creation.requested").exists())
        with self.assertRaises(ValidationError):
            self.create()
        self.assertEqual(self.reconcile(agreement).state, "verified")
        self.provider_create.assert_called_once()
        self.assert_no_access_granted()

    def test_malformed_provider_response_never_grants_or_loses_attempt(self):
        self.provider_create.side_effect = None
        self.provider_create.return_value = {"id": "sub_wrong"}
        with self.assertRaises(ValidationError):
            self.create()
        self.assertEqual(RecurringAgreement.objects.get().state, "unknown")
        self.assert_no_access_granted()

    def test_reconciliation_validates_every_binding_dimension_and_preserves_history(self):
        agreement = self.create()
        good = {**agreement.request_snapshot, "id": "sub_fixture", "entity": "subscription",
                "status": "active", "has_scheduled_changes": False}
        bad = [{"plan_id": "plan_other"}, {"quantity": 2}, {"quantity": True}, {"total_count": 13},
               {"notes": {"workspace_id": "999", "rokkad_attempt": str(self.key)}},
               {"notes": {"workspace_id": str(self.workspace.pk), "rokkad_attempt": str(uuid4())}},
               {"customer_notify": True}, {"has_scheduled_changes": True}, {"offer_id": "offer_other"},
               {"status": "unknown"}, {"id": "sub_other"}]
        for mutation in bad:
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                self.reconcile(agreement, {**good, **mutation})
        for item_change in [{"amount": 1}, {"currency": "USD"}]:
            with self.subTest(item_change=item_change):
                self.provider_plan["item"].update(item_change)
                with self.assertRaises(ValidationError):
                    self.reconcile(agreement, good)
                self.provider_plan["item"] = {"amount": 176882, "currency": "INR"}
        agreement.refresh_from_db()
        self.assertEqual(agreement.provider_status, "created")
        self.assertEqual(agreement.events.count(), 2)
        self.assert_no_access_granted()

    def test_provider_lifecycle_observation_does_not_shorten_paid_access_or_release_slot(self):
        agreement = self.create()
        subscription = Subscription.objects.create(company=self.workspace, plan=self.plan, status="active", auto_renew=False)
        paid_end = subscription.end_date
        for status in ["authenticated", "active", "pending", "halted", "cancelled", "completed", "expired"]:
            entity = {**agreement.request_snapshot, "id": "sub_fixture", "entity": "subscription",
                      "status": status, "has_scheduled_changes": False}
            self.reconcile(agreement, entity)
            subscription.refresh_from_db()
            self.assertEqual(subscription.end_date, paid_end)
            self.assertEqual(subscription.status, "active")
            self.assertFalse(subscription.auto_renew)
        self.assertFalse(Invoice.objects.exists())
        with self.assertRaises(ValidationError):
            self.create(request_key=uuid4())

    def test_owner_workspace_mode_and_gate_boundaries(self):
        with transaction.atomic():
            Membership.objects.create(company=self.workspace, user=self.outsider,
                role=Role.objects.get_or_create(name="Admin")[0])
        with self.assertRaises(PermissionDenied):
            self.create(actor=self.outsider)
        with self.assertRaises(PermissionDenied):
            recurring.bind_plan(actor=self.owner, plan_id=self.plan.pk, cycle="monthly",
                provider_plan_id="plan_fixture", reason="Not a platform operator")
        for overrides in [dict(BILLING_RECURRING_ENABLED=False), dict(RAZORPAY_KEY_ID="rzp_live_fixture"),
                          dict(RAZORPAY_KEY_SECRET="")]:
            with self.subTest(overrides=overrides), override_settings(**overrides), self.assertRaises(PermissionDenied):
                self.create()
        with workspace_context(self.workspace.pk), self.assertRaises(ImproperlyConfigured):
            self.create()
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())
        agreement = self.create()
        with self.assertRaises(PermissionDenied):
            self.reconcile(agreement, actor=self.outsider)
        with transaction.atomic():
            other = Company.all_objects.create(name="Other", schema_name="recurring_other", owner=self.owner, creator=self.owner)
            Membership.objects.create(company=other, user=self.owner, role=Role.objects.get(name="Owner"))
        with self.assertRaises(ValidationError):
            self.reconcile(agreement, workspace_id=other.pk)
        with self.assertRaises(ValidationError):
            self.create(workspace_id=other.pk)

    def test_stale_catalog_seats_lifecycle_and_existing_terms_block_new_agreements(self):
        for state in [Company.LifecycleState.ARCHIVED, Company.LifecycleState.SUSPENDED]:
            Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state=state)
            with self.assertRaises(ValidationError):
                self.create()
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state=Company.LifecycleState.ACTIVE)
        Plan.objects.filter(pk=self.plan.pk).update(price=Decimal("1500"))
        with self.assertRaises(ValidationError):
            self.create()
        Plan.objects.filter(pk=self.plan.pk).update(price=Decimal("1499"))
        with patch.object(recurring, "get_workspace_member_usage", return_value=7) as usage:
            with self.assertRaises(ValidationError):
                self.create()
            self.assertTrue(usage.call_args.kwargs["include_pending_invitations"])
        Subscription.objects.create(company=self.workspace, plan=self.plan, status="active")
        with self.assertRaises(ValidationError):
            self.create()
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_outstanding_manual_checkout_blocks_recurring_and_still_confirms(self):
        with workspace_context(self.workspace.pk), patch.object(RazorpayService, "create_order", return_value={
            "id": "order_fixture", "amount": 176882, "currency": "INR"}):
            invoice = create_checkout(workspace=self.workspace, actor=self.owner, plan_id=self.plan.pk,
                billing_cycle="monthly", request_key=uuid4())
        with self.assertRaises(ValidationError):
            self.create()
        from .checkout import _apply_capture
        _apply_capture(invoice_id=invoice.pk, payment={"id": "pay_fixture", "order_id": "order_fixture",
            "amount": 176882, "currency": "INR", "status": "captured"})
        self.assertEqual(Payment.objects.count(), 1)
        self.provider_create.assert_not_called()

    def test_yearly_binding_is_explicit_and_does_not_follow_catalog_changes(self):
        self.provider_plan.update(id="plan_yearly", period="yearly")
        self.provider_plan["item"]["amount"] = 1768820
        binding = recurring.bind_plan(actor=self.admin, plan_id=self.plan.pk, cycle="yearly",
            provider_plan_id="plan_yearly", reason="Annual offer")
        self.assertEqual(binding.snapshot["base_amount"], "14990.00")
        self.assertEqual(binding.snapshot["amount"], 1768820)
        self.assertEqual(binding.pk, recurring.bind_plan(actor=self.admin, plan_id=self.plan.pk, cycle="yearly",
            provider_plan_id="plan_yearly", reason="Repeat registration").pk)
        self.provider_plan["interval"] = 2
        with self.assertRaises(ValidationError):
            self.create(binding_id=binding.pk)
        self.provider_create.assert_not_called()

    def test_database_rejects_history_rewrites_deletes_and_second_open_agreement(self):
        agreement = self.create()
        operations = [
            lambda: RecurringPlanBinding.objects.filter(pk=self.binding.pk).update(snapshot={}),
            lambda: RecurringAgreement.objects.filter(pk=agreement.pk).update(request_snapshot={}),
            lambda: RecurringAgreement.objects.filter(pk=agreement.pk).update(provider_subscription_id="sub_other"),
            lambda: RecurringAgreement.objects.filter(pk=agreement.pk).update(closed_at=timezone.now()),
            lambda: RecurringAgreementEvent.objects.filter(agreement=agreement).update(detail={"forged": True}),
            lambda: RecurringAgreementEvent.objects.filter(agreement=agreement).delete(),
            lambda: RecurringAgreement.objects.create(workspace=self.workspace, binding=self.binding,
                request_key=uuid4(), request_snapshot=agreement.request_snapshot, actor=self.owner),
        ]
        for operation in operations:
            with self.subTest(operation=operation), self.assertRaises(DatabaseError), transaction.atomic():
                operation()
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("DELETE FROM subscriptions_recurringagreement WHERE id = %s", [agreement.pk])

    def test_concurrent_attempts_only_call_provider_once_after_commit(self):
        entered, finish = Event(), Event()

        def delayed_create(payload):
            result = self.created_entity(payload)
            entered.set()
            if not finish.wait(timeout=20):
                raise RuntimeError("Test synchronization timed out")
            return result

        def first():
            close_old_connections()
            try:
                return self.create().pk
            finally:
                connections.close_all()

        self.provider_create.side_effect = delayed_create
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(first)
            try:
                self.assertTrue(entered.wait(timeout=15))
                # A separate connection sees the committed intent while provider I/O is in flight.
                self.assertEqual(RecurringAgreement.objects.get().state, "creating")
                with self.assertRaises(ValidationError):
                    self.create()
                with self.assertRaises(ValidationError):
                    self.create(request_key=uuid4())
            finally:
                finish.set()
            self.assertEqual(future.result(timeout=15), RecurringAgreement.objects.get().pk)
        self.provider_create.assert_called_once()

    def test_contract_services_and_history_guards_under_restricted_runtime_role(self):
        role = connection.ops.quote_name("recurring_test_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            agreement = self.create()
            self.assertEqual(self.reconcile(agreement).state, "verified")
            with self.assertRaises(DatabaseError), transaction.atomic():
                RecurringAgreement.objects.filter(pk=agreement.pk).update(request_snapshot={})
            with self.assertRaises(PermissionDenied):
                self.reconcile(agreement, actor=self.outsider)
            self.assert_no_access_granted()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")


class RecurringTransportTests(SimpleTestCase):
    def test_provider_requests_are_bounded_and_do_not_follow_redirects_or_retry(self):
        with patch("apps.subscriptions.razorpay_service.client") as make_client:
            provider = make_client.return_value
            RazorpayService.get_plan("plan_fixture")
            provider.plan.fetch.assert_called_once_with("plan_fixture", timeout=20, allow_redirects=False)
            provider.subscription.create.side_effect = TimeoutError("Private provider detail")
            with self.assertRaisesMessage(BillingProviderError, "outcome is unknown"):
                RazorpayService.create_subscription({"quantity": 1})
            provider.subscription.create.assert_called_once_with(data={"quantity": 1}, timeout=20, allow_redirects=False)
            RazorpayService.get_subscription("sub_fixture")
            provider.subscription.fetch.assert_called_once_with("sub_fixture", timeout=20, allow_redirects=False)
