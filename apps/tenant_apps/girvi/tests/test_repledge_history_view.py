from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.custody_views import repledge_history_report


class RepledgeHistoryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.custody_views.render")
    @patch("apps.tenant_apps.girvi.views.custody_views.build_repledge_history_read_model")
    def test_view_renders_selector_context(self, mock_selector, mock_render):
        request = self.factory.get(
            "/girvi/reports/repledge-history/",
            data={"status": "active", "customer": "11", "lender": "22"},
        )
        request.user = self.user
        request.tenant = SimpleNamespace(schema_name="tenant-1", owner=self.user)

        expected = {
            "history": [SimpleNamespace(id=1)],
            "total_active": 1,
            "total_returned": 0,
        }
        mock_selector.return_value = expected
        response = SimpleNamespace(status_code=200)
        mock_render.return_value = response

        result = repledge_history_report(request)

        self.assertEqual(result, response)
        mock_selector.assert_called_once_with(
            status="active",
            customer_id="11",
            lender_id="22",
        )
        self.assertEqual(mock_render.call_args.args[2], expected)
