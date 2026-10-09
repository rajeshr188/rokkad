"""No previous receipts or monitoring policy are prerequisites for a closed position."""
from copy import deepcopy
import json
from pathlib import Path
from django.test import SimpleTestCase

from apps.tenant_apps.loans.services import closed_position_contract as contract
from apps.tenant_apps.loans.services.portability_validation import PortabilityValidationError


def document():
    return dict(profile=contract.PROFILE,
        source=dict(namespace="491cf2e4-99eb-499c-b555-68f3a8d5caaa", system="external-register", loan_id="loan-1"),
        loan=dict(number="OLD0001", borrower_reference=dict(system="external-register", id="borrower-1"),
            original_date=None, closed_on=None, original_principal=None, monthly_rate=None, tenure_months=None),
        position=dict(state="CLOSED", as_of="2026-10-09", currency="INR", principal="0", interest="0", fees="0",
            custody="UNKNOWN", basis="OWNER_CLOSED_POSITION", evidence_reference="Owner-reviewed closed loan register"),
        earlier_history="UNAVAILABLE", retained_evidence=None)


class ClosedPositionContractTests(SimpleTestCase):
    def test_published_version_one_schema_is_frozen(self):
        from django.conf import settings
        published = json.loads((Path(settings.BASE_DIR) / "docs/contracts/loan-closed-position-v1.schema.json").read_text())
        self.assertEqual(published, {"$schema": "https://json-schema.org/draft/2020-12/schema", **contract.SCHEMA})

    def test_unknown_original_terms_need_no_receipts_policy_approval_or_collateral(self):
        value = document()
        self.assertEqual(contract.parse(contract.encode(value)), value)
        report = contract.review_document(value)
        self.assertEqual(report["balances"], dict(principal="0", interest="0", fees="0"))
        self.assertEqual(report["earlier_history"], "UNAVAILABLE")
        self.assertFalse(report["admission_authorized"])
        for key in ("requires_monitoring_policy", "requires_origination_approval", "requires_receipt_reconstruction"):
            self.assertFalse(report[key])
        self.assertIn("original_principal", report["missing_original_details"])

    def test_known_details_are_preserved_without_a_complete_calculation_contract(self):
        value = document()
        value["loan"].update(original_date="2000-01-01", closed_on="2000-02-01", original_principal="1000.00", monthly_rate="0", tenure_months=12)
        value["position"]["custody"] = "RETURNED_TO_BORROWER"
        self.assertEqual(contract.parse(contract.encode(value)), value)

    def test_unknown_amount_is_not_encoded_as_zero(self):
        value = document()
        value["loan"]["original_principal"] = "0"
        with self.assertRaises(PortabilityValidationError):
            contract.validate_document(value)

    def test_active_or_nonzero_position_cannot_be_described_as_closed(self):
        for key, actual in (("state", "ACTIVE"), ("principal", "1"), ("interest", "1"), ("fees", "1")):
            with self.subTest(key=key):
                value = document(); value["position"][key] = actual
                with self.assertRaises(PortabilityValidationError):
                    contract.validate_document(value)

    def test_dates_cannot_be_invented_to_fit_a_position(self):
        for original, closed in (("2026-10-10", None), (None, "2026-10-10"), ("2026-10-01", "2026-09-30")):
            with self.subTest(original=original, closed=closed):
                value = document(); value["loan"].update(original_date=original, closed_on=closed)
                with self.assertRaises(PortabilityValidationError):
                    contract.validate_document(value)

    def test_no_fake_history_or_settings_extensions(self):
        for key in ("events", "policy", "approval", "monitoring"):
            value = document(); value[key] = {}
            with self.assertRaises(PortabilityValidationError):
                contract.validate_document(value)
        value = document(); value["earlier_history"] = "COMPLETE"
        with self.assertRaises(PortabilityValidationError):
            contract.validate_document(value)

    def test_malformed_duplicate_key_float_and_unbounded_payload_refused(self):
        samples = [b'{"profile":"a","profile":"b"}', b'{"amount":NaN}',
            contract.encode(document()).replace(b'"original_principal":null', b'"original_principal":10.1'),
            b'x' * (contract.MAX_BYTES + 1), b'\xff', b'[]']
        for sample in samples:
            with self.subTest(prefix=sample[:30]):
                with self.assertRaises(PortabilityValidationError):
                    contract.parse(sample)

    def test_retained_source_identity_known_values_and_raw_rows_are_bound(self):
        from apps.tenant_apps.data_portability.tests.test_loan_archive import document as archive_document
        evidence = archive_document()
        value = document(); source = evidence["source"]; facts = evidence["facts"]
        value["source"] = {key: source[key] for key in ("namespace", "system", "loan_id")}
        value["loan"].update(number=facts["loan_number"], borrower_reference=facts["borrower_reference"],
            original_date=facts["opened_on"], original_principal=facts["original_principal"])
        value["retained_evidence"] = evidence
        self.assertEqual(contract.parse(contract.encode(value)), value)
        for key, different in (("number", "DIFFERENT"), ("original_date", None), ("original_principal", None)):
            changed = deepcopy(value); changed["loan"][key] = different
            with self.assertRaises(PortabilityValidationError):
                contract.validate_document(changed)
        changed = deepcopy(value); changed["source"]["loan_id"] = "another-loan"
        with self.assertRaises(PortabilityValidationError):
            contract.validate_document(changed)
        changed = deepcopy(value); changed["retained_evidence"]["facts"]["reported_balance"] = "1"
        with self.assertRaises(PortabilityValidationError):
            contract.validate_document(changed)
