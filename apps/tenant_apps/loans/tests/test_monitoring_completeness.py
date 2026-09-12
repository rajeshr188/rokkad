import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.forms.models import model_to_dict
from django.test import RequestFactory, override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import LoanMonitoringPolicy, LoanRiskSnapshot, PawnLoan
from apps.tenant_apps.loans.selectors.monitoring_policy import resolve_monitoring_policy
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio, get_risk_portfolio_summary
from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot, reassess_pawn_loans_batch, RiskSnapshotRefreshError
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.loans.web.economic_forms import LoanMonitoringPolicyForm
from apps.tenant_apps.loans.web.economic_setup import pawn_economics_setup
from apps.tenant_apps.loans.web.operations import pawn_risk_portfolio
from apps.tenant_apps.rates.models import Rate


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MonitoringPortfolioTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "monitoring-portfolio"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.actor = get_user_model().objects.create_user(username="monitoring-owner")
        tenant.name = "Monitoring"
        tenant.owner = tenant.creator = cls.actor
        tenant.save()
        Membership.objects.create(user=cls.actor, company=tenant, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        fixtures.CollateralReappraisalTests.make_loan(self)

    def extra_loan(self, state="ACTIVE"):
        return PawnLoan.objects.create(workspace=self.tenant, license=self.loan.license, series=self.loan.series,
            borrower=self.loan.borrower, product_version=self.loan.product_version, loan_number=uuid.uuid4().hex,
            state=state, principal_amount=1000, monthly_interest_rate=2, loan_date=self.today)

    def refresh(self):
        return refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)

    def amendment_data(self, **changes):
        data = model_to_dict(self.policy, fields=LoanMonitoringPolicyForm.Meta.fields)
        data.update(license=None, supersedes=self.policy, effective_from=self.today, amendment_reason="Review evidence limits")
        data.update(changes)
        return data

    def amend(self, **changes):
        return create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **self.amendment_data(**changes))

    def test_unassessed_active_loans_are_counted_and_closed_loans_excluded(self):
        self.extra_loan("CLOSED")
        summary = get_risk_portfolio_summary()
        self.assertEqual(summary.loan_count, 1)
        self.assertEqual(summary.unassessed_count, 1)
        self.assertIsNone(summary.total_exposure)
        self.assertEqual([row.pk for row in get_risk_portfolio(status="UNASSESSED")], [self.loan.pk])
        snapshot = self.refresh()
        summary = get_risk_portfolio_summary()
        self.assertEqual(summary.current_count, 1)
        self.assertEqual(summary.unknown_coverage_count, 1)
        self.assertTrue(summary.totals_complete)
        self.assertEqual(summary.total_exposure, snapshot.exposure)
        self.assertIn("STALE_RATE", snapshot.source_provenance["coverage"]["blockers"])
        self.assertEqual(snapshot.source_provenance["coverage"]["basis"], "Maturity payoff")
        self.assertIsNone(snapshot.source_provenance["coverage"]["shortfall"])

    def test_date_rollover_and_future_assessment_never_count_as_current(self):
        snapshot = self.refresh()
        self.assertEqual(get_risk_portfolio_summary(as_of_date=self.today + timedelta(days=1)).stale_count, 1)
        self.assertEqual(get_risk_portfolio_summary(as_of_date=self.today - timedelta(days=1)).stale_count, 1)
        self.assertEqual(get_risk_portfolio(as_of_date=self.today + timedelta(days=1), min_dpd=0).paginator.count, 0)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "CURRENT")  # Read did not rewrite evidence.

    def test_batch_retries_outdated_and_never_assessed_without_error_starvation(self):
        broken = self.extra_loan()
        first = reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=1)
        self.assertEqual(first["current"], 1)
        second = reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=1)
        self.assertEqual(second["errors"][0]["loan_id"], broken.pk)
        later = self.extra_loan()
        third = reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=1)
        self.assertEqual(third["errors"][0]["loan_id"], later.pk)
        # An old error attempt moves behind an older pending assessment.
        fourth = reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today + timedelta(days=1), batch_size=1)
        self.assertEqual(fourth["current"], 1)
        self.assertEqual(LoanRiskSnapshot.objects.get(loan=self.loan).as_of_date, self.today + timedelta(days=1))

    def test_source_invalidation_is_transactional_and_rolls_back_with_source(self):
        snapshot = self.refresh()
        with self.assertRaisesMessage(ValueError, "rollback"):
            with transaction.atomic():
                Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
                snapshot.refresh_from_db()
                self.assertEqual(snapshot.status, "STALE")
                raise ValueError("rollback")
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "CURRENT")
        Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "STALE")

    def test_failed_first_assessment_does_not_block_source_corrections(self):
        with patch("apps.tenant_apps.loans.services.risk_snapshots.get_pawn_loan_exposure", side_effect=ValueError("Invalid evidence")):
            with self.assertRaises(RiskSnapshotRefreshError):
                self.refresh()
        snapshot = LoanRiskSnapshot.objects.get(loan=self.loan)
        self.assertEqual(snapshot.assessment_fingerprint, "")
        Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
        self.loan.refresh_from_db()
        self.loan.save()
        self.amend(rate_freshness_days=10)
        fixtures.CollateralReappraisalTests.reassess(self)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "ERROR")
        self.assertEqual(self.refresh().status, "CURRENT")

    def test_amendment_preserves_old_settings_and_date_resolution(self):
        snapshot = self.refresh()
        successor = self.amend(rate_freshness_days=10)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.rate_freshness_days, 7)
        self.assertIsNone(self.policy.effective_until)
        self.assertEqual(successor.supersedes_id, self.policy.pk)
        self.assertEqual(successor.created_by, self.actor)
        for day, expected in ((self.today - timedelta(days=1), self.policy.pk), (self.today, successor.pk)):
            self.assertEqual(resolve_monitoring_policy(workspace_id=self.tenant.pk, license_id=self.loan.license_id, as_of_date=day).pk, expected)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "STALE")
        with self.assertRaises(ValidationError):
            self.amend(rate_freshness_days=11)
        self.policy = successor
        second = self.amend(rate_freshness_days=12)
        self.assertEqual(resolve_monitoring_policy(workspace_id=self.tenant.pk, license_id=self.loan.license_id, as_of_date=self.today).pk, second.pk)

    def test_amendments_require_authorization_reason_and_non_backdated_start(self):
        for changes in ({"amendment_reason": ""}, {"effective_from": self.today - timedelta(days=1)}):
            with self.assertRaises(ValidationError):
                self.amend(**changes)
        with self.assertRaises(PermissionDenied):
            create_loan_monitoring_policy(workspace=self.tenant, actor=None, **self.amendment_data())
        Company.objects.filter(pk=self.tenant.pk).update(lifecycle_state="ARCHIVED")
        with self.assertRaises(ValidationError):
            self.amend()
        with self.assertRaises(RiskSnapshotRefreshError):
            self.refresh()
        with self.assertRaises(RiskSnapshotRefreshError):
            reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today)

    def test_closed_loan_skips_live_health_and_invalidation_then_reopens(self):
        from apps.tenant_apps.loans.services import (
            preview_pawn_loan_full_release, release_pawn_loan_in_full, reverse_pawn_loan_event,
            finalize_pawn_loan_accrual,
        )
        from apps.tenant_apps.loans.web.pawn_reads import pawn_loan_detail
        from apps.tenant_apps.loans.models import LoanNumberSequence
        LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE",
            prefix="R-", width=5, maximum_number=10000)
        snapshot = self.refresh()
        for period in (1, 2, 3):
            finalize_pawn_loan_accrual(self.loan.pk, period_number=period, actor=self.actor)
        quote = preview_pawn_loan_full_release(self.loan.pk)
        release = release_pawn_loan_in_full(self.loan.pk, settlement_amount=quote.minimum_settlement,
            request_key="monitoring-close", actor=self.actor)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "CLOSED")
        snapshot.refresh_from_db()
        saved = (snapshot.status, snapshot.error_message, snapshot.updated_at, snapshot.source_provenance)
        Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
        self.amend(rate_freshness_days=10)
        snapshot.refresh_from_db()
        self.assertEqual((snapshot.status, snapshot.error_message, snapshot.updated_at, snapshot.source_provenance), saved)
        self.assertEqual(reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today)["selected"], 0)
        request = RequestFactory().get("/")
        request.user, request.workspace = self.actor, self.tenant
        with patch("apps.tenant_apps.loans.web.pawn_reads.get_pawn_loan_risk_assessment") as risk, \
             patch("apps.tenant_apps.loans.web.pawn_reads.get_pawn_loan_collateral_valuation") as valuation, \
             patch("apps.tenant_apps.loans.web.pawn_reads.get_pawn_loan_delinquency") as delinquency:
            self.assertContains(pawn_loan_detail(request, self.loan.pk), "Live health monitoring has stopped")
            risk.assert_not_called()
            valuation.assert_not_called()
            delinquency.assert_not_called()
        with patch("apps.tenant_apps.loans.web.operations.assess_risk_alert_communication_readiness") as readiness:
            pawn_risk_portfolio(request)
            readiness.assert_not_called()
        reverse_pawn_loan_event(release.loan_event.pk, reason="Correct development release", actor=self.actor)
        self.loan.refresh_from_db()
        snapshot.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")
        self.assertEqual(snapshot.status, "STALE")
        self.assertEqual(reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today)["current"], 1)

    def test_prepared_reads_preserve_results_and_reject_wrong_loan_or_date(self):
        from dataclasses import replace
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        from apps.tenant_apps.loans.selectors.delinquency import get_pawn_loan_delinquency
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
        from apps.tenant_apps.loans.services import record_pawn_loan_repayment, reverse_pawn_loan_event
        for stage in ("opening", "repayment", "reversal"):
            if stage == "repayment":
                repayment = record_pawn_loan_repayment(self.loan.pk, amount="100", request_key="bench-parity", actor=self.actor)
            elif stage == "reversal":
                reverse_pawn_loan_event(repayment.loan_event.pk, reason="Parity after reversal", actor=self.actor)
            exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today)
            delinquency = get_pawn_loan_delinquency(self.loan.pk, as_of_date=self.today)
            collateral = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today)
            risk = get_pawn_loan_risk_assessment(self.loan.pk, as_of_date=self.today)
            self.assertEqual(collateral, get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today, _exposure=exposure))
            self.assertEqual(risk, get_pawn_loan_risk_assessment(self.loan.pk, as_of_date=self.today,
                _delinquency=delinquency, _collateral=collateral))
            snapshot = self.refresh()
            self.assertEqual(snapshot.exposure, exposure.total_economic_exposure)
            self.assertEqual(snapshot.assessment_fingerprint, risk.fingerprint)
        for changes in ({"loan_id": -1}, {"as_of_date": self.today - timedelta(days=1)}):
            with self.assertRaises(ValueError):
                get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today, _exposure=replace(exposure, **changes))
            with self.assertRaises(ValueError):
                get_pawn_loan_risk_assessment(self.loan.pk, as_of_date=self.today, _delinquency=replace(delinquency, **changes))
            with self.assertRaises(ValueError):
                get_pawn_loan_risk_assessment(self.loan.pk, as_of_date=self.today, _collateral=replace(collateral, **changes))

    def test_form_and_history_offer_a_preserving_amendment(self):
        request = RequestFactory().get("/", {"amend_monitoring": self.policy.pk})
        request.user, request.workspace = self.actor, self.tenant
        page = pawn_economics_setup(request)
        self.assertContains(page, "Review these compliance thresholds")
        self.assertContains(page, "Amend monitoring policy")
        self.assertContains(page, "Save new policy version")
        self.assertContains(page, f'value="{self.policy.pk}"')
        data = self.amendment_data()
        data["license"], data["supersedes"] = "", self.policy.pk
        form = LoanMonitoringPolicyForm(data, workspace=self.tenant, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)

    def test_amendment_post_preserves_mode_on_error_and_rejects_repeat(self):
        data = self.amendment_data()
        data["license"], data["supersedes"] = "", self.policy.pk
        payload = {"monitoring-" + key: value for key, value in data.items()}
        payload.update(action="monitoring")
        payload["monitoring-amendment_reason"] = ""

        def post():
            request = RequestFactory().post("/", payload)
            request.user, request.workspace = self.actor, self.tenant
            with patch("apps.tenant_apps.loans.web.economic_setup.messages.success"):
                return pawn_economics_setup(request)

        self.assertContains(post(), "Save new policy version")
        self.assertEqual(LoanMonitoringPolicy.objects.count(), 1)
        payload["monitoring-amendment_reason"] = "Review evidence limits"
        self.assertEqual(post().status_code, 302)
        self.assertEqual(LoanMonitoringPolicy.objects.count(), 2)
        self.assertEqual(post().status_code, 200)
        self.assertEqual(LoanMonitoringPolicy.objects.count(), 2)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.rate_freshness_days, 7)

    def test_portfolio_page_displays_unknown_and_unassessed_without_old_money(self):
        self.refresh()
        loan = self.extra_loan()
        request = RequestFactory().get("/")
        request.user, request.workspace = self.actor, self.tenant
        with patch("apps.tenant_apps.loans.web.operations.assess_risk_alert_communication_readiness"):
            response = pawn_risk_portfolio(request)
        self.assertContains(response, loan.loan_number)
        self.assertContains(response, "UNASSESSED")
        self.assertContains(response, "Unknown coverage")
        self.assertContains(response, "The metal price is older")
        self.assertContains(response, "Unavailable")

    def test_restricted_role_enforces_policy_history_and_source_invalidation(self):
        snapshot = self.refresh()
        role = connection.ops.quote_name("monitoring_rls_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            for sql in ("UPDATE loans_loanmonitoringpolicy SET rate_freshness_days=999 WHERE id=%s", "DELETE FROM loans_loanmonitoringpolicy WHERE id=%s"):
                with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(sql, [self.policy.pk])
            self.amend(rate_freshness_days=12)
            snapshot.refresh_from_db()
            self.assertEqual(snapshot.status, "STALE")
            snapshot = self.refresh()
            Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
            snapshot.refresh_from_db()
            self.assertEqual(snapshot.status, "STALE")
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
