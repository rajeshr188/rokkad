import copy
import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.tenant_apps.data_portability.legacy_preview import build_preview, propose_collateral_exclusions
from apps.tenant_apps.data_portability.legacy_reconciliation import build_worksheet, compare_expressions
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.data_portability.tests.test_legacy_dump import NAMESPACE, source, row


class LegacyReconciliationTests(SimpleTestCase):
    def compare(self, start, end, monthly="10"):
        return compare_expressions(datetime.fromisoformat(start), datetime.fromisoformat(end), Decimal(monthly))

    def test_calendar_month_and_elapsed_day_paths_differ_at_month_end(self):
        result = self.compare("2021-01-31T00:00:00+00:00", "2021-02-28T00:00:00+00:00")
        self.assertEqual(result["completed_calendar_months"], 1)
        self.assertEqual(result["elapsed_whole_days"], 28)
        self.assertEqual(result["model_gross_interest"], "10")
        self.assertEqual(result["report_gross_interest"], "0")
        before = self.compare("2021-01-31T00:00:00+00:00", "2021-02-27T23:59:59+00:00")
        self.assertEqual(before["completed_calendar_months"], 0)

    def test_rounding_modes_and_negative_report_expression_are_not_normalized(self):
        result = self.compare("2021-01-01T00:00:00+00:00", "2021-02-02T00:00:00+00:00", "10.5")
        self.assertEqual((result["model_gross_interest"], result["report_gross_interest"]), ("10", "11"))
        same_day = self.compare("2021-01-01T00:00:00+00:00", "2021-01-01T20:00:00+00:00", "10.5")
        self.assertEqual(same_day["report_gross_interest"], "-11")

    def test_utc_elapsed_days_and_invalid_time_order(self):
        result = self.compare("2021-01-01T00:00:00+00:00", "2021-02-01T00:00:00+05:30")
        self.assertEqual(result["completed_calendar_months"], 0)
        self.assertEqual(result["elapsed_whole_days"], 30)
        self.assertIsNone(self.compare("2021-01-01T00:00:00+00:00", "2020-12-31T00:00:00+00:00"))
        self.assertIsNone(self.compare("0001-01-01T00:00:00+14:00", "2021-01-01T00:00:00+00:00"))
        self.assertIsNone(self.compare("2021-01-01T00:00:00", "2021-01-01T00:00:00+00:00"))

    def build(self, data):
        summary, records = build_preview(data, schema="tenant_a", source_namespace=NAMESPACE)
        propose_collateral_exclusions(summary, records)
        return summary, records

    def test_sample_is_deterministic_source_preserving_and_never_invents_balances(self):
        summary, records = self.build(source())
        before = copy.deepcopy((summary, records))
        result = build_worksheet(summary, records, as_of="2021-02-28", business_timezone="Asia/Kolkata")
        self.assertEqual((summary, records), before)
        self.assertEqual(result, build_worksheet(summary, list(reversed(records)), as_of="2021-02-28", business_timezone="Asia/Kolkata"))
        self.assertEqual(result["retained_active_loans"], 1)
        self.assertEqual(result["retained_active_with_payment_rows"], 0)
        self.assertEqual(result["sample_count"], 1)
        sample = result["samples"][0]
        self.assertEqual(sample["diagnostic"]["stored_payment_sum"], "0")
        self.assertTrue(all(v is None for v in sample["reviewed_opening"].values()))
        self.assertFalse(sample["import_ready"])
        self.assertFalse(result["cutover_approved"])

    def test_released_payment_control_is_distinct_from_retained_active_sample(self):
        data = source()
        data["tables"]["girvi_loanpayment"]["1"] = row("girvi_loanpayment", id="1", loan_id="1", payment_date="2021-02-01T00:00:00+00:00", payment_amount="110", principal_payment="100", interest_payment="10", with_release="t")
        data["tables"]["girvi_release"]["1"] = row("girvi_release", id="1", loan_id="1", release_date="2021-02-01T00:00:00+00:00", released_by_id="1", release_id="R1")
        result = build_worksheet(*self.build(data), as_of="2021-03-01", business_timezone="UTC")
        self.assertEqual(result["retained_active_loans"], 0)
        sample = result["samples"][0]
        self.assertEqual(sample["source_state"], "RELEASED")
        self.assertIn("outside active migration", sample["reasons"][0])
        self.assertEqual(sample["evaluated_at"], "2021-02-01T00:00:00+00:00")
        self.assertEqual(sample["diagnostic"]["stored_principal_payment_sum"], "100")

    def test_missing_items_and_excluded_active_loans_are_not_sampled(self):
        data = source()
        data["tables"]["girvi_loanitem"] = {}
        result = build_worksheet(*self.build(data), as_of="2021-03-01", business_timezone="UTC")
        self.assertEqual(result["sample_count"], 0)

    def test_scope_and_invalid_comparison_parameters_fail_closed(self):
        summary, records = self.build(source())
        for day, zone in (("not-date", "UTC"), ("9999-12-31", "UTC"), ("2021-03-01", "not-a-zone")):
            with self.subTest(day=day, zone=zone), self.assertRaises(PortabilityError):
                build_worksheet(summary, records, as_of=day, business_timezone=zone)
        records[0]["source"]["schema"] = "tenant_b"
        with self.assertRaises(PortabilityError):
            build_worksheet(summary, records, as_of="2021-03-01", business_timezone="UTC")

    def test_command_emits_comparison_before_complete_without_database_access(self):
        with TemporaryDirectory() as directory, patch("apps.tenant_apps.data_portability.management.commands.preview_legacy_dump.inspect_archive", return_value=source()):
            output = Path(directory) / "report"
            call_command("preview_legacy_dump", dump="source.dump", source_schema="tenant_a", source_namespace=NAMESPACE,
                         output_dir=str(output), propose_skip_incomplete_collateral=True, prepare_openings=True,
                         reconciliation_as_of="2021-03-01", reconciliation_timezone="UTC", stdout=io.StringIO())
            self.assertTrue((output / "COMPLETE").exists())
            self.assertEqual(json.loads((output / "reconciliation.json").read_text())["sample_count"], 1)
