import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.tenant_apps.data_portability.legacy_archive_preview import candidates, write_report
from apps.tenant_apps.data_portability.legacy_preview import build_preview
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.loans.services.archive_contract import parse
from .test_legacy_dump import source, row, NAMESPACE


class ArchivePreviewTests(SimpleTestCase):
    options = {"business_timezone": "Asia/Kolkata", "review_date": "2026-09-13"}

    def prepare(self, data=None):
        data = data or source()
        data["tables"]["girvi_release"]["1"] = row("girvi_release", id="1", loan_id="1",
            release_date="2020-12-31 20:00:00+00", released_by_id="1")
        return build_preview(data, schema="tenant_a", source_namespace=NAMESPACE)

    def test_claims_keep_unknowns_raw_graph_and_timezone(self):
        summary, records = self.prepare()
        result = next(candidates(summary, records, **self.options))
        self.assertIsNone(result["held_reason"])
        document = result["document"]
        self.assertEqual(document["facts"]["closed_on"], "2021-01-01")
        for field in ("payments", "original_principal", "reported_balance"):
            self.assertIsNone(document["facts"][field])
        self.assertIsNone(document["facts"]["collateral"][0]["net_weight"])
        self.assertEqual(document["source_records"][0]["facts"]["loan_amount"], "1000")
        self.assertEqual({r["source"]["table"] for r in document["source_records"][:-1]},
            {"girvi_loan", "girvi_loanitem", "girvi_release", "contact_customer", "girvi_series", "girvi_license"})

    def test_unreleased_excluded_and_profile_cannot_cross_source(self):
        summary, records = build_preview(source(), schema="tenant_a", source_namespace=NAMESPACE)
        self.assertEqual(list(candidates(summary, records, **self.options)), [])
        with self.assertRaises(PortabilityError):
            list(candidates(summary, records, **self.options, owner_profile="jcl-owner/2"))

    def test_zero_payment_is_preserved_missing_collateral_unknown(self):
        data = source()
        data["tables"]["girvi_loanitem"] = {}
        data["tables"]["girvi_loanpayment"]["1"] = row("girvi_loanpayment", id="1", loan_id="1",
            payment_amount="0", payment_date="2021-01-02 00:00:00+00")
        summary, records = self.prepare(data)
        result = next(candidates(summary, records, **self.options))
        self.assertIsNone(result["document"]["facts"]["collateral"])
        self.assertEqual(result["document"]["facts"]["payments"][0]["amount"], "0")

    def test_invalid_contract_is_held_with_source_preserved(self):
        data = source()
        data["tables"]["contact_customer"]["1"]["name"] = "x" * 256
        summary, records = self.prepare(data)
        result = next(candidates(summary, records, **self.options))
        self.assertTrue(result["held_reason"])
        self.assertEqual(result["document"]["facts"]["borrower_name"], "x" * 256)

    def test_description_mapping_retains_exact_evidence_and_other_controls_hold(self):
        data = source()
        raw = "Ring\r\nchain\tPendant"
        data["tables"]["girvi_loanitem"]["1"]["itemdesc"] = raw
        summary, records = self.prepare(data)
        result = next(candidates(summary, records, **self.options))
        self.assertIsNone(result["held_reason"])
        self.assertEqual(result["document"]["facts"]["collateral"][0]["description"], "Ring chain Pendant")
        self.assertEqual(result["transformations"][0]["before"], raw)
        self.assertEqual(next(r for r in result["document"]["source_records"] if r.get("source", {}).get("table") == "girvi_loanitem")["facts"]["itemdesc"], raw)
        data["tables"]["girvi_loanitem"]["1"]["itemdesc"] = "Ring\x7fchain"
        summary, records = self.prepare(data)
        self.assertTrue(next(candidates(summary, records, **self.options))["held_reason"])

    def test_timestamp_contradiction_is_not_hidden_by_same_business_date(self):
        from apps.tenant_apps.data_portability.legacy_archive_review import date_findings, select_pilot_case
        summary, records = self.prepare()
        result = next(candidates(summary, records, **self.options))
        result["date_findings"] = date_findings(result["document"], **self.options)
        self.assertEqual(result["date_findings"][0]["code"], "RELEASE_BEFORE_ORIGINATION")
        self.assertIsNone(select_pilot_case(result, result["document"], {}))

    def test_pilot_is_bounded_distinct_and_excludes_errors(self):
        from apps.tenant_apps.data_portability.legacy_archive_review import select_pilot_case
        summary, records = self.prepare()
        result = next(candidates(summary, records, **self.options))
        result["date_findings"] = []
        document = result["document"]
        for record in document["source_records"]:
            if "issues" in record:
                record["issues"] = []
        self.assertEqual(select_pilot_case(result, document, {}), "unknown-payments")
        self.assertIsNone(select_pilot_case(result, document, {"unknown-payments": result}))
        document["source_records"][0]["issues"] = [{"severity": "ERROR"}]
        self.assertIsNone(select_pilot_case(result, document, {}))

    def test_scoped_weight_and_multiple_release_claims(self):
        summary, records = self.prepare()
        from apps.tenant_apps.data_portability.legacy_owner_rules import NAMESPACE as owner_namespace
        summary.update(source_namespace=owner_namespace, source_schema="jcl")
        result = next(candidates(summary, records, **self.options, owner_profile="jcl-owner/2"))
        self.assertEqual(result["document"]["facts"]["collateral"][0]["net_weight"], "10")
        release = next(r for r in records if r["source"]["table"] == "girvi_release")
        import copy
        other = copy.deepcopy(release)
        other["source"]["id"] = "2"
        other["source"]["external_id"] = "girvi_release:2"
        other["facts"]["id"] = "2"
        records.append(other)
        result = next(candidates(summary, records, **self.options))
        self.assertIsNone(result["document"]["facts"]["closed_on"])
        self.assertTrue(any("multiple release" in note for note in result["mapping_notes"]))

    def test_report_roundtrip_escape_no_overwrite_and_no_database(self):
        data = source()
        data["tables"]["girvi_loan"]["1"]["loan_id"] = "<script>alert(1)</script>"
        self.prepare(data)
        with TemporaryDirectory() as temp:
            output = Path(temp) / "report"
            with patch("apps.tenant_apps.data_portability.management.commands.preview_legacy_closed_archive.inspect_archive", return_value=data):
                call_command("preview_legacy_closed_archive", dump="unused", source_schema="tenant_a",
                    source_namespace=NAMESPACE, output_dir=str(output), stdout=io.StringIO(), **self.options)
            report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(report["counts"]["schema_valid_candidates"], 1)
            self.assertEqual(report["counts"]["accepted"], 0)
            self.assertTrue((output / "COMPLETE").exists())
            self.assertTrue((output / "case-review.html").exists())
            self.assertEqual((output / ".gitignore").read_text(), "*\n")
            self.assertNotIn("<script>", (output / "review.html").read_text(encoding="utf-8"))
            self.assertEqual(len((output / "source-records.jsonl").read_text().splitlines()), sum(report["source"]["counts"].values()))
            with ZipFile(output / "candidates.zip") as bundle:
                self.assertEqual(parse(bundle.read(bundle.namelist()[0]))["facts"]["loan_number"], "<script>alert(1)</script>")
            summary, records = self.prepare()
            with self.assertRaises(PortabilityError):
                write_report(output, summary, records, **self.options)
