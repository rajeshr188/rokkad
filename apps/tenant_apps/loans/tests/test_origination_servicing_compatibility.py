"""LO-04: actual admission paths, mixed rates and independent monitoring facts."""
from datetime import date
from decimal import Decimal
from io import StringIO
import json
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain.monthly_contract import item_monthly_interest
from apps.tenant_apps.loans.selectors.continuation import resolve_loan_continuation
from apps.tenant_apps.loans.selectors.evidence_quality import loan_evidence_quality
from apps.tenant_apps.loans.selectors.interest_contract_inventory import interest_contract_inventory
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
from apps.tenant_apps.loans.services.paper_repayments import preview_paper_repayment, record_paper_repayment
from apps.tenant_apps.loans.services.pawn_interest import finalize_pawn_loan_accrual
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from .test_continuation_admissions import AdmissionFixture
from .test_settlement_continuation import on
from .test_opening_release import OpeningReleaseFixture


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MixedRateServicingTests(AdmissionFixture):
    multiple_items = True
    principal = Decimal("5025.50")
    reduction = Decimal("100.50")
    second_rate = Decimal("4")

    def paper_receipt(self, loan, day, amount, split, key):
        facts = dict(amount=amount, received_on=day, receipt_reference="Synthetic book / " + key,
            request_key=key, actor=self.actor, item_principal_split=split)
        review = preview_paper_repayment(loan.pk, **facts)
        result = record_paper_repayment(loan.pk, **facts, review_token=review.review_token, confirmed_received=True)
        count = loan.loan_events.count()
        self.assertTrue(record_paper_repayment(loan.pk, **facts, review_token=review.review_token,
            confirmed_received=True).already_recorded)
        self.assertEqual(loan.loan_events.count(), count)
        return result

    def interest(self, principals):
        return sum(item_monthly_interest(p, r, self.quantum) for p, r in zip(principals, self.item_rates))

    def test_completed_receipt_uses_actual_lower_rate_split_on_every_origin(self):
        received, entered = date(2026, 5, 5), date(2026, 5, 7)
        reduction = Decimal("125.25")
        with self.scoped(), on(entered):
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    items = list(loan.collateral_items.order_by("pk"))
                    before = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
                    facts = dict(amount=reduction, received_on=received, receipt_reference="Missing split",
                        request_key="missing-split", actor=self.actor)
                    with self.assertRaisesMessage(ValueError, "item"):
                        preview_paper_repayment(loan.pk, **facts)
                    with self.assertRaises(ValueError):
                        preview_paper_repayment(loan.pk, **facts,
                            item_principal_split={str(self.loans[(self.loans.index(loan)+1) % 4].collateral_items.first().pk): reduction})
                    self.assertEqual(before, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
                    result = self.paper_receipt(loan, received, reduction,
                        {str(items[0].pk): str(reduction), str(items[1].pk): "0"}, "lower-rate-" + str(loan.pk))
                    self.assertEqual((result.allocation.interest, result.allocation.principal), (0, reduction))
                    self.assertEqual(result.loan_event.effective_date, received)
                    self.assertEqual(result.loan_event.created_at.date(), entered)
                    self.assertEqual(result.loan_event.payload["repayment"]["item_principal_allocation_order"], "STAFF_SPECIFIED")
                    remaining = (self.item_remaining[0]-reduction, self.item_remaining[1])
                    self.assertEqual(tuple(t.principal_outstanding for t in get_pawn_principal_tranche_balances(loan)), remaining)
                    expected = self.interest(remaining)
                    self.assertEqual(get_servicing_position(loan, as_of_date=date(2026, 5, 6)).balance.interest_outstanding, expected)
                    for pk, fingerprint in before:
                        self.assertEqual(m.PawnLoanEvent.objects.get(pk=pk).payload_fingerprint, fingerprint)
                    # A current collection retains the ordinary highest-rate-first
                    # rule even when the financial origin was paper or a checkpoint.
                    with on(date(2026, 5, 7)):
                        current = record_pawn_loan_repayment(loan.pk, amount=expected+100,
                            request_key="current-after-paper-"+str(loan.pk), actor=self.actor)
                    self.assertEqual(current.item_allocations[0].collateral_item_id, items[1].pk)
                    self.assertEqual(current.item_allocations[0].principal_applied, 100)
                    self.assertEqual(get_servicing_position(loan, as_of_date=date(2026, 6, 6)).balance.interest_outstanding,
                        self.interest((remaining[0], remaining[1]-100)))

    def test_payment_on_charge_day_changes_following_month_not_that_charge(self):
        day, reduction = date(2026, 5, 6), Decimal("125.25")
        recording_clock = timezone.now()
        with self.scoped(), on(date(2026, 5, 7)):
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    items = list(loan.collateral_items.order_by("pk"))
                    result = self.paper_receipt(loan, day, self.monthly+reduction,
                        {str(items[0].pk): str(reduction)}, "boundary-"+str(loan.pk))
                    self.assertEqual((result.allocation.interest, result.allocation.principal), (self.monthly, reduction))
                    self.assertEqual(get_servicing_position(loan, as_of_date=date(2026, 6, 5)).balance.interest_outstanding, 0)
                    expected = self.interest((self.item_remaining[0]-reduction, self.item_remaining[1]))
                    self.assertEqual(get_servicing_position(loan, as_of_date=date(2026, 6, 6)).balance.interest_outstanding, expected)
                    continuation = resolve_loan_continuation(loan, as_of_date=date(2026, 6, 6))
                    self.assertEqual(continuation.contract.currency_quantum, self.quantum)
                    self.assertEqual(continuation.recorded_balance.principal_outstanding, self.remaining-reduction)
                    if loan.pk == self.opening.pk:
                        from apps.tenant_apps.loans.services.opening_export import export_opening
                        from apps.tenant_apps.loans.services.opening_restore import parse_opening_export
                        # Admission was entered in October; a May receipt date
                        # does not backdate the checkpoint's recording timestamp.
                        with patch("django.utils.timezone.now", return_value=recording_clock):
                            exported = parse_opening_export(export_opening(workspace_id=self.a.pk,
                                actor=self.actor, loan_id=loan.pk))
                        self.assertEqual(exported["manifest"]["profile"], "loan-opening-export/4")


class MixedRateWholeRupeeServicingTests(MixedRateServicingTests):
    quantum = Decimal("1")


class OriginationMonitoringCompatibilityTests(AdmissionFixture):
    def test_current_appraisal_books_and_risk_refresh_are_independent_on_every_origin(self):
        day = date(2026, 7, 21)
        with self.scoped(), on(day):
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    frozen = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
                    refresh_loan_risk_snapshot(loan.pk, as_of_date=day)
                    loan.refresh_from_db()
                    quality = loan_evidence_quality(loan, as_of_date=day)
                    self.assertEqual(quality["assessment"]["status"], "CURRENT")
                    self.assertEqual(quality["calculation"]["status"], "SUPPORTED")
                    self.assertEqual(quality["valuation"]["status"], "UNAVAILABLE")
                    original_coverage = quality["transactions"]["complete"]
                    item = loan.collateral_items.get()
                    record_collateral_reappraisal(loan_id=loan.pk, item_id=item.pk, actor=self.actor,
                        appraised_value=10000, method="PHYSICAL_INSPECTION", evidence_reference="Synthetic current inspection",
                        review_notes="Valuation is independent of original lending evidence", expected_version=item.appraisals.count())
                    loan.refresh_from_db()
                    self.assertEqual(loan_evidence_quality(loan, as_of_date=day)["assessment"]["status"], "STALE")
                    snapshot = refresh_loan_risk_snapshot(loan.pk, as_of_date=day)
                    loan.refresh_from_db()
                    quality = loan_evidence_quality(loan, as_of_date=day)
                    self.assertEqual(quality["valuation"]["status"], "ELIGIBLE")
                    self.assertEqual(quality["transactions"]["complete"], original_coverage)
                    self.assertEqual(snapshot.exposure, self.remaining+self.monthly*3)
                    facts = dict(through_date=day, confirmed_complete=True, source_reference="Synthetic book reconciliation",
                        request_key="books-"+str(loan.pk))
                    _, token = preview_transaction_review(loan.pk, actor=self.actor, **facts)
                    confirm_transaction_review(loan.pk, actor=self.actor, **facts, review_token=token, acknowledged=True)
                    loan.refresh_from_db()
                    self.assertTrue(loan_evidence_quality(loan, as_of_date=day)["transactions"]["complete"])
                    self.assertEqual(frozen, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
                    if loan.pk in (self.paper.pk, self.imported.pk):
                        self.assertFalse(loan.approval_snapshots.exists())
                        self.assertEqual(loan.policy_snapshot.basis, "RECORDED_CONTRACT")
                    if loan.pk == self.opening.pk:
                        self.assertEqual(quality["history"]["from_date"], self.cutover)
                        self.assertEqual(quality["history"]["principal_basis"], "OPENING_CHECKPOINT")

    def test_inventory_separates_supported_contract_from_reversed_charge_hold(self):
        with self.scoped(), on(date(2026, 5, 6)):
            rows = interest_contract_inventory()
            self.assertEqual({row["status"] for row in rows}, {"SHARED_CONTRACT"})
            self.assertEqual({row["continuation_status"] for row in rows}, {"SUPPORTED"})
            charge = finalize_pawn_loan_accrual(self.direct.pk, actor=self.actor, period_number=1)
            charge = finalize_pawn_loan_accrual(self.direct.pk, actor=self.actor, period_number=2)
            reverse_pawn_loan_event(charge.loan_event.pk, actor=self.actor, reason="Synthetic monthly recognition correction")
            before = list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint"))
            row = next(r for r in interest_contract_inventory() if r["loan_id"] == self.direct.pk)
            self.assertEqual(row["status"], "SHARED_CONTRACT")
            self.assertEqual(row["continuation_status"], "HELD")
            self.assertIn("reversed monthly charge", row["continuation_blocker"])
            self.assertEqual(row["disposition"], "HOLD_AND_REVIEW")
            self.assertFalse(row["automatic_conversion"])
            output = StringIO()
            call_command("check_loan_interest_contracts", workspace_id=self.a.pk, stdout=output)
            printed = next(json.loads(line) for line in output.getvalue().splitlines()
                if json.loads(line)["loan_id"] == self.direct.pk)
            self.assertEqual(printed["continuation_status"], "HELD")
            self.assertEqual(before, list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint")))
            with self.assertRaises(ValueError):
                interest_contract_inventory(as_of_date="2026-05-06")
            invalid = m.PawnLoan.objects.create(workspace=self.a, borrower=self.direct.borrower,
                license=self.direct.license, series=self.direct.series, product_version=self.direct.product_version,
                loan_number="MISSING-ORIGIN", loan_date=self.original, principal_amount=100,
                monthly_interest_rate=2, tenure_months=12, state="ACTIVE")
            row = next(r for r in interest_contract_inventory() if r["loan_id"] == invalid.pk)
            self.assertEqual(row["status"], "INVALID_ORIGIN")
            self.assertEqual(row["continuation_status"], "HELD")
            self.assertEqual(row["disposition"], "HOLD_AND_REVIEW")
        with self.scoped(self.b):
            self.assertEqual(interest_contract_inventory(), [])


class LegacyOpeningInventoryTests(OpeningReleaseFixture):
    def test_retained_opening_rounding_is_reported_without_adopting_shared_terms(self):
        day = date(2021, 2, 2)
        with on(day):
            before = list(self.loan.loan_events.values_list("pk", "payload_fingerprint"))
            position = get_servicing_position(self.loan, as_of_date=day)
            self.assertEqual(position.contract.rounding_mode, self.payload["opening"]["review"]["terms"]["rounding_mode"])
            self.assertEqual(position.contract.rounding_mode, "HALF_EVEN")
            row = next(r for r in interest_contract_inventory() if r["loan_id"] == self.loan.pk)
            self.assertEqual(row["status"], "REVIEW_CORRECTION")
            self.assertEqual(row["rounding_mode"], "HALF_EVEN")
            self.assertEqual(row["rounding_scope"], "AGGREGATE")
            self.assertEqual(row["currency_quantum"], "1")
            self.assertEqual(row["policy_currency_quantum"], "0.01")
            self.assertEqual(row["disposition"], "KEEP_FROZEN_TERMS_OR_EXPLICITLY_CORRECT")
            self.assertFalse(row["automatic_conversion"])
            self.assertEqual(before, list(self.loan.loan_events.values_list("pk", "payload_fingerprint")))
