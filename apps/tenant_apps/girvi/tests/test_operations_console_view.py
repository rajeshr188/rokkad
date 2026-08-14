from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.template.loader import get_template

from apps.tenant_apps.girvi.models import GirviPostingOutboxStatus
from apps.tenant_apps.girvi.views.reports import girvi_operations_console


class GirviOperationsConsoleViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    def _request(self, method="get", data=None):
        request_factory = self.factory.post if method.lower() == "post" else self.factory.get
        request = request_factory("/girvi/reports/operations-console/", data=data or {})
        request.user = self.user
        request.tenant = SimpleNamespace(
            schema_name="tenant-1",
            owner=SimpleNamespace(is_authenticated=True),
            theme="default",
            logo="",
        )
        request.htmx = False
        return request

    def test_console_template_uses_the_registered_global_rates_route(self):
        source = get_template("girvi/reports/operations_console.html").template.source

        self.assertIn("{% url 'rate_list' %}", source)
        self.assertNotIn("{% url 'rates:rate_list' %}", source)

    @patch("apps.tenant_apps.girvi.views.reports.render")
    @patch("apps.tenant_apps.girvi.views.reports.build_operations_console_read_model")
    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value={"girvi_report_view"})
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_get_renders_console_context(
        self,
        _role_name,
        _effective_permissions,
        mock_read_model,
        mock_render,
    ):
        request = self._request()
        response = SimpleNamespace(status_code=200)
        mock_render.return_value = response
        mock_read_model.return_value = {
            "payment_counts": {"total": 10, "posted": 8, "pending": 2},
            "outbox_counts": {"failed": 1},
            "series_summary": {"total": 4, "active": 3, "loans_locked": 1, "releases_locked": 0},
            "rate_summary": {"rates": 6, "sources": 2},
            "failed_events": [],
            "recent_audit_events": [],
        }

        result = girvi_operations_console(request)

        self.assertEqual(result, response)
        context = mock_render.call_args.args[2]
        self.assertEqual(context["payment_counts"]["total"], 10)
        self.assertEqual(context["payment_counts"]["posted"], 8)
        self.assertEqual(context["series_summary"]["active"], 3)
        self.assertEqual(context["rate_summary"]["rates"], 6)

    @patch("apps.tenant_apps.girvi.views.reports.redirect")
    @patch("apps.tenant_apps.girvi.views.reports.messages.success")
    @patch("apps.tenant_apps.girvi.views.reports.get_object_or_404")
    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value={"girvi_report_view"})
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_post_retry_failed_event_queues_pending(
        self,
        _role_name,
        _effective_permissions,
        mock_get_object,
        mock_success,
        mock_redirect,
    ):
        request = self._request(method="post", data={"retry_event_id": "12"})
        event = MagicMock(pk=12, status=GirviPostingOutboxStatus.FAILED)
        mock_get_object.return_value = event
        mock_redirect.return_value = SimpleNamespace(status_code=302)

        response = girvi_operations_console(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(event.status, GirviPostingOutboxStatus.PENDING)
        event.save.assert_called_once()
        mock_success.assert_called_once()
        mock_redirect.assert_called_once_with("girvi:girvi_operations_console")
