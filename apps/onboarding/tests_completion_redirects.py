from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.onboarding import views


class OnboardingCompletionRedirectTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _request(self):
        request = self.factory.get("/onboarding/complete/")
        request.user = SimpleNamespace(is_authenticated=True)
        return request

    def _progress(self, *, is_complete=False):
        return SimpleNamespace(
            is_complete=is_complete,
            complete_onboarding=lambda: None,
        )

    @patch("apps.onboarding.views.redirect")
    def test_completed_start_redirects_to_workspace_setup_when_workspace_exists(
        self,
        mock_redirect,
    ):
        request = self._request()
        workspace = SimpleNamespace(id=9, schema_name="demo")

        with patch(
            "apps.onboarding.views.get_or_create_progress",
            return_value=self._progress(is_complete=True),
        ), patch(
            "apps.onboarding.views.resolve_request_workspace",
            return_value=workspace,
        ) as mock_resolve:
            views.onboarding_start(request)

        mock_resolve.assert_called_once_with(
            request,
            include_public=False,
            allow_profile_fallback=True,
        )
        mock_redirect.assert_called_once_with(
            "workspace_settings_setup",
            workspace_id=9,
        )

    @patch("apps.onboarding.views.redirect")
    def test_completed_start_falls_back_to_workspace_list_without_workspace(
        self,
        mock_redirect,
    ):
        request = self._request()

        with patch(
            "apps.onboarding.views.get_or_create_progress",
            return_value=self._progress(is_complete=True),
        ), patch(
            "apps.onboarding.views.resolve_request_workspace",
            return_value=None,
        ):
            views.onboarding_start(request)

        mock_redirect.assert_called_once_with("workspace_list")

    @patch("apps.onboarding.views.AuditLog.log")
    @patch("apps.onboarding.views.redirect")
    def test_onboarding_complete_redirects_to_workspace_setup(
        self,
        mock_redirect,
        mock_audit_log,
    ):
        request = self._request()
        workspace = SimpleNamespace(id=12, schema_name="demo")
        progress = self._progress(is_complete=False)

        with patch(
            "apps.onboarding.views.get_or_create_progress",
            return_value=progress,
        ), patch(
            "apps.onboarding.views.resolve_request_workspace",
            return_value=workspace,
        ):
            views.onboarding_complete(request)

        mock_audit_log.assert_called_once()
        mock_redirect.assert_called_once_with(
            "workspace_settings_setup",
            workspace_id=12,
        )

    @patch("apps.onboarding.views.messages")
    @patch("apps.onboarding.views.redirect")
    def test_onboarding_skip_redirects_to_workspace_setup_when_workspace_exists(
        self,
        mock_redirect,
        mock_messages,
    ):
        request = self._request()
        workspace = SimpleNamespace(id=15, schema_name="demo")
        progress = self._progress(is_complete=False)

        with patch(
            "apps.onboarding.views.get_or_create_progress",
            return_value=progress,
        ), patch(
            "apps.onboarding.views.resolve_request_workspace",
            return_value=workspace,
        ):
            views.onboarding_skip(request)

        mock_messages.warning.assert_called_once()
        mock_redirect.assert_called_once_with(
            "workspace_settings_setup",
            workspace_id=15,
        )
