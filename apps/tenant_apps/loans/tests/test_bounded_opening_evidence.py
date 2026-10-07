"""Actual admission and servicing of LC-05's explicit evidence profiles."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain.monthly_contract import RULE
from apps.tenant_apps.loans.services.opening_continuation import preview_opening_collection
from apps.tenant_apps.loans.services.opening_export import export_opening
from apps.tenant_apps.loans.services.opening_restore import parse_opening_export
from apps.tenant_apps.loans.services.opening_validation import validate_opening
from apps.tenant_apps.loans.services.paper_repayments import preview_paper_repayment, record_paper_repayment
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from .test_opening_import import OpeningImportFixture
from .test_opening_checkpoint import checkpoint


class ExplicitOpeningFixture(OpeningImportFixture):
    precise = False

    def setUp(self):
        super().setUp()
        self.review.update(checkpoint(self.review))
        first = self.review["collateral"][0]
        first.update(original_principal="500", remaining_principal="400")
        second = deepcopy(first)
        second.update(id="girvi_loanitem:2", description="Second ring", monthly_rate="2")
        self.review["collateral"].append(second)
        self.review["source"]["item_ids"].append(second["id"])
        self.review["continuation"].update(bases=[dict(item_id=i["id"], principal_base="450") for i in self.review["collateral"]],
            expected_period_interest="13.50", recognized_interest="13.50", current_period_recognized_interest="13.50")
        self.review["balances"]["fees"] = "25"
        if self.precise:
            self.review["profile"] = "loan-opening-review/5"
            self.review["cutover"]["occurred_at"] = "2021-02-20T10:00:00+05:30"
        self.setup["policy"].update(policy_version=2, minimum_first_month=False)
        with self.scoped():
            m.LoanProductVersion.objects.filter(pk=self.review["mapping"]["product_version_id"]).update(calculation_contract_version=RULE)
            self.origin = self.write()
            self.loan = self.origin.loan
            self.items = list(self.loan.collateral_items.order_by("pk"))
        self.on = date(2021, 2, 21)

    def receipt(self, **changes):
        values = dict(amount="115", received_on=self.on, receipt_reference="Book / receipt 5",
            request_key="explicit-5", actor=self.actor, fees_paid="10",
            item_principal_split={str(self.items[0].pk): "70", str(self.items[1].pk): "30"})
        values.update(changes)
        review = preview_paper_repayment(self.loan.pk, **values)
        result = record_paper_repayment(self.loan.pk, **values, review_token=review.review_token, confirmed_received=True)
        return result, values, review


class ExplicitOpeningTests(ExplicitOpeningFixture):
    def test_explicit_item_split_and_fee_component_replay_next_month_and_retry(self):
        with self.scoped():
            result, values, review = self.receipt()
            self.assertEqual((result.allocation.fees, result.allocation.interest, result.allocation.principal), (10, 5, 100))
            self.assertEqual(result.loan_event.payload["opening_collection"]["profile"], "opening-payments/2")
            self.assertEqual(result.loan_event.payload["repayment"]["recording"]["profile"], "paper-repayment/2")
            self.assertTrue(record_paper_repayment(self.loan.pk, **values, review_token=review.review_token, confirmed_received=True).already_recorded)
            position = get_servicing_position(self.loan, as_of_date=date(2021, 3, 2))
            self.assertEqual((position.balance.principal_outstanding, position.balance.interest_outstanding,
                              position.balance.fees_outstanding), (700, Decimal("10.70"), 15))
            exported = parse_opening_export(export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk))
            self.assertEqual(exported["manifest"]["profile"], "loan-opening-export/4")

    def test_missing_fee_component_and_missing_split_do_not_write(self):
        with self.scoped():
            for changes in ({"fees_paid": None}, {"item_principal_split": None}, {"fees_paid": "30"},
                    {"item_principal_split": {str(self.items[0].pk): "100", str(self.items[1].pk): "1"}}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    self.receipt(**changes)
                self.assertEqual(self.loan.loan_events.count(), 1)

    def test_explicit_zero_fees_does_not_claim_fee_priority(self):
        with self.scoped():
            result, _, _ = self.receipt(amount="105", fees_paid="0")
            self.assertEqual((result.allocation.fees, result.allocation.principal), (0, 100))
            self.assertEqual(get_servicing_position(self.loan, as_of_date=self.on).balance.fees_outstanding, 25)

    def test_sparse_actual_split_replays_zero_items_and_retains_explicit_fee_component(self):
        with self.scoped():
            result, _, _ = self.receipt(item_principal_split={str(self.items[0].pk): "100"})
            self.assertEqual([row.principal_applied for row in result.item_allocations], [100, 0])
            position = get_servicing_position(self.loan, as_of_date=date(2021, 3, 2))
            self.assertEqual((position.balance.principal_outstanding, position.balance.interest_outstanding,
                position.balance.fees_outstanding), (700, Decimal("11.00"), 15))
            parse_opening_export(export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk))
            for mutation in ("foreign_zero", "missing_zero_line"):
                events = [SimpleNamespace(pk=e.pk, event_kind=e.event_kind, effective_date=e.effective_date,
                    payload=deepcopy(e.payload), reversal_of_id=e.reversal_of_id) for e in self.loan.loan_events.all()]
                row = next(e for e in events if e.pk == result.loan_event.pk)
                if mutation == "foreign_zero":
                    row.payload["repayment"]["recording"]["item_principal_split"]["999999999"] = "0.00"
                else:
                    row.payload["repayment"]["item_principal_allocations"].pop()
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    preview_opening_collection(self.loan, events=events, as_of_date=self.on)

    def test_tampered_explicit_split_or_profile_fails_replay(self):
        with self.scoped():
            result, _, _ = self.receipt()
            for mutation in ("fees", "split", "old_profile"):
                events = [SimpleNamespace(pk=e.pk, event_kind=e.event_kind, effective_date=e.effective_date,
                    payload=deepcopy(e.payload), reversal_of_id=e.reversal_of_id) for e in self.loan.loan_events.all()]
                row = next(e for e in events if e.pk == result.loan_event.pk)
                if mutation == "fees":
                    row.payload["repayment"]["recording"]["fees_paid"] = "9.00"
                elif mutation == "split":
                    row.payload["repayment"]["recording"]["item_principal_split"][str(self.items[0].pk)] = "71.00"
                else:
                    row.payload["opening_collection"]["profile"] = "opening-payments/1"
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    preview_opening_collection(self.loan, events=events, as_of_date=self.on)

    def test_current_payment_priority_and_reversal_are_unchanged(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=self.on):
            result = record_pawn_loan_repayment(self.loan.pk, amount="130", request_key="current", actor=self.actor)
            self.assertEqual((result.allocation.fees, result.allocation.interest, result.allocation.principal), (25, 5, 100))
            self.assertEqual(result.item_allocations[0].collateral_item_id, self.items[1].pk)
            reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Wrong receipt")
            balance = get_servicing_position(self.loan, as_of_date=self.on).balance
            self.assertEqual((balance.principal_outstanding, balance.interest_outstanding, balance.fees_outstanding), (800, 5, 25))


class PreciseOpeningTests(ExplicitOpeningFixture):
    precise = True

    def test_current_same_day_receipts_and_reversal_have_actual_order(self):
        self.on = date(2021, 2, 20)
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=self.on):
            with patch("django.utils.timezone.now", return_value=datetime.fromisoformat("2021-02-20T11:00:00+05:30")):
                first = record_pawn_loan_repayment(self.loan.pk, amount="130", request_key="first-current", actor=self.actor)
            with patch("django.utils.timezone.now", return_value=datetime.fromisoformat("2021-02-20T12:00:00+05:30")):
                second = record_pawn_loan_repayment(self.loan.pk, amount="50", request_key="second-current", actor=self.actor)
            self.assertEqual(get_servicing_position(self.loan, as_of_date=self.on).balance.principal_outstanding, 650)
            events = [SimpleNamespace(pk=e.pk, event_kind=e.event_kind, effective_date=e.effective_date,
                payload=deepcopy(e.payload), reversal_of_id=e.reversal_of_id) for e in self.loan.loan_events.all()]
            next(e for e in events if e.pk == second.loan_event.pk).payload["opening_collection"]["occurred_at"] = first.loan_event.payload["opening_collection"]["occurred_at"]
            with self.assertRaisesMessage(ValueError, "distinct actual timestamps"):
                preview_opening_collection(self.loan, events=events, as_of_date=self.on)
            with patch("django.utils.timezone.now", return_value=datetime.fromisoformat("2021-02-20T13:00:00+05:30")):
                reverse_pawn_loan_event(second.loan_event.pk, actor=self.actor, reason="Wrong second receipt")
            self.assertEqual(get_servicing_position(self.loan, as_of_date=self.on).balance.principal_outstanding, 700)

    def test_current_full_release_after_precise_checkpoint(self):
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        self.on = date(2021, 2, 20)
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=self.on), patch(
                "django.utils.timezone.now", return_value=datetime.fromisoformat("2021-02-20T11:00:00+05:30")):
            release_pawn_loan_in_full(self.loan.pk, actor=self.actor, settlement_amount="830", request_key="precise-release")
            self.loan.refresh_from_db()
            self.assertEqual(self.loan.state, "CLOSED")
            self.assertEqual(get_servicing_position(self.loan, as_of_date=self.on).balance.principal_outstanding, 0)

    def test_actual_receipt_after_checkpoint_same_day_and_order_guard(self):
        with self.scoped():
            self.on = date(2021, 2, 20)
            for actual in (None, "2021-02-20T09:59:00+05:30", "2021-02-20T10:00:00+05:30"):
                with self.subTest(actual=actual), self.assertRaises(ValueError):
                    self.receipt(received_at=actual)
            result, _, _ = self.receipt(received_at="2021-02-20T11:00:00+05:30")
            self.assertEqual(get_servicing_position(self.loan, as_of_date=self.on).balance.principal_outstanding, 700)
            with self.assertRaises(ValueError):
                self.receipt(received_at="2021-02-20T10:30:00+05:30", receipt_reference="Earlier", request_key="earlier")
            exported = parse_opening_export(export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk))
            self.assertEqual(exported["manifest"]["profile"], "loan-opening-export/4")
            self.assertEqual(result.loan_event.payload["opening_collection"]["occurred_at"], "2021-02-20T11:00:00+05:30")

    def test_checkpoint_alone_has_explicit_portable_version(self):
        with self.scoped():
            exported = parse_opening_export(export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=self.loan.pk))
            self.assertEqual(exported["manifest"]["profile"], "loan-opening-export/4")
            self.assertEqual(exported["evidence"]["events"][0]["payload"]["opening"]["review"]["profile"], "loan-opening-review/5")


class PrecisionValidationTests(SimpleTestCase):
    def test_old_profile_cannot_acquire_timestamp_or_precise_profile_lose_it(self):
        doc = checkpoint()
        doc["cutover"]["occurred_at"] = "2021-02-20T10:00:00+05:30"
        self.assertFalse(validate_opening(doc)["document_reconciled"])
        doc["profile"] = "loan-opening-review/5"
        self.assertTrue(validate_opening(doc)["document_reconciled"], validate_opening(doc))
        for actual in (None, "2021-02-20T10:00:00", "2021-02-21T10:00:00+05:30"):
            doc["cutover"]["occurred_at"] = actual
            self.assertFalse(validate_opening(doc)["document_reconciled"])
