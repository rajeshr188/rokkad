import json
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.selectors import build_item_custody_status_payload


class ItemCustodyStatusSelectorTests(SimpleTestCase):
    def test_build_item_custody_status_payload_with_repledge(self):
        lender = SimpleNamespace(name="Lender A")
        taken_loan = SimpleNamespace(id=9, loan_id="TL-009", lender=lender)
        item = SimpleNamespace(
            id=11,
            custody_status="with_lender",
            get_custody_status_display=lambda: "With lender",
            is_repledged=True,
            repledged_to=taken_loan,
            is_available_for_release=False,
            is_available_for_repledge=False,
            can_be_returned_from_lender=True,
        )

        payload = build_item_custody_status_payload(item)

        self.assertEqual(payload["item_id"], 11)
        self.assertEqual(payload["custody_display"], "With lender")
        self.assertEqual(payload["repledged_to"]["loan_id"], "TL-009")
        self.assertTrue(payload["can_return"])

    def test_build_item_custody_status_payload_without_repledge(self):
        item = SimpleNamespace(
            id=21,
            custody_status="in_vault",
            get_custody_status_display=lambda: "In vault",
            is_repledged=False,
            repledged_to=None,
            is_available_for_release=True,
            is_available_for_repledge=True,
            can_be_returned_from_lender=False,
        )

        payload = build_item_custody_status_payload(item)

        self.assertEqual(payload["item_id"], 21)
        self.assertIsNone(payload["repledged_to"])
        self.assertTrue(payload["can_release"])
        self.assertTrue(payload["can_repledge"])
