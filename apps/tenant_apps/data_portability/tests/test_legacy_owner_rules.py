import copy
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.tenant_apps.data_portability.legacy_owner_rules import COLLECTION_PROFILE, NAMESPACE, PROFILE, MATURITY_EVIDENCE, maturity_tenure
from apps.tenant_apps.data_portability.legacy_preview import build_preview, propose_collateral_exclusions
from apps.tenant_apps.data_portability.legacy_reconciliation import build_worksheet
from apps.tenant_apps.data_portability.opening_review import prepare_openings, reconcile_documents
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.data_portability.tests.test_legacy_dump import row, source


class LegacyOwnerRulesTests(SimpleTestCase):
    def test_confirmed_linode_weight_maps_net_only_and_scopes_maturity(self):
        from apps.tenant_apps.data_portability.legacy_owner_rules import LINODE_PROFILE, LINODE_WEIGHT_EVIDENCE, LINODE_TERMS_EVIDENCE
        for schema, profile in (("jsk", "linode-jsk/1"), ("lakshmipawnbroker", "linode-lakshmi/1")):
            summary, records = build_preview(source(schema), schema=schema, source_namespace=NAMESPACE, source_profile=profile)
            propose_collateral_exclusions(summary, records)
            prepared = prepare_openings(summary, records, owner_profile=LINODE_PROFILE)[0]
            self.assertEqual(prepared["profile"], "loan-opening-review/2")
            self.assertEqual(prepared["collateral"][0]["net_weight"], "10")
            self.assertIsNone(prepared["collateral"][0]["gross_weight"])
            self.assertEqual(prepared["collateral"][0]["weight_reference"], LINODE_WEIGHT_EVIDENCE)
            self.assertIsNone(prepared["collateral"][0]["custody_reference"])
            self.assertIsNone(prepared["balances"])
            self.assertEqual(maturity_tenure(summary, {"tenure":"0"}, owner_profile=LINODE_PROFILE), (3, LINODE_TERMS_EVIDENCE))
            with self.assertRaises(PortabilityError):
                prepare_openings({**summary, "source_profile": None}, records, owner_profile=LINODE_PROFILE)
            with self.assertRaises(PortabilityError):
                maturity_tenure(summary, {"tenure": "0"}, owner_profile=None)

    def test_linode_terms_extend_only_confirmed_interest_and_maturity(self):
        from apps.tenant_apps.data_portability.legacy_owner_rules import linode_terms
        from apps.tenant_apps.data_portability.legacy_profiles import PROFILES
        for profile in PROFILES.values():
            summary = dict(source_namespace=NAMESPACE, source_schema=profile.schema, source_profile=profile.key)
            for raw, expected, basis in [("0", 3, "OWNER_MISSING_MATURITY_RULE"), ("6", 6, "RECORDED_TENURE")]:
                with self.subTest(schema=profile.schema, tenure=raw):
                    facts = {"tenure": raw}
                    result = linode_terms(summary, facts)
                    self.assertEqual(result["tenure_months"], expected)
                    self.assertEqual(result["maturity_basis"], basis)
                    self.assertEqual(result["interest_rule"], "original-anniversary-upfront-inclusive/2")
                    self.assertTrue(result["first_month_paid_upfront"])
                    self.assertFalse(result["opening_balances_approved"])
                    self.assertFalse(result["custody_confirmed"])
                    self.assertEqual(facts, {"tenure": raw})
            for raw in ("bad", "-1", "1.5", "1201"):
                with self.assertRaises(PortabilityError):
                    linode_terms(summary, {"tenure": raw})

    def test_linode_terms_cannot_expand_old_weight_attestation_or_wrong_scope(self):
        from apps.tenant_apps.data_portability.legacy_owner_rules import linode_terms, check_profile
        valid = dict(source_namespace=NAMESPACE, source_schema="jsk", source_profile="linode-jsk/1")
        for field, value in (("source_namespace", "other"), ("source_schema", "jcl"), ("source_profile", None)):
            with self.assertRaises(PortabilityError):
                linode_terms({**valid, field: value}, {"tenure": "0"})
        with self.assertRaises(PortabilityError):
            check_profile(valid, COLLECTION_PROFILE)

    def test_maturity_fallback_preserves_recorded_tenure_and_rejects_invalid_or_wrong_scope(self):
        summary, _ = self.build()
        for raw in (None, "", "0", "0.00"):
            with self.subTest(raw=raw):
                self.assertEqual(maturity_tenure(summary, {"tenure": raw}), (3, MATURITY_EVIDENCE))
        for raw in ("3", "6", "12"):
            self.assertEqual(maturity_tenure(summary, {"tenure": raw}), (int(raw), None))
        for raw in ("-1", "NaN", "bad", "1.5", "1201"):
            with self.subTest(raw=raw), self.assertRaises(PortabilityError):
                maturity_tenure(summary, {"tenure": raw})
        for field, value in (("source_schema", "other"), ("source_namespace", "other")):
            with self.subTest(field=field), self.assertRaises(PortabilityError):
                maturity_tenure({**summary, field: value}, {"tenure": "0"})

    def test_v2_preserves_bronze_and_net_only_evidence_without_filling_due_terms(self):
        data = source("jcl")
        data["tables"]["girvi_loanitem"]["1"]["itemtype"] = "Bronze"
        summary, records = self.build(data)
        before = copy.deepcopy((summary, records))
        mapped = prepare_openings(summary, records, owner_profile=COLLECTION_PROFILE)
        self.assertEqual(mapped[0]["profile"], "loan-opening-review/2")
        self.assertEqual(mapped[0]["collateral"][0]["metal"], "BRONZE")
        self.assertEqual(mapped[0]["collateral"][0]["net_weight"], "10")
        self.assertIsNone(mapped[0]["collateral"][0]["gross_weight"])
        for key in ("terms", "obligations", "balances", "continuation"):
            self.assertIsNone(mapped[0][key])
        self.assertFalse(reconcile_documents(mapped)[0]["import_ready"])
        self.assertEqual((summary, records), before)

    def build(self, data=None):
        summary, records = build_preview(data or source("jcl"), schema="jcl", source_namespace=NAMESPACE)
        propose_collateral_exclusions(summary, records)
        return summary, records

    def worksheet(self, summary, records, **kwargs):
        return build_worksheet(summary, records, as_of="2021-02-01", business_timezone="Asia/Kolkata", owner_profile=PROFILE, **kwargs)

    def test_opt_in_maps_only_net_weight_with_evidence_and_preserves_source(self):
        summary, records = self.build()
        before = copy.deepcopy((summary, records))
        default = prepare_openings(summary, records)
        mapped = prepare_openings(summary, records, owner_profile=PROFILE)
        self.assertIsNone(default[0]["collateral"][0]["net_weight"])
        item = mapped[0]["collateral"][0]
        self.assertEqual(item["net_weight"], "10")
        self.assertIsNone(item["gross_weight"])
        self.assertEqual(item["purity"], "90")
        self.assertTrue(item["weight_reference"].endswith("jcl-net-weight"))
        self.assertEqual((summary, records), before)
        self.assertIsNone(mapped[0]["balances"])
        self.assertEqual(reconcile_documents(mapped)[0]["document_reconciled"], 0)

    def test_wrong_namespace_tenant_or_profile_rejected(self):
        for field, value in (("source_namespace", "290f318a-6523-45a9-aa42-56e675be34ab"), ("source_schema", "other")):
            summary, records = self.build()
            summary[field] = value
            with self.subTest(field=field), self.assertRaises(PortabilityError):
                prepare_openings(summary, records, owner_profile=PROFILE)
            with self.assertRaises(PortabilityError):
                self.worksheet(summary, records)
        with self.assertRaises(PortabilityError):
            prepare_openings(*self.build(), owner_profile="unknown")

    def test_collection_diagnostic_is_separate_from_old_expressions_and_openings(self):
        summary, records = self.build()
        before = copy.deepcopy((summary, records))
        result = self.worksheet(summary, records)
        diagnostic = result["owner_rule_diagnostics"][0]
        self.assertEqual(diagnostic["calculation"]["additional_interest"], "0")
        self.assertEqual(result["samples"][0]["comparison"]["model_gross_interest"], "10")
        self.assertFalse(diagnostic["import_ready"])
        self.assertTrue(all(v is None for v in result["samples"][0]["reviewed_opening"].values()))
        self.assertEqual((summary, records), before)

    def test_source_mismatch_payments_and_fractional_charges_are_held(self):
        for problem, expected in (("mismatch", "SOURCE_ERRORS"), ("payment", "PAYMENT_TREATMENT_UNREVIEWED"),
                                  ("fractional", "FRACTIONAL_AGGREGATION_UNCONFIRMED"), ("rate", "ITEM_MONTHLY_CHARGE_UNRECONCILED")):
            data = source("jcl")
            if problem == "mismatch":
                data["tables"]["girvi_loan"]["1"]["loan_amount"] = "2000"
            elif problem == "payment":
                data["tables"]["girvi_loanpayment"]["1"] = row("girvi_loanpayment", id="1", loan_id="1", payment_date="2021-01-20T00:00:00+00:00", payment_amount="10", principal_payment="0", interest_payment="10", with_release="f")
            elif problem == "fractional":
                data["tables"]["girvi_loan"]["1"]["interest"] = "10.5"
                data["tables"]["girvi_loanitem"]["1"].update(interest="10.5", interestrate="1.05")
            else:
                data["tables"]["girvi_loanitem"]["1"]["interestrate"] = "2"
            diagnostic = self.worksheet(*self.build(data))["owner_rule_diagnostics"][0]
            with self.subTest(problem=problem):
                self.assertIsNone(diagnostic["calculation"])
                self.assertIn(expected, diagnostic["blockers"])

    def test_business_timezone_precedes_anniversary_calculation(self):
        data = source("jcl")
        data["tables"]["girvi_loan"]["1"]["loan_date"] = "2021-01-01T20:00:00+00:00"
        result = self.worksheet(*self.build(data))["owner_rule_diagnostics"][0]["calculation"]
        self.assertEqual(result["original_date"], "2021-01-02")
        self.assertEqual(result["next_increase_on"], "2021-02-03")

    def test_multiple_whole_rupee_items_calculate_but_fractional_items_do_not_cancel(self):
        data = source("jcl")
        data["tables"]["girvi_loanitem"]["2"] = copy.deepcopy(data["tables"]["girvi_loanitem"]["1"])
        data["tables"]["girvi_loanitem"]["2"]["id"] = "2"
        data["tables"]["girvi_loan"]["1"].update(loan_amount="2000", interest="20")
        summary, records = self.build(data)
        diagnostic = build_worksheet(summary, records, as_of="2021-02-02", business_timezone="UTC", owner_profile=PROFILE)["owner_rule_diagnostics"][0]
        self.assertEqual(diagnostic["calculation"]["additional_interest"], "20")
        for item in data["tables"]["girvi_loanitem"].values():
            item.update(interestrate="1.05", interest="10.5")
        data["tables"]["girvi_loan"]["1"]["interest"] = "21"
        diagnostic = self.worksheet(*self.build(data))["owner_rule_diagnostics"][0]
        self.assertIsNone(diagnostic["calculation"])
        self.assertIn("FRACTIONAL_AGGREGATION_UNCONFIRMED", diagnostic["blockers"])

    def test_command_applies_profile_and_rejects_missing_date_before_reading_dump(self):
        with TemporaryDirectory() as directory, patch("apps.tenant_apps.data_portability.management.commands.preview_legacy_dump.inspect_archive", return_value=source("jcl")) as inspect:
            inspect.return_value["tables"]["girvi_loan"]["1"]["loan_id"] = "<script>bad</script>"
            options = dict(dump="source.dump", source_schema="jcl", source_namespace=NAMESPACE, owner_profile=PROFILE,
                           output_dir=str(Path(directory) / "review"), propose_skip_incomplete_collateral=True,
                           prepare_openings=True, stdout=io.StringIO())
            with self.assertRaises(CommandError):
                call_command("preview_legacy_dump", **options)
            inspect.assert_not_called()
            call_command("preview_legacy_dump", **options, reconciliation_as_of="2021-02-01", reconciliation_timezone="UTC")
            output = Path(options["output_dir"])
            self.assertTrue((output / "COMPLETE").exists())
            self.assertEqual(json.loads((output / "reconciliation.json").read_text())["owner_profile"], PROFILE)
            self.assertEqual(json.loads((output / "opening-candidates.jsonl").read_text())["collateral"][0]["net_weight"], "10")
            html = (output / "owner-rule-review.html").read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;bad&lt;/script&gt;", html)
            self.assertNotIn("<script>", html)

    def test_v2_sums_fractional_items_and_months_without_inventing_collections(self):
        data = source("jcl")
        item = data["tables"]["girvi_loanitem"]["1"]
        item.update(interestrate="1.05", interest="10.5")
        data["tables"]["girvi_loanitem"]["2"] = dict(item, id="2")
        data["tables"]["girvi_loan"]["1"].update(loan_amount="2000", interest="21")
        summary, records = self.build(data)
        before = copy.deepcopy((summary, records))
        result = build_worksheet(summary, records, as_of="2021-03-02", business_timezone="UTC", owner_profile=COLLECTION_PROFILE)
        diagnostic = result["owner_rule_diagnostics"][0]
        self.assertEqual(diagnostic["calculation"]["additional_interest"], "42")
        self.assertEqual(diagnostic["calculation"]["monthly_interest_unrounded"], "21.0")
        self.assertEqual(diagnostic["blockers"], [])
        self.assertEqual(diagnostic["collection_evidence"], {"actual_interest_collected": None, "interest_lost": None})
        self.assertFalse(diagnostic["import_ready"])
        self.assertIsNone(prepare_openings(summary, records, owner_profile=COLLECTION_PROFILE)[0]["balances"])
        self.assertEqual((summary, records), before)
        # The old explicit profile preserves its conservative fractional hold.
        self.assertIn("FRACTIONAL_AGGREGATION_UNCONFIRMED", self.worksheet(summary, records)["owner_rule_diagnostics"][0]["blockers"])

    def test_v2_keeps_source_error_payment_and_rate_holds(self):
        for problem, expected in (("mismatch", "SOURCE_ERRORS"), ("payment", "PAYMENT_TREATMENT_UNREVIEWED"),
                                  ("rate", "ITEM_MONTHLY_CHARGE_UNRECONCILED")):
            data = source("jcl")
            if problem == "mismatch":
                data["tables"]["girvi_loan"]["1"]["loan_amount"] = "2000"
            elif problem == "payment":
                data["tables"]["girvi_loanpayment"]["1"] = row("girvi_loanpayment", id="1", loan_id="1", payment_date="2021-01-20T00:00:00+00:00", payment_amount="10", principal_payment="0", interest_payment="10", with_release="f")
            else:
                data["tables"]["girvi_loanitem"]["1"]["interestrate"] = "2"
            result = build_worksheet(*self.build(data), as_of="2021-03-02", business_timezone="UTC", owner_profile=COLLECTION_PROFILE)
            diagnostic = result["owner_rule_diagnostics"][0]
            with self.subTest(problem=problem):
                self.assertIsNone(diagnostic["calculation"])
                self.assertIn(expected, diagnostic["blockers"])
                self.assertIsNone(diagnostic["collection_evidence"]["interest_lost"])

    def test_v2_is_source_scoped_and_emits_reviewable_rehearsal_report(self):
        with TemporaryDirectory() as directory, patch("apps.tenant_apps.data_portability.management.commands.preview_legacy_dump.inspect_archive", return_value=source("jcl")) as inspect:
            data = inspect.return_value
            data["tables"]["girvi_loanitem"]["1"].update(interestrate="1.05", interest="10.5")
            data["tables"]["girvi_loan"]["1"]["interest"] = "10.5"
            output = Path(directory) / "report"
            options = dict(dump="source.dump", source_schema="jcl", source_namespace=NAMESPACE,
                           owner_profile=COLLECTION_PROFILE, output_dir=str(output), prepare_openings=True,
                           propose_skip_incomplete_collateral=True, reconciliation_as_of="2021-03-02",
                           reconciliation_timezone="UTC", stdout=io.StringIO())
            for field, value in (("source_namespace", "290f318a-6523-45a9-aa42-56e675be34ab"), ("source_schema", "other")):
                with self.subTest(field=field), self.assertRaises(CommandError):
                    call_command("preview_legacy_dump", **{**options, field: value})
            inspect.assert_not_called()
            call_command("preview_legacy_dump", **options)
            result = json.loads((output / "reconciliation.json").read_text())
            self.assertEqual(result["owner_rule_diagnostics"][0]["calculation"]["additional_interest"], "21")
            self.assertTrue((output / "COMPLETE").exists())
            html = (output / "owner-rule-review.html").read_text(encoding="utf-8")
            self.assertIn("rounded once", html)
            self.assertIn("accepted interest losses are separate", html)
            self.assertNotIn("Fractional item charges require", html)
