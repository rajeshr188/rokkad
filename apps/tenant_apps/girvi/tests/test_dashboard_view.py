from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.dashboard import girvi_dashboard


class GirviDashboardViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.dashboard.render")
    @patch("apps.tenant_apps.girvi.views.dashboard.Notification")
    @patch("apps.tenant_apps.girvi.views.dashboard.StatementItem")
    @patch("apps.tenant_apps.girvi.views.dashboard.LoanItemStorageBox")
    @patch("apps.tenant_apps.girvi.views.dashboard.Series")
    @patch("apps.tenant_apps.girvi.views.dashboard.License")
    @patch("apps.tenant_apps.girvi.views.dashboard.Release")
    @patch("apps.tenant_apps.girvi.views.dashboard.GivenLoan")
    @patch("apps.tenant_apps.girvi.views.dashboard.get_dashboard_payment_counts")
    def test_dashboard_uses_payment_count_selector(
        self,
        mock_payment_counts,
        mock_given_loan,
        mock_release,
        mock_license,
        mock_series,
        mock_storage_box,
        mock_statement_item,
        mock_notification,
        mock_render,
    ):
        request = self.factory.get("/girvi/")
        request.user = self.user

        given_manager = mock_given_loan.objects
        given_manager.count.return_value = 3
        given_manager.unreleased.return_value.count.return_value = 2
        given_manager.released.return_value.count.return_value = 1
        given_manager.non_performing_loans_stats.return_value.count.return_value = 0
        given_manager.get_queryset.return_value.total_loan_amount.return_value = 100

        mock_release.objects.count.return_value = 1
        mock_release.objects.order_by.return_value.__getitem__.return_value = []
        mock_license.objects.count.return_value = 1
        mock_license.objects.filter.return_value.count.return_value = 1
        mock_series.objects.count.return_value = 1
        mock_series.objects.filter.return_value.count.return_value = 1
        mock_storage_box.objects.count.return_value = 1
        mock_statement_item.objects.count.return_value = 1
        mock_notification.objects.count.return_value = 1
        mock_notification.objects.filter.return_value.count.return_value = 1
        mock_notification.StatusType.Draft = "Draft"
        mock_payment_counts.return_value = {
            "total_payments": 9,
            "pending_payments": 4,
        }
        response = SimpleNamespace(status_code=200)
        mock_render.return_value = response

        result = girvi_dashboard(request)

        self.assertEqual(result, response)
        mock_payment_counts.assert_called_once_with()
        context = mock_render.call_args.args[2]
        self.assertEqual(context["total_payments"], 9)
        self.assertEqual(context["pending_payments"], 4)
