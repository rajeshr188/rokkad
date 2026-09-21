import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import LoanRiskSnapshot
from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
from apps.tenant_apps.loans.selectors.risk_portfolio import SNAPSHOT_CONTRACT
from apps.tenant_apps.loans.tests import test_dashboard_batch as fixtures


class DashboardHealthTests(TestCase):
    setUp = fixtures.DashboardBatchTests.setUp
    loan = fixtures.DashboardBatchTests.loan

    def snapshot(self, workspace=None, *, collateral="800", shortfall="300", **changes):
        workspace = workspace or self.workspace
        loan = self.loan(workspace)
        values = dict(workspace=workspace, loan=loan, as_of_date=timezone.localdate(),
            status="CURRENT", assessed_at=timezone.now(), assessment_fingerprint=uuid.uuid4().hex,
            exposure=Decimal("1100"), collateral_value=Decimal(collateral), ltv_ratio=Decimal("1.375"),
            source_provenance={"calculation_contract": SNAPSHOT_CONTRACT,
                "financial": {"projected_interest": "100.00", "recorded_total_due": "1000.00", "integrity_findings": []},
                "coverage": {"exposure": "1100", "shortfall": shortfall, "blockers": [], "status": "BREACH"}})
        values.update(changes)
        return LoanRiskSnapshot.objects.create(**values)

    def summary(self):
        return get_dashboard_health_summary(workspace=self.workspace)

    def test_empty_then_many_loans_use_one_query_without_netting_shortfalls(self):
        with workspace_context(self.workspace.pk):
            with self.assertNumQueries(1):
                empty = self.summary()
            self.assertTrue(empty["financial_complete"])
            self.assertEqual(empty["economic_exposure"], 0)
            self.snapshot()
            with self.assertNumQueries(1):
                single = self.summary()
            self.assertEqual(single["projected_interest"], Decimal("100"))
            for _ in range(10):
                self.snapshot(collateral="2000", shortfall="0")
            with self.assertNumQueries(1):
                result = self.summary()
            self.assertEqual(result["economic_exposure"], Decimal("12100"))
            self.assertEqual(result["collateral_value"], Decimal("20800"))
            self.assertEqual(result["full_shortfall"], Decimal("300"))
            self.assertEqual(result["undercovered_count"], 1)

    def test_incomplete_assessments_exclude_closed_and_never_report_partial_totals(self):
        with workspace_context(self.workspace.pk):
            self.snapshot()
            closed = self.snapshot()
            closed.loan.state = "CLOSED"
            closed.loan.save(update_fields=["state"])
            self.loan(self.workspace)
            for changes in ({"status": "STALE"}, {"status": "ERROR"},
                            {"as_of_date": timezone.localdate()-timedelta(days=1)},
                            {"as_of_date": timezone.localdate()+timedelta(days=1)},
                            {"source_provenance": {"calculation_contract": "LOAN_RISK_SNAPSHOT_V2"}}):
                self.snapshot(**changes)
            result = self.summary()
            self.assertEqual(result["loan_count"], 7)
            self.assertEqual(result["current_count"], 1)
            self.assertEqual(result["stale_count"], 4)
            self.assertEqual(result["error_count"], 1)
            self.assertEqual(result["unassessed_count"], 1)
            self.assertEqual(result["undercovered_count"], 1)
            for field in ("economic_exposure", "projected_interest", "collateral_value", "full_shortfall"):
                self.assertIsNone(result[field])

    def test_unknown_coverage_keeps_valid_financial_totals(self):
        with workspace_context(self.workspace.pk):
            snapshot = self.snapshot(ltv_ratio=None, shortfall=None)
            snapshot.source_provenance["coverage"].update(blockers=["STALE_RATE"], status="UNKNOWN")
            snapshot.save(update_fields=["source_provenance"])
            result = self.summary()
            self.assertEqual(result["economic_exposure"], Decimal("1100"))
            self.assertEqual(result["projected_interest"], Decimal("100"))
            self.assertEqual(result["unknown_coverage_count"], 1)
            self.assertIsNone(result["collateral_value"])

    def test_missing_malformed_or_inconsistent_financial_evidence_is_unavailable(self):
        with workspace_context(self.workspace.pk):
            snapshot = self.snapshot()
            for value in (None, "NaN", "Infinity", "bad", "-1", "9" * 80, "99", {}, []):
                with self.subTest(value=value):
                    snapshot.source_provenance["financial"]["projected_interest"] = value
                    snapshot.save(update_fields=["source_provenance"])
                    result = self.summary()
                    self.assertIsNone(result["economic_exposure"])
                    self.assertEqual(result["financial_count"], 0)
            snapshot.source_provenance["financial"].update(projected_interest="100", integrity_findings=["Schedule mismatch"])
            snapshot.save(update_fields=["source_provenance"])
            self.assertIsNone(self.summary()["economic_exposure"])
            del snapshot.source_provenance["financial"]
            snapshot.save(update_fields=["source_provenance"])
            self.assertIsNone(self.summary()["economic_exposure"])

    def test_malformed_coverage_is_unknown_without_hiding_financial_totals(self):
        with workspace_context(self.workspace.pk):
            snapshot = self.snapshot()
            for value in (None, "NaN", "bad", "-3", "9" * 80):
                snapshot.source_provenance["coverage"]["shortfall"] = value
                snapshot.save(update_fields=["source_provenance"])
                result = self.summary()
                self.assertEqual(result["economic_exposure"], Decimal("1100"))
                self.assertIsNone(result["full_shortfall"])

    def test_workspace_boundary_under_restricted_role(self):
        with self.assertNumQueries(0), self.assertRaises(ValueError):
            self.summary()
        other = Company.objects.create(name="Other health", schema_name="health-other", owner=self.owner, creator=self.owner)
        with workspace_context(other.pk):
            self.snapshot(other, collateral="99999", shortfall="0")
        with workspace_context(self.workspace.pk):
            self.snapshot()
            with self.assertNumQueries(0), self.assertRaises(ValueError):
                get_dashboard_health_summary(workspace=other)
            role = connection.ops.quote_name("health_read_" + uuid.uuid4().hex)
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
                cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
                cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
                cursor.execute(f"SET LOCAL ROLE {role}")
            try:
                result = self.summary()
                self.assertEqual(result["loan_count"], 1)
                self.assertEqual(result["collateral_value"], Decimal("800"))
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")
