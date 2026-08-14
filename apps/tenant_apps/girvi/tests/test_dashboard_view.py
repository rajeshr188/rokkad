from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.dashboard import girvi_dashboard


class GirviDashboardViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.dashboard.render")
    @patch("apps.tenant_apps.girvi.views.dashboard.build_girvi_dashboard_read_model")
    def test_dashboard_uses_read_model_selector(
        self,
        mock_read_model,
        mock_render,
    ):
        request = self.factory.get("/girvi/")
        request.user = self.user
        request.tenant = SimpleNamespace(
            schema_name="test",
            owner=SimpleNamespace(is_authenticated=True),
            theme=None,
            logo=None,
        )

        mock_read_model.return_value = {
            "total_loans": 3,
            "unreleased_loans": 2,
            "released_loans": 1,
            "overdue_loans": 0,
            "total_loan_amount": 100,
            "total_releases": 1,
            "recent_releases": [],
            "total_licenses": 1,
            "active_licenses": 1,
            "total_series": 1,
            "active_series": 1,
            "total_boxes": 1,
            "total_payments": 9,
            "pending_payments": 4,
            "total_statements": 1,
            "total_notifications": 1,
            "pending_notifications": 1,
            "due_today": [],
            "operational_queue": {
                "due_today": [],
                "overdue_candidates": [],
                "npa_candidates": [],
                "cure_candidates": [],
                "notice_candidates": [],
                "counts": {
                    "due_today": 0,
                    "overdue_candidates": 0,
                    "npa_candidates": 0,
                    "cure_candidates": 0,
                    "notice_candidates": 0,
                },
            },
            "queue_counts": {
                "due_today": 0,
                "overdue_candidates": 0,
                "npa_candidates": 0,
                "cure_candidates": 0,
                "notice_candidates": 0,
            },
        }
        response = SimpleNamespace(status_code=200)
        mock_render.return_value = response

        result = girvi_dashboard(request)

        self.assertEqual(result, response)
        mock_read_model.assert_called_once_with(
            user=request.user,
            workspace=request.tenant,
        )
        context = mock_render.call_args.args[2]
        self.assertEqual(context["total_payments"], 9)
        self.assertEqual(context["pending_payments"], 4)
        self.assertIn("operational_queue", context)
        self.assertIn("queue_counts", context)
