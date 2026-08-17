from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from django_project.middleware import SubscriptionValidationMiddleware


class Phase1SubscriptionBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SubscriptionValidationMiddleware(lambda request: None)
        self.workspace = SimpleNamespace(id=7, schema_name="acme")

    def _request(self, path):
        request = self.factory.get(path)
        request.user = SimpleNamespace(is_authenticated=True)
        request.workspace = self.workspace
        request.tenant = self.workspace
        return request

    def test_business_restriction_runs_after_workspace_is_established(self):
        request = self._request("/party/")
        decision = SimpleNamespace(
            allowed=False,
            reason="NO_SUBSCRIPTION",
            message="No subscription.",
            subscription=None,
        )
        resolved = SimpleNamespace(url_name="party_list", view_name="party:party_list")

        with patch("django_project.middleware.resolve", return_value=resolved), patch(
            "django_project.middleware.subscription_access_service.evaluate_access",
            return_value=decision,
        ) as evaluate, patch("django_project.middleware.messages"), patch(
            "django_project.middleware.redirect", return_value=SimpleNamespace(status_code=302)
        ) as redirect:
            response = self.middleware.process_request(request)

        evaluate.assert_called_once_with(user=request.user, workspace=self.workspace)
        redirect.assert_called_once_with(
            "workspace_subscriptions:plan-list", workspace_slug="acme"
        )
        self.assertIs(request.workspace, self.workspace)
        self.assertIs(request.tenant, request.workspace)
        self.assertEqual(response.status_code, 302)

    def test_billing_recovery_route_keeps_context_and_skips_restriction(self):
        request = self._request("/w/acme/settings/billing/dashboard/")
        resolved = SimpleNamespace(
            url_name="dashboard",
            view_name="workspace_subscriptions:dashboard",
        )

        with patch("django_project.middleware.resolve", return_value=resolved), patch(
            "django_project.middleware.subscription_access_service.evaluate_access"
        ) as evaluate:
            response = self.middleware.process_request(request)

        evaluate.assert_not_called()
        self.assertIsNone(response)
        self.assertIs(request.workspace, self.workspace)
