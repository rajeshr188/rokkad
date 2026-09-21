from django.test import SimpleTestCase

from apps.tenant_apps.data_portability import child_contracts, contracts
from apps.tenant_apps.data_portability.legacy_party_preparation import build_party_preparation
from apps.tenant_apps.data_portability.parsers import PortabilityError

NAMESPACE = "6ca968d6-2647-4dbb-8e39-24f0c1a12ed6"


def source(schema="jcl"):
    tables = {"contact_customer": {"1": {"id": "1", "created": "2025-01-01T00:00:00+00:00", "updated": "", "name": "Asha", "firstname": "", "lastname": "", "gender": "", "religion": "", "customer_type": "", "relatedas": "S/O", "relatedto": "Ram", "active": "t", "created_by_id": "1"}},
              "contact_contact": {"2": {"id": "2", "created": "2025-01-01T00:00:00+00:00", "contact_type": "M", "phone_number": "9876543210", "last_updated": "", "customer_id": "1", "is_verified": "f", "is_default": "t"}},
              "contact_address": {"3": {"id": "3", "area": "Area", "created": "2025-01-01T00:00:00+00:00", "doorno": "1", "zipcode": "560001", "last_updated": "", "street": "Road", "city": "Bengaluru", "customer_id": "1", "is_verified": "f", "is_default": "t"}},
              "girvi_license": {}, "girvi_series": {}, "girvi_loan": {}, "girvi_loanitem": {}, "girvi_loanpayment": {}, "girvi_release": {}}
    return {"source_schema": schema, "tables": tables}


class LegacyPartyPreparationTests(SimpleTestCase):
    def test_prepares_deterministic_legacy_source_records(self):
        result = build_party_preparation(source("jsk"), schema="jsk", source_namespace=NAMESPACE, source_profile="linode-jsk/1")
        self.assertEqual(result["counts"], {contracts.PROFILE: 1, child_contracts.CONTACT: 1, child_contracts.ADDRESS: 1})
        self.assertEqual(result["source_system"], "legacy:6ca968d626474dbb8e3924f0c1a12ed6:jsk")
        master = result["records"][contracts.PROFILE][0]
        self.assertEqual(master["relation_kind"], "SON_OF")
        self.assertEqual(master["source_refs"][0]["external_id"], "contact_customer:1")
        self.assertFalse(result["invalid"])

    def test_profile_mismatch_fails_closed(self):
        with self.assertRaises(PortabilityError):
            build_party_preparation(source(), schema="jcl", source_namespace=NAMESPACE, source_profile="linode-jsk/1")

    def test_relationship_without_name_becomes_a_review_item_not_an_invalid_party(self):
        data = source("jsk")
        data["tables"]["contact_customer"]["1"]["relatedto"] = ""
        result = build_party_preparation(data, schema="jsk", source_namespace=NAMESPACE, source_profile="linode-jsk/1")
        self.assertIsNone(result["records"][contracts.PROFILE][0]["relation_kind"])
        self.assertFalse(result["invalid"])
        self.assertEqual(result["review"][0]["code"], "RELATION_NAME_REQUIRED")
