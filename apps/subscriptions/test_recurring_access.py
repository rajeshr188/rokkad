from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.template.loader import render_to_string
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.platform_mail.models import Delivery
from apps.tenancy.context import workspace_context
from .models import (Invoice, Payment, Plan, RecurringAccessResolution, RecurringAgreement,
                     RecurringCycle, Subscription, SubscriptionEntitlement, SubscriptionEvent, WorkspaceAccessDecision)
from .razorpay_service import BillingProviderError, RazorpayService
from .recurring_access import apply_held_period
from .test_recurring_cycles import CycleFixture


class HeldFixture(CycleFixture):
    def setUp(self):
        super().setUp()
        self.record("two")
        self.start = self.now + timedelta(days=15)
        self.end = self.start + timedelta(days=30)
        self.add_cycle("held", self.start, self.end)
        self.held = self.record("held")
        self.subscription = Subscription.objects.get(company=self.workspace)
        self.revision = self.subscription.updated_at.isoformat()

    def apply(self, **changes):
        args = dict(workspace=self.workspace, actor=self.owner, cycle_id=self.held.pk,
                    revision=self.revision, reason="Reviewed due paid period")
        with workspace_context(self.workspace.pk):
            return apply_held_period(**{**args, **changes})


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture",
                   BILLING_RECURRING_ENABLED=False, BILLING_TAX_RATE="18",
                   STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                             "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class HeldAccessTests(HeldFixture, TestCase):
    def test_due_application_is_exact_audited_and_idempotent_after_refund_or_cancellation(self):
        frozen = self.held.evidence.copy()
        with patch("django.utils.timezone.now", return_value=self.start):
            result = self.apply()
            self.assertEqual(self.apply().pk, result.pk)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.end_date, self.end)
        self.assertEqual(self.subscription.status, "active")
        self.assertFalse(self.subscription.auto_renew)
        self.held.refresh_from_db()
        self.assertEqual(self.held.access_action, "review")
        self.assertEqual(self.held.evidence, frozen)
        self.assertEqual(result.evidence["before"]["revision"], self.revision)
        self.assertEqual(result.actor_id, self.owner.pk)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="recurring.access_resolved").count(), 1)
        for model in (Invoice, Payment, RecurringCycle, Delivery):
            self.assertEqual(model.objects.count(), 2)
        Subscription.objects.filter(pk=self.subscription.pk).update(status="cancelled")
        self.payments["pay_held"].update(status="refunded", amount_refunded=176882)
        with patch.object(RazorpayService, "get_invoice") as remote:
            self.assertEqual(self.apply().pk, result.pk)
            remote.assert_not_called()
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, "cancelled")

    def test_future_expired_and_stale_revision_leave_everything_unchanged(self):
        before = list(Subscription.objects.values())
        for at, revision in [(self.start-timedelta(seconds=1), self.revision),
                             (self.end, self.revision), (self.start, "stale")]:
            with self.subTest(at=at, revision=revision), patch("django.utils.timezone.now", return_value=at):
                with self.assertRaises(ValidationError):
                    self.apply(revision=revision)
        self.assertEqual(list(Subscription.objects.values()), before)
        self.assertFalse(RecurringAccessResolution.objects.exists())

    def test_authorization_workspace_mode_and_reason_boundaries_precede_provider_reads(self):
        with patch.object(RazorpayService, "get_invoice") as remote:
            for reason in ("", " "*3, "x"*1001):
                with self.assertRaises(ValidationError):
                    self.apply(reason=reason)
            with self.assertRaises(PermissionDenied):
                self.apply(actor=self.other)
            with override_settings(RAZORPAY_KEY_ID="rzp_live_fixture"), self.assertRaises(PermissionDenied):
                self.apply()
            with self.assertRaises(ValidationError):
                self.apply(cycle_id=self.held.pk+100)
            other_workspace = Company.all_objects.create(name="Other", schema_name="held_other", owner=self.other, creator=self.other)
            Membership.objects.create(company=other_workspace, user=self.other, role=Role.objects.get(name="Owner"))
            with workspace_context(other_workspace.pk), self.assertRaises(ValidationError):
                apply_held_period(workspace=other_workspace, actor=self.other, cycle_id=self.held.pk,
                                  revision=self.revision, reason="Wrong workspace")
            self.owner.is_active = False
            self.owner.save(update_fields=["is_active"])
            with self.assertRaises(PermissionDenied):
                self.apply()
            remote.assert_not_called()

    def test_provider_refunds_identity_changes_and_outage_fail_closed(self):
        with patch("django.utils.timezone.now", return_value=self.start):
            for amount in (1, 176882):
                self.payments["pay_held"]["amount_refunded"] = amount
                with self.assertRaises(ValidationError):
                    self.apply()
            self.payments["pay_held"]["amount_refunded"] = 0
            self.invoices["inv_held"]["paid_at"] -= 1
            with self.assertRaises(ValidationError):
                self.apply()
            self.invoices["inv_held"]["paid_at"] += 1
            with patch.object(RazorpayService, "get_invoice", side_effect=BillingProviderError("Unavailable")):
                with self.assertRaises(BillingProviderError):
                    self.apply()
        self.assertFalse(RecurringAccessResolution.objects.exists())
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.updated_at.isoformat(), self.revision)

    def test_local_refund_recorded_during_provider_reads_blocks_application(self):
        from .recovery import _record_refund
        from .recurring_access import _facts
        def race(*args, **kwargs):
            facts = _facts(*args, **kwargs)
            _record_refund(invoice_id=self.held.invoice_id, payment=self.payments["pay_held"],
                refund={"id": "rfnd_race", "payment_id": "pay_held", "amount": 100,
                        "currency": "INR", "status": "processed"})
            return facts
        with patch("django.utils.timezone.now", return_value=self.start), patch(
                "apps.subscriptions.recurring_access._facts", side_effect=race):
            with self.assertRaisesMessage(ValidationError, "locally recorded"):
                self.apply()
        self.assertFalse(RecurringAccessResolution.objects.exists())

    def test_newer_terms_trial_plan_and_local_cancellation_are_not_overwritten(self):
        other_plan = Plan.objects.create(name="Other terms", tier="starter", price=2000, description="Different plan")
        for fields in ({"end_date": self.end}, {"status": "cancelled"}, {"status": "trial"},
                       {"plan_id": other_plan.pk}, {"trial_end_date": self.start+timedelta(days=1)}):
            with self.subTest(fields=fields), transaction.atomic():
                Subscription.objects.filter(pk=self.subscription.pk).update(**fields)
                with patch("django.utils.timezone.now", return_value=self.start), self.assertRaises(ValidationError):
                    self.apply()
                transaction.set_rollback(True)
        self.assertFalse(RecurringAccessResolution.objects.exists())

    def test_workspace_lifecycle_closed_agreement_and_capacity_block(self):
        for state in (Company.LifecycleState.SUSPENDED, Company.LifecycleState.ARCHIVED, Company.LifecycleState.DELETION_PENDING):
            with self.subTest(state=state), transaction.atomic():
                Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state=state)
                with patch("django.utils.timezone.now", return_value=self.start), self.assertRaises(ValidationError):
                    self.apply()
                transaction.set_rollback(True)
        with patch("django.utils.timezone.now", return_value=self.start):
            with patch("apps.subscriptions.recurring_access.get_workspace_member_usage", return_value=7), self.assertRaises(ValidationError):
                self.apply()
            RecurringAgreement.objects.filter(pk=self.agreement.pk).update(provider_status="cancelled", closed_at=self.now)
            with self.assertRaises(ValidationError):
                self.apply()

    def test_provider_cancellation_does_not_discard_paid_time_and_override_survives(self):
        from .access_policy import workspace_activity
        self.provider_agreement["status"] = "cancelled"
        RecurringAgreement.objects.filter(pk=self.agreement.pk).update(provider_status="cancelled")
        SubscriptionEntitlement.objects.filter(subscription=self.subscription, feature_code="workspace.max_members").update(
            source="override", value="8", override_reason="Reviewed", override_actor=self.owner)
        WorkspaceAccessDecision.objects.create(workspace=self.workspace, actor=self.owner, mode="read_only",
                                               reason="Existing restriction", expires_at=self.end)
        with patch("django.utils.timezone.now", return_value=self.start):
            self.apply()
            self.assertEqual(workspace_activity(self.workspace).mode, "read_only")
        self.assertEqual(SubscriptionEntitlement.objects.get(subscription=self.subscription,
                         feature_code="workspace.max_members").value, "8")

    def test_resolution_failure_rolls_back_access_and_entitlements(self):
        before = list(Subscription.objects.values())
        entitlements = list(SubscriptionEntitlement.objects.order_by("pk").values())
        with patch("django.utils.timezone.now", return_value=self.start), patch(
                "apps.subscriptions.recurring_access.RecurringAccessResolution.objects.create", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                self.apply()
        self.assertEqual(list(Subscription.objects.values()), before)
        self.assertEqual(list(SubscriptionEntitlement.objects.order_by("pk").values()), entitlements)
        self.assertFalse(SubscriptionEvent.objects.filter(event_type="recurring.access_resolved").exists())

    def test_reviewed_cycle_counts_for_later_capture_and_replay_never_reapplies(self):
        with patch("django.utils.timezone.now", return_value=self.start):
            self.apply()
        self.add_cycle("next", self.end, self.end+timedelta(days=30))
        with patch("django.utils.timezone.now", return_value=self.end):
            following = self.record("next")
            self.assertEqual(following.access_action, "applied")
            self.assertEqual(self.record("held").pk, self.held.pk)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.end_date, following.period_end)

    def test_owner_views_and_receipt_show_resolution_and_command_retry_is_harmless(self):
        with patch("django.utils.timezone.now", return_value=self.start):
            self.apply()
        self.client.force_login(self.owner)
        page = self.client.get(reverse("workspace_subscriptions:recurring", kwargs={"workspace_slug": self.workspace.slug}))
        self.assertContains(page, "Applied after billing review")
        self.assertNotContains(page, "Payments awaiting access review")
        invoice = self.client.get(reverse("workspace_subscriptions:invoice-detail", kwargs={
            "workspace_slug": self.workspace.slug, "pk": self.held.invoice_id}))
        self.assertContains(invoice, "Paid period applied after billing review")
        html = render_to_string("subscriptions/emails/subscription_confirmation.html", {"invoice": Invoice.objects.get(pk=self.held.invoice_id)})
        self.assertIn("applied after billing review", html)
        self.assertNotIn("access needs a billing review", html)
        out = StringIO()
        call_command("apply_recurring_period", workspace_id=self.workspace.pk, actor_id=self.owner.pk,
                     cycle_id=self.held.pk, revision=self.revision, reason="Command retry", stdout=out)
        self.assertIn('"resolution_id"', out.getvalue())
        self.assertEqual(RecurringAccessResolution.objects.count(), 1)

    def test_ownership_change_during_provider_reads_is_rechecked(self):
        from .recurring_access import _facts
        def race(*args, **kwargs):
            facts = _facts(*args, **kwargs)
            Company.all_objects.filter(pk=self.workspace.pk).update(owner=self.other)
            return facts
        with patch("django.utils.timezone.now", return_value=self.start), patch(
                "apps.subscriptions.recurring_access._facts", side_effect=race), self.assertRaises(PermissionDenied):
            self.apply()
        self.assertFalse(RecurringAccessResolution.objects.exists())

    def test_database_rejects_resolution_for_an_ordinary_cycle(self):
        with self.assertRaises(DatabaseError), transaction.atomic():
            RecurringAccessResolution.objects.create(cycle=RecurringCycle.objects.get(provider_invoice_id="inv_two"),
                actor=self.owner, reason="Wrong cycle", evidence={})


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture", BILLING_TAX_RATE="18")
class FirstHeldAccessTests(CycleFixture, TestCase):
    def test_first_monthly_hold_can_activate_its_inactive_financial_parent(self):
        start = self.now + timedelta(days=1)
        self.add_cycle("first", start, start+timedelta(days=30))
        cycle = self.record("first")
        subscription = Subscription.objects.get(company=self.workspace)
        self.assertEqual(subscription.status, "past_due")
        self.assertFalse(SubscriptionEntitlement.objects.exists())
        with workspace_context(self.workspace.pk), patch("django.utils.timezone.now", return_value=start):
            apply_held_period(workspace=self.workspace, actor=self.owner, cycle_id=cycle.pk,
                revision=subscription.updated_at.isoformat(), reason="First paid period due")
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "active")
        self.assertEqual(subscription.end_date, cycle.period_end)
        self.assertEqual(SubscriptionEntitlement.objects.get(feature_code="workspace.max_members").value, "6")


@override_settings(RAZORPAY_KEY_ID="rzp_test_fixture", RAZORPAY_KEY_SECRET="fixture", BILLING_TAX_RATE="18")
class ConcurrentHeldAccessTests(HeldFixture, TransactionTestCase):
    def test_restricted_concurrent_reviews_apply_once_and_evidence_is_immutable(self):
        role = connection.ops.quote_name("held_test_"+uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        barrier = Barrier(2)
        def run():
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {role}")
                barrier.wait(timeout=10)
                return self.apply().pk
            finally:
                connections.close_all()
        try:
            with patch("django.utils.timezone.now", return_value=self.start), ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: run(), range(2)))
            self.assertEqual(results[0], results[1])
            self.assertEqual(RecurringAccessResolution.objects.count(), 1)
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            for mutation in (lambda: RecurringAccessResolution.objects.update(reason="rewrite"),
                             lambda: RecurringAccessResolution.objects.all().delete()):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    mutation()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
