from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.repledge_workflow import (
    RepledgeWorkflowService,
)


class _PostData(dict):
    def getlist(self, key):
        return self.get(key, [])


class RepledgeWorkflowServiceTests(SimpleTestCase):
    def test_parse_create_payload_reads_series_fallback(self):
        post_data = _PostData(
            {
                "item_ids": ["1", "2"],
                "lender_id": "4",
                "loan_amount": "5000",
                "loan_date": "2026-06-22",
                "notes": "bundle",
                "series": "7",
            }
        )

        payload = RepledgeWorkflowService.parse_create_payload(post_data)

        self.assertEqual(payload["item_ids"], ["1", "2"])
        self.assertEqual(payload["series_id"], "7")

    @patch("apps.tenant_apps.girvi.service_modules.repledge_workflow.create_repledge_from_items")
    def test_create_repledge_returns_success_result(self, create_mock):
        taken_loan = SimpleNamespace(id=8, loan_id="TL-008")
        create_mock.return_value = taken_loan
        post_data = _PostData({"item_ids": ["1"], "lender_id": "4", "loan_amount": "5000"})

        result = RepledgeWorkflowService.create_repledge(post_data, user=SimpleNamespace())

        self.assertTrue(result.success)
        self.assertEqual(result.taken_loan, taken_loan)
        self.assertEqual(result.selected_item_count, 1)

    @patch(
        "apps.tenant_apps.girvi.service_modules.repledge_workflow.create_repledge_from_items",
        side_effect=ValueError("invalid items"),
    )
    def test_create_repledge_returns_error_result_on_failure(self, _create_mock):
        post_data = _PostData({"item_ids": ["1"]})

        result = RepledgeWorkflowService.create_repledge(post_data, user=SimpleNamespace())

        self.assertFalse(result.success)
        self.assertIn("invalid items", result.error_message)
