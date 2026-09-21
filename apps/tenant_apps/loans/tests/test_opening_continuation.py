import copy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.services.legacy_interest import AGGREGATE_RULE, aggregate_collection_interest
from apps.tenant_apps.loans.services.opening_validation import COLLECTION_PROFILE, validate_opening
from apps.tenant_apps.loans.services.opening_evidence import opening_event_payload, OpeningEvidenceError
from apps.tenant_apps.loans.services.opening_continuation import preview_opening_collection, opening_interest_breakdown
from apps.tenant_apps.loans.tests.test_opening_validation import reviewed_opening
from apps.tenant_apps.loans.tests.test_opening_evidence import loan_reference


def collection_review(original=date(2021, 1, 1), cutover=date(2021, 1, 20), *, rate="1", unpaid=None):
    """Synthetic reviewed evidence only; never used to fill source candidates."""
    doc = reviewed_opening()
    doc["profile"] = COLLECTION_PROFILE
    doc["source"]["loan_timestamp"] = original.isoformat() + "T00:00:00+00:00"
    doc["cutover"]["date"] = cutover.isoformat()
    doc["terms"].update(original_date=original.isoformat(), billing_anchor=original.isoformat(),
        maturity_date=f"{original.year}-04-30", rule_id=AGGREGATE_RULE, partial_rule="INCLUSIVE_UPFRONT")
    doc["collateral"][0].update(original_principal="1000", remaining_principal="1000", monthly_rate=rate)
    doc["collateral"][0]["valuation"]["date"] = cutover.isoformat()
    calculated = aggregate_collection_interest(original, cutover, Decimal("1000") * Decimal(rate) / 100)
    baseline = calculated["additional_interest"]
    interest = baseline if unpaid is None else unpaid
    doc["balances"].update(principal="1000", interest=interest)
    doc["obligations"][0].update(due=f"{original.year}-04-30", principal="1000", interest=str(Decimal(interest) + 100), recognized_interest=interest)
    doc["continuation"] = {"covered_through": cutover.isoformat(), "additional_months": calculated["additional_months"],
        "recognized_interest": baseline, "recognized_unpaid_interest": interest, "first_month_paid": True,
        "evidence_reference": "Synthetic approved coverage including earlier recognized interest"}
    return doc


class OpeningContinuationTests(SimpleTestCase):
    def test_breakdown_distinguishes_elapsed_time_from_chargeable_months(self):
        doc = collection_review(date(2026, 1, 10), date(2026, 2, 10), rate="20")
        row = opening_interest_breakdown(doc, as_of_date=date(2026, 2, 10))
        self.assertEqual((row["elapsed_months"], row["elapsed_days"], row["charge_months"]), (1, 0, 0))
        self.assertEqual(row["total_interest"], 0)
        row = opening_interest_breakdown(doc, as_of_date=date(2026, 2, 11))
        self.assertEqual((row["charge_months"], row["new_months"], row["total_interest"]), (1, 1, 200))

    def test_breakdown_preserves_partial_paid_coverage_and_rounds_cumulatively(self):
        doc = collection_review(date(2026, 1, 10), date(2026, 2, 11), rate="14.82", unpaid="90")
        row = opening_interest_breakdown(doc, as_of_date=date(2026, 4, 11))
        self.assertEqual(row["monthly_interest"], Decimal("148.20"))
        self.assertEqual((row["cutover_months"], row["charge_months"], row["new_months"]), (1, 3, 2))
        self.assertEqual(row["cumulative_interest"], 445)
        self.assertEqual(row["additional_interest"], 297)
        self.assertEqual(row["total_interest"], 387)

    def test_breakdown_short_month_boundary_and_pre_cutover_rejection(self):
        doc = collection_review(date(2026, 1, 31), date(2026, 2, 28))
        row = opening_interest_breakdown(doc, as_of_date=date(2026, 2, 28))
        self.assertEqual(row["charge_months"], 0)
        self.assertEqual(row["next_increase_on"], date(2026, 3, 1))
        self.assertEqual(opening_interest_breakdown(doc, as_of_date=date(2026, 3, 1))["charge_months"], 1)
        with self.assertRaises(OpeningEvidenceError):
            opening_interest_breakdown(doc, as_of_date=date(2026, 2, 27))

    def preview(self, doc, day):
        loan = loan_reference()
        loan.loan_date = date.fromisoformat(doc["terms"]["original_date"])
        mapping = {item["id"]: 11 + index for index, item in enumerate(doc["collateral"])}
        event = SimpleNamespace(pk=1, event_kind="MIGRATION_OPENING", effective_date=date.fromisoformat(doc["cutover"]["date"]),
            payload=opening_event_payload(loan, review=doc, item_mapping=mapping))
        return preview_opening_collection(loan, events=(event,), as_of_date=day)

    def test_first_month_and_inclusive_month_end_boundaries(self):
        for original, cutover, cases in (
            (date(2026, 1, 10), date(2026, 1, 20), ((date(2026, 2, 10), 0), (date(2026, 2, 11), 200), (date(2026, 2, 20), 200))),
            (date(2026, 1, 31), date(2026, 2, 10), ((date(2026, 2, 28), 0), (date(2026, 3, 1), 200), (date(2026, 3, 31), 200), (date(2026, 4, 1), 400))),
            (date(2024, 1, 31), date(2024, 2, 10), ((date(2024, 2, 29), 0), (date(2024, 3, 1), 200), (date(2024, 4, 1), 400))),
        ):
            doc = collection_review(original, cutover, rate="20")
            for day, expected in cases:
                with self.subTest(original=original, day=day):
                    self.assertEqual(self.preview(doc, day).additional_interest, expected)

    def test_cutover_recognition_is_not_charged_again_when_already_paid_or_lost(self):
        doc = collection_review(date(2026, 1, 10), date(2026, 3, 15), rate="20", unpaid="290")
        self.assertEqual(doc["continuation"]["recognized_interest"], "400")
        self.assertEqual(self.preview(doc, date(2026, 3, 20)).additional_interest, 0)
        self.assertEqual(self.preview(doc, date(2026, 4, 11)).additional_interest, 200)
        self.assertEqual(doc["balances"]["interest"], "290")

    def test_cumulative_rounding_is_independent_of_cutover(self):
        # 148.2 monthly: cumulative 148, 296, 445. Monthly rounding would lose 1.
        values = []
        for month, next_month in ((2, 3), (3, 4)):
            doc = collection_review(date(2026, 1, 10), date(2026, month, 11), rate="14.82")
            values.append(self.preview(doc, date(2026, next_month, 11)).additional_interest)
        self.assertEqual(values, [148, 149])
        doc = collection_review(date(2026, 1, 10), date(2026, 2, 11), rate="14.82")
        self.assertEqual(self.preview(doc, date(2026, 4, 11)).additional_interest, sum(values))

    def test_rounding_aggregates_items_before_months(self):
        doc = collection_review(date(2026, 1, 10), date(2026, 1, 20), rate="14.82")
        item = copy.deepcopy(doc["collateral"][0])
        item["id"] = "girvi_loanitem:2"
        doc["collateral"].append(item)
        doc["source"]["item_ids"].append(item["id"])
        doc["balances"]["principal"] = doc["obligations"][0]["principal"] = "2000"
        result = validate_opening(doc)
        self.assertTrue(result["document_reconciled"], result["issues"])
        self.assertEqual(result["reconciliation"]["collection_checkpoint"]["monthly_interest_unrounded"], "296.40")
        self.assertEqual(self.preview(doc, date(2026, 4, 11)).additional_interest, 889)

    def test_changed_principal_missing_coverage_and_rule_overrides_are_held(self):
        mutations = (("continuation", "first_month_paid", False), ("continuation", "recognized_interest", "1"),
            ("continuation", "covered_through", "2021-01-19"), ("continuation", "additional_months", 1),
            ("terms", "period_rule", "CLAMPED_CONTIGUOUS"), ("terms", "rounding_scope", "PER_ITEM"),
            ("terms", "rule_id", "unknown"), ("terms", "interest_basis", "OUTSTANDING_AT_PERIOD_START"))
        for group, key, value in mutations:
            doc = collection_review()
            doc[group][key] = value
            with self.subTest(group=group, key=key):
                self.assertFalse(validate_opening(doc)["document_reconciled"])
        doc = collection_review()
        doc["collateral"][0]["remaining_principal"] = doc["balances"]["principal"] = doc["obligations"][0]["principal"] = "900"
        self.assertIn("COLLECTION_PRINCIPAL_CHANGED", {i["code"] for i in validate_opening(doc)["issues"]})

    def test_unknown_unpaid_interest_is_never_zero_and_old_profile_is_not_upgraded(self):
        doc = collection_review()
        doc["balances"]["interest"] = None
        self.assertFalse(validate_opening(doc)["document_reconciled"])
        with self.assertRaisesMessage(OpeningEvidenceError, "supported collection"):
            self.preview(reviewed_opening(), date(2021, 2, 1))

    def test_cutover_is_zero_continuation_and_prior_dates_are_unavailable(self):
        doc = collection_review()
        self.assertEqual(self.preview(doc, date(2021, 1, 20)).additional_interest, 0)
        with self.assertRaisesMessage(OpeningEvidenceError, "before the migration cutover"):
            self.preview(doc, date(2021, 1, 19))
        result = validate_opening(doc)
        self.assertEqual(result["profile"], COLLECTION_PROFILE)
        self.assertFalse(result["import_ready"])
