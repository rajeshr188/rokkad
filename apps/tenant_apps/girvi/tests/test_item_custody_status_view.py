import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.custody_views import api_item_custody_status


class ItemCustodyStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.custody_views.build_item_custody_status_payload")
    @patch("apps.tenant_apps.girvi.views.custody_views.get_object_or_404")
    def test_api_item_custody_status_delegates_payload_builder(
        self,
        mock_get_object,
        mock_payload,
    ):
        request = self.factory.get("/girvi/api/items/11/custody/")
        request.user = self.user
        request.tenant = SimpleNamespace(schema_name="tenant-1", owner=self.user)

        item = SimpleNamespace(id=11)
        mock_get_object.return_value = item
        mock_payload.return_value = {
            "item_id": 11,
            "custody_status": "with_lender",
            "custody_display": "With lender",
            "is_repledged": True,
            "repledged_to": {"id": 9, "loan_id": "TL-009", "lender": "Lender A"},
            "can_release": False,
            "can_repledge": False,
            "can_return": True,
        }

        response = api_item_custody_status(request, item_id=11)

        mock_payload.assert_called_once_with(item)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode("utf-8"))
        self.assertEqual(payload["item_id"], 11)
        self.assertEqual(payload["repledged_to"]["loan_id"], "TL-009")
