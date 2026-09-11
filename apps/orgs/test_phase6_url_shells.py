from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from apps.orgs import views


class CanonicalWorkspaceUrlTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.workspace = SimpleNamespace(id=7, schema_name="acme")
        self.user = SimpleNamespace(is_authenticated=True)

    def test_primary_workspace_routes_are_slug_scoped(self):
        expected = {
            "workspace_slug_dashboard": "/w/acme/",
            "workspace_slug_settings": "/w/acme/settings/",
            "workspace_slug_settings_setup": "/w/acme/settings/setup/",
            "workspace_slug_settings_setup_state": "/w/acme/settings/setup/state/",
            "workspace_slug_settings_team": "/w/acme/settings/team/",
            "workspace_slug_settings_invitations": "/w/acme/settings/invitations/",
            "workspace_slug_settings_invite": "/w/acme/settings/invitations/new/",
            "workspace_slug_settings_modules": "/w/acme/settings/modules/",
            "workspace_slug_settings_security": "/w/acme/settings/security/",
            "workspace_slug_settings_archive": "/w/acme/settings/archive/",
        }
        for name, path in expected.items():
            with self.subTest(name=name):
                self.assertEqual(reverse(name, kwargs={"workspace_slug": "acme"}), path)
                self.assertEqual(resolve(path).view_name, name)

    def test_slug_routes_render_targets_without_redirecting_to_integer_urls(self):
        cases = (
            (views.workspace_slug_dashboard, "workspace_dashboard"),
            (views.workspace_slug_settings_home, "workspace_detail"),
            (views.workspace_slug_settings_setup, "workspace_setup"),
            (views.workspace_slug_settings_setup_state, "workspace_setup_state"),
            (views.workspace_slug_settings_team, "membership_list"),
            (views.workspace_slug_settings_invitations, "companyinvitations_list"),
            (views.workspace_slug_settings_invite, "team_invite"),
            (views.workspace_slug_settings_profile, "workspace_update"),
            (views.workspace_slug_settings_roles, "membership_list"),
            (views.workspace_slug_settings_modules, "workspace_modules"),
            (views.workspace_slug_settings_security, "workspace_security"),
            (views.workspace_slug_settings_archive, "workspace_delete"),
        )
        for wrapper, target_name in cases:
            with self.subTest(wrapper=wrapper.__name__):
                request = self.factory.get("/w/acme/")
                request.user = self.user
                with patch(
                    "apps.orgs.web.slug_routes._get_workspace_from_slug",
                    return_value=self.workspace,
                ), patch(
                    f"apps.orgs.web.slug_routes.{target_name}",
                    return_value=HttpResponse("canonical"),
                ) as target:
                    response = wrapper(request, workspace_slug="acme")

                self.assertEqual(response.status_code, 200)
                target.assert_called_once_with(request, workspace_id=7)
