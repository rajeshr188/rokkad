"""Console authorization and read-only semantics with forced RLS in effect."""
from datetime import timedelta
import uuid

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, CompanyInvitation, Membership, Role
from apps.orgs.services.platform_console import console_directory, console_overview, console_workspace
from apps.platform_mail.models import Delivery
from apps.subscriptions.access_policy import record_access_decision
from apps.subscriptions.models import Plan, Subscription
from apps.tenancy.context import workspace_context


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PlatformConsoleTests(TestCase):
    def setUp(self):
        role = connection.ops.quote_name("console_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        users = get_user_model().objects
        self.admin = users.create_user(username="console-admin", email="operator@example.test", is_staff=True, is_superuser=True)
        self.owner = users.create_user(username="console-owner", email="owner@example.test")
        self.workspace = self.make_workspace("alpha")
        self.plan = Plan.objects.create(name="Console fixture", tier="starter", price=0, max_users=6)
        self.urls = [reverse("platform_console"), reverse("platform_workspaces"),
                     reverse("platform_workspace", kwargs={"slug": self.workspace.slug}), reverse("platform_guide")]

    def make_workspace(self, name, lifecycle="ACTIVE"):
        workspace = Company.all_objects.create(name=name, schema_name=name, owner=self.owner,
            creator=self.owner, lifecycle_state=lifecycle)
        Membership.objects.create(user=self.owner, company=workspace, role=Role.objects.get_or_create(name="Owner")[0])
        return workspace

    def subscription(self, days, workspace=None):
        workspace = workspace or self.workspace
        sub = Subscription.objects.create(company=workspace, plan=self.plan, status="trial")
        Subscription.objects.filter(pk=sub.pk).update(trial_end_date=timezone.now()+timedelta(days=days))
        return sub

    def test_services_deny_non_admin_inactive_and_scoped_context_before_reads(self):
        calls = [lambda actor: console_overview(actor=actor), lambda actor: console_directory(actor=actor),
                 lambda actor: console_workspace(actor=actor, slug=self.workspace.slug)]
        self.owner.is_staff = True
        for call in calls:
            for actor in (None, self.owner):
                with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
                    call(actor)
            self.admin.is_active = False
            with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
                call(self.admin)
            self.admin.is_active = True
            with workspace_context(self.workspace.pk), self.assertNumQueries(0), self.assertRaises(PermissionDenied):
                call(self.admin)

    def test_http_auth_get_only_and_private_cache(self):
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.owner)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        for url in self.urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(self.client.get(reverse("platform_workspace", kwargs={"slug": "absent"})).status_code, 404)

    def test_reports_only_select_and_include_inactive_workspace_metadata(self):
        self.make_workspace("suspended", "SUSPENDED")
        self.make_workspace("archived", "ARCHIVED")
        self.make_workspace("deletion", "DELETION_PENDING")
        self.make_workspace("public")
        with CaptureQueriesContext(connection) as queries:
            overview = console_overview(actor=self.admin)
            report = console_directory(actor=self.admin)
            detail = console_workspace(actor=self.admin, slug=self.workspace.slug)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        self.assertEqual(overview["counts"]["total"], 4)
        self.assertEqual(overview["counts"]["active"], 1)
        self.assertEqual(len(report["rows"]), 4)
        self.assertEqual(detail["activity"].mode, "recovery")
        self.assertEqual(detail["member_count"], 1)

    def test_current_access_respects_grace_expired_extension_and_lifecycle(self):
        self.subscription(-1)
        self.assertEqual(console_workspace(actor=self.admin, slug="alpha")["activity"].mode, "grace")
        Subscription.objects.filter(company=self.workspace).update(trial_end_date=timezone.now()-timedelta(days=100))
        self.assertEqual(console_workspace(actor=self.admin, slug="alpha")["activity"].mode, "read_only")
        record_access_decision(workspace=self.workspace, actor=self.admin, mode="full",
            expires_at=timezone.now()+timedelta(days=2), reason="Confirmed support extension")
        self.assertEqual(console_workspace(actor=self.admin, slug="alpha")["activity"].mode, "full")
        record_access_decision(workspace=self.workspace, actor=self.admin, mode="default", reason="End exception")
        self.assertEqual(console_workspace(actor=self.admin, slug="alpha")["activity"].mode, "read_only")
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state="SUSPENDED")
        self.assertEqual(console_workspace(actor=self.admin, slug="alpha")["activity"].mode, "blocked")

    def test_filters_counts_and_validated_requests(self):
        self.subscription(3)
        other = self.make_workspace("beta", "ARCHIVED")
        report = console_directory(actor=self.admin, query="owner@example.test")
        self.assertEqual(report["page"].paginator.count, 2)
        self.assertEqual(console_directory(actor=self.admin, lifecycle="ARCHIVED")["rows"][0]["workspace"], other)
        self.assertEqual(console_overview(actor=self.admin)["counts"]["trial_ending"], 1)
        self.assertEqual(console_directory(actor=self.admin, attention="no_subscription")["rows"][0]["workspace"], other)
        self.client.force_login(self.admin)
        for params in ({"lifecycle": "invented"}, {"attention": "invented"}, {"page": "x"}, {"page": "0"}):
            self.assertEqual(self.client.get(self.urls[1], params).status_code, 400)
        self.assertContains(self.client.get(self.urls[1], {"query": "absent"}), "No workspaces match")

    def test_invitation_delivery_acceptance_membership_and_secrets_are_distinct(self):
        invitation = CompanyInvitation.objects.create(company=self.workspace,
            role=Role.objects.get_or_create(name="Viewer")[0], email="member@example.test",
            key="SECRET-INVITATION-KEY", status="accepted", accepted=True)
        Delivery.objects.create(invitation=invitation, key="SECRET-DELIVERY-KEY", recipient=invitation.email,
                                status="delivered")
        detail = console_workspace(actor=self.admin, slug="alpha")
        self.assertEqual(detail["invitations"][0]["state"], "accepted")
        self.assertFalse(detail["invitations"][0]["member"])
        self.assertEqual(console_overview(actor=self.admin)["counts"]["mail"], 0)
        Delivery.objects.filter(invitation=invitation).update(status="unknown")
        self.assertEqual(console_overview(actor=self.admin)["counts"]["mail"], 1)
        self.client.force_login(self.admin)
        response = self.client.get(self.urls[2])
        self.assertNotContains(response, "SECRET-INVITATION-KEY")
        self.assertNotContains(response, "SECRET-DELIVERY-KEY")
        self.assertContains(response, "Manage access extension")
        self.assertContains(response, reverse("workspace_subscriptions:access-controls", kwargs={"workspace_slug": "alpha"}))

    def test_directory_is_bounded_and_pagination_preserves_search(self):
        for n in range(26):
            self.make_workspace(f"page-{n:02}")
        with CaptureQueriesContext(connection) as queries:
            report = console_directory(actor=self.admin, query="page-")
        self.assertEqual(len(report["rows"]), 25)
        self.assertLess(len(queries), 60)  # Existing canonical access policy: at most two reads per row.
        self.assertEqual(len(console_directory(actor=self.admin, query="page-", page=2)["rows"]), 1)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.urls[1], {"query": "page-"}), "query=page-&amp;page=2")

    def test_expired_pending_invitation_and_case_insensitive_membership(self):
        EmailAddress.objects.create(user=self.owner, email=self.owner.email, verified=True)
        CompanyInvitation.objects.create(company=self.workspace, role=Role.objects.get(name="Owner"),
            email=self.owner.email.upper(), key="private", sent=timezone.now()-timedelta(days=100))
        detail = console_workspace(actor=self.admin, slug="alpha")
        self.assertTrue(detail["owner_verified"])
        self.assertEqual(detail["invitations"][0]["state"], "expired")
        self.assertTrue(detail["invitations"][0]["member"])

    def test_inactive_workspaces_do_not_link_to_unavailable_settings(self):
        self.client.force_login(self.admin)
        for lifecycle in ("SUSPENDED", "ARCHIVED", "DELETION_PENDING"):
            Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state=lifecycle)
            response = self.client.get(self.urls[2])
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "Open workspace settings")
            self.assertNotContains(response, "Manage access extension")
            if lifecycle == "ARCHIVED":
                self.assertContains(response, reverse("app_archived_workspaces"))
