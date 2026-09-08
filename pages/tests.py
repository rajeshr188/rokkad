import inspect
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from pages import views


class DashboardWorkspaceResolutionTests(SimpleTestCase):
    def test_login_landing_uses_validated_preference_without_setting_request_scope(self):
        request = RequestFactory().get("/dashboard/")
        request.user = SimpleNamespace(is_authenticated=True)
        workspace = SimpleNamespace(slug="last-used")
        with patch("pages.views.resolve_request_workspace", return_value=None) as resolve_workspace, patch(
            "pages.views.resolve_preferred_workspace", return_value=workspace,
        ) as preferred, patch("pages.views.redirect") as redirect:
            inspect.unwrap(views.Dashboard)(request)
        resolve_workspace.assert_called_once_with(request)
        preferred.assert_called_once_with(request.user)
        redirect.assert_called_once_with("workspace_slug_dashboard", workspace_slug="last-used")
        self.assertFalse(hasattr(request, "workspace"))

    def test_login_landing_handles_no_single_and_multiple_workspaces(self):
        for count in (0, 1, 2):
            with self.subTest(count=count):
                request = RequestFactory().get("/dashboard/")
                rows = [SimpleNamespace(company=SimpleNamespace(slug=f"ws-{index}")) for index in range(count)]
                memberships = SimpleNamespace(select_related=lambda *_args: SimpleNamespace(filter=lambda **_kwargs: rows))
                request.user = SimpleNamespace(is_authenticated=True, memberships=memberships)
                with patch("pages.views.resolve_request_workspace", return_value=None), patch(
                    "pages.views.resolve_preferred_workspace", return_value=None,
                ), patch("pages.views.redirect") as redirect:
                    inspect.unwrap(views.Dashboard)(request)
                if count == 1:
                    redirect.assert_called_once_with("workspace_slug_dashboard", workspace_slug="ws-0")
                else:
                    redirect.assert_called_once_with("workspace_selector")

    def test_legacy_company_dashboard_uses_explicit_request_context_only(self):
        request = RequestFactory().get("/company/dashboard/")
        request.user = SimpleNamespace(is_authenticated=True)

        with patch(
            "pages.views.resolve_request_workspace", return_value=None
        ) as resolve_workspace, patch(
            "pages.views.redirect", return_value=SimpleNamespace(status_code=302)
        ) as redirect:
            response = inspect.unwrap(views.company_dashboard)(request)

        resolve_workspace.assert_called_once_with(request, include_public=True)
        redirect.assert_called_once_with("workspace_selector")
        self.assertEqual(response.status_code, 302)
