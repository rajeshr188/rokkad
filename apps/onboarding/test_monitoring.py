"""Operator authorization and evidence semantics under a restricted DB role."""
from datetime import timedelta
from io import StringIO
import json
import uuid

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, CompanyInvitation, Membership, Role
from apps.platform_mail.models import Delivery
from apps.subscriptions.models import Plan, Subscription, SubscriptionEvent
from apps.tenancy.context import workspace_context
from .models import OnboardingProgress
from .services.monitoring import onboarding_report


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class OnboardingReportTests(TestCase):
    def setUp(self):
        role = connection.ops.quote_name("onboarding_report_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        self.admin = get_user_model().objects.create_user(username="report-admin",
            email="admin@example.com", is_staff=True, is_superuser=True)
        self.owner = get_user_model().objects.create_user(username="report-owner", email="owner@example.com")
        self.url = reverse("admin:onboarding_progress_report")

    def test_denies_ordinary_staff_inactive_and_workspace_context_before_reading(self):
        for actor in (None, self.owner):
            with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
                onboarding_report(actor=actor)
        self.owner.is_staff = True
        with self.assertRaises(PermissionDenied):
            onboarding_report(actor=self.owner)
        self.admin.is_active = False
        with self.assertRaises(PermissionDenied):
            onboarding_report(actor=self.admin)
        self.admin.is_active = True
        with workspace_context(87654321), self.assertRaises(PermissionDenied):
            onboarding_report(actor=self.admin)

    def test_no_workspace_and_skipped_team_are_not_success_and_report_only_selects(self):
        OnboardingProgress.objects.filter(user=self.owner).update(is_complete=True, skipped_team=True)
        get_user_model().objects.create_user(username="disabled-rehearsal", is_active=False)
        with CaptureQueriesContext(connection) as queries:
            report = onboarding_report(actor=self.admin)
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        self.assertEqual(report["account_count"], 1)
        row = report["accounts"][0]
        self.assertEqual(row["relationship"], "No Workspace yet")
        self.assertFalse(row["email_verified"])
        self.assertTrue(row["wizard_complete"])
        self.assertEqual(row["workspaces"], [])

    def test_public_trial_expiry_delivery_and_acceptance_are_separate(self):
        now = timezone.now()
        EmailAddress.objects.create(user=self.owner, email=self.owner.email, verified=True)
        workspace = Company.all_objects.create(name="Report trial", schema_name="report-trial",
            owner=self.owner, creator=self.owner)
        role = Role.objects.get_or_create(name="Owner")[0]
        Membership.objects.create(user=self.owner, company=workspace, role=role)
        plan = Plan.objects.create(name="Report plan", tier="starter", price=0, max_users=6)
        sub = Subscription.objects.create(company=workspace, plan=plan, status="trial",
            trial_end_date=now - timedelta(days=100))
        Subscription.objects.filter(pk=sub.pk).update(trial_end_date=now - timedelta(days=100))
        SubscriptionEvent.objects.create(subscription=sub, event_type="trial.started",
            payload={"actor_id": self.owner.pk, "accepted_terms": {"version": "public-trial-fixture"}})
        invitation = CompanyInvitation.objects.create(company=workspace, role=role, email="team@example.com",
            key="must-never-appear", sent=now - timedelta(days=100))
        Delivery.objects.create(invitation=invitation, key="report-delivery", status="delivered", attempt_count=1)
        row = onboarding_report(actor=self.admin)["accounts"][0]["workspaces"][0]
        self.assertEqual(row["trial_kind"], "Public trial")
        self.assertEqual(row["access"], "read_only")
        self.assertEqual(row["step"], "Team invited")
        self.assertEqual(row["recent_invitations"][0]["state"], "expired")
        self.assertFalse(row["recent_invitations"][0]["current_member"])
        self.assertNotIn("must-never-appear", str(row))
        CompanyInvitation.objects.filter(pk=invitation.pk).update(status="accepted", accepted=True)
        row = onboarding_report(actor=self.admin)["accounts"][0]["workspaces"][0]
        self.assertEqual(row["step"], "Team invitation accepted")
        self.assertFalse(row["recent_invitations"][0]["current_member"])

    def test_admin_get_only_filters_and_command(self):
        self.client.force_login(self.admin)
        page = self.client.get(self.url)
        self.assertContains(page, "No Workspace yet")
        self.assertContains(page, "owner@example.com")
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertEqual(self.client.get(self.url, {"since": "invalid"}).status_code, 400)
        self.assertContains(self.client.get(self.url, {"query": "missing"}), "No matching active accounts")
        self.owner.is_staff = True
        self.owner.save(update_fields=["is_staff"])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        output = StringIO()
        call_command("report_onboarding", actor_id=self.admin.pk, stdout=output)
        self.assertEqual(json.loads(output.getvalue())["account_count"], 1)

    def test_signup_cutoff_and_pagination(self):
        for number in range(26):
            get_user_model().objects.create_user(username=f"page-{number}")
        first = onboarding_report(actor=self.admin)
        second = onboarding_report(actor=self.admin, page=2)
        self.assertEqual(len(first["accounts"]), 25)
        self.assertEqual(len(second["accounts"]), 2)
        self.assertTrue(first["has_next"])
        self.assertEqual(onboarding_report(actor=self.admin, since=timezone.now())["account_count"], 0)
