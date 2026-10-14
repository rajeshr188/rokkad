"""Per-calculation reuse must preserve dated financial facts and RLS boundaries."""
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure, _read_financial_inputs
from apps.tenant_apps.loans.selectors.delinquency import get_pawn_loan_delinquency
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot, RiskSnapshotRefreshError
from apps.tenant_apps.loans.models import LoanRiskSnapshot
from . import test_collateral_reappraisal as native
from . import test_recorded_origination as paper
from . import test_shared_monthly_contract as monthly
from .test_opening_event_storage import OpeningEventFixture
from .test_opening_continuation import collection_review


def assert_input_parity(test, loan, day):
    events = list(loan.loan_events.values())
    expected_exposure = get_pawn_loan_exposure(loan.pk, as_of_date=day)
    expected_delinquency = get_pawn_loan_delinquency(loan.pk, as_of_date=day)
    inputs = _read_financial_inputs(loan.pk, as_of_date=day)
    with test.assertNumQueries(0):
        test.assertEqual(get_pawn_loan_exposure(loan.pk, as_of_date=day, _inputs=inputs), expected_exposure)
    test.assertEqual(get_pawn_loan_delinquency(loan.pk, as_of_date=day, _inputs=inputs), expected_delinquency)
    test.assertEqual(list(loan.loan_events.values()), events)


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MonitoringEfficiencyTests(WorkspaceTestCase):
    get_test_schema_name = classmethod(lambda cls: "monitoring-efficiency")
    setup_tenant = classmethod(native.CollateralReappraisalTests.setup_tenant.__func__)

    def setUp(self):
        native.CollateralReappraisalTests.make_loan(self, method="LATEST_APPRAISAL")

    def test_financial_reads_reused_with_equal_risk_and_book_evidence(self):
        inputs = _read_financial_inputs(self.loan.pk, as_of_date=self.today)
        inputs = replace(inputs, transaction_coverage=transaction_completeness(inputs.loan, self.today))
        exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today, _inputs=inputs)
        with self.assertNumQueries(0):
            delinquency = get_pawn_loan_delinquency(self.loan.pk, as_of_date=self.today, _inputs=inputs)
        collateral = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today, _exposure=exposure)
        kwargs = dict(as_of_date=self.today, _exposure=exposure, _delinquency=delinquency, _collateral=collateral)
        with CaptureQueriesContext(connection) as baseline:
            expected = get_pawn_loan_risk_assessment(self.loan.pk, **kwargs)
        with CaptureQueriesContext(connection) as reused:
            actual = get_pawn_loan_risk_assessment(self.loan.pk, **kwargs, _inputs=inputs)
        self.assertEqual(actual, expected)
        self.assertLess(len(reused), len(baseline))
        events = list(self.loan.loan_events.values())
        with patch("apps.tenant_apps.loans.services.risk_snapshots._read_financial_inputs", wraps=_read_financial_inputs) as read:
            snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        read.assert_called_once_with(self.loan.pk, as_of_date=self.today)
        self.assertEqual(snapshot.assessment_fingerprint, expected.fingerprint)
        self.assertEqual(snapshot.source_provenance["transactions"], inputs.transaction_coverage.evidence())
        self.assertEqual(list(self.loan.loan_events.values()), events)

    def test_prepared_inputs_refuse_other_loan_date_or_workspace_without_queries(self):
        inputs = _read_financial_inputs(self.loan.pk, as_of_date=self.today)
        for selector in (get_pawn_loan_exposure, get_pawn_loan_delinquency, get_pawn_loan_risk_assessment):
            for loan_id, day in ((self.loan.pk + 1, self.today), (self.loan.pk, self.today + timedelta(days=1))):
                with self.subTest(selector=selector, loan_id=loan_id, day=day), self.assertNumQueries(0):
                    with self.assertRaisesMessage(ValueError, "Prepared financial inputs"):
                        selector(loan_id, as_of_date=day, _inputs=inputs)
        with without_workspace_context():
            other = Company.objects.create(name="Other monitoring", schema_name="other-monitoring", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk):
            for selector in (get_pawn_loan_exposure, get_pawn_loan_delinquency, get_pawn_loan_risk_assessment):
                with self.assertNumQueries(0), self.assertRaisesMessage(ValueError, "Workspace"):
                    selector(self.loan.pk, as_of_date=self.today, _inputs=inputs)
        with without_workspace_context(), self.assertNumQueries(0), self.assertRaises(ValueError):
            get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today, _inputs=inputs)

    def test_dated_inputs_match_standalone_financial_readers(self):
        for day in (self.loan.loan_date, self.loan.loan_date + timedelta(days=31), self.today):
            with self.subTest(day=day):
                assert_input_parity(self, self.loan, day)

    def test_book_evidence_failure_retains_financial_support_and_clears_current_metrics(self):
        with patch("apps.tenant_apps.loans.selectors.transaction_completeness.transaction_completeness",
                   side_effect=ValueError("Invalid retained book evidence")):
            with self.assertRaisesMessage(RiskSnapshotRefreshError, "Invalid retained book evidence"):
                refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        snapshot = LoanRiskSnapshot.objects.get(loan=self.loan)
        self.assertEqual(snapshot.status, "ERROR")
        self.assertEqual(snapshot.source_provenance["financial"]["calculation_status"], "SUPPORTED")
        self.assertIsNone(snapshot.exposure)
        self.assertIsNone(snapshot.days_past_due)
        self.assertIsNone(snapshot.ltv_ratio)

    def test_item_quotes_and_latest_appraisals_are_bounded_and_not_cached_between_calls(self):
        from apps.tenant_apps.loans.services import (
            CollateralDraftInput, CreatePawnDraftCommand, create_pawn_draft,
            append_collateral_photo, approve_pawn_loan, disburse_pawn_loan,
            create_pawn_metal_interest_rate_policy,
        )
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        from apps.tenant_apps.rates.models import Rate
        from apps.tenant_apps.rates.facade import get_latest_commodity_valuation_rate
        from django.core.files.uploadedfile import SimpleUploadedFile
        original = self.loan
        create_pawn_metal_interest_rate_policy(workspace=self.tenant, license=original.license,
            metal="SILVER", monthly_interest_rate=2, effective_from=original.loan_date, actor=self.actor)
        with patch("django.utils.timezone.now", return_value=self.quote.effective_at):
            Rate.objects.create(rate_source=self.source, metal=Rate.Metal.SILVER, buying_rate=300, selling_rate=310)
            loan = create_pawn_draft(CreatePawnDraftCommand(workspace_id=self.tenant.pk, borrower_id=original.borrower_id,
                license_id=original.license_id, series_id=original.series_id, product_version_id=original.product_version_id,
                principal_amount=1000, monthly_interest_rate=2, loan_date=original.loan_date, tenure_months=12,
                collateral=tuple(CollateralDraftInput(description=f"Item {n}", metal="SILVER" if n == 9 else "GOLD",
                    gross_weight=Decimal("1"), net_weight=Decimal("1"), purity_percentage=Decimal("100"),
                    allocated_principal=Decimal("100"), latest_appraised_value=Decimal("2000")) for n in range(10))), actor=self.actor)
            for item in loan.collateral_items.all():
                append_collateral_photo(item.pk, upload=SimpleUploadedFile("item.jpg", bytes.fromhex("ffd8ffe0") + b"fixture", content_type="image/jpeg"), actor=self.actor)
            approve_pawn_loan(loan.pk, actor=self.actor)
            disburse_pawn_loan(loan.pk, effective_date=loan.loan_date, actor=self.actor)
        exposure = get_pawn_loan_exposure(loan.pk, as_of_date=self.today)
        path = "apps.tenant_apps.loans.selectors.collateral_valuation.get_latest_commodity_valuation_rate"
        with patch(path, wraps=get_latest_commodity_valuation_rate) as lookup, CaptureQueriesContext(connection) as queries:
            value = get_pawn_loan_collateral_valuation(loan.pk, as_of_date=self.today, _exposure=exposure)
        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(len(value.items), 10)
        appraisal_queries = [q for q in queries if 'FROM "loans_collateralappraisal"' in q['sql']]
        self.assertEqual(len(appraisal_queries), 1)
        self.assertEqual({row.appraisal_id for row in value.items}, set(loan.collateral_items.values_list("appraisals__pk", flat=True)))
        item = loan.collateral_items.order_by("pk").first()
        prior = next(row for row in value.items if row.collateral_item_id == item.pk).appraisal_id
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=1)):
            future = record_collateral_reappraisal(loan_id=loan.pk, item_id=item.pk, actor=self.actor,
                appraised_value=3000, method="PHYSICAL_INSPECTION", evidence_reference="Synthetic next day", review_notes="Test", expected_version=1)
        quote = Rate.objects.create(rate_source=self.source, buying_rate=3500, selling_rate=3600)
        again = get_pawn_loan_collateral_valuation(loan.pk, as_of_date=self.today, _exposure=exposure)
        self.assertEqual(next(row for row in again.items if row.collateral_item_id == item.pk).appraisal_id, prior)
        self.assertEqual({row.rate_id for row in again.items if row.collateral_item_id != loan.collateral_items.get(metal="SILVER").pk}, {quote.pk})
        tomorrow = get_pawn_loan_collateral_valuation(loan.pk, as_of_date=self.today + timedelta(days=1))
        self.assertEqual(next(row for row in tomorrow.items if row.collateral_item_id == item.pk).appraisal_id, future.pk)


class PaperMonitoringInputParityTests(WorkspaceTestCase):
    get_test_schema_name = classmethod(lambda cls: "paper-monitoring-inputs")
    setup_tenant = classmethod(paper.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = paper.RecordedOriginationTests.make_snapshot

    def test_paper_inputs_preserve_anniversary_amounts_and_dated_reads(self):
        loan = self.make_snapshot(advance=1).loan
        for day in (loan.loan_date, loan.loan_date + timedelta(days=31), loan.loan_date + timedelta(days=65)):
            with self.subTest(day=day):
                assert_input_parity(self, loan, day)


class NativeMonthlyInputParityTests(WorkspaceTestCase):
    get_test_schema_name = classmethod(lambda cls: "native-monthly-monitoring-inputs")
    setup_tenant = classmethod(monthly.SharedNativeContractTests.setup_tenant.__func__)
    make_loan = monthly.SharedNativeContractTests.make_loan
    setUp = monthly.SharedNativeContractTests.setUp

    def test_shared_monthly_inputs_preserve_anniversary_and_short_month_boundaries(self):
        for day in (date(2026, 5, 5), date(2026, 5, 6), date(2026, 6, 5), date(2026, 6, 6)):
            with self.subTest(day=day):
                assert_input_parity(self, self.loan, day)


class OpeningMonitoringInputParityTests(OpeningEventFixture):
    get_test_schema_name = classmethod(lambda cls: "opening-monitoring-inputs")

    def review_document(self):
        return collection_review()

    def test_opening_inputs_preserve_checkpoint_amounts_grace_and_date_boundaries(self):
        from apps.tenant_apps.loans.services.opening_obligations import persist_opening_repayment_schedule
        persist_opening_repayment_schedule(self.loan.pk, actor=self.actor)
        for day in (date(2021, 1, 20), date(2021, 2, 1), date(2021, 2, 2)):
            with self.subTest(day=day):
                assert_input_parity(self, self.loan, day)
