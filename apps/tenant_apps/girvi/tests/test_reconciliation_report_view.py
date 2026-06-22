from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.reports import loan_accounting_reconciliation_report


class LoanAccountingReconciliationReportViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.reports.render")
    @patch("apps.tenant_apps.girvi.views.reports.build_loan_accounting_reconciliation_report")
    def test_report_view_renders_selector_payload(
        self,
        mock_selector,
        mock_render,
    ):
        request = self.factory.get("/girvi/reports/reconciliation/")
        request.user = self.user
        request.tenant = SimpleNamespace(
            schema_name="tenant-1",
            owner=SimpleNamespace(is_authenticated=True),
            theme=None,
            logo=None,
        )

        mock_selector.return_value = {
            "rows": [{"loan_id": "GL-001"}],
            "counts": {
                "missing_disbursal_voucher": 1,
                "failed_payment_posting": 0,
                "release_without_voucher": 0,
                "posted_voucher_state_mismatch": 0,
            },
            "total_issues": 1,
            "scanned_loans": 5,
            "generated_at": "2026-06-22T10:00:00",
        }
        response = SimpleNamespace(status_code=200)
        mock_render.return_value = response

        result = loan_accounting_reconciliation_report(request)

        self.assertEqual(result, response)
        mock_selector.assert_called_once_with()
        context = mock_render.call_args.args[2]
        self.assertIn("report", context)
        self.assertIn("report_rows", context)
        self.assertIn("report_counts", context)
        self.assertEqual(context["report"]["total_issues"], 1)
