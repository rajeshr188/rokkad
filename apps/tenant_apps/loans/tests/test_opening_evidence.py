import copy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.services.opening_evidence import OpeningEvidenceError, opening_event_payload, read_opening_evidence
from apps.tenant_apps.loans.selectors.balances import calculate_pawn_loan_balance, PawnLoanBalanceSelectorError
from apps.tenant_apps.loans.tests.test_opening_validation import reviewed_opening


def loan_reference():
    return SimpleNamespace(pk=10, workspace_id=1, borrower_id=2, license_revision_id=3,
                           series_id=4, product_version_id=5, loan_date=date(2021, 1, 1), tenure_months=3)


def opening_event(loan=None):
    loan = loan or loan_reference()
    return SimpleNamespace(pk=1, event_kind="MIGRATION_OPENING", effective_date=date(2021, 1, 20),
        payload=opening_event_payload(loan, review=reviewed_opening(), item_mapping={"girvi_loanitem:1": 11}))


class OpeningEvidenceTests(SimpleTestCase):
    def setUp(self):
        self.loan = loan_reference()
        self.origin = opening_event(self.loan)

    def balance(self, events=None, day=date(2021, 1, 20)):
        return calculate_pawn_loan_balance(self.loan, events=events or [self.origin], collateral_items=(),
            policy_snapshot=SimpleNamespace(currency_quantum=Decimal("0.01"), interest_method="SIMPLE"), as_of_date=day)

    def event(self, pk, kind, day, **values):
        return SimpleNamespace(pk=pk, event_kind=kind, effective_date=day, payload={"values": values})

    def test_opening_is_not_new_lending_or_fabricated_accrual_and_payment_history(self):
        result = self.balance()
        self.assertEqual((result.opening_principal, result.opening_interest, result.opening_fees), (900, 24, 0))
        self.assertEqual((result.principal_disbursed, result.interest_accrued, result.principal_paid, result.interest_paid), (0, 0, 0, 0))
        self.assertEqual(result.total_due, 924)
        self.assertEqual(result.financial_history_from, date(2021, 1, 20))
        self.assertEqual(result.due_date, date(2021, 4, 1))

    def test_post_cutover_events_use_opening_amounts_and_concessions(self):
        payment = self.event(2, "REPAYMENT", date(2021, 1, 21), principal="100", interest="10")
        result = self.balance([self.origin, payment], date(2021, 1, 21))
        self.assertEqual((result.principal_outstanding, result.interest_outstanding), (800, 14))
        release = self.event(3, "RELEASE_RECEIPT", date(2021, 1, 22), principal="800", interest="9", interest_concession="5")
        settled = self.balance([self.origin, payment, release], date(2021, 1, 22))
        self.assertTrue(settled.financially_settled)
        self.assertEqual((settled.principal_paid, settled.interest_paid, settled.interest_conceded), (900, 19, 5))
        reversal = self.event(4, "REVERSAL", date(2021, 1, 23), principal="800", interest="9", interest_concession="5")
        reversal.payload["reversal"] = {"original_event_kind": "RELEASE_RECEIPT"}
        restored = self.balance([self.origin, payment, release, reversal], date(2021, 1, 23))
        self.assertEqual((restored.principal_outstanding, restored.interest_outstanding, restored.interest_conceded), (800, 14, 0))

    def test_earlier_history_and_overlapping_events_are_rejected(self):
        with self.assertRaisesMessage(PawnLoanBalanceSelectorError, "before the migration cutover"):
            self.balance(day=date(2021, 1, 19))
        for day in (date(2021, 1, 19), date(2021, 1, 20)):
            with self.subTest(day=day), self.assertRaisesMessage(PawnLoanBalanceSelectorError, "strictly after"):
                self.balance([self.origin, self.event(2, "REPAYMENT", day, principal="1")])

    def test_duplicate_mixed_or_reversed_opening_is_not_a_valid_origin(self):
        for kind in ("MIGRATION_OPENING", "DISBURSAL", "RENEWAL_OPENING", "REVERSAL"):
            second = self.event(2, kind, date(2021, 1, 21), principal="900")
            if kind == "REVERSAL":
                second.payload["reversal"] = {"original_event_kind": "MIGRATION_OPENING"}
            with self.subTest(kind=kind), self.assertRaises(PawnLoanBalanceSelectorError):
                self.balance([self.origin, second], date(2021, 1, 22))

    def test_frozen_review_and_materialized_amounts_must_match(self):
        for key, value in (("principal", "901"), ("interest", "NaN"), ("fees", "1"), ("net_cash", "900")):
            event = copy.deepcopy(self.origin)
            event.payload["values"][key] = value
            with self.subTest(key=key), self.assertRaises(PawnLoanBalanceSelectorError):
                self.balance([event])
        event = copy.deepcopy(self.origin)
        event.payload["opening"]["review"]["continuation"] = None
        with self.assertRaises(PawnLoanBalanceSelectorError):
            self.balance([event])

    def test_destinations_item_mapping_and_dates_cannot_be_rebound(self):
        for attr in ("workspace_id", "borrower_id", "license_revision_id", "series_id", "product_version_id"):
            loan = copy.copy(self.loan)
            setattr(loan, attr, 999)
            with self.subTest(attr=attr), self.assertRaises(OpeningEvidenceError):
                read_opening_evidence(loan, self.origin)
        for mapping in ({}, {"girvi_loanitem:1": True}, {"girvi_loanitem:1": -1}, {"other": 11}):
            with self.subTest(mapping=mapping), self.assertRaises(OpeningEvidenceError):
                opening_event_payload(self.loan, review=reviewed_opening(), item_mapping=mapping)
        self.origin.effective_date = date(2021, 1, 21)
        with self.assertRaises(OpeningEvidenceError):
            read_opening_evidence(self.loan, self.origin)

    def test_unsupported_currency_version_or_reversal_envelope_is_rejected(self):
        for key, value in (("currency", "USD"), ("contract_version", 2), ("contract_version", True),
                           ("reversal", {"original_event_kind": "DISBURSAL"})):
            event = copy.deepcopy(self.origin)
            event.payload[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(OpeningEvidenceError):
                read_opening_evidence(self.loan, event)

    def test_builder_copies_review_and_keeps_origination_facts_separate(self):
        review = reviewed_opening()
        payload = opening_event_payload(self.loan, review=review, item_mapping={"girvi_loanitem:1": 11})
        review["balances"]["principal"] = "1"
        self.assertEqual(payload["values"]["principal"], "900")
        self.assertEqual(payload["opening"]["review"]["collateral"][0]["original_principal"], "1000")
        self.assertNotIn("net_cash", payload["values"])
        self.assertNotIn("approval", payload)
