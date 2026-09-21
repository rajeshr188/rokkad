import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.tenant_apps.data_portability import legacy_preview, opening_review as review
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.data_portability.tests.test_legacy_dump import NAMESPACE, row, source
from apps.tenant_apps.loans.tests.test_opening_validation import reviewed_opening


class OpeningReviewTests(SimpleTestCase):
    def test_version_two_checkpoint_is_reconciled_without_import_authority(self):
        from apps.tenant_apps.loans.tests.test_opening_continuation import collection_review
        document = collection_review()
        report, results = review.reconcile_documents([document])
        self.assertEqual(report["document_reconciled"], 1)
        self.assertEqual(results[0]["profile"], "loan-opening-review/2")
        self.assertFalse(report["import_ready"])
        self.assertFalse(results[0]["import_ready"])

    def prepare(self, data):
        summary, records = legacy_preview.build_preview(data, schema="tenant_a", source_namespace=NAMESPACE)
        legacy_preview.propose_collateral_exclusions(summary, records)
        before = copy.deepcopy((summary, records))
        documents = review.prepare_openings(summary, records)
        self.assertEqual((summary, records), before)
        return summary, records, documents

    def test_preparation_preserves_known_facts_and_never_invents_unknowns(self):
        summary, records, documents = self.prepare(source())
        doc = documents[0]
        self.assertEqual(doc["source"]["loan_id"], "girvi_loan:1")
        self.assertEqual(doc["source"]["selection_sha256"], summary["exclusion_proposal"]["selection_sha256"])
        self.assertEqual(doc["mapping"]["borrower_external_id"], "contact_customer:1")
        self.assertEqual(doc["collateral"][0]["original_principal"], "1000")
        self.assertEqual(doc["collateral"][0]["monthly_rate"], "1")
        self.assertEqual(doc["collateral"][0]["quantity"], 1)
        for field in ("balances", "cutover", "terms", "continuation", "obligations"):
            self.assertIsNone(doc[field])
        for field in ("gross_weight", "net_weight", "remaining_principal", "valuation"):
            self.assertIsNone(doc["collateral"][0][field])
        report, results = review.reconcile_documents(documents)
        self.assertEqual(report["loans"], 1)
        self.assertEqual(report["document_reconciled"], 0)
        self.assertEqual(report["loans_requiring_review"]["balances"], 1)
        self.assertFalse(results[0]["import_ready"])

    def test_excluded_and_released_loans_never_become_active_openings(self):
        data = source()
        data["tables"]["girvi_loanitem"]["1"]["weight"] = "0"
        _, records, documents = self.prepare(data)
        self.assertEqual(documents, [])
        self.assertEqual(len(records), 5)
        data = source()
        data["tables"]["girvi_release"]["1"] = row("girvi_release", id="1", loan_id="1", released_by_id="1", release_date="2021-02-01T00:00:00+00:00", release_id="R1")
        self.assertEqual(self.prepare(data)[2], [])

    def test_retained_source_errors_remain_blockers(self):
        data = source()
        data["tables"]["girvi_loan"]["1"]["loan_amount"] = "2000"
        _, _, documents = self.prepare(data)
        self.assertIn("PRINCIPAL_ITEM_MISMATCH", {i["code"] for i in documents[0]["source"]["errors"]})
        self.assertIn("SOURCE_ERRORS", {i["code"] for i in review.reconcile_documents(documents)[1][0]["issues"]})

    def test_requires_explicit_selection_and_one_tenant(self):
        summary, records = legacy_preview.build_preview(source(), schema="tenant_a", source_namespace=NAMESPACE)
        with self.assertRaises(PortabilityError):
            review.prepare_openings(summary, records)
        legacy_preview.propose_collateral_exclusions(summary, records)
        records[0]["source"]["schema"] = "tenant_b"
        with self.assertRaises(PortabilityError):
            review.prepare_openings(summary, records)

    def test_file_rejects_duplicates_nonfinite_invalid_utf8_and_limits(self):
        content = (legacy_preview.encode(reviewed_opening()) + "\n").encode()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "review.jsonl"
            for bad in (b"", b"\n", b"\xff", b'{"x":1,"x":2}\n', b'{"x":NaN}\n', b'{"x":"\\ud800"}\n', b"\x00\n", b"[" * 1500):
                path.write_bytes(bad)
                with self.subTest(bad=bad[:30]), self.assertRaises(PortabilityError):
                    review.read_documents(path)
            path.write_bytes(content)
            self.assertEqual(review.read_documents(path), [reviewed_opening()])
            for limit in ("MAX_LINE_BYTES", "MAX_BYTES", "MAX_LOANS"):
                with patch.object(review, limit, 1 if limit != "MAX_LOANS" else 0), self.assertRaises(PortabilityError):
                    review.read_documents(path)

    def test_batch_cannot_mix_scope_cutover_or_workspaces_or_duplicate_loans(self):
        first = reviewed_opening()
        with self.assertRaises(PortabilityError):
            review.reconcile_documents([first, first])
        for group, field, value in (("source", "schema", "tenant_b"), ("source", "namespace", NAMESPACE.upper()),
                                    ("source", "archive_sha256", "d" * 64), ("source", "selection_sha256", "d" * 64),
                                    ("mapping", "workspace_id", 2), ("cutover", "date", "2021-01-21"),
                                    ("cutover", "timezone", "UTC")):
            second = copy.deepcopy(first)
            second["source"]["loan_id"] = "girvi_loan:2"
            second[group][field] = value
            with self.subTest(group=group, field=field), self.assertRaises(PortabilityError):
                review.reconcile_documents([first, second])

    def test_review_output_escapes_source_text_and_preserves_all_issues(self):
        doc = reviewed_opening()
        doc["source"]["loan_id"] = "<script>alert(1)</script>"
        doc["balances"] = None
        with TemporaryDirectory() as directory:
            output = Path(directory) / "report"
            summary = review.write_review(output, [doc])
            self.assertFalse(summary["import_ready"])
            self.assertTrue((output / "COMPLETE").exists())
            self.assertEqual((output / ".gitignore").read_text(), "*\n")
            html = (output / "opening-review.html").read_text()
            self.assertNotIn("<script>", html)
            self.assertIn("&lt;script&gt;", html)
            self.assertIn("Missing evidence", html)
            self.assertIn("Operational readiness: not evaluated", html)
            self.assertEqual(summary["category_counts"], {"MISSING_EVIDENCE": 1})
            result = json.loads((output / "opening-results.jsonl").read_text())
            self.assertEqual(result["source_loan_id"], doc["source"]["loan_id"])
            with self.assertRaises(PortabilityError):
                review.write_review(output, [doc])

    def test_output_failure_never_gets_complete_marker(self):
        with TemporaryDirectory() as directory, patch.object(review, "MAX_LINE_BYTES", 1):
            output = Path(directory) / "report"
            with self.assertRaises(PortabilityError):
                review.write_review(output, [reviewed_opening()])
            self.assertFalse((output / "COMPLETE").exists())

    def test_commands_prepare_and_revalidate_with_no_database_access(self):
        with TemporaryDirectory() as directory, patch("apps.tenant_apps.data_portability.management.commands.preview_legacy_dump.inspect_archive", return_value=source()):
            output, checked = Path(directory) / "source", Path(directory) / "checked"
            stdout = io.StringIO()
            call_command("preview_legacy_dump", dump="source.dump", source_schema="tenant_a", source_namespace=NAMESPACE,
                         output_dir=str(output), propose_skip_incomplete_collateral=True, prepare_openings=True, stdout=stdout)
            self.assertTrue((output / "COMPLETE").exists())
            self.assertEqual(len((output / "records.jsonl").read_text().splitlines()), 5)
            self.assertIn("1 opening review candidates", stdout.getvalue())
            call_command("validate_loan_openings", input=str(output / "opening-candidates.jsonl"), output_dir=str(checked), stdout=stdout)
            self.assertEqual(json.loads((checked / "opening-summary.json").read_text())["loans"], 1)
            self.assertIn("0 documents reconciled", stdout.getvalue())
            with self.assertRaises(CommandError):
                call_command("preview_legacy_dump", dump="source.dump", source_schema="tenant_a", source_namespace=NAMESPACE,
                             output_dir=str(output), prepare_openings=True, stdout=stdout)
