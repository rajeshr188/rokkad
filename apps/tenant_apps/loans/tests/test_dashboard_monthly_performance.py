"""Modern monthly dashboard query bounds and canonical evidence parity."""
from datetime import date
from decimal import Decimal
import uuid

from django.db import connection
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch
from django.test import override_settings

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.orgs.models import Company
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.selectors.accrual_evidence import load_pawn_accrual_evidence
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.counter_work import get_workspace_counter_work
from apps.tenant_apps.loans.selectors.obligation_state import (
    get_obligation_states_for_loans, get_active_repayment_schedule_as_of,
    calculate_obligation_state_as_of,
)
from apps.tenant_apps.loans.services.pawn_interest import (
    preview_pawn_loan_accruals, _itemized_accrual_lines,
)
from . import test_shared_monthly_contract as monthly_fixtures
from . import test_dashboard_batch as batch_fixtures


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DashboardMonthlyPerformanceTests(WorkspaceTestCase):
    setup_tenant = classmethod(monthly_fixtures.SharedNativeContractTests.setup_tenant.__func__)
    make_loan = monthly_fixtures.SharedNativeContractTests.make_loan
    setUp = monthly_fixtures.SharedNativeContractTests.setUp
    event = batch_fixtures.DashboardBatchTests.event

    def additional_native_loan(self):
        from apps.tenant_apps.loans.services import (
            CreatePawnDraftCommand, CollateralDraftInput, create_pawn_draft,
            append_collateral_photo, approve_pawn_loan, disburse_pawn_loan,
        )
        original = self.loan
        with patch("django.utils.timezone.now", return_value=self.quote.effective_at):
            loan = create_pawn_draft(CreatePawnDraftCommand(
                workspace_id=self.tenant.pk, borrower_id=original.borrower_id,
                license_id=original.license_id, series_id=original.series_id,
                product_version_id=original.product_version_id,
                principal_amount=original.principal_amount,
                monthly_interest_rate=original.monthly_interest_rate,
                loan_date=original.loan_date, tenure_months=original.tenure_months,
                collateral=(CollateralDraftInput(description="Second ring", metal="GOLD",
                    gross_weight=self.item.gross_weight, net_weight=self.item.net_weight,
                    purity_percentage=self.item.purity_percentage,
                    allocated_principal=self.item.allocated_principal,
                    latest_appraised_value=self.item.latest_appraised_value),)), actor=self.actor)
            append_collateral_photo(loan.collateral_items.get().pk,
                upload=SimpleUploadedFile("ring.jpg", bytes.fromhex("ffd8ffe0") + b"fixture", content_type="image/jpeg"),
                actor=self.actor)
            approve_pawn_loan(loan.pk, actor=self.actor)
            disburse_pawn_loan(loan.pk, effective_date=loan.loan_date, actor=self.actor)
        return loan

    def test_queue_queries_are_bounded_across_loans_and_months_with_single_parity(self):
        loans = [self.loan]
        for count in (1, 3):
            if count == 3:
                for _ in range(2):
                    loans.append(self.additional_native_loan())
            for on in (date(2026, 5, 6), date(2027, 5, 6)):
                with self.subTest(count=count, on=on), self.assertNumQueries(13):
                    work = get_workspace_counter_work(workspace=self.tenant, as_of_date=on)
                batch = get_obligation_states_for_loans(workspace=self.tenant,
                    loan_ids=[loan.pk for loan in loans], as_of_date=on)
                for loan in loans:
                    single = calculate_obligation_state_as_of(
                        get_active_repayment_schedule_as_of(loan, on), on)
                    self.assertEqual(batch[loan.pk], single)
                self.assertEqual(sum(work["queues"][key]["count"] for key in ("due", "overdue")),
                    count if on == date(2027, 5, 6) else 0)

    def test_loaded_item_calculations_match_existing_dated_readers_without_queries(self):
        loan = PawnLoan.objects.select_related("policy_snapshot").get(pk=self.loan.pk)
        evidence = load_pawn_accrual_evidence((loan,))[loan.pk]
        for on in (date(2026, 4, 5), date(2026, 5, 5), date(2026, 6, 5)):
            balance = get_pawn_loan_balance(loan, as_of_date=on)
            args = dict(as_of_date=on, period_fraction=Decimal("1"),
                aggregate_balance=balance, currency_quantum=Decimal(".01"),
                pending_advance_applied={}, use_original_principal=on == loan.loan_date)
            expected = _itemized_accrual_lines(loan, **args)
            with self.assertNumQueries(0):
                self.assertEqual(evidence.balance(on), balance)
                self.assertEqual(_itemized_accrual_lines(loan, _evidence=evidence, **args), expected)
        # All periods reuse the loaded evidence; no hidden per-period ORM reads.
        with self.assertNumQueries(0):
            previews = preview_pawn_loan_accruals(loan.pk, as_of_date=date(2027, 5, 6),
                known_through=date(2026, 5, 6), _evidence=evidence)
        self.assertGreater(len(previews), 12)

    def test_restricted_batch_and_evidence_reject_foreign_workspace_inputs(self):
        with without_workspace_context():
            other = Company.objects.create(name="Monthly foreign", schema_name="monthly-foreign",
                owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk):
            foreign = batch_fixtures.DashboardBatchTests.loan(self, other)
            batch_fixtures.DashboardBatchTests.schedule(self, foreign, 1, 1)
        role = connection.ops.quote_name("dashboard_monthly_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            with self.assertNumQueries(0), self.assertRaisesMessage(ValueError, "Workspace"):
                load_pawn_accrual_evidence((self.loan, foreign))
            with self.assertNumQueries(12):
                batch = get_obligation_states_for_loans(workspace=self.tenant,
                    loan_ids=[self.loan.pk, foreign.pk], as_of_date=date(2027, 5, 6))
            self.assertIsNotNone(batch[self.loan.pk].schedule_id)
            self.assertIsNone(batch[foreign.pk].schedule_id)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
        evidence = load_pawn_accrual_evidence((self.loan,))[self.loan.pk]
        with without_workspace_context(), workspace_context(other.pk), self.assertNumQueries(0):
            with self.assertRaisesMessage(ValueError, "Workspace"):
                evidence.balance(date(2026, 5, 6))

from . import test_continuation_admissions as admission_fixtures


class DashboardMonthlyAdmissionParityTests(admission_fixtures.AdmissionFixture):
    def test_all_admitted_profiles_match_single_states_across_receipts_and_dates(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        ids = [loan.pk for loan in self.loans]
        with self.scoped():
            def compare(on):
                with self.assertNumQueries(12):
                    batch = get_obligation_states_for_loans(workspace=self.a,
                        loan_ids=ids, as_of_date=on)
                for loan in self.loans:
                    self.assertEqual(batch[loan.pk], calculate_obligation_state_as_of(
                        get_active_repayment_schedule_as_of(loan, on), on))
            compare(date(2026, 5, 5))
            compare(date(2027, 5, 5))
            receipts = []
            with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 20)):
                for loan in self.loans:
                    receipts.append(record_pawn_loan_repayment(loan.pk,
                        amount=self.monthly + Decimal("100"),
                        request_key="batch-receipt-" + str(loan.pk), actor=self.actor))
            compare(date(2026, 5, 5))  # Later receipts cannot leak into earlier forecasts.
            compare(date(2026, 5, 20))
            with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 21)):
                for loan, receipt in zip(self.loans, receipts):
                    if loan in (self.paper, self.imported):
                        with self.assertRaisesMessage(ValueError, "Review paper history correction"):
                            reverse_pawn_loan_event(receipt.loan_event.pk,
                                actor=self.actor, reason="Synthetic cancelled receipt")
                    else:
                        reverse_pawn_loan_event(receipt.loan_event.pk,
                            actor=self.actor, reason="Synthetic cancelled receipt")
            compare(date(2026, 5, 20))
            compare(date(2026, 5, 21))


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DashboardLegacyRecordedParityTests(WorkspaceTestCase):
    setup_tenant = classmethod(monthly_fixtures.SharedPaperContractTests.setup_tenant.__func__)
    make_snapshot = monthly_fixtures.SharedPaperContractTests.make_snapshot
    prepare_history = monthly_fixtures.SharedPaperContractTests.prepare_history
    setUp = monthly_fixtures.SharedPaperContractTests.setUp
    admit = monthly_fixtures.SharedPaperContractTests.admit

    def test_old_anniversary_profiles_keep_their_dated_and_rounded_results(self):
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
        from apps.tenant_apps.loans.services.recorded_collections import collection_state
        for index, profile in enumerate(("recorded-anniversary/1", "recorded-anniversary/2")):
            self.data["number"] = "P-00" + str(10 + index)
            self.data["source_reference"] = "Synthetic old book " + str(index)
            self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
            with patch("apps.tenant_apps.loans.services.recorded_history.RECORDED_PROFILE", profile), \
                    patch("apps.tenant_apps.loans.services.recorded_history.POLICY_VERSION", 1):
                admitted = self.admit()
            loan = PawnLoan.objects.select_related("policy_snapshot").get(pk=admitted.pk)
            evidence = load_pawn_accrual_evidence((loan,))[loan.pk]
            for on in (date(2026, 5, 4), date(2026, 5, 5), date(2026, 5, 6), date(2027, 5, 5)):
                expected = collection_state(loan, on, known_through=date(2026, 5, 5))
                with self.assertNumQueries(0):
                    self.assertEqual(collection_state(loan, on, known_through=date(2026, 5, 5),
                        _evidence=evidence), expected)
                with self.assertNumQueries(12):
                    batch = get_obligation_states_for_loans(workspace=self.tenant,
                        loan_ids=[loan.pk], as_of_date=on)
                self.assertEqual(batch[loan.pk], calculate_obligation_state_as_of(
                    get_active_repayment_schedule_as_of(loan, on), on))
