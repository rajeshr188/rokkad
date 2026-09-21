import copy

from django.test import SimpleTestCase

from apps.tenant_apps.data_portability.tests.test_loan_history import document
from apps.tenant_apps.loans.services.history_contract import HistoryError, encode, parse, validate
from apps.tenant_apps.loans.services.history_import import _chronology
from apps.tenant_apps.loans.services.opening_validation import validate_opening
from apps.tenant_apps.loans.services.portability_validation import (
    MALFORMED_DATA, MISSING_EVIDENCE, HISTORICAL_INCONSISTENCY, OPERATIONAL_READINESS,
)
from .test_opening_validation import reviewed_opening


class PortabilityClassificationTests(SimpleTestCase):
    def test_opening_categories_never_relax_reconciliation(self):
        cases = [
            ("balances", "principal", "NaN", "AMOUNT_REQUIRED", MALFORMED_DATA),
            ("balances", "principal", None, "AMOUNT_REQUIRED", MISSING_EVIDENCE),
            ("balances", "evidence_reference", "", "REQUIRED_TEXT", MISSING_EVIDENCE),
            ("balances", "principal", "901", "ITEM_PRINCIPAL_MISMATCH", HISTORICAL_INCONSISTENCY),
            ("terms", "partial_rule", "UNSUPPORTED", "RULE_REQUIRED", OPERATIONAL_READINESS),
            ("mapping", "series_id", None, "INTEGER_REQUIRED", OPERATIONAL_READINESS),
        ]
        for group, field, value, code, category in cases:
            doc = reviewed_opening()
            doc[group][field] = value
            before = copy.deepcopy(doc)
            with self.subTest(code=code, value=value):
                result = validate_opening(doc)
                issue = next(i for i in result["issues"] if i["code"] == code)
                self.assertEqual(issue["category"], category)
                self.assertEqual(issue["severity"], "ERROR")
                self.assertFalse(result["document_reconciled"])
                self.assertFalse(result["import_ready"])
                self.assertEqual(doc, before)

    def test_reconciled_opening_does_not_claim_operational_readiness(self):
        result = validate_opening(reviewed_opening())
        self.assertTrue(result["document_reconciled"])
        self.assertFalse(result["import_ready"])
        self.assertEqual(result["issues"], [])
        self.assertEqual(len(result["readiness_checks"]), len(result["pending"]))
        for check in result["readiness_checks"]:
            self.assertEqual(check["category"], OPERATIONAL_READINESS)
            self.assertEqual(check["status"], "NOT_EVALUATED")

    def test_complete_history_contract_keeps_valid_round_trips(self):
        for closed in (False, True):
            doc = document(closed)
            before = copy.deepcopy(doc)
            self.assertEqual(parse(encode(doc)), doc)
            _chronology(doc)
            self.assertEqual(doc, before)

    def test_missing_history_and_malformed_values_remain_rejected(self):
        cases = [("events", [], MISSING_EVIDENCE),
                 ("tenure_months", "3", MALFORMED_DATA),
                 ("tenure_months", 13, OPERATIONAL_READINESS)]
        for field, value, category in cases:
            doc = document()
            doc["loan"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(HistoryError) as raised:
                validate(doc)
            self.assertEqual(raised.exception.issue["category"], category)
            self.assertEqual(raised.exception.issue["field"], f"document.loan.{field}")
        with self.assertRaises(HistoryError) as raised:
            parse(b"not json\n{}\n")
        self.assertEqual(raised.exception.issue["category"], MALFORMED_DATA)

    def test_closed_fact_without_release_is_not_accepted(self):
        doc = document()
        doc["loan"]["state"] = "CLOSED"
        validate(doc)
        with self.assertRaises(HistoryError) as raised:
            _chronology(doc)
        self.assertEqual(raised.exception.issue["category"], MISSING_EVIDENCE)
        self.assertEqual(raised.exception.issue["code"], "CLOSED_RELEASE_EVIDENCE")
        self.assertEqual(str(raised.exception), "Closed loans require evidenced full release.")

    def test_old_history_bound_is_not_reported_as_false_history(self):
        doc = document()
        doc["loan"]["disbursed_on"] = "2000-01-01"
        with self.assertRaises(HistoryError) as raised:
            _chronology(doc)
        self.assertEqual(raised.exception.issue["category"], OPERATIONAL_READINESS)
        doc = document()
        doc["loan"]["events"][1]["date"] = "2022-01-01"
        with self.assertRaises(HistoryError) as raised:
            _chronology(doc)
        self.assertEqual(raised.exception.issue["category"], HISTORICAL_INCONSISTENCY)
