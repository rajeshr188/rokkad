from django.contrib.auth import get_user_model
from django.http import Http404
from django.db import connection
from django.db.models import Max
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.configuration.views import WorkspacePreferenceBuilder
from apps.orgs import views as org_views
from apps.orgs.models import Company, Membership, Role


class WorkspacePreferencesViewTests(TestCase):
    def setUp(self):
        if hasattr(connection, "set_schema_to_public"):
            connection.set_schema_to_public()
        self.factory = RequestFactory()
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="central-pref-owner",
            email="central-pref-owner@example.com",
            password="pass",
        )
        self.other_user = User.objects.create_user(
            username="central-pref-other",
            email="central-pref-other@example.com",
            password="pass",
        )
        self.owner_role, _ = Role.objects.get_or_create(name="Owner")
        self.member_role, _ = Role.objects.get_or_create(name="Member")

        next_company_id = (
            Company.all_objects.aggregate(max_id=Max("id"))["max_id"] or 0
        ) + 1
        self.workspace = Company(
            id=next_company_id,
            name="Central Preference Workspace",
            schema_name=f"central_pref_workspace_{next_company_id}",
            owner=self.owner,
            creator=self.owner,
        )
        self.workspace.auto_create_schema = False
        self.workspace.save()
        Membership.objects.create(
            user=self.owner,
            company=self.workspace,
            role=self.owner_role,
        )
        if hasattr(self.owner, "profile"):
            self.owner.profile.workspace = self.workspace
            self.owner.profile.save(update_fields=["workspace"])

    def tearDown(self):
        if hasattr(connection, "set_schema_to_public"):
            connection.set_schema_to_public()

    def test_owner_can_open_central_workspace_preferences(self):
        request = self.factory.get(
            reverse(
                "workspace_settings_preferences",
                kwargs={"workspace_id": self.workspace.id},
            )
        )
        request.user = self.owner

        response = WorkspacePreferenceBuilder.as_view()(
            request,
            workspace_id=self.workspace.id,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("configuration/workspace_preferences.html", response.template_name)
        self.assertEqual(response.context_data["workspace"], self.workspace)
        self.assertIn("accounting", [row["name"] for row in response.context_data["sections"]])

    def test_non_member_cannot_open_central_workspace_preferences(self):
        request = self.factory.get(
            reverse(
                "workspace_settings_preferences",
                kwargs={"workspace_id": self.workspace.id},
            )
        )
        request.user = self.other_user

        with self.assertRaises(Http404):
            WorkspacePreferenceBuilder.as_view()(request, workspace_id=self.workspace.id)

    def test_legacy_girvi_preferences_route_remains_reachable_for_owner(self):
        request = self.factory.get(
            reverse("workspace_preferences", kwargs={"workspace_id": self.workspace.id})
        )
        request.user = self.owner
        request.tenant = self.workspace

        response = org_views.CompanyPreferenceBuilder.as_view()(
            request,
            workspace_id=self.workspace.id,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("company/company_preferences.html", response.template_name)
