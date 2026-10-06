"""Reviewed lifecycle transitions, audit atomicity and commercial boundaries under RLS."""
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.orgs.services.platform_console import console_workspace
from apps.orgs.services.platform_lifecycle import confirm_lifecycle, review_lifecycle
from apps.orgs import test_platform_console as console_tests
from apps.subscriptions.access_policy import record_access_decision, workspace_activity
from apps.subscriptions.models import Subscription, WorkspaceAccessDecision
from apps.tenancy.context import workspace_context


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PlatformLifecycleTests(TestCase):
    setUp = console_tests.PlatformConsoleTests.setUp
    make_workspace = console_tests.PlatformConsoleTests.make_workspace
    subscription = console_tests.PlatformConsoleTests.subscription

    def review(self, action="suspend", **kwargs):
        return review_lifecycle(actor=kwargs.get("actor", self.admin),
            slug=kwargs.get("slug", self.workspace.slug), action=action)

    def confirm(self, action="suspend", token=None, **kwargs):
        return confirm_lifecycle(actor=kwargs.get("actor", self.admin), slug=kwargs.get("slug", self.workspace.slug),
            action=action, token=token or self.review(action)["review_token"],
            reason=kwargs.get("reason", "Requested operational review"),
            confirmation=kwargs.get("confirmation", self.workspace.slug))

    def url(self, action="suspend"):
        return reverse("platform_workspace_lifecycle", kwargs={"slug": self.workspace.slug, "action": action})

    def test_suspend_restore_audited_without_commercial_changes(self):
        self.subscription(-100)
        before = list(Subscription.objects.filter(company=self.workspace).values())
        token = self.review()["review_token"]
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.lifecycle_state, "ACTIVE")
        self.assertFalse(AuditLog.objects.filter(action="WORKSPACE_LIFECYCLE_CHANGE").exists())
        suspended = self.confirm(token=token)
        self.assertEqual(workspace_activity(suspended).mode, "blocked")
        self.assertEqual(self.review("restore")["activity"].mode, "read_only")
        restored = self.confirm("restore")
        self.assertEqual(workspace_activity(restored).mode, "read_only")
        self.assertEqual(before, list(Subscription.objects.filter(company=self.workspace).values()))
        self.assertEqual(WorkspaceAccessDecision.objects.count(), 0)
        history = console_workspace(actor=self.admin, slug=self.workspace.slug)["lifecycle_history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["actor"], self.admin)
        self.assertEqual(history[0]["before"], "SUSPENDED")
        self.assertEqual(history[0]["after"], "ACTIVE")
        self.assertEqual(history[0]["reason"], "Requested operational review")

    def test_restore_preview_respects_grace_and_existing_extension(self):
        self.subscription(-1)
        self.confirm()
        self.assertEqual(self.review("restore")["activity"].mode, "grace")
        record_access_decision(workspace=self.workspace, actor=self.admin, mode="full",
            expires_at=timezone.now()+timedelta(days=2), reason="Existing approved extension")
        self.assertEqual(self.review("restore")["activity"].mode, "full")
        self.assertEqual(workspace_activity(self.confirm("restore")).mode, "full")
        self.assertEqual(WorkspaceAccessDecision.objects.count(), 1)

    def test_duplicate_and_old_state_cycle_cannot_reapply(self):
        token = self.review()["review_token"]
        self.confirm(token=token)
        with self.assertRaises(ValidationError):
            self.confirm(token=token)
        self.confirm("restore")
        with self.assertRaises(ValidationError):
            self.confirm(token=token)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.lifecycle_state, "ACTIVE")
        self.assertEqual(AuditLog.objects.filter(action="WORKSPACE_LIFECYCLE_CHANGE").count(), 2)

    def test_tampered_expired_other_actor_and_workspace_tokens_rejected(self):
        token = self.review()["review_token"]
        with self.assertRaises(ValidationError):
            self.confirm(token=token + "tampered")
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp()+901):
            with self.assertRaises(ValidationError):
                self.confirm(token=token)
        another = self.make_workspace("beta")
        with self.assertRaises(ValidationError):
            self.confirm(token=token, slug=another.slug, confirmation=another.slug)
        self.owner.is_superuser = True
        with self.assertRaises(ValidationError):
            self.confirm(token=token, actor=self.owner)
        self.assertFalse(AuditLog.objects.filter(action="WORKSPACE_LIFECYCLE_CHANGE").exists())

    def test_changed_projected_access_requires_new_review(self):
        self.subscription(1)
        self.confirm()
        token = self.review("restore")["review_token"]
        Subscription.objects.filter(company=self.workspace).update(trial_end_date=timezone.now()-timedelta(days=100))
        with self.assertRaises(ValidationError):
            self.confirm("restore", token=token)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.lifecycle_state, "SUSPENDED")

    def test_authorization_and_context_checked_before_queries(self):
        token = self.review()["review_token"]
        self.owner.is_staff = True
        for actor in (None, self.owner):
            with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
                self.review(actor=actor)
            with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
                self.confirm(token=token, actor=actor)
        self.admin.is_active = False
        with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
            self.confirm(token=token)
        self.admin.is_active = True
        with workspace_context(self.workspace.pk), self.assertNumQueries(0), self.assertRaises(PermissionDenied):
            self.confirm(token=token)

    def test_reason_confirmation_and_states_restricted(self):
        for kwargs in ({"reason": " "}, {"reason": "x"*1001}, {"confirmation": "wrong"}):
            with self.assertRaises(ValidationError):
                self.confirm(**kwargs)
        for state in ("ARCHIVED", "DELETION_PENDING"):
            Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state=state)
            for action in ("suspend", "restore", "delete"):
                with self.assertRaises(ValidationError):
                    self.review(action)

    def test_audit_failure_rolls_back_lifecycle(self):
        with patch("apps.orgs.services.control_plane.AuditLog.log", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.confirm()
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.lifecycle_state, "ACTIVE")

    def test_http_csrf_confirmation_and_success(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        self.assertEqual(self.client.post(self.url()).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(self.url())
        self.assertContains(response, "Business workspace access will be blocked")
        self.assertIn("no-store", response["Cache-Control"])
        token = response.context["form"].initial["token"]
        data = {"token": token, "reason": "Operator acceptance", "confirmation": self.workspace.slug}
        self.assertEqual(self.client.post(self.url(), data).status_code, 400)
        data["acknowledged"] = "on"
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        self.assertEqual(secure.post(self.url(), data).status_code, 403)
        self.assertRedirects(self.client.post(self.url(), data), reverse("platform_workspace", kwargs={"slug": self.workspace.slug}))
        self.assertEqual(self.client.post(self.url(), data).status_code, 409)
        self.assertEqual(self.client.get(self.url("delete")).status_code, 404)
        self.assertContains(self.client.get(self.url("restore")), "Setup / recovery only")

    def test_stale_http_review_renews_token_but_clears_confirmation(self):
        self.client.force_login(self.admin)
        token = self.review()["review_token"]
        Company.all_objects.filter(pk=self.workspace.pk).update(name="Renamed workspace")
        response = self.client.post(self.url(), {"token": token, "reason": "Keep this reason",
            "confirmation": self.workspace.slug, "acknowledged": "on"})
        self.assertEqual(response.status_code, 409)
        form = response.context["form"]
        self.assertFalse(form.is_bound)
        self.assertEqual(form.initial["reason"], "Keep this reason")
        self.assertNotIn("confirmation", form.initial)
        self.assertNotEqual(form.initial["token"], token)
