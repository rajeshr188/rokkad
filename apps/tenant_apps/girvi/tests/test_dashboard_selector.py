from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.selectors import build_girvi_dashboard_read_model


class DashboardSelectorTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.selectors.GivenLoan")
    @patch("apps.tenant_apps.girvi.models.Release")
    @patch("apps.tenant_apps.girvi.models.License")
    @patch("apps.tenant_apps.girvi.models.Series")
    @patch("apps.tenant_apps.girvi.models.LoanItemStorageBox")
    @patch("apps.tenant_apps.girvi.models.StatementItem")
    @patch("apps.tenant_apps.girvi.selectors.get_pending_notifications_count")
    @patch("apps.tenant_apps.girvi.selectors.get_total_notifications_count")
    @patch("apps.tenant_apps.girvi.selectors.get_dashboard_payment_counts")
    @patch("apps.tenant_apps.girvi.selectors.build_dashboard_operational_queue")
    def test_build_girvi_dashboard_read_model_shape(
        self,
        mock_operational_queue,
        mock_payment_counts,
        mock_total_notifications,
        mock_pending_notifications,
        mock_statement_item,
        mock_storage_box,
        mock_series,
        mock_license,
        mock_release,
        mock_given_loan,
    ):
        given_manager = mock_given_loan.objects
        given_manager.count.return_value = 10
        given_manager.unreleased.return_value.count.return_value = 8
        given_manager.released.return_value.count.return_value = 2
        given_manager.non_performing_loans_stats.return_value.count.return_value = 1
        given_manager.get_queryset.return_value.total_loan_amount.return_value = 4500

        mock_release.objects.count.return_value = 2
        mock_release.objects.order_by.return_value.__getitem__.return_value = [SimpleNamespace(id=1)]
        mock_license.objects.count.return_value = 3
        mock_license.objects.filter.return_value.count.return_value = 2
        mock_series.objects.count.return_value = 4
        mock_series.objects.filter.return_value.count.return_value = 3
        mock_storage_box.objects.count.return_value = 12
        mock_statement_item.objects.count.return_value = 6
        mock_total_notifications.return_value = 9
        mock_pending_notifications.return_value = 5

        mock_payment_counts.return_value = {"total_payments": 7, "pending_payments": 1}
        mock_operational_queue.return_value = {
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
        }

        payload = build_girvi_dashboard_read_model(user=SimpleNamespace(), workspace=SimpleNamespace())

        self.assertEqual(payload["total_loans"], 10)
        self.assertEqual(payload["total_loan_amount"], 4500)
        self.assertEqual(payload["total_payments"], 7)
        self.assertEqual(payload["pending_notifications"], 5)
        self.assertIn("queue_counts", payload)

    def test_reconciliation_report_context_helper(self):
        from apps.tenant_apps.girvi.selectors import (
            build_loan_accounting_reconciliation_report_context,
        )

        report = {
            "rows": [{"loan_id": "GL-001"}],
            "counts": {"missing_disbursal_voucher": 1},
        }

        context = build_loan_accounting_reconciliation_report_context(report=report)

        self.assertEqual(context["report"], report)
        self.assertEqual(context["report_rows"], report["rows"])
        self.assertEqual(context["report_counts"], report["counts"])

    def test_operational_controls_context_helper(self):
        from apps.tenant_apps.girvi.selectors import build_operational_controls_report_context

        report = {
            "aging": {"rows": [{"loan_id": "GL-001"}], "bucket_counts": {"current": 1}},
            "custody": {"rows": []},
            "release_ready": {"rows": [], "ready_count": 0},
            "rate_exceptions": {"rows": [], "total": 0},
        }

        context = build_operational_controls_report_context(report=report)

        self.assertEqual(context["report"], report)
        self.assertEqual(context["aging_rows"], report["aging"]["rows"])
        self.assertEqual(context["aging_bucket_counts"], report["aging"]["bucket_counts"])
        self.assertEqual(context["rate_exception_total"], 0)
