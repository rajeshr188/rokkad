from django.test import SimpleTestCase

from apps.tenant_apps.data_portability import child_contracts, contracts
from apps.tenant_apps.data_portability.legacy_party_preparation import build_party_preparation
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture

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
        self.assertEqual(result["records"][child_contracts.CONTACT][0]["party_external_id"], master["id"])
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

    def test_legacy_source_system_shape_is_accepted(self):
        from apps.tenant_apps.data_portability.services import LEGACY_SOURCE_SYSTEM
        self.assertTrue(LEGACY_SOURCE_SYSTEM.fullmatch("legacy:6ca968d626474dbb8e3924f0c1a12ed6:jcl"))
        self.assertFalse(LEGACY_SOURCE_SYSTEM.fullmatch("legacy:6ca968d6-2647-4dbb-8e39-24f0c1a12ed6:jcl"))


class LegacyPartyImportTests(PortabilityFixture):
    def test_prepared_parent_and_children_commit_replay_and_isolate(self):
        from apps.tenant_apps.data_portability import services, children
        from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod

        prepared = build_party_preparation(source('jsk'), schema='jsk',
            source_namespace=NAMESPACE, source_profile='linode-jsk/1')
        with self.scoped():
            for profile, records in prepared['records'].items():
                content = ''.join(contracts.dump(row) + '\n' for row in records).encode('utf-8')
                batch = services.stage_import(workspace_id=self.a.pk, actor=self.actor,
                    content=content, filename='legacy.jsonl', source_system=prepared['source_system'], profile=profile)
                batch = self.ready(batch, mapping={})
                self.assertEqual(batch.state, 'READY', list(batch.rows.values_list('issues', flat=True)))
                self.commit(batch, acknowledge_warnings=True)
                self.commit(batch, acknowledge_warnings=True)
            party = Party.objects.get()
            self.assertEqual(PartyContactMethod.objects.get().party_id, party.pk)
            self.assertEqual(PartyAddress.objects.get().party_id, party.pk)
            self.assertIsNotNone(children.parent_for(prepared['records'][child_contracts.CONTACT][0], self.a.pk))
        with self.scoped(self.b):
            self.assertIsNone(children.parent_for(prepared['records'][child_contracts.CONTACT][0], self.b.pk))
            self.assertFalse(Party.objects.exists())
