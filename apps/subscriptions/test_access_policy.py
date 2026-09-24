from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from .access_policy import record_access_decision, require_business_write, workspace_activity
from . import entitlements
from .models import Invoice, Payment, Plan, Subscription, SubscriptionEvent, WorkspaceAccessDecision
from .services import ensure_entitlements_for_subscription


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class WorkspaceAccessPolicyTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="access-owner")
        self.admin = get_user_model().objects.create_superuser(username="access-platform", email="platform@example.test", password="test")
        self.staff = get_user_model().objects.create_user(username="access-staff")
        self.workspace = Company.objects.create(name="Access tests", schema_name="access-tests", owner=self.owner, creator=self.owner)
        for actor, name in ((self.owner, "Owner"), (self.staff, "Member")):
            role, _ = Role.objects.get_or_create(name=name)
            Membership.objects.create(user=actor, company=self.workspace, role=role)
        self.plan = Plan.objects.create(name="Access plan", tier="starter", price=100, max_users=5, has_advanced_reporting=True)
        self.sub = Subscription.objects.create(company=self.workspace, plan=self.plan)
        ensure_entitlements_for_subscription(self.sub)
        self.now = timezone.now()
        self.client.force_login(self.owner)

    def expire(self, days=8):
        Subscription.objects.filter(pk=self.sub.pk).update(trial_end_date=self.now - timedelta(days=days))
        self.sub.refresh_from_db()

    def grant(self, mode="full", **kwargs):
        return record_access_decision(workspace=self.workspace, actor=kwargs.pop("actor", self.admin), mode=mode,
            expires_at=kwargs.pop("expires_at", None if mode == "default" else self.now + timedelta(days=10)),
            reason=kwargs.pop("reason", "Approved rehearsal access"), **kwargs)

    def url(self, name, *args):
        return reverse(name, args=[self.workspace.slug, *args])

    def test_trial_and_paid_grace_boundaries_preserve_billing_evidence(self):
        for status, field in (("trial", "trial_end_date"), ("active", "end_date")):
            Subscription.objects.filter(pk=self.sub.pk).update(status=status, **{field: self.now})
            original = Subscription.objects.values().get(pk=self.sub.pk)
            self.assertEqual(workspace_activity(self.workspace, at=self.now - timedelta(seconds=1)).mode, "full")
            self.assertEqual(workspace_activity(self.workspace, at=self.now + timedelta(seconds=1)).mode, "grace")
            self.assertEqual(workspace_activity(self.workspace, at=self.now + timedelta(days=7) - timedelta(microseconds=1)).mode, "grace")
            self.assertEqual(workspace_activity(self.workspace, at=self.now + timedelta(days=7)).mode, "read_only")
            self.assertEqual(Subscription.objects.values().get(pk=self.sub.pk), original)
        self.assertFalse(SubscriptionEvent.objects.exists())

    def test_cancelled_and_past_due_get_no_automatic_grace(self):
        for status in ("cancelled", "past_due", "expired"):
            Subscription.objects.filter(pk=self.sub.pk).update(status=status)
            self.assertEqual(workspace_activity(self.workspace).mode, "read_only")

    def test_extension_expiry_and_revocation_do_not_resurrect_old_grant(self):
        self.expire()
        self.grant()
        shorter = self.grant(expires_at=self.now + timedelta(days=1))
        self.assertTrue(workspace_activity(self.workspace).can_write)
        self.assertEqual(workspace_activity(self.workspace, at=shorter.expires_at).mode, "read_only")
        self.grant(mode="default")
        self.assertEqual(workspace_activity(self.workspace).mode, "read_only")
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(SubscriptionEvent.objects.exists())
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, "trial")

    def test_only_platform_can_grant_and_decisions_require_reason_and_expiry(self):
        for actor in (self.owner, self.staff):
            with self.assertRaises(PermissionDenied):
                self.grant(actor=actor)
        for values in ({"reason": " "}, {"expires_at": None}, {"expires_at": self.now - timedelta(seconds=1)}):
            with self.assertRaises(ValidationError):
                self.grant(**values)
        self.assertEqual(WorkspaceAccessDecision.objects.count(), 0)

    def test_restriction_overrides_paid_access_but_never_workspace_suspension(self):
        self.grant(mode="read_only")
        self.assertEqual(workspace_activity(self.workspace).mode, "read_only")
        self.grant()
        for state in ("SUSPENDED", "ARCHIVED", "DELETION_PENDING"):
            self.workspace.lifecycle_state = state
            self.workspace.save(update_fields=["lifecycle_state"])
            self.assertEqual(workspace_activity(self.workspace).mode, "blocked")
            with self.assertRaises(PermissionDenied):
                require_business_write(self.workspace)

    def test_grace_and_extension_preserve_entitlements_readonly_drops_write_capacity(self):
        self.expire(days=1)
        self.assertEqual(entitlements.limit(self.workspace, "workspace.max_members"), 5)
        self.expire()
        self.assertIsNone(entitlements.limit(self.workspace, "workspace.max_members"))
        self.assertTrue(entitlements.enabled(self.workspace, "reporting.advanced"))
        self.grant()
        self.assertEqual(entitlements.limit(self.workspace, "workspace.max_members"), 5)

    def test_no_subscription_grant_uses_reviewed_plan_snapshot_without_creating_trial(self):
        other = Company.objects.create(name="New access", schema_name="new-access", owner=self.owner, creator=self.owner)
        role = Role.objects.get(name="Owner")
        Membership.objects.create(user=self.owner, company=other, role=role)
        with self.assertRaises(ValidationError):
            record_access_decision(workspace=other, actor=self.admin, mode="full", expires_at=self.now + timedelta(days=2), reason="Pilot")
        decision = record_access_decision(workspace=other, actor=self.admin, mode="full", expires_at=self.now + timedelta(days=2), reason="Pilot", plan=self.plan)
        self.assertFalse(Subscription.objects.filter(company=other).exists())
        self.assertEqual(entitlements.limit(other, "workspace.max_members"), 5)
        self.plan.max_users = 999
        self.plan.save()
        self.assertEqual(entitlements.limit(other, "workspace.max_members"), 5)
        self.assertEqual(workspace_activity(other, at=decision.expires_at).mode, "read_only")
        self.assertEqual(workspace_activity(self.workspace).mode, "full")

    def test_readonly_staff_can_read_and_receive_clear_denial_without_billing_redirect(self):
        self.expire()
        self.client.force_login(self.staff)
        page = self.client.get(self.url("workspace_slug_parties"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Read-only workspace")
        self.assertContains(page, "Contact your workspace owner")
        denied = self.client.post(self.url("workspace_slug_party_create"), {"name": "Denied"})
        self.assertEqual(denied.status_code, 403)
        self.assertContains(denied, "Contact your workspace owner", status_code=403)
        self.assertNotIn("Location", denied)
        # A GET displaying an edit form is not an approved read-only route.
        self.assertEqual(self.client.get(self.url("workspace_slug_party_create")).status_code, 403)

    def test_owner_recovery_and_platform_controls_remain_authorized(self):
        Subscription.objects.filter(pk=self.sub.pk).update(trial_end_date=self.now + timedelta(days=3))
        self.assertContains(self.client.get(self.url("workspace_subscriptions:dashboard")), "Subscription ending soon")
        self.expire()
        billing = self.client.get(self.url("workspace_subscriptions:dashboard"))
        self.assertContains(billing, "Trial ended")
        self.assertContains(billing, "Online subscription payment is not yet available")
        url = self.url("workspace_subscriptions:access-controls")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"mode": "full", "expires_at": (self.now + timedelta(days=5)).isoformat(), "reason": "Browser extension"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(workspace_activity(self.workspace).can_write)
        self.assertContains(self.client.get(self.url("workspace_subscriptions:dashboard")), "Temporary workspace access")

    @patch("apps.subscriptions.razorpay_service.RazorpayService.create_order")
    def test_disabled_checkout_never_calls_provider(self, provider):
        response = self.client.post(self.url("workspace_subscriptions:order-create"), {}, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        provider.assert_not_called()

    def test_service_writes_and_new_document_issuance_are_denied(self):
        from apps.tenant_apps.loans.services.product_catalog import seed_default_loan_products
        from apps.tenant_apps.party.services.action_access import require_party_service_permission
        from apps.tenant_apps.data_portability.access import require_access
        from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
        from apps.tenant_apps.loans.services.action_access import require_loan_action
        from apps.tenant_apps.notify_v2.services.delivery_service import dispatch_job
        from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
        self.expire()
        with workspace_context(self.workspace.pk):
            for command in (
                lambda: seed_default_loan_products(actor=self.owner),
                lambda: require_party_service_permission(self.workspace.pk, self.owner, "data.create"),
                lambda: require_access(self.workspace.pk, self.owner, "commit"),
                lambda: require_loan_action(SimpleNamespace(workspace=self.workspace), self.owner, "loan.repay"),
                lambda: dispatch_job(SimpleNamespace(workspace_id=self.workspace.pk)),
                lambda: LoanDocumentLayoutService.issue(workspace=self.workspace, document_type="loan_ticket", source_type="test", source_id=1, source_fingerprint="test", payload_schema_version=1, render_result=SimpleNamespace(), filename="not-created.pdf", actor=self.owner),
            ):
                with self.assertRaises(PermissionDenied):
                    command()
            # The same setup authority remains valid for read-only export.
            self.assertEqual(require_history_setup_access(self.workspace.pk, self.owner, read_only=True), self.workspace)

    def test_command_records_immutable_history(self):
        call_command("set_workspace_access", workspace_id=self.workspace.pk, actor_id=self.admin.pk,
            mode="full", until=(self.now + timedelta(days=5)).isoformat(), reason="Operator grant", stdout=StringIO())
        row = WorkspaceAccessDecision.objects.get()
        with self.assertRaises(ValidationError):
            row.save()
        for operation in (lambda: WorkspaceAccessDecision.objects.filter(pk=row.pk).update(reason="rewrite"),
                          lambda: WorkspaceAccessDecision.objects.filter(pk=row.pk).delete()):
            with self.assertRaises(DatabaseError), transaction.atomic():
                operation()
