from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain.monthly_contract import (
    anniversary, period_dates, charge_count, item_monthly_interest, RULE,
)
from apps.tenant_apps.loans.services.pawn_interest import preview_pawn_loan_accruals, finalize_pawn_loan_accrual
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history, admit_recorded_history
from apps.tenant_apps.loans.services.opening_policy_interest import calculation
from apps.tenant_apps.loans.services.opening_validation import validate_opening
from apps.tenant_apps.loans.selectors.servicing_contract import resolve_servicing_contract
from . import test_recorded_origination as origins, test_recorded_history as histories
from .test_collateral_reappraisal import CollateralReappraisalTests
from .test_opening_import import OpeningImportFixture
from .test_opening_continuation import collection_review


def policy_review(original=date(2021, 1, 1), cutover=date(2021, 1, 20), rate="1", quantum="0.01"):
    review = collection_review(original, cutover, rate=rate)
    review["profile"] = "loan-opening-review/3"
    review["terms"].update(rule_id=RULE, rounding_scope="PER_ITEM", rounding_mode="HALF_UP", interest_quantum=quantum)
    result = calculation(review, cutover)
    review["continuation"].update(recognized_interest=result["additional_interest"],
        recognized_unpaid_interest=result["additional_interest"])
    review["balances"]["interest"] = result["additional_interest"]
    review["obligations"][0]["recognized_interest"] = result["additional_interest"]
    return review


class SharedMonthlyMathTests(SimpleTestCase):
    def test_upfront_april_anniversary_and_later_boundaries(self):
        original = date(2026, 4, 5)
        self.assertEqual(period_dates(original, 1), (original, date(2026, 5, 5)))
        self.assertEqual(period_dates(original, 2), (date(2026, 5, 6), date(2026, 6, 5)))
        for on, count in ((date(2026, 5, 4), 0), (date(2026, 5, 5), 0), (date(2026, 5, 6), 1),
                          (date(2026, 6, 5), 1), (date(2026, 6, 6), 2)):
            self.assertEqual(charge_count(original, on) * item_monthly_interest("10000", "2", ".01"), count * 200)

    def test_short_month_does_not_move_original_anchor(self):
        for year, feb in ((2026, 28), (2024, 29)):
            original = date(year, 1, 31)
            self.assertEqual(anniversary(original, 1), date(year, 2, feb))
            self.assertEqual(period_dates(original, 2), (date(year, 3, 1), date(year, 3, 31)))
            self.assertEqual(charge_count(original, date(year, 3, 1)), 1)
            self.assertEqual(charge_count(original, date(year, 3, 31)), 1)
            self.assertEqual(charge_count(original, date(year, 4, 1)), 2)

    def test_policy_quantum_and_item_period_rounding(self):
        self.assertEqual(item_monthly_interest("5025", "2", "1.0000"), Decimal("101"))
        self.assertEqual(item_monthly_interest("500.25", "2", ".0100"), Decimal("10.01"))
        review = policy_review(rate="1.05", quantum="1")
        self.assertEqual(calculation(review, date(2021, 3, 2))["additional_interest"], "22")

    def test_whole_rupee_interest_keeps_actual_principal_and_fees_in_paise(self):
        from apps.tenant_apps.loans.domain import CollateralTrancheInput, DisbursalFeeInput, calculate_pawn_disbursal_economics
        value = calculate_pawn_disbursal_economics([CollateralTrancheInput(
            reference="ring", metal="GOLD", net_weight=Decimal("10"), purity_percentage=Decimal("100"),
            allocated_principal=Decimal("5025.25"), monthly_interest_rate=Decimal("2"),
            metal_rate_per_unit=None, latest_appraised_value=Decimal("10000"))], valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal(".8"), currency_quantum=Decimal("1"), interest_policy_version=2,
            fees=[DisbursalFeeInput(code="DOC", name="Document", calculation_type="FIXED", value=Decimal("10.25"))])
        self.assertEqual((value.gross_principal, value.advance_interest, value.deducted_fees, value.net_disbursed),
                         (Decimal("5025.25"), Decimal("101"), Decimal("10.25"), Decimal("4914")))

    def test_multi_item_schedule_rounds_each_item_each_month(self):
        from apps.tenant_apps.loans.domain import RepaymentScheduleInput, ScheduleRateTranche
        from apps.tenant_apps.loans.services.repayment_schedules import generate_repayment_schedule
        for structure in ("FLEXIBLE_PARTIAL_PAYMENT", "PERIODIC_INTEREST_BULLET"):
            value = RepaymentScheduleInput(repayment_structure=structure, amortisation_method="NONE",
                disbursed_on=date(2026, 4, 5), principal=Decimal("1000.50"), monthly_interest_rate=Decimal("2"),
                tenure_months=12, interest_policy_version=2,
                rate_tranches=(ScheduleRateTranche(Decimal("500.25"), Decimal("2")),)*2)
            self.assertEqual(generate_repayment_schedule(value).contractual_interest, Decimal("240.24"))

    def test_opening_policy_profile_reconciles_and_rejects_wrong_rule(self):
        review = policy_review()
        self.assertTrue(validate_opening(review)["document_reconciled"])
        review["terms"]["rounding_mode"] = "HALF_EVEN"
        self.assertFalse(validate_opening(review)["document_reconciled"])

    def test_principal_reduction_on_last_covered_day_and_first_new_day(self):
        review = policy_review(date(2026, 4, 5), date(2026, 4, 20), rate="2")
        item = review["collateral"][0]["id"]
        def payment(on):
            return SimpleNamespace(event_kind="REPAYMENT", effective_date=on, payload={"repayment": {
                "item_principal_allocations": [{"collateral_item_id": 17, "principal_applied": "200"}]}})
        mapping = {item: 17}
        self.assertEqual(calculation(review, date(2026, 5, 6), [(payment(date(2026, 5, 5)), None)], mapping)["additional_interest"], "16.00")
        self.assertEqual(calculation(review, date(2026, 5, 6), [(payment(date(2026, 5, 6)), None)], mapping)["additional_interest"], "20.00")
        self.assertEqual(calculation(review, date(2026, 6, 6), [(payment(date(2026, 5, 6)), None)], mapping)["additional_interest"], "36.00")


class SharedPaperContractTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history

    def setUp(self):
        self.prepare_history()
        self.data.update(date="2026-04-05", advance_months=1, cash_paid="9800")

    def admit(self):
        _, token = preview_recorded_history(**self.args, data=self.data)
        return admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)[0]

    def test_paper_upfront_shared_boundary_is_read_only(self):
        loan = self.admit()
        for on, expected in ((date(2026, 5, 5), 0), (date(2026, 5, 6), 200), (date(2026, 6, 5), 200)):
            self.assertEqual(collection_balance(loan, on).interest_outstanding, expected)
        self.assertEqual(resolve_servicing_contract(loan, as_of_date=date(2026, 5, 6)).anniversary_rule, "DAY_AFTER_ORIGINAL_ANNIVERSARY")
        # Closure API is covered separately; the read here must never write accruals.
        self.assertEqual(loan.loan_events.count(), 1)

    def close_on(self, on, amount):
        self.data.update(final_state="CLOSED", events=[histories.RecordedHistoryTests.row(self,
            kind="CLOSE", date=on, amount=amount, number="R-0008", recipient="Borrower")])
        loan = self.admit()
        self.assertEqual(loan.state, "CLOSED")
        self.assertEqual(collection_balance(loan, date(2026, 6, 6)).total_due, 0)
        return loan.releases.get()

    def test_paper_closure_on_covered_anniversary_has_no_additional_charge(self):
        self.assertEqual(self.close_on("2026-05-05", "10000").interest_amount, 0)

    def test_paper_closure_on_next_day_includes_new_month_charge(self):
        self.assertEqual(self.close_on("2026-05-06", "10200").interest_amount, 200)

    def test_paper_quantum_saved_and_not_replaced_by_current_setup(self):
        self.data.update(principal="5025", currency_quantum="1", cash_paid="4924")
        loan = self.admit()
        self.assertEqual(loan.disbursal_snapshot.advance_interest, 101)
        self.assertEqual(collection_balance(loan, date(2026, 5, 6)).interest_outstanding, 101)
        self.assertEqual(collection_balance(loan, date(2026, 6, 6)).interest_outstanding, 202)
        self.assertEqual(loan.policy_snapshot.currency_quantum, 1)
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 6)):
            paid = record_pawn_loan_repayment(loan.pk, amount="201.25", request_key="whole-interest-paise-cash", actor=self.actor)
        self.assertEqual(Decimal(paid.loan_event.payload["values"]["principal"]), Decimal("100.25"))

    def test_legacy_paper_correction_compensates_and_keeps_accepted_amounts(self):
        from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction, record_contract_correction
        from apps.tenant_apps.loans.services.recorded_collections import recording_for
        self.data["events"] = [dict(kind="PAYMENT", date="2026-05-05", amount="2000", reference="Actual receipt",
            number="", rate=None, tenure=None, recipient="")]
        with patch("apps.tenant_apps.loans.services.recorded_history.RECORDED_PROFILE", "recorded-anniversary/1"), \
             patch("apps.tenant_apps.loans.services.recorded_history.POLICY_VERSION", 1):
            loan = self.admit()
        old_origin = loan.disbursal_snapshot.loan_event
        old_payload = deepcopy(old_origin.payload)
        old_receipt = loan.loan_events.get(event_kind="REPAYMENT")
        self.assertEqual(Decimal(old_receipt.payload["values"]["interest"]), 200)
        facts = dict(date="2026-04-05", principal="10000", rate="2", cash_paid="9800",
            reference="Checked original agreement", reason="Corrected early-anniversary software calculation",
            request_key="shared-contract-correction", adopt_shared_interest=True, currency_quantum="0.01")
        _, token = preview_contract_correction(loan.pk, actor=self.actor, data=facts)
        record_contract_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        loan.refresh_from_db()
        old_origin.refresh_from_db()
        old_receipt.refresh_from_db()
        self.assertEqual(old_origin.payload, old_payload)
        self.assertEqual(Decimal(old_receipt.payload["values"]["interest"]), 200)
        self.assertEqual(recording_for(loan)["collection_profile"], "recorded-anniversary/3")
        self.assertEqual(collection_balance(loan, date(2026, 5, 5)).principal_outstanding, 8000)
        self.assertEqual(collection_balance(loan, date(2026, 5, 6)).interest_outstanding, 160)
        self.assertEqual(old_receipt.reversed_by_event.reversal_of_id, old_receipt.pk)

    def test_rollout_inventory_is_scoped_read_only_and_does_not_adopt(self):
        from apps.tenant_apps.loans.selectors.interest_contract_inventory import interest_contract_inventory
        from apps.tenancy.context import workspace_context, without_workspace_context
        with patch("apps.tenant_apps.loans.services.recorded_history.RECORDED_PROFILE", "recorded-anniversary/1"), \
             patch("apps.tenant_apps.loans.services.recorded_history.POLICY_VERSION", 1):
            loan = self.admit()
        old = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
        row = next(row for row in interest_contract_inventory() if row["loan_id"] == loan.pk)
        self.assertEqual(row["status"], "REVIEW_CORRECTION")
        self.assertFalse(row["automatic_conversion"])
        self.assertEqual(old, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
        with without_workspace_context():
            from apps.orgs.models import Company
            other = Company.objects.create(name="Inventory other", schema_name="inventory-other", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk):
            self.assertEqual(interest_contract_inventory(), [])


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SharedNativeContractTests(WorkspaceTestCase):
    setup_tenant = classmethod(CollateralReappraisalTests.setup_tenant.__func__)
    make_loan = CollateralReappraisalTests.make_loan

    def setUp(self):
        with patch("django.utils.timezone.localdate", return_value=date(2026, 10, 5)), patch(
                "django.utils.timezone.now", return_value=timezone.make_aware(datetime(2026, 10, 5, 12))):
            self.make_loan(method="LATEST_APPRAISAL", age_days=183, activate=False)
        from apps.tenant_apps.loans.services.license_series import _record_license_revision
        self.loan.license_revision = _record_license_revision(self.loan.license,
            kind=m.LoanLicenseRevision.Kind.INITIAL, actor=self.actor)
        self.loan.save(update_fields=["license_revision"])
        if hasattr(self, "original_principal"):
            self.item.allocated_principal = self.original_principal
            self.item.latest_appraised_value = Decimal("10000")
            self.item.save(update_fields=["allocated_principal", "latest_appraised_value"])
        from apps.tenant_apps.loans.services.economic_policies import create_pawn_loan_economic_policy
        create_pawn_loan_economic_policy(workspace=self.tenant, license=self.loan.license,
            valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal(".8"), advance_interest_periods=1,
            currency_quantum=getattr(self, "interest_quantum", Decimal(".01")),
            effective_from=self.loan.loan_date, actor=self.actor)
        if hasattr(self, "original_principal"):
            from decimal import ROUND_HALF_UP
            self.loan.principal_amount = self.original_principal
            monthly = item_monthly_interest(self.original_principal, self.item.monthly_interest_rate, self.interest_quantum)
            self.loan.monthly_interest_rate = (monthly / self.original_principal * 100).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)
            self.loan.save(update_fields=["principal_amount", "monthly_interest_rate"])
        from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan
        with patch("django.utils.timezone.now", return_value=self.quote.effective_at):
            approve_pawn_loan(self.loan.pk, actor=self.actor)
            disburse_pawn_loan(self.loan.pk, effective_date=self.loan.loan_date, actor=self.actor)
        self.loan.refresh_from_db()

    def test_native_advance_boundary_has_no_charge_on_may_fifth(self):
        self.assertEqual(self.loan.loan_date, date(2026, 4, 5))
        self.assertEqual(self.loan.policy_snapshot.policy_version, 2)
        fifth = preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 5, 5))
        sixth = preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 5, 6))
        self.assertEqual(sum(p.recognized_interest for p in fifth), 0)
        self.assertEqual(sum(p.recognized_interest for p in sixth), 20)
        self.assertEqual(sixth[1].period_start, date(2026, 5, 6))

    def test_native_zero_period_finalization_and_exact_portable_evidence(self):
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 5)):
            result = finalize_pawn_loan_accrual(self.loan.pk, actor=self.actor, period_number=1)
        self.assertEqual(result.accrual.recognized_interest, 0)
        self.assertIsNone(result.loan_event)
        from apps.tenant_apps.loans.services.history_accrual import stored_accrual
        portable = stored_accrual(result.accrual, self.loan.policy_snapshot, {self.item.pk: "ring"})
        self.assertEqual((portable["start"], portable["end"], portable["period_days"]), ("2026-04-05", "2026-05-05", 31))

    def test_native_full_settlement_boundary_and_reopening(self):
        from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        m.LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE",
            prefix="RL-", width=5, maximum_number=10000)
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 5)):
            finalize_pawn_loan_accrual(self.loan.pk, actor=self.actor, period_number=1)
            self.assertEqual(preview_pawn_loan_full_release(self.loan.pk).minimum_settlement, 1000)
            closed = release_pawn_loan_in_full(self.loan.pk, settlement_amount=1000, request_key="native-covered-close", actor=self.actor)
            reverse_pawn_loan_event(closed.loan_event.pk, actor=self.actor, reason="Customer return cancelled")
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 6)):
            self.assertEqual(preview_pawn_loan_full_release(self.loan.pk).minimum_settlement, 1020)
            closed = release_pawn_loan_in_full(self.loan.pk, settlement_amount=1020, request_key="native-next-charge-close", actor=self.actor)
            self.assertEqual(closed.release.interest_amount, 20)
            reverse_pawn_loan_event(closed.loan_event.pk, actor=self.actor, reason="Return cancelled again")
        self.assertEqual(sum(row.recognized_interest for row in preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 5, 6))), 20)

    def test_native_reversed_charge_requires_review_instead_of_losing_a_month(self):
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 5)):
            finalize_pawn_loan_accrual(self.loan.pk, actor=self.actor, period_number=1)
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 6)):
            charge = finalize_pawn_loan_accrual(self.loan.pk, actor=self.actor, period_number=2)
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 7)):
            reverse_pawn_loan_event(charge.loan_event.pk, actor=self.actor, reason="Recognition needs correction")
            with self.assertRaisesMessage(ValueError, "reversed monthly charge"):
                preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 5, 7))
            with self.assertRaisesMessage(ValueError, "charge was reversed"):
                finalize_pawn_loan_accrual(self.loan.pk, actor=self.actor, period_number=2)

    def test_native_collection_recognizes_started_charge_atomically_and_not_repeated(self):
        from apps.tenant_apps.loans.services.pawn_repayment import preview_pawn_loan_repayment, record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 6)):
            self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2026, 5, 6)).total_economic_exposure, 1020)
            self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2026, 5, 6)).maturity_payoff, 1220)
            with self.assertRaises(ValueError):
                record_pawn_loan_repayment(self.loan.pk, amount=10000, request_key="excessive", actor=self.actor)
            self.assertFalse(self.loan.loan_events.filter(event_kind="REPAYMENT").exists())
            self.assertEqual(self.loan.interest_accruals.count(), 0)
            preview = preview_pawn_loan_repayment(self.loan.pk, amount=220)
            self.assertEqual((preview.allocation.interest, preview.allocation.principal), (20, 200))
            paid = record_pawn_loan_repayment(self.loan.pk, amount=220, request_key="native-due", actor=self.actor)
            self.assertEqual(self.loan.interest_accruals.get(period_number=2).recognized_interest, 20)
            self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2026, 5, 6)).maturity_payoff, 960)
            self.assertTrue(record_pawn_loan_repayment(self.loan.pk, amount=220, request_key="native-due", actor=self.actor).already_recorded)
            self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2026, 5, 5)).total_economic_exposure, 1000)
            self.assertEqual(preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 6, 5)), ())
            self.assertEqual(preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 6, 6))[0].recognized_interest, 16)
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 7)):
            reverse_pawn_loan_event(paid.loan_event.pk, actor=self.actor, reason="Receipt cancelled")
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2026, 5, 7)).total_economic_exposure, 1020)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2026, 5, 7)).maturity_payoff, 1220)


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SharedNativeWholeRupeeTests(WorkspaceTestCase):
    setup_tenant = classmethod(CollateralReappraisalTests.setup_tenant.__func__)
    make_loan = CollateralReappraisalTests.make_loan
    setUp = SharedNativeContractTests.setUp
    interest_quantum = Decimal("1")
    original_principal = Decimal("5025.25")

    def test_saved_origination_collection_and_monitoring_agree(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        self.assertEqual(self.loan.principal_amount, Decimal("5025.25"))
        self.assertEqual(self.loan.disbursal_snapshot.advance_interest, 101)
        self.assertEqual(self.loan.policy_snapshot.currency_quantum, 1)
        self.assertEqual(self.loan.repayment_schedules.get().contractual_interest, 1212)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2026, 5, 6)).total_economic_exposure, Decimal("5126.25"))
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 6)):
            paid = record_pawn_loan_repayment(self.loan.pk, amount="201.25", request_key="native-whole-policy", actor=self.actor)
            from apps.tenant_apps.loans.services.history_export import export_history
            from apps.tenant_apps.loans.services.history_contract import parse
            exported = parse(export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=self.loan.pk))
            self.assertEqual(exported["manifest"]["profile"], "loan-history/3")
            self.assertEqual(exported["loan"]["policy"]["currency_quantum"], "1")
            self.assertEqual(exported["loan"]["disbursal"]["principal"], "5025.25")
        self.assertEqual(Decimal(paid.loan_event.payload["values"]["principal"]), Decimal("100.25"))


class SharedOpeningContractTests(OpeningImportFixture):
    def setUp(self):
        super().setUp()
        self.review["profile"] = "loan-opening-review/3"
        self.review["terms"].update(rule_id=RULE, rounding_scope="PER_ITEM", rounding_mode="HALF_UP", interest_quantum="0.01")
        self.setup["policy"]["policy_version"] = 2
        self.setup["policy"]["minimum_first_month"] = False
        with self.scoped():
            m.LoanProductVersion.objects.filter(pk=self.review["mapping"]["product_version_id"]).update(calculation_contract_version=RULE)

    def test_imported_policy_boundary_cutover_payment_reversal_and_export(self):
        from apps.tenant_apps.loans.services.opening_servicing import opening_payment_balance
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        from apps.tenant_apps.loans.services.opening_export import export_opening
        from apps.tenant_apps.loans.services.opening_restore import parse_opening_export
        with self.scoped():
            loan = self.write().loan
            self.assertEqual(opening_payment_balance(loan, as_of_date=date(2021, 2, 1))[0].interest_outstanding, 0)
            self.assertEqual(opening_payment_balance(loan, as_of_date=date(2021, 2, 2))[0].interest_outstanding, 10)
            with patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
                paid = record_pawn_loan_repayment(loan.pk, amount=210, request_key="policy-payment", actor=self.actor)
            self.assertEqual(opening_payment_balance(loan, as_of_date=date(2021, 3, 2))[0].interest_outstanding, 8)
            document = parse_opening_export(export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk))
            self.assertEqual(document["evidence"]["origin"]["document"]["review"]["profile"], "loan-opening-review/3")
            with patch("django.utils.timezone.localdate", return_value=date(2021, 3, 3)):
                reverse_pawn_loan_event(paid.loan_event.pk, actor=self.actor, reason="Cancelled collection")
            self.assertEqual(opening_payment_balance(loan, as_of_date=date(2021, 3, 3))[0].interest_outstanding, 20)

    def test_imported_shared_release_and_reversal_preserve_exact_paise_evidence(self):
        from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        from apps.tenant_apps.loans.services.opening_servicing import opening_payment_balance
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            loan = self.write().loan
            self.assertEqual(preview_pawn_loan_full_release(loan.pk).minimum_settlement, 1010)
            release = release_pawn_loan_in_full(loan.pk, settlement_amount=1010, request_key="shared-full-release", actor=self.actor)
            reverse_pawn_loan_event(release.loan_event.pk, actor=self.actor, reason="Return cancelled")
            loan.refresh_from_db()
            self.assertEqual(loan.state, "ACTIVE")
            self.assertEqual(opening_payment_balance(loan, as_of_date=date(2021, 2, 2))[0].total_due, 1010)
