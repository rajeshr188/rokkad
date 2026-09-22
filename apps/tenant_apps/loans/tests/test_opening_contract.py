import copy
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from django.test import SimpleTestCase

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.history_contract import HistoryError, digest, dump
from apps.tenant_apps.loans.services.opening_contract import PROFILE, ROW_FIELDS, decode_row
from apps.tenant_apps.loans.services.opening_export import _row
from apps.tenant_apps.loans.services.opening_restore import parse_opening_export

FIXTURES = Path(__file__).with_name("fixtures")


class OpeningContractTests(SimpleTestCase):
    def test_v2_row_definition_adds_payment_lines_without_changing_v1(self):
        from django.conf import settings
        from apps.tenant_apps.loans.services.opening_contract import PAYMENT_PROFILE, ROW_FIELDS_V2
        published = json.loads((Path(settings.BASE_DIR) / "docs/contracts/loan-opening-export-v2-rows.json").read_text(encoding="utf-8"))
        self.assertEqual(published, json.loads(dump({"profile": PAYMENT_PROFILE, "fields": ROW_FIELDS_V2})))
        self.assertEqual({k: v for k, v in ROW_FIELDS_V2.items() if k != "repayment_lines"}, ROW_FIELDS)

    def test_v1_row_definition_matches_published_contract(self):
        from django.conf import settings
        published = json.loads((Path(settings.BASE_DIR) / "docs/contracts/loan-opening-export-v1-rows.json").read_text(encoding="utf-8"))
        self.assertEqual(published, json.loads(dump({"profile": PROFILE, "fields": ROW_FIELDS})))

    def source(self, name="active"):
        return (FIXTURES / f"opening-export-v1-{name}.jsonl").read_bytes()

    def test_frozen_exports_parse_without_rewriting_source_evidence(self):
        for name in ("active", "servicing"):
            with self.subTest(name=name):
                content = self.source(name)
                document = parse_opening_export(content)
                self.assertEqual(content, (dump(document["manifest"]) + "\n" + dump(document["evidence"]) + "\n").encode())
                for kind in ROW_FIELDS:
                    rows = document["evidence"][kind]
                    for row in rows if isinstance(rows, list) else [rows]:
                        self.assertEqual(_row(kind, decode_row(kind, row)), row)

    def test_old_producer_restore_flag_is_not_an_admission_permission(self):
        manifest, evidence = [json.loads(line) for line in self.source().splitlines()]
        manifest["restore_supported"] = False
        parsed = parse_opening_export((dump(manifest) + "\n" + dump(evidence) + "\n").encode())
        self.assertFalse(parsed["manifest"]["restore_supported"])
        self.assertEqual(parsed["evidence"], evidence)

    def test_model_field_changes_do_not_reinterpret_v1_nulls_or_types(self):
        content = self.source()
        field = m.PawnCollateralItem._meta.get_field("gross_weight")
        with patch.object(field, "null", False), patch.object(field, "to_python", side_effect=AssertionError("Model converter used")):
            parsed = parse_opening_export(content)
            row = parsed["evidence"]["items"][0]
            self.assertIsNone(row["gross_weight"])
            item = decode_row("items", row)
            item.new_internal_column = "Must not enter v1"
            self.assertEqual(_row("items", item), row)

    def test_unknown_fields_are_rejected_even_with_a_fresh_checksum(self):
        manifest, evidence = [json.loads(line) for line in self.source().splitlines()]
        evidence["items"][0]["new_internal_column"] = "not a v1 field"
        manifest["sha256"] = digest(evidence)
        with self.assertRaises(HistoryError):
            parse_opening_export((dump(manifest) + "\n" + dump(evidence) + "\n").encode())

    def test_wire_types_and_unknown_values_remain_explicit(self):
        row = json.loads(self.source().splitlines()[1])["items"][0]
        for field, invalid in (("id", True), ("id", "1"), ("id", 0),
                               ("net_weight", 10), ("net_weight", "NaN"),
                               ("net_weight", "invalid"), ("description", None),
                               ("description", 12), ("created_at", "2021-01-01T00:00:00")):
            value = copy.deepcopy(row)
            value[field] = invalid
            with self.subTest(field=field, invalid=invalid), self.assertRaises(HistoryError):
                decode_row("items", value)
        value = {**row, "net_weight": "1.230000", "public_id": 1}
        decoded = decode_row("items", value)
        self.assertEqual(decoded.net_weight, Decimal("1.230000"))
        self.assertEqual(decoded.public_id, UUID(int=1))
        self.assertIsNone(decoded.gross_weight)
