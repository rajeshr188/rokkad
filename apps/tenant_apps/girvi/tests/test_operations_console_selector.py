from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.selectors import build_operations_console_read_model


class OperationsConsoleSelectorTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.integrations.dea_adapter.get_payment_voucher_posting_counts")
    @patch("apps.tenant_apps.girvi.services.get_rate_setup_counts")
    @patch("apps.tenant_apps.girvi.models.Series")
    @patch("apps.tenant_apps.girvi.models.LoanChangeLog")
    @patch("apps.tenant_apps.girvi.models.GirviPostingOutboxEvent")
    @patch("apps.tenant_apps.girvi.models.GirviPostingOutboxStatus")
    def test_build_operations_console_read_model_shape(
        self,
        mock_status,
        mock_outbox,
        mock_changelog,
        mock_series,
        mock_rate_counts,
        mock_payment_counts,
    ):
        mock_status.choices = [("failed", "Failed"), ("pending", "Pending")]
        mock_status.FAILED = "failed"
        mock_status.DEAD_LETTER = "dead_letter"

        mock_payment_counts.return_value = {
            "total": 12,
            "posted": 9,
            "pending": 3,
        }

        mock_series.objects.count.return_value = 5
        mock_series.objects.filter.side_effect = [
            SimpleNamespace(count=lambda: 4),
            SimpleNamespace(count=lambda: 1),
            SimpleNamespace(count=lambda: 0),
        ]

        mock_rate_counts.return_value = {"rates": 7, "sources": 2}

        # 1) outbox status counts dictionary comprehension
        # 2) failed-events queryset
        mock_outbox.objects.filter.side_effect = [
            SimpleNamespace(count=lambda: 1),
            SimpleNamespace(count=lambda: 2),
            SimpleNamespace(order_by=lambda *_args, **_kwargs: []),
        ]
        mock_changelog.objects.select_related.return_value.order_by.return_value.__getitem__.return_value = []

        payload = build_operations_console_read_model()

        self.assertEqual(payload["payment_counts"]["total"], 12)
        self.assertEqual(payload["series_summary"]["active"], 4)
        self.assertEqual(payload["rate_summary"]["rates"], 7)
        self.assertIn("failed", payload["outbox_counts"])
        self.assertIn("recent_audit_events", payload)
