import inspect
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from pages import views


class DashboardWorkspaceResolutionTests(SimpleTestCase):
    def test_global_dashboard_never_requests_retired_profile_fallback(self):
        request = RequestFactory().get("/dashboard/")
        memberships = SimpleNamespace(
            filter=lambda **_kwargs: SimpleNamespace(exists=lambda: True)
        )
        request.user = SimpleNamespace(
            is_authenticated=True,
            memberships=memberships,
        )

        with patch(
            "pages.views.resolve_request_workspace", return_value=None
        ) as resolve_workspace, patch(
            "pages.views.redirect", return_value=SimpleNamespace(status_code=302)
        ) as redirect:
            response = inspect.unwrap(views.Dashboard)(request)

        resolve_workspace.assert_called_once_with(request, include_public=True)
        redirect.assert_called_once_with("workspace_selector")
        self.assertEqual(response.status_code, 302)

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
