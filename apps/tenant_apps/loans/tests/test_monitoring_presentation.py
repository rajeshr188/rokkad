"""Live reads, saved freshness, financial support and book checks stay distinct."""
from uuid import uuid4
from datetime import timedelta
from unittest.mock import patch

from django.db import connection
from django.test import override_settings, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
from apps.tenant_apps.loans.selectors.evidence_quality import loan_evidence_quality
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio_summary
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot, RiskSnapshotRefreshError
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from . import test_monitoring_input_boundary as fixtures


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MonitoringPresentationTests(WorkspaceTestCase):
    get_test_schema_name = classmethod(lambda cls: "monitoring-presentation")
    setup_tenant = classmethod(fixtures.MonitoringInputBoundaryTests.setup_tenant.__func__)
    setUp = fixtures.MonitoringInputBoundaryTests.setUp
    data = fixtures.MonitoringInputBoundaryTests.data
    amend = fixtures.MonitoringInputBoundaryTests.amend
    legacy_loan = fixtures.MonitoringInputBoundaryTests.legacy_loan

    def detail(self, loan=None):
        from apps.tenant_apps.loans.web.pawn_reads import pawn_loan_detail
        request = RequestFactory().get("/")
        request.user, request.workspace = self.actor, self.tenant
        return pawn_loan_detail(request, (loan or self.loan).pk)

    def test_live_results_do_not_claim_to_refresh_the_saved_assessment(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today)
        collateral = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today)
        risk = get_pawn_loan_risk_assessment(self.loan.pk, as_of_date=self.today)
        with CaptureQueriesContext(connection) as reads:
            quality = loan_evidence_quality(self.loan, as_of_date=self.today,
                exposure=exposure, observation=collateral, risk=risk)
        self.assertEqual(quality["assessment"]["status"], "UNASSESSED")
        self.assertEqual(quality["calculation"]["status"], "SUPPORTED")
        self.assertEqual(quality["valuation"]["status"], "ELIGIBLE")
        self.assertEqual(quality["basis"], "LIVE")
        self.assertEqual(quality["capture"]["status"], "SYSTEM_CAPTURE_ASSUMPTION")
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE ")) for q in reads))
        self.assertFalse(m.LoanRiskSnapshot.objects.filter(loan=self.loan).exists())
        page = self.detail()
        self.assertContains(page, "Live calculation shown")
        self.assertContains(page, "UNASSESSED")
        self.assertContains(page, "SUPPORTED")

    def test_detail_preserves_independent_observation_when_debt_cannot_be_projected(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        loan, _item = self.legacy_loan()
        page = self.detail(loan)
        self.assertContains(page, "Independent current collateral observation")
        self.assertContains(page, "Risk unavailable")
        self.assertContains(page, "UNAVAILABLE")
        self.assertNotContains(page, "No identified risk flags")
        self.assertFalse(m.LoanRiskSnapshot.objects.filter(loan=loan).exists())

    def test_advisory_cause_separates_evidence_from_measured_risk(self):
        risk = get_pawn_loan_risk_assessment(self.loan.pk, as_of_date=self.today)
        quality = loan_evidence_quality(self.loan, as_of_date=self.today, risk=risk)
        self.assertEqual(quality["risk"]["label"], "Evidence needs attention")
        self.assertEqual(quality["risk"]["severity"], "HIGH")
        self.amend(valuation_basis="CALCULATED_METAL_VALUE", ltv_warning_ratio=".1", ltv_breach_ratio=".2", ltv_critical_ratio=".3")
        risk = get_pawn_loan_risk_assessment(self.loan.pk, as_of_date=self.today)
        quality = loan_evidence_quality(self.loan, as_of_date=self.today, risk=risk)
        self.assertEqual(quality["risk"]["label"], "Measured risk needs attention")
        self.assertEqual(quality["risk"]["severity"], "CRITICAL")

    def test_failed_book_check_retains_supported_financial_diagnostics(self):
        with patch("apps.tenant_apps.loans.selectors.transaction_completeness.transaction_completeness",
                   side_effect=ValueError("Book evidence needs review")):
            with self.assertRaises(RiskSnapshotRefreshError):
                refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        quality = loan_evidence_quality(self.loan, as_of_date=self.today)
        self.assertEqual(quality["assessment"]["status"], "ERROR")
        self.assertEqual(quality["calculation"]["status"], "SUPPORTED")
        self.assertEqual(quality["risk"]["label"], "Risk unavailable")
        self.assertEqual(get_dashboard_health_summary(workspace=self.tenant)["financial_count"], 0)

    def test_capture_choice_is_reviewed_per_loan_and_can_return_to_paper(self):
        def review(mode, complete):
            data = dict(through_date=self.today, confirmed_complete=complete, future_capture=mode,
                source_reference="Fictional complete or incomplete source check", request_key=uuid4().hex)
            _summary, token = preview_transaction_review(self.loan.pk, actor=self.actor, **data)
            confirm_transaction_review(self.loan.pk, actor=self.actor, **data, review_token=token, acknowledged=True)
        review("ROKKAD_ONLY", True)
        quality = loan_evidence_quality(self.loan, as_of_date=self.today)
        self.assertEqual(quality["capture"]["status"], "ROKKAD_ONLY")
        review("PAPER_MIXED", False)
        quality = loan_evidence_quality(self.loan, as_of_date=self.today)
        self.assertEqual(quality["capture"]["status"], "PAPER_MIXED")
        self.assertEqual(quality["transactions"]["status"], "INCOMPLETE")

    def test_saved_position_disclosure_does_not_recalculate_financial_history(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        with patch("apps.tenant_apps.loans.selectors.financial_inputs.get_pawn_loan_financial_inputs",
                side_effect=AssertionError("A saved portfolio disclosure must not recalculate debt")):
            quality = loan_evidence_quality(self.loan, as_of_date=self.today)
        self.assertEqual(quality["assessment"]["status"], "CURRENT")
        self.assertEqual(quality["transactions"]["status"], "RECORDED_POSITION")
        self.assertTrue(quality["transactions"]["complete"])

    def test_dashboard_and_portfolio_exclude_the_same_unusable_saved_amounts(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        for amount in ("bad", "NaN", "-1", "999999999999999999999"):
            snapshot.source_provenance["financial"]["projected_interest"] = amount
            snapshot.save(update_fields=["source_provenance"])
            self.loan.refresh_from_db()
            with self.subTest(amount=amount):
                dashboard = get_dashboard_health_summary(workspace=self.tenant)
                portfolio = get_risk_portfolio_summary()
                quality = loan_evidence_quality(self.loan, as_of_date=self.today)
                self.assertEqual(dashboard["financial_count"], portfolio.financial_count)
                self.assertEqual(dashboard["coverage_count"], portfolio.coverage_count)
                self.assertEqual(dashboard["unknown_coverage_count"], portfolio.unknown_coverage_count)
                self.assertIsNone(portfolio.total_exposure)
                self.assertEqual(quality["calculation"]["status"], "UNAVAILABLE")
                self.assertEqual(quality["risk"]["label"], "Risk unavailable")

    def test_unknown_reference_limit_keeps_coverage_and_missing_book_proof_stays_unknown(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        snapshot.source_provenance["coverage"]["status"] = "REFERENCE_LIMIT_UNAVAILABLE"
        snapshot.source_provenance["coverage"]["headroom"] = None
        snapshot.source_provenance.pop("transactions")
        snapshot.save(update_fields=["source_provenance"])
        self.loan.refresh_from_db()
        dashboard = get_dashboard_health_summary(workspace=self.tenant)
        portfolio = get_risk_portfolio_summary()
        self.assertEqual(dashboard["coverage_count"], 1)
        self.assertEqual(portfolio.coverage_count, 1)
        self.assertTrue(dashboard["valuation_complete"])
        self.assertFalse(dashboard["transactions_complete"])
        self.assertEqual(dashboard["transaction_unknown_count"], 1)
        self.assertFalse(portfolio.totals_complete)

    def test_displayed_appraisal_excludes_later_today_evidence(self):
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        instant = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        with patch("django.utils.timezone.now", return_value=instant + timedelta(hours=4)):
            record_collateral_reappraisal(loan_id=self.loan.pk, item_id=self.item.pk, actor=self.actor,
                appraised_value="9999", method="PHYSICAL_INSPECTION", evidence_reference="Fictional later inspection",
                review_notes="Scheduled later-today evidence", expected_version=1)
        with patch("django.utils.timezone.now", return_value=instant):
            page = self.detail()
        self.assertNotContains(page, "9,999")
