"""Source-scoped closed-position preparation does not reconstruct missing history."""
from copy import deepcopy
from datetime import date
from uuid import UUID
from django.test import SimpleTestCase

from apps.tenant_apps.data_portability import legacy_closed_positions as adapter
from apps.tenant_apps.loans.services import archive_contract, closed_position_contract
from .test_loan_archive import document as archive_document


def retained(schema="jcl"):
    value = archive_document()
    system = f"legacy:{UUID(adapter.SOURCE_NAMESPACE).hex}:{schema}"
    value["source"].update(namespace=adapter.SOURCE_NAMESPACE, system=system, loan_id="girvi_loan:1")
    value["facts"].update(raw_status="RELEASE_ROW_PRESENT", original_principal=None,
        closed_on="2000-01-02", borrower_reference=dict(system=system, id="contact_customer:1"))
    value["source_records"] = [
        dict(source=dict(source_system=system, table="girvi_loan", id="1", external_id="girvi_loan:1"),
            facts=dict(customer_id="1", series_id="1", loan_amount="0", interest="0", tenure="0")),
        dict(source=dict(source_system=system, table="girvi_release", id="1", external_id="girvi_release:1"),
            facts=dict(loan_id="1"))]
    return value


class LegacyClosedPositionTests(SimpleTestCase):
    def prepare(self, value):
        return adapter.prepare_closed_position(value, as_of=date(2026, 10, 9),
            release_meaning_reference=adapter.RELEASE_MEANING_REFERENCE)

    def test_all_three_reviewed_sources_accept_missing_terms_and_collateral(self):
        for schema in sorted(adapter.SOURCE_SCHEMAS):
            with self.subTest(schema=schema):
                value = retained(schema); before = deepcopy(value)
                prepared = self.prepare(value)
                self.assertIsNone(prepared["loan"]["original_principal"])
                self.assertIsNone(prepared["loan"]["monthly_rate"])
                self.assertIsNone(prepared["loan"]["tenure_months"])
                self.assertEqual(prepared["position"]["custody"], "RETURNED_TO_BORROWER")
                self.assertEqual(prepared["position"]["principal"], "0")
                self.assertEqual(prepared["retained_evidence"], value)
                self.assertEqual(value, before)
                self.assertEqual(closed_position_contract.parse(closed_position_contract.encode(prepared)), prepared)

    def test_mutable_raw_amount_and_available_receipts_do_not_become_a_fake_payout(self):
        value = retained(); value["source_records"][0]["facts"]["loan_amount"] = "5000"
        value["facts"]["payments"] = [dict(id="receipt-1", date="1999-01-01", amount="100")]
        prepared = self.prepare(value)
        self.assertIsNone(prepared["loan"]["original_principal"])
        self.assertEqual(prepared["earlier_history"], "UNAVAILABLE")
        self.assertEqual(prepared["retained_evidence"]["facts"]["payments"], value["facts"]["payments"])
        self.assertNotIn("events", prepared)

    def test_retained_owner_closed_zero_position_does_not_assert_return_or_closure_date(self):
        value = retained(); value["source_records"].pop()
        value["source_records"].append(dict(owner_decision="Owner confirmed closed; zero remaining debt."))
        value["facts"].update(raw_status="NO_RELEASE_ROW; OWNER_REPORTS_CLOSED", reported_balance="0", closed_on=None)
        prepared = self.prepare(value)
        self.assertEqual(prepared["position"]["basis"], "OWNER_CLOSED_POSITION")
        self.assertEqual(prepared["position"]["custody"], "UNKNOWN")
        self.assertIsNone(prepared["loan"]["closed_on"])
        self.assertEqual(prepared["position"]["as_of"], "2026-10-09")

    def test_other_installation_and_schema_cannot_use_the_owner_confirmation(self):
        for value in (retained("unreviewed"), retained()):
            if value["source"]["system"].endswith(":jcl"):
                value["source"]["namespace"] = "491cf2e4-99eb-499c-b555-68f3a8d5caaa"
            with self.assertRaises(ValueError):
                self.prepare(value)
        with self.assertRaises(ValueError):
            adapter.prepare_closed_position(retained(), as_of=date(2026,10,9), release_meaning_reference="")

    def test_wrong_loan_release_or_missing_borrower_requires_review(self):
        for change in ("release", "borrower", "ambiguous"):
            value = retained()
            if change == "release": value["source_records"][1]["facts"]["loan_id"] = "2"
            elif change == "borrower": value["facts"]["borrower_reference"] = None
            else: value["source_records"].append(deepcopy(value["source_records"][0]))
            result = adapter.classify_closed_position(value, as_of=date(2026,10,9), release_meaning_reference=adapter.RELEASE_MEANING_REFERENCE)
            self.assertEqual(result["status"], "REVIEW")
            self.assertIsNone(result["document"])
            self.assertTrue(result["reason"])

    def test_nonzero_balance_and_contradictory_dates_are_retained_as_exceptions(self):
        for field, actual in (("reported_balance", "1"), ("closed_on", "1980-01-01")):
            value = retained(); value["facts"][field] = actual; before = deepcopy(value)
            archive_contract.validate_document(value)
            result = adapter.classify_closed_position(value, as_of=date(2026,10,9), release_meaning_reference=adapter.RELEASE_MEANING_REFERENCE)
            self.assertEqual(result["status"], "REVIEW")
            self.assertEqual(value, before)

    def test_owner_zero_position_needs_a_retained_owner_decision(self):
        value = retained(); value["source_records"].pop()
        value["facts"].update(raw_status="NO_RELEASE_ROW; OWNER_REPORTS_CLOSED", reported_balance="0", closed_on=None)
        with self.assertRaises(ValueError):
            self.prepare(value)

    def test_existing_borrower_reference_cannot_point_to_another_source_customer(self):
        value = retained(); value["facts"]["borrower_reference"]["id"] = "contact_customer:2"
        with self.assertRaises(ValueError):
            self.prepare(value)

    def test_source_table_ids_and_release_identity_must_agree(self):
        for table in ("loan", "release"):
            value = retained()
            if table == "loan": value["source_records"][0]["source"]["id"] = "2"
            else: value["source_records"][1]["source"]["external_id"] = "girvi_release:2"
            with self.assertRaises(ValueError):
                self.prepare(value)
