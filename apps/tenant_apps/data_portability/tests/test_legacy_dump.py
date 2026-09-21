import copy
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.tenant_apps.data_portability import legacy_dump as dump, legacy_preview as preview
from apps.tenant_apps.data_portability.parsers import PortabilityError

NAMESPACE = "290f318a-6523-45a9-aa42-56e675be34ab"


def row(table, **values):
    return {field: values.get(field) for field in dump.COLUMNS[table]}


def source(schema="tenant_a"):
    tables = {table: {} for table in dump.COLUMNS}
    def add(table, **values):
        tables[table][values["id"]] = row(table, **values)
    add("contact_customer", id="1", name="Asha", active="t", relatedas="s", relatedto="Parent")
    add("girvi_license", id="1", name="Old licence", renewal_date="2020-01-01")
    add("girvi_series", id="1", name="A", license_id="1", max_limit="5", is_active="t")
    add("girvi_loan", id="1", loan_id="A00001", customer_id="1", series_id="1",
        loan_date="2021-01-01 00:00:00+00", loan_type="Given", interest_type="Simple",
        loan_amount="1000", interest="10", tenure="3", value="2000")
    add("girvi_loanitem", id="1", loan_id="1", itemtype="Gold", itemdesc="Ring",
        loanamount="1000", interestrate="1", interest="10", quantity="1", weight="10", purity="90")
    return {"tables": tables, "source_schema": schema, "archive_sha256": "a" * 64,
            "schemas": {schema: [*tables, "auth_permission", "dea_account"]}}


def copy_bytes(extracted):
    chunks = [b"-- untrusted archive SQL is inert\nSELECT dangerous_function();\n"]
    for table, rows in extracted["tables"].items():
        headers = sorted(next(iter(rows.values())).keys() if rows else dump.COLUMNS[table])
        chunks.append(f"COPY {extracted['source_schema']}.{table} ({', '.join(headers)}) FROM stdin;\n".encode())
        for data in rows.values():
            values = []
            for header in headers:
                value = data[header]
                values.append(b"\\N" if value is None else value.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r").encode())
            chunks.append(b"\t".join(values) + b"\n")
        chunks.append(b"\\.\n")
    return b"".join(chunks)


class CopyParserTests(SimpleTestCase):
    def test_known_later_columns_are_preserved_but_arbitrary_changes_fail(self):
        data=source()
        data['tables']['girvi_loanitem']['1']['is_repledged']='f'
        data['tables']['girvi_series']['1']['loan_type']='Given'
        self.assertEqual(dump.parse_copy(copy_bytes(data),'tenant_a'), data['tables'])
        data['tables']['girvi_loanitem']['1']['unexpected']='value'
        with self.assertRaises(PortabilityError):
            dump.parse_copy(copy_bytes(data),'tenant_a')

    def test_copy_decoding_preserves_text_null_and_literal_backslashes(self):
        data = source()
        data["tables"]["contact_customer"]["1"]["name"] = "தமிழ்\tline\n\\N\\."
        self.assertEqual(dump.parse_copy(copy_bytes(data), "tenant_a"), data["tables"])
        self.assertEqual(dump.decode_copy_field(b"\\141\\x62"), "ab")
        for invalid in (b"\\", b"\\x", b"\\777", b"\\q", b"\\000", b"\xff"):
            with self.subTest(invalid=invalid), self.assertRaises(PortabilityError):
                dump.decode_copy_field(invalid)

    def test_scope_duplicate_shape_and_truncation_fail_closed(self):
        content = copy_bytes(source())
        variants = [content.replace(b"tenant_a.contact_customer", b"tenant_b.contact_customer"),
                    content.replace(b"active, ", b"unexpected, ", 1),
                    content + content, content[:-3], content.replace(b"COPY tenant_a.contact_customer", b"COPY public.contact_customer")]
        for value in variants:
            with self.subTest(value=value[:50]), self.assertRaises(PortabilityError):
                dump.parse_copy(value, "tenant_a")
        with self.assertRaises(PortabilityError):
            dump.parse_copy(content, "public")

    def test_duplicate_keys_and_bounded_rows_fields_lines(self):
        data = source()
        data["tables"]["contact_customer"]["2"] = data["tables"]["contact_customer"]["1"]
        with self.assertRaises(PortabilityError):
            dump.parse_copy(copy_bytes(data), "tenant_a")
        with patch.object(dump, "MAX_ROWS", 1), self.assertRaises(PortabilityError):
            dump.parse_copy(copy_bytes(source()), "tenant_a")
        with patch.object(dump, "MAX_FIELD_BYTES", 2), self.assertRaises(PortabilityError):
            dump.decode_copy_field(b"long")
        with patch.object(dump, "MAX_LINE_BYTES", 10), self.assertRaises(PortabilityError):
            dump.parse_copy(copy_bytes(source()), "tenant_a")
        with patch.object(dump, "MAX_EXTRACT_BYTES", 1), self.assertRaises(PortabilityError):
            dump.parse_copy(b"long", "tenant_a")

    def test_inventory_never_confuses_table_data_and_excludes_public(self):
        toc = b"1; 1259 10 TABLE tenant_a girvi_loan owner\n2; 0 10 TABLE DATA tenant_a girvi_loan owner\n3; 1259 11 TABLE public girvi_loan owner\n"
        self.assertEqual(dump.archive_inventory(toc), {"tenant_a": ["girvi_loan"]})
        for schema in ("tenant.*", "tenant-a", "../tenant", "tenant;drop", "public"):
            with self.assertRaises(PortabilityError):
                dump.source_schema(schema)

    def test_copy_rejects_missing_tables_bad_width_and_nonascii_headers(self):
        content = copy_bytes(source())
        for invalid in (b"SELECT 1;", content.replace(b"Asha", b"Asha\textra", 1),
                        content.replace(b"active,", "actívé,".encode(), 1)):
            with self.subTest(invalid=invalid[:40]), self.assertRaises(PortabilityError):
                dump.parse_copy(invalid, "tenant_a")

    def test_selected_inventory_ignores_unsupported_sibling_but_keeps_own_guards(self):
        own = b"1; 1259 10 TABLE tenant_a girvi_loan owner\n"
        sibling = b"2; 1259 11 TABLE tenant-b girvi_loan owner\n"
        self.assertEqual(dump.archive_inventory(own+sibling, schema="tenant_a"),
                         {"tenant_a": ["girvi_loan"]})
        self.assertEqual(dump.archive_inventory(sibling, schema="tenant_a"), {})
        for content, schema in ((own+sibling, None), (own+own, "tenant_a"),
                                (own+b"3; 1259 12 TABLE tenant_a bad-table owner\n", "tenant_a"),
                                (sibling, "tenant-b"), (own, "public")):
            with self.subTest(schema=schema, content=content), self.assertRaises(PortabilityError):
                dump.archive_inventory(content, schema=schema)


class LegacyPreviewTests(SimpleTestCase):
    def test_later_custody_and_series_claims_hold_affected_loans(self):
        for value in ('t', None, 'invalid'):
            data=source()
            data['tables']['girvi_loanitem']['1']['is_repledged']=value
            summary, records=self.build(data)
            self.assertEqual(summary['issue_counts']['REPLEDGE_CUSTODY_REVIEW'],1)
            loan=next(r for r in records if r['source']['table']=='girvi_loan')
            self.assertTrue(any(i['code']=='LINKED_ITEM_ISSUE' for i in loan['issues']))
        for value in ('Taken', None, ''):
            data=source()
            data['tables']['girvi_series']['1']['loan_type']=value
            summary,_=self.build(data)
            self.assertEqual(summary['issue_counts']['UNSUPPORTED_SERIES_LOAN_TYPE'],1)
        data=source()
        data['tables']['girvi_loanitem']['1']['is_repledged']='f'
        data['tables']['girvi_series']['1']['loan_type']='Given'
        summary,records=self.build(data)
        self.assertEqual(summary['records_with_errors'],0)
        self.assertEqual(next(r for r in records if r['source']['table']=='girvi_loanitem')['facts']['is_repledged'],'f')

    def build(self, data):
        return preview.build_preview(data, schema=data["source_schema"], source_namespace=NAMESPACE)

    def test_reference_identity_is_stable_and_tenant_specific(self):
        data = source()
        summary, records = self.build(data)
        modified = copy.deepcopy(data)
        modified["tables"]["contact_customer"]["1"]["name"] = "Changed name"
        _, changed = self.build(modified)
        _, other = self.build(source("tenant_b"))
        self.assertEqual(records[0]["proposed_id"], changed[0]["proposed_id"])
        self.assertEqual(records[0]["source"], changed[0]["source"])
        self.assertNotEqual(records[0]["source_sha256"], changed[0]["source_sha256"])
        self.assertNotEqual(records[0]["proposed_id"], other[0]["proposed_id"])
        loan = next(r for r in records if r["source"]["table"] == "girvi_loan")
        self.assertEqual(loan["references"]["customer_id"]["external_id"], "contact_customer:1")
        self.assertEqual(loan["facts"]["loan_id"], "A00001")
        self.assertEqual(summary["loan_cohorts"], {"UNRELEASED": 1})
        self.assertFalse(any(r["import_ready"] for r in records))
        self.assertIsNone(summary["destination_workspace"])
        with self.assertRaises(PortabilityError):
            preview.build_preview(data, schema="tenant_b", source_namespace=NAMESPACE)

    def test_release_without_payment_keeps_fact_and_does_not_invent_settlement(self):
        data = source()
        data["tables"]["girvi_release"]["1"] = row("girvi_release", id="1", loan_id="1", released_by_id="1", release_date="2021-02-01 00:00:00+00", release_id="R00001")
        summary, records = self.build(data)
        loan = next(r for r in records if r["source"]["table"] == "girvi_loan")
        self.assertEqual(loan["review_route"], "RELEASED_RECORD_REVIEW")
        self.assertEqual(summary["counts"]["girvi_loanpayment"], 0)
        self.assertEqual(summary["records_with_errors"], 0)
        self.assertFalse(loan["import_ready"])

    def test_missing_references_and_financial_discrepancies_are_reported(self):
        data = source()
        data["tables"]["girvi_loan"]["1"].update(customer_id="99", loan_amount="2000", interest="15")
        data["tables"]["girvi_loanpayment"]["1"] = row("girvi_loanpayment", id="1", loan_id="1", payment_date="2020-12-31 00:00:00+00", payment_amount="100", principal_payment="90", interest_payment="20", with_release="f")
        summary, records = self.build(data)
        for code in ("MISSING_REFERENCE", "PRINCIPAL_ITEM_MISMATCH", "INTEREST_ITEM_MISMATCH", "DATE_BEFORE_LOAN", "PAYMENT_SPLIT_MISMATCH", "LINKED_EVENT_ISSUE"):
            self.assertEqual(summary["issue_counts"][code], 1)
        self.assertFalse(any(r["import_ready"] for r in records))

    def test_invalid_dates_numbers_and_child_issues(self):
        data = source()
        data["tables"]["girvi_loan"]["1"].update(loan_date="2021-01-01", loan_amount="NaN", tenure="Infinity")
        data["tables"]["girvi_loanitem"]["1"].update(weight="-2", purity="101")
        summary, _ = self.build(data)
        for code in ("INVALID_DATE", "INVALID_NUMBER", "NEGATIVE_NUMBER", "INVALID_PURITY", "LINKED_ITEM_ISSUE"):
            self.assertIn(code, summary["issue_counts"])

    def test_duplicate_numbers_releases_and_orphan_children_are_explicit(self):
        data = source()
        data["tables"]["girvi_loan"]["2"] = {**data["tables"]["girvi_loan"]["1"], "id": "2"}
        for pk in ("1", "2"):
            data["tables"]["girvi_release"][pk] = row("girvi_release", id=pk, loan_id="1", release_date="2021-02-01 00:00:00+00", released_by_id="1")
        data["tables"]["contact_contact"]["1"] = row("contact_contact", id="1", customer_id="999", is_default="f", is_verified="f")
        summary, _ = self.build(data)
        self.assertEqual(summary["issue_counts"]["DUPLICATE_LOAN_NUMBER"], 2)
        self.assertEqual(summary["issue_counts"]["MULTIPLE_RELEASES"], 1)
        self.assertEqual(summary["issue_counts"]["MISSING_REFERENCE"], 1)

    def test_artifacts_escape_html_preserve_source_and_never_overwrite(self):
        data = source()
        data["tables"]["girvi_loan"]["1"].update(loan_id='<script>alert("x")</script>', loan_amount="0")
        summary, records = self.build(data)
        html = preview.render_html(summary, records)
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        with TemporaryDirectory() as directory:
            output = Path(directory) / "preview"
            preview.write_preview(output, summary, records)
            self.assertTrue((output / "COMPLETE").is_file())
            self.assertEqual(json.loads((output / "summary.json").read_text()), summary)
            self.assertEqual(len((output / "records.jsonl").read_text(encoding="utf-8").splitlines()), len(records))
            with self.assertRaises(PortabilityError):
                preview.write_preview(output, summary, records)


class LegacyArchiveCommandTests(SimpleTestCase):
    def test_command_does_not_query_database(self):
        data = source()
        with TemporaryDirectory() as directory, patch("apps.tenant_apps.data_portability.management.commands.preview_legacy_dump.inspect_archive", return_value=data):
            output = io.StringIO()
            call_command("preview_legacy_dump", dump="source.dump", source_schema="tenant_a", source_namespace=NAMESPACE, output_dir=str(Path(directory)/"report"), stdout=output)
            self.assertIn("Nothing imported", output.getvalue())
        # SimpleTestCase rejects all database queries by default.

    def test_missing_namespace_and_inventory_mode_validation(self):
        with self.assertRaises(CommandError):
            call_command("preview_legacy_dump", dump="source.dump", source_schema="tenant_a", output_dir="unused")
        with self.assertRaises(CommandError):
            call_command("preview_legacy_dump", dump="source.dump", list_schemas=True, output_dir="unused")
        with self.assertRaises(PortabilityError):
            preview.namespace_uuid("00000000-0000-0000-0000-000000000000")

    def test_archive_uses_frozen_snapshot_and_only_selected_tables(self):
        data = source()
        toc = ''.join(f"{i}; 1259 {i} TABLE tenant_a {table} owner\n" for i, table in enumerate(data["tables"], 1)).encode()
        toc += b"100; 1259 100 TABLE unrelated-tenant girvi_loan owner\n"
        calls = []
        def run(executable, args, limit):
            calls.append(args)
            self.assertEqual(Path(args[-1]).read_bytes(), b"PGDMPfixture")
            return toc if args[0] == "--list" else copy_bytes(data)
        with TemporaryDirectory() as directory, patch.object(dump.shutil, "which", return_value="pg_restore"), patch.object(dump, "_run_restore", side_effect=run):
            archive = Path(directory)/"source.dump"
            archive.write_bytes(b"PGDMPfixture")
            result = dump.inspect_archive(archive, schema="tenant_a")
        self.assertEqual(result["tables"], data["tables"])
        self.assertIn("--schema=tenant_a", calls[1])
        self.assertIn("--file=-", calls[1])
        self.assertNotIn("--dbname", calls[1])
        self.assertFalse(Path(calls[0][-1]).exists())

    def test_bad_archives_and_unknown_schema_do_not_extract_data(self):
        with TemporaryDirectory() as directory:
            archive = Path(directory)/"source.dump"
            archive.write_bytes(b"not a custom archive")
            with self.assertRaises(PortabilityError):
                dump.inspect_archive(archive, schema="tenant_a")
            archive.write_bytes(b"PGDMPfixture")
            with patch.object(dump, "MAX_ARCHIVE_BYTES", 5), self.assertRaises(PortabilityError):
                dump.inspect_archive(archive, schema="tenant_a")
            with patch.object(dump.shutil, "which", return_value="pg_restore"), patch.object(dump, "_run_restore", return_value=b"") as restore:
                with self.assertRaises(PortabilityError):
                    dump.inspect_archive(archive, schema="missing")
                self.assertEqual(restore.call_count, 1)

    def test_report_write_failure_never_marks_complete(self):
        data = source()
        summary, records = preview.build_preview(data, schema="tenant_a", source_namespace=NAMESPACE)
        with TemporaryDirectory() as directory:
            output = Path(directory)/"report"
            with patch.object(preview, "render_html", side_effect=OSError("disk unavailable")), self.assertRaises(PortabilityError):
                preview.write_preview(output, summary, records)
            self.assertFalse((output/"COMPLETE").exists())

    def test_subprocess_failure_size_and_timeout_have_safe_errors(self):
        # A local Python helper exercises real pipe limits/termination without a DB.
        # pg_restore-specific --no-password is consumed by this mock command builder.
        original = subprocess.Popen
        def helper(code):
            return patch.object(dump.subprocess, "Popen", side_effect=lambda args, **kwargs: original([sys.executable, "-c", code], **kwargs))
        with helper("print('a' * 10000)"), self.assertRaises(PortabilityError):
            dump._run_restore("ignored", [], 10)
        with helper("import sys; sys.stderr.write('private secret'); sys.exit(1)"), self.assertRaisesRegex(PortabilityError, "could not read"):
            dump._run_restore("ignored", [], 100)
        with helper("import time; time.sleep(10)"), patch.object(dump, "EXTRACT_TIMEOUT", 0.1), self.assertRaisesRegex(PortabilityError, "time limit"):
            dump._run_restore("ignored", [], 100)


class CollateralExclusionProposalTests(SimpleTestCase):
    def build(self, data):
        return preview.build_preview(data, schema=data["source_schema"], source_namespace=NAMESPACE)

    def test_skip_is_proposed_and_preserves_source_rows_hashes_issues(self):
        data = source()
        data["tables"]["girvi_loanitem"]["1"]["weight"] = "0"
        summary, records = self.build(data)
        original = copy.deepcopy(records)
        preview.propose_collateral_exclusions(summary, records)
        proposal = summary["exclusion_proposal"]
        self.assertEqual(proposal["excluded_loans"], 1)
        self.assertFalse(proposal["approved"])
        self.assertIsNone(proposal["age_cutoff"])
        self.assertEqual(proposal["groups"][0]["source_principal_known_sum"], "1000")
        self.assertEqual(len(records), len(original))
        for before, after in zip(original, records):
            for field in ("facts", "source_sha256", "source", "proposed_id", "issues", "review_route"):
                self.assertEqual(before[field], after[field])
            self.assertFalse(after["import_ready"])
        self.assertNotIn("exclusion_proposal", records[0])  # Customer remains available.
        item = next(r for r in records if r["source"]["table"] == "girvi_loanitem")
        self.assertEqual(item["exclusion_proposal"]["disposition"], "SKIP_WITH_LOAN")

    def test_whole_loan_graph_is_marked_when_one_item_is_incomplete(self):
        data = source()
        data["tables"]["girvi_loanitem"]["2"] = {**data["tables"]["girvi_loanitem"]["1"], "id": "2", "weight": "0"}
        data["tables"]["girvi_loanpayment"]["1"] = row("girvi_loanpayment", id="1", loan_id="1", payment_date="2021-02-01 00:00:00+00", payment_amount="10", principal_payment="0", interest_payment="10", with_release="t")
        data["tables"]["girvi_release"]["1"] = row("girvi_release", id="1", loan_id="1", release_date="2021-02-01 00:00:00+00", released_by_id="1")
        summary, records = self.build(data)
        preview.propose_collateral_exclusions(summary, records)
        graph = [r for r in records if r["source"]["table"] in {"girvi_loanitem", "girvi_loanpayment", "girvi_release"}]
        self.assertEqual(len(graph), 4)
        self.assertTrue(all(r["exclusion_proposal"]["disposition"] == "SKIP_WITH_LOAN" for r in graph))
        self.assertEqual(summary["exclusion_proposal"]["groups"][2]["loans"], 1)

    def test_no_age_payment_or_metal_filter_is_inferred(self):
        data = source()
        data["tables"]["girvi_loan"]["1"]["loan_date"] = "1990-01-01 00:00:00+00"
        data["tables"]["girvi_loanitem"]["1"]["itemtype"] = "Bronze"
        summary, records = self.build(data)
        preview.propose_collateral_exclusions(summary, records)
        self.assertEqual(summary["exclusion_proposal"]["excluded_loans"], 0)
        self.assertIn("NO_PAYMENT_ROWS", summary["issue_counts"])
        self.assertIn("METAL_MAPPING_REQUIRED", summary["issue_counts"])

    def test_missing_items_invalid_values_and_description_are_explicit(self):
        for field, value, reason in (("weight", None, "INVALID_ITEM_WEIGHT"),
                                    ("purity", "101", "INVALID_ITEM_PURITY"),
                                    ("quantity", "1.5", "INVALID_ITEM_QUANTITY"),
                                    ("loanamount", "0", "INVALID_ITEM_LOANAMOUNT"),
                                    ("itemdesc", " ", "MISSING_ITEM_DESCRIPTION")):
            data = source()
            data["tables"]["girvi_loanitem"]["1"][field] = value
            summary, records = self.build(data)
            preview.propose_collateral_exclusions(summary, records)
            self.assertEqual(summary["exclusion_proposal"]["reasons"], {reason: 1})
        data["tables"]["girvi_loanitem"] = {}
        summary, records = self.build(data)
        preview.propose_collateral_exclusions(summary, records)
        self.assertEqual(summary["exclusion_proposal"]["reasons"], {"NO_STRUCTURED_ITEMS": 1})

    def test_unknown_principal_is_counted_and_fingerprint_changes_with_source(self):
        data = source()
        data["tables"]["girvi_loanitem"] = {}
        data["tables"]["girvi_loan"]["1"]["loan_amount"] = None
        summary, records = self.build(data)
        preview.propose_collateral_exclusions(summary, records)
        self.assertEqual(summary["exclusion_proposal"]["groups"][0]["source_principal_unknown_count"], 1)
        fingerprint = summary["exclusion_proposal"]["selection_sha256"]
        preview.propose_collateral_exclusions(summary, records)
        self.assertEqual(fingerprint, summary["exclusion_proposal"]["selection_sha256"])
        data["tables"]["girvi_loan"]["1"]["loan_amount"] = "1000"
        summary, records = self.build(data)
        preview.propose_collateral_exclusions(summary, records)
        self.assertNotEqual(fingerprint, summary["exclusion_proposal"]["selection_sha256"])
        records[0]["source"]["schema"] = "tenant_b"
        with self.assertRaises(PortabilityError):
            preview.propose_collateral_exclusions(summary, records)

    def test_opt_in_command_emits_exclusion_manifest_without_dropping_rows(self):
        data = source()
        data["tables"]["girvi_loanitem"] = {}
        with TemporaryDirectory() as directory, patch("apps.tenant_apps.data_portability.management.commands.preview_legacy_dump.inspect_archive", return_value=data):
            output = Path(directory)/"report"
            call_command("preview_legacy_dump", dump="source.dump", source_schema="tenant_a", source_namespace=NAMESPACE, output_dir=str(output), propose_skip_incomplete_collateral=True, stdout=io.StringIO())
            exclusions = [json.loads(s) for s in (output/"proposed-exclusions.jsonl").read_text().splitlines()]
            self.assertEqual(len(exclusions), 1)
            self.assertEqual(len((output/"records.jsonl").read_text().splitlines()), 4)
            self.assertIn("unapproved selection proposal", (output/"review.html").read_text())
