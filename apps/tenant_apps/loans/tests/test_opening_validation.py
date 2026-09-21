import copy
from datetime import date

from django.test import SimpleTestCase

from apps.tenant_apps.loans.services.opening_validation import PROFILE, _anniversary, validate_opening


def reviewed_opening():
    """Synthetic reviewed facts, not a representation of the production source."""
    return {
        "profile": PROFILE,
        "source": {"namespace": "290f318a-6523-45a9-aa42-56e675be34ab", "schema": "tenant_a",
                   "loan_id": "girvi_loan:1", "number": "A00001", "loan_timestamp": "2021-01-01T00:00:00+00:00",
                   "borrower_id": "contact_customer:1", "item_ids": ["girvi_loanitem:1"],
                   "archive_sha256": "a" * 64, "selection_sha256": "b" * 64, "loan_sha256": "c" * 64,
                   "state": "UNRELEASED", "excluded": False, "errors": []},
        "cutover": {"date": "2021-01-20", "timezone": "Asia/Kolkata", "evidence_reference": "Synthetic cutover"},
        "mapping": {"workspace_id": 1, "borrower_id": 2,
                    "borrower_source_system": "legacy:290f318a652345a9aa4256e675be34ab:tenant_a",
                    "borrower_external_id": "contact_customer:1", "licence_revision_id": 3,
                    "series_id": 4, "product_version_id": 5, "evidence_reference": "Synthetic mapping"},
        "balances": {"principal": "900", "interest": "24", "fees": "0", "evidence_reference": "Synthetic balance review"},
        "terms": {"original_date": "2021-01-01", "maturity_date": "2021-04-01", "grace_days": 3,
                  "billing_anchor": "2021-01-01", "rule_id": "SYNTHETIC-ORIGINAL-1", "period_rule": "ORIGINAL_ANNIVERSARY",
                  "interest_basis": "ORIGINAL_PRINCIPAL", "partial_rule": "COMPLETED_ONLY",
                  "partial_cutoff_days": None, "partial_lower_fraction": None,
                  "rounding_scope": "AGGREGATE", "rounding_mode": "HALF_EVEN", "interest_quantum": "1",
                  "evidence_reference": "Synthetic agreed terms"},
        "collateral": [{"id": "girvi_loanitem:1", "description": "Ring", "quantity": 1, "metal": "GOLD",
                        "gross_weight": "10", "net_weight": "9", "purity": "90",
                        "original_principal": "1000", "remaining_principal": "900", "monthly_rate": "1",
                        "weight_reference": "Synthetic weights", "custody_reference": "Synthetic custody",
                        "valuation": {"amount": "2000", "date": "2021-01-20", "evidence_reference": "Synthetic assessment"}}],
        "obligations": [{"id": "due-1", "due": "2021-04-01", "principal": "900", "interest": "30",
                         "recognized_interest": "24", "evidence_reference": "Synthetic original obligations"}],
        "continuation": {"period_number": 1, "period_start": "2021-01-01", "period_end": "2021-01-31",
                         "bases": [{"item_id": "girvi_loanitem:1", "principal_base": "1000"}],
                         "recognized_interest": "4", "recognized_unpaid_interest": "4",
                         "advance_covered_interest": "0", "expected_period_interest": "10",
                         "evidence_reference": "Synthetic period reconciliation"},
        "review_reference": "Synthetic operator review",
    }


class OpeningValidationTests(SimpleTestCase):
    def codes(self, doc):
        result = validate_opening(doc, today=date(2026, 9, 12))
        self.assertFalse(result["import_ready"])
        self.assertFalse(result["document_reconciled"])
        return {i["code"] for i in result["issues"]}

    def test_partial_period_credits_recognition_without_replaying_payments(self):
        doc = reviewed_opening()
        before = copy.deepcopy(doc)
        result = validate_opening(doc)
        self.assertEqual(result["issues"], [])
        self.assertTrue(result["document_reconciled"])
        self.assertFalse(result["import_ready"])
        self.assertEqual(result["reconciliation"], {"opening_total": "924", "calculated_full_period_interest": "10", "additional_full_period_interest": "6"})
        self.assertEqual(doc, before)
        doc["continuation"]["recognized_unpaid_interest"] = "0"
        doc["balances"]["interest"] = "20"
        doc["obligations"][0]["recognized_interest"] = "20"
        result = validate_opening(doc)
        self.assertTrue(result["document_reconciled"])
        self.assertEqual(result["reconciliation"]["additional_full_period_interest"], "6")

    def test_advance_coverage_is_separate_and_overcoverage_is_not_clamped(self):
        doc = reviewed_opening()
        doc["continuation"]["advance_covered_interest"] = "2"
        self.assertEqual(validate_opening(doc)["reconciliation"]["additional_full_period_interest"], "4")
        doc["continuation"]["advance_covered_interest"] = "7"
        self.assertIn("CARRY_OVER_COVERED", self.codes(doc))
        self.assertNotIn("additional_full_period_interest", validate_opening(doc)["reconciliation"])

    def test_unknown_balances_are_not_zero_and_values_are_bounded(self):
        for value in (None, 0, True, "NaN", "Infinity", "1e2", "-1", "0.001", "1000000000000", [], {}):
            doc = reviewed_opening()
            doc["balances"]["fees"] = value
            with self.subTest(value=value):
                self.assertTrue(self.codes(doc) & {"AMOUNT_REQUIRED", "AMOUNT_RANGE"})
        doc = reviewed_opening()
        doc["balances"]["principal"] = "0"
        self.assertIn("AMOUNT_RANGE", self.codes(doc))

    def test_collateral_and_obligations_reconcile_independently(self):
        for group, field, code in (("collateral", "remaining_principal", "ITEM_PRINCIPAL_MISMATCH"),
                                   ("obligations", "principal", "OBLIGATION_BALANCE_MISMATCH"),
                                   ("obligations", "recognized_interest", "OBLIGATION_BALANCE_MISMATCH")):
            doc = reviewed_opening()
            doc[group][0][field] = "1"
            with self.subTest(group=group, field=field):
                self.assertIn(code, self.codes(doc))
        doc = reviewed_opening()
        doc["obligations"][0]["interest"] = "100"
        self.assertTrue(validate_opening(doc)["document_reconciled"])

    def test_item_identity_quantity_weight_and_custody_are_required(self):
        for field, value, code in (("id", "different-item", "ITEM_SET_MISMATCH"),
                                   ("quantity", True, "INTEGER_REQUIRED"), ("gross_weight", "8", "WEIGHT_ORDER"),
                                   ("purity", "101", "PURITY_RANGE"), ("custody_reference", None, "REQUIRED_TEXT"),
                                   ("monthly_rate", "100.000001", "RATE_RANGE"), ("gross_weight", "10000000000", "WEIGHT_RANGE"),
                                   ("remaining_principal", "1001", "PRINCIPAL_INCREASE")):
            doc = reviewed_opening()
            doc["collateral"][0][field] = value
            with self.subTest(field=field):
                self.assertIn(code, self.codes(doc))
        doc = reviewed_opening()
        doc["collateral"].append(copy.deepcopy(doc["collateral"][0]))
        self.assertIn("DUPLICATE_ITEM", self.codes(doc))

    def test_empty_obligation_is_rejected_before_database_preview(self):
        doc = reviewed_opening()
        row = copy.deepcopy(doc["obligations"][0])
        row.update(id="empty", principal="0", interest="0", recognized_interest="0")
        doc["obligations"].append(row)
        self.assertIn("AMOUNT_RANGE", self.codes(doc))
        issue = next(i for i in validate_opening(doc)["issues"] if i["code"] == "AMOUNT_RANGE")
        self.assertEqual(issue["field"], "obligations[1]")
        self.assertEqual(issue["category"], "MALFORMED_DATA")

    def test_separate_principal_and_interest_obligations_remain_valid(self):
        doc = reviewed_opening()
        interest = copy.deepcopy(doc["obligations"][0])
        interest.update(id="interest", principal="0")
        doc["obligations"][0].update(interest="0", recognized_interest="0")
        doc["obligations"].append(interest)
        self.assertTrue(validate_opening(doc)["document_reconciled"])

    def test_original_dates_timezone_and_overdue_obligations_are_preserved(self):
        doc = reviewed_opening()
        doc["cutover"]["date"] = "2021-05-15"
        doc["continuation"].update(period_number=5, period_start="2021-05-01", period_end="2021-05-31")
        self.assertTrue(validate_opening(doc)["document_reconciled"])
        doc["obligations"][0]["due"] = "2021-05-16"
        self.assertIn("PRINCIPAL_REAGED", self.codes(doc))
        doc = reviewed_opening()
        doc["source"]["loan_timestamp"] = "2020-12-31T20:00:00+00:00"
        self.assertTrue(validate_opening(doc)["document_reconciled"])
        doc["terms"]["original_date"] = "2020-12-31"
        self.assertIn("ORIGINAL_DATE_CHANGED", self.codes(doc))

    def test_month_end_period_rules_remain_distinct_and_do_not_reset(self):
        self.assertEqual(_anniversary(date(2020, 1, 31), 2, "ORIGINAL_ANNIVERSARY"), date(2020, 3, 31))
        self.assertEqual(_anniversary(date(2020, 1, 31), 2, "CLAMPED_CONTIGUOUS"), date(2020, 3, 29))
        doc = reviewed_opening()
        doc["continuation"]["period_start"] = "2021-01-21"
        self.assertIn("PERIOD_RESET", self.codes(doc))
        doc["terms"]["billing_anchor"] = "2021-01-21"
        self.assertIn("BILLING_ANCHOR_CHANGED", self.codes(doc))

    def test_boundary_requires_next_period_without_prior_recognition(self):
        doc = reviewed_opening()
        doc["cutover"]["date"] = "2021-01-31"
        self.assertIn("PERIOD_CUTOVER", self.codes(doc))
        doc["continuation"].update(period_number=2, period_start="2021-02-01", period_end="2021-02-28")
        self.assertIn("UNSTARTED_RECOGNITION", self.codes(doc))
        doc["continuation"].update(recognized_interest="0", recognized_unpaid_interest="0")
        self.assertTrue(validate_opening(doc)["document_reconciled"])

    def test_basis_must_match_original_or_period_start_not_silently_cutover(self):
        doc = reviewed_opening()
        doc["continuation"]["bases"][0]["principal_base"] = "900"
        self.assertIn("ORIGINAL_BASIS", self.codes(doc))
        doc["terms"]["interest_basis"] = "OUTSTANDING_AT_PERIOD_START"
        doc["continuation"]["expected_period_interest"] = "9"
        self.assertTrue(validate_opening(doc)["document_reconciled"])
        doc["continuation"]["bases"][0]["principal_base"] = "899"
        self.assertIn("PERIOD_BASIS", self.codes(doc))
        doc["continuation"]["bases"][0]["principal_base"] = "1001"
        self.assertIn("PRINCIPAL_INCREASE", self.codes(doc))

    def test_rounding_mode_and_scope_change_calculated_charge(self):
        doc = reviewed_opening()
        doc["collateral"][0]["monthly_rate"] = "1.05"
        self.assertTrue(validate_opening(doc)["document_reconciled"])
        doc["terms"]["rounding_mode"] = "HALF_UP"
        self.assertIn("PERIOD_INTEREST_MISMATCH", self.codes(doc))
        self.assertEqual(validate_opening(doc)["reconciliation"]["calculated_full_period_interest"], "11")
        second = copy.deepcopy(doc["collateral"][0])
        second.update(id="girvi_loanitem:2", remaining_principal="0")
        doc["collateral"].append(second)
        doc["source"]["item_ids"].append(second["id"])
        doc["continuation"]["bases"].append({"item_id": second["id"], "principal_base": "1000"})
        doc["continuation"]["expected_period_interest"] = "21"
        self.assertTrue(validate_opening(doc)["document_reconciled"])
        doc["terms"]["rounding_scope"] = "PER_ITEM"
        self.assertEqual(validate_opening(doc)["reconciliation"]["calculated_full_period_interest"], "22")
        self.assertIn("PERIOD_INTEREST_MISMATCH", self.codes(doc))

    def test_source_errors_exclusion_and_borrower_scope_cannot_pass(self):
        for field, value, code in (("errors", [{"code": "LINKED_ITEM_ISSUE"}], "SOURCE_ERRORS"),
                                   ("excluded", True, "SOURCE_NOT_SELECTED"), ("state", "RELEASED", "SOURCE_NOT_SELECTED"),
                                   ("schema", "public", "SOURCE_SCOPE"), ("namespace", "bad", "SOURCE_NAMESPACE"),
                                   ("archive_sha256", "a", "SOURCE_HASH")):
            doc = reviewed_opening()
            doc["source"][field] = value
            with self.subTest(field=field):
                self.assertIn(code, self.codes(doc))
        doc = reviewed_opening()
        doc["mapping"]["borrower_source_system"] = doc["mapping"]["borrower_source_system"].replace("tenant_a", "tenant_b")
        self.assertIn("BORROWER_REFERENCE", self.codes(doc))

    def test_unsupported_shapes_and_calendar_extremes_return_issues(self):
        for group in reviewed_opening():
            for value in (None, [], "bad", True, {}):
                if group == "review_reference" and value == "bad":
                    continue  # A nonempty evidence reference is structurally valid, not authenticated.
                doc = reviewed_opening()
                doc[group] = value
                with self.subTest(group=group, value=value):
                    self.codes(doc)
        doc = reviewed_opening()
        doc["continuation"]["period_start"] = "0001-01-01"
        self.assertIn("PERIOD_RESET", self.codes(doc))
        doc["terms"]["billing_anchor"] = "9999-12-31"
        self.assertIn("PERIOD_RANGE", self.codes(doc))
        doc = reviewed_opening()
        doc["source"]["loan_timestamp"] = "0001-01-01T00:00:00+14:00"
        self.assertIn("SOURCE_DATE", self.codes(doc))

    def test_slab_inputs_future_cutover_and_unpaid_carry_fail_explicitly(self):
        doc = reviewed_opening()
        doc["terms"]["partial_rule"] = "SLAB"
        self.assertIn("INTEGER_REQUIRED", self.codes(doc))
        doc["terms"].update(partial_cutoff_days=15, partial_lower_fraction="0.5")
        self.assertTrue(validate_opening(doc)["document_reconciled"])
        doc["cutover"]["date"] = "2027-01-01"
        self.assertIn("FUTURE_CUTOVER", self.codes(doc))
        doc = reviewed_opening()
        doc["continuation"]["recognized_unpaid_interest"] = "25"
        self.assertTrue({"UNPAID_CARRY", "CARRY_BALANCE"} <= self.codes(doc))
