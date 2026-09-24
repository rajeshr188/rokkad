from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from django_project.middleware import SubscriptionValidationMiddleware
from apps.subscriptions.access_policy import WorkspaceActivity


class Phase1SubscriptionBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SubscriptionValidationMiddleware(lambda request: None)
        self.workspace = SimpleNamespace(id=7, slug="acme", schema_name="legacy_acme", owner_id=1)

    def _request(self, path):
        request = self.factory.get(path)
        request.user = SimpleNamespace(is_authenticated=True, pk=1)
        request.workspace = self.workspace
        return request

    def test_business_restriction_runs_after_workspace_is_established(self):
        request = self._request("/party/")
        resolved = SimpleNamespace(url_name="party_list", view_name="party:party_list")
        decision = WorkspaceActivity("recovery", "Needs subscription")

        with patch("django_project.middleware.resolve", return_value=resolved), patch(
            "apps.subscriptions.access_policy.workspace_activity",
            return_value=decision,
        ) as policy, patch(
            "django_project.middleware.redirect", return_value=SimpleNamespace(status_code=302)
        ) as redirect:
            response = self.middleware.process_request(request)

        policy.assert_called_once_with(self.workspace)
        self.assertIs(request.workspace_activity, decision)
        redirect.assert_called_once_with(
            "workspace_subscriptions:plan-list", workspace_slug="acme"
        )
        self.assertIs(request.workspace, self.workspace)
        self.assertEqual(response.status_code, 302)

    def test_billing_recovery_route_keeps_context_and_skips_restriction(self):
        request = self._request("/w/acme/settings/billing/dashboard/")
        resolved = SimpleNamespace(
            url_name="dashboard",
            view_name="workspace_subscriptions:dashboard",
        )

        with patch("django_project.middleware.resolve", return_value=resolved), patch(
            "apps.subscriptions.access_policy.workspace_activity"
        ) as policy:
            response = self.middleware.process_request(request)

        policy.assert_not_called()
        self.assertIsNone(response)
        self.assertIs(request.workspace, self.workspace)
