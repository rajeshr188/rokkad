from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase
from django.template.loader import render_to_string
from django.urls import Resolver404, resolve
from apps.configuration.views import WorkspacePreferenceBuilder
from apps.orgs.web.account_preferences import CompanyPreferenceBuilder


class WorkspacePreferencesViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.workspace = SimpleNamespace(pk=13, id=13, slug="acme")

    def request(self, method="get"):
        request = getattr(self.factory, method)("/w/acme/settings/preferences/")
        request.user = SimpleNamespace(is_authenticated=True)
        request.workspace = self.workspace
        return request

    def test_both_bookmarks_show_guidance_and_reject_writes(self):
        for view in (WorkspacePreferenceBuilder, CompanyPreferenceBuilder):
            with self.subTest(view=view.__name__), patch("apps.configuration.views.get_object_or_404", return_value=self.workspace), patch("apps.configuration.views._assert_workspace_access") as access:
                response = view.as_view()(self.request(), workspace_id=13)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context_data["workspace"], self.workspace)
                self.assertNotIn("form", response.context_data)
                access.assert_called_once_with(response._request, self.workspace, {"workspace_settings"})
                response = view.as_view()(self.request("post"), workspace_id=13)
                self.assertEqual(response.status_code, 405)

    def test_denied_user_cannot_read_or_post_to_either_route(self):
        for view in (WorkspacePreferenceBuilder, CompanyPreferenceBuilder):
            for method in ("get", "post"):
                with self.subTest(view=view.__name__, method=method), patch("apps.configuration.views.get_object_or_404", return_value=self.workspace), patch("apps.configuration.views._assert_workspace_access", side_effect=PermissionDenied):
                    with self.assertRaises(PermissionDenied):
                        view.as_view()(self.request(method), workspace_id=13)

    def test_generic_preference_editor_is_not_routed(self):
        with self.assertRaises(Resolver404):
            resolve("/dynamic_preferences/global/")

    def test_data_reader_can_find_archive_and_reports_without_settings(self):
        request = self.request()
        request.path = "/w/acme/"
        request.resolver_match = SimpleNamespace(url_name="workspace_slug_dashboard")
        html = render_to_string("components/navigation/sidebar.html", {"request":request,"user_permissions":{"data.view"}})
        self.assertIn("Historical loans", html)
        self.assertIn("Reports", html)
        self.assertNotIn("workspace-settings-nav", html)
        self.assertNotIn("Preferences", html)

    def test_user_without_data_view_does_not_get_record_links(self):
        request = self.request()
        html = render_to_string("components/navigation/sidebar.html", {"request":request,"user_permissions":set()})
        self.assertNotIn("Historical loans", html)
        self.assertNotIn("Release batches", html)
