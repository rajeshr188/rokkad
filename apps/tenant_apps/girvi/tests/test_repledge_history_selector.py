from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.selectors import build_repledge_history_read_model


class RepledgeHistorySelectorTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.models.custody_tracking.RepledgeHistory")
    def test_build_repledge_history_read_model_applies_filters(self, mock_history):
        history_qs = MagicMock()
        filtered_qs = MagicMock()
        customer_qs = MagicMock()
        lender_qs = MagicMock()

        mock_history.objects.select_related.return_value = history_qs
        history_qs.filter.return_value = filtered_qs
        filtered_qs.filter.return_value = customer_qs
        customer_qs.filter.return_value = lender_qs
        lender_qs.__getitem__.return_value = [SimpleNamespace(id=1)]

        count_qs = MagicMock()
        count_qs.count.side_effect = [3, 7]
        mock_history.objects.filter.return_value = count_qs

        payload = build_repledge_history_read_model(
            status="active",
            customer_id="11",
            lender_id="22",
        )

        self.assertIn("history", payload)
        self.assertEqual(payload["total_active"], 3)
        self.assertEqual(payload["total_returned"], 7)
        history_qs.filter.assert_called_once_with(returned_at__isnull=True)
        filtered_qs.filter.assert_called_once_with(loan_item__loan__borrower_id="11")
        customer_qs.filter.assert_called_once_with(taken_loan__lender_id="22")
