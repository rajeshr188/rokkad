import copy
import hashlib

from django.test import SimpleTestCase

from apps.tenant_apps.data_portability.legacy_preview import build_preview, encode
from apps.tenant_apps.data_portability.legacy_profiles import CORRECTION_LEDGER_VERSION, CORRECTIONS, PROFILES, apply_corrections
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.data_portability.tests.test_legacy_dump import NAMESPACE, source


class LegacySourceProfileTests(SimpleTestCase):
    def test_purity_corrections_are_exact_versioned_rows_and_preserve_raw_hashes(self):
        for profile in ("linode-jsk/2", "linode-lakshmi/2"):
            schema = PROFILES[profile].schema
            data = source(schema)
            corrections = [c for c in CORRECTIONS if c["profile"] == profile]
            self.assertEqual(len(corrections), 3)
            for correction in corrections:
                item = copy.deepcopy(data["tables"]["girvi_loanitem"]["1"])
                item.update(id=correction["source_id"], purity=correction["original"])
                data["tables"]["girvi_loanitem"][item["id"]] = item
            # An unrelated bad value remains bad, even under the new profile.
            data["tables"]["girvi_loanitem"]["1"]["purity"] = "150.00"
            original = copy.deepcopy(data)
            _, old = build_preview(data, schema=schema, source_namespace=NAMESPACE, source_profile=profile[:-1] + "1")
            self.assertTrue(all(r["source"]["correction"] is None for r in old))
            _, records = build_preview(data, schema=schema, source_namespace=NAMESPACE, source_profile=profile)
            indexed = {r["source"]["external_id"]: r for r in records}
            for correction in corrections:
                record = indexed["girvi_loanitem:" + correction["source_id"]]
                raw = data["tables"]["girvi_loanitem"][correction["source_id"]]
                self.assertEqual(record["facts"]["purity"], "100.00")
                self.assertEqual(record["source"]["correction"]["original"], raw["purity"])
                self.assertEqual(record["source"]["correction"]["ledger"], "linode-production-corrections/2")
                self.assertEqual(record["source_sha256"], hashlib.sha256(encode(raw).encode()).hexdigest())
            self.assertEqual(indexed["girvi_loanitem:1"]["facts"]["purity"], "150.00")
            self.assertEqual(data, original)
            effective, _ = apply_corrections(data["tables"], profile_key=profile)
            _, evidence = apply_corrections(effective, profile_key=profile)
            self.assertTrue(all(e["state"] == "ALREADY_CORRECTED_AT_SOURCE" for e in evidence.values()))
            effective["girvi_loanitem"][corrections[0]["source_id"]]["purity"] = "99.00"
            with self.assertRaisesRegex(PortabilityError, "does not match"):
                apply_corrections(effective, profile_key=profile)
            del effective["girvi_loanitem"][corrections[0]["source_id"]]
            with self.assertRaisesRegex(PortabilityError, "does not match"):
                apply_corrections(effective, profile_key=profile)

    def jcl_source_with_corrected_loan(self):
        data = source("jcl")
        loan = copy.deepcopy(data["tables"]["girvi_loan"]["1"])
        loan.update(id="29887", loan_id="R09911", loan_date="2026-12-16 09:47:00+00")
        item = copy.deepcopy(data["tables"]["girvi_loanitem"]["1"])
        item.update(id="29887", loan_id="29887")
        data["tables"]["girvi_loan"]["29887"] = loan
        data["tables"]["girvi_loanitem"]["29887"] = item
        return data, loan

    def test_profiles_cover_exactly_the_three_discovered_tenants(self):
        self.assertEqual({profile.schema for profile in PROFILES.values()}, {"jcl", "jsk", "lakshmipawnbroker"})

    def test_jcl_effective_fact_is_corrected_but_source_hash_and_evidence_preserve_original(self):
        data, original = self.jcl_source_with_corrected_loan()
        summary, records = build_preview(data, schema="jcl", source_namespace=NAMESPACE, source_profile="linode-jcl/1")
        record = next(record for record in records if record["source"]["table"] == "girvi_loan" and record["source"]["id"] == "29887")
        self.assertEqual(summary["source_profile"], "linode-jcl/1")
        self.assertEqual(record["facts"]["loan_date"], "2025-12-16 09:47:00+00")
        self.assertEqual(record["source"]["correction"]["ledger"], CORRECTION_LEDGER_VERSION)
        self.assertEqual(record["source"]["correction"]["original"], original["loan_date"])
        self.assertEqual(record["source_sha256"], hashlib.sha256(encode(original).encode("utf-8")).hexdigest())
        self.assertEqual(data["tables"]["girvi_loan"]["29887"]["loan_date"], "2026-12-16 09:47:00+00")

    def test_jcl_profile_rejects_missing_or_unapproved_source_correction(self):
        with self.assertRaisesRegex(PortabilityError, "reviewed correction"):
            build_preview(source("jcl"), schema="jcl", source_namespace=NAMESPACE, source_profile="linode-jcl/1")
        data, _ = self.jcl_source_with_corrected_loan()
        data["tables"]["girvi_loan"]["29887"]["loan_date"] = "2025-12-16 09:47:00+00"
        _, records = build_preview(data, schema="jcl", source_namespace=NAMESPACE, source_profile="linode-jcl/1")
        record = next(record for record in records if record["source"]["id"] == "29887")
        self.assertEqual(record["source"]["correction"]["state"], "ALREADY_CORRECTED_AT_SOURCE")
        data["tables"]["girvi_loan"]["29887"]["loan_date"] = "2024-12-16 09:47:00+00"
        with self.assertRaisesRegex(PortabilityError, "does not match"):
            build_preview(data, schema="jcl", source_namespace=NAMESPACE, source_profile="linode-jcl/1")

    def test_profile_schema_mismatch_and_other_tenants_fail_closed_or_preserve_source(self):
        with self.assertRaisesRegex(PortabilityError, "does not match"):
            build_preview(source("jsk"), schema="jsk", source_namespace=NAMESPACE, source_profile="linode-jcl/1")
        for schema, profile in (("jsk", "linode-jsk/1"), ("lakshmipawnbroker", "linode-lakshmi/1")):
            with self.subTest(schema=schema):
                data = source(schema)
                summary, records = build_preview(data, schema=schema, source_namespace=NAMESPACE, source_profile=profile)
                self.assertEqual(summary["source_profile"], profile)
                self.assertTrue(all(record["source"]["correction"] is None for record in records))
