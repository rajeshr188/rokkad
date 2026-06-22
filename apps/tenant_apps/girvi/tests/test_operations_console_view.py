from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

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

    @patch("apps.tenant_apps.girvi.views.reports.render")
    @patch("apps.tenant_apps.girvi.views.reports.LoanChangeLog")
    @patch("apps.tenant_apps.girvi.views.reports.GirviPostingOutboxEvent")
    @patch("apps.tenant_apps.girvi.views.reports.Series")
    @patch("apps.tenant_apps.girvi.views.reports.RateSource")
    @patch("apps.tenant_apps.girvi.views.reports.Rate")
    @patch("apps.tenant_apps.girvi.views.reports.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value={"girvi_report_view"})
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_get_renders_console_context(
        self,
        _role_name,
        _effective_permissions,
        mock_payment_voucher,
        mock_rate,
        mock_rate_source,
        mock_series,
        mock_outbox,
        mock_changelog,
        mock_render,
    ):
        request = self._request()
        response = SimpleNamespace(status_code=200)
        mock_render.return_value = response

        mock_payment_voucher.objects.count.return_value = 10
        mock_payment_voucher.objects.filter.side_effect = [
            SimpleNamespace(count=lambda: 8),
            SimpleNamespace(count=lambda: 2),
        ]
        mock_rate.objects.count.return_value = 6
        mock_rate_source.objects.count.return_value = 2
        mock_series.objects.count.return_value = 4
        mock_series.objects.filter.side_effect = [
            SimpleNamespace(count=lambda: 3),
            SimpleNamespace(count=lambda: 1),
            SimpleNamespace(count=lambda: 0),
        ]
        mock_outbox.objects.filter.return_value.count.return_value = 1
        mock_outbox.objects.filter.return_value.order_by.return_value.__getitem__.return_value = []
        mock_changelog.objects.select_related.return_value.order_by.return_value.__getitem__.return_value = []

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
