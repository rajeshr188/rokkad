"""Evidence dimensions through real admissions, refresh, reports and exports."""
import csv
import io
from datetime import date
from unittest.mock import patch

from apps.tenant_apps.loans.selectors.evidence_quality import loan_evidence_quality
from apps.tenant_apps.loans.selectors.reports import get_pawn_loan_reports, get_pawn_party_statement
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio, get_risk_portfolio_summary
from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from apps.tenant_apps.loans.services.report_exports import (
    build_pawn_loan_report_dataset, build_party_statement_dataset, render_report_dataset,
)
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from .test_continuation_admissions import AdmissionFixture


class ContinuationQualityTests(AdmissionFixture):
    on = date(2026, 7, 21)  # Beyond the standing 90-day appraisal freshness limit.

    def test_current_supported_calculation_is_independent_of_books_and_valuation(self):
        with self.scoped():
            snapshot = refresh_loan_risk_snapshot(self.opening.pk, as_of_date=self.on)
            quality = loan_evidence_quality(self.opening, as_of_date=self.on)
            self.assertEqual(quality["assessment"]["status"], "CURRENT")
            self.assertEqual(quality["calculation"]["status"], "SUPPORTED")
            self.assertFalse(quality["transactions"]["complete"])
            self.assertEqual(quality["valuation"]["status"], "UNAVAILABLE")
            self.assertEqual(quality["history"]["principal_basis"], "OPENING_CHECKPOINT")
            self.assertEqual(quality["history"]["from_date"], self.cutover)
            self.assertEqual(snapshot.source_provenance["financial"]["principal_history_basis"], "OPENING_CHECKPOINT")
            self.assertEqual(snapshot.source_provenance["financial"]["history_from"], self.cutover.isoformat())
            with patch("django.utils.timezone.localdate", return_value=self.on):
                summary = get_risk_portfolio_summary()
                dashboard = get_dashboard_health_summary(workspace=self.a)
                page = get_risk_portfolio()
            self.assertEqual(summary.provisional_count, 1)
            self.assertEqual(summary.unknown_coverage_count, 1)
            self.assertFalse(summary.totals_complete)
            self.assertEqual(summary.total_exposure, snapshot.exposure)
            self.assertEqual(dashboard["financial_count"], 1)
            self.assertFalse(dashboard["financial_complete"])
            self.assertTrue(any(loan.evidence_quality["assessment"]["status"] == "CURRENT"
                for loan in page.object_list))

    def test_stale_assessment_does_not_hide_supported_payment_calculation(self):
        with self.scoped():
            snapshot = refresh_loan_risk_snapshot(self.direct.pk, as_of_date=self.on)
            snapshot.source_provenance["calculation_contract"] = "LOAN_RISK_SNAPSHOT_V5"
            snapshot.save(update_fields=["source_provenance"])
            quality = loan_evidence_quality(self.direct, as_of_date=self.on, calculation_status="SUPPORTED",
                calculation_message="Collection preview at the payment date.")
            self.assertEqual(quality["assessment"]["status"], "STALE")
            self.assertEqual(quality["calculation"]["status"], "SUPPORTED")
            self.assertEqual(quality["valuation"]["status"], "UNASSESSED")
            self.assertEqual(quality["transactions"]["capture_basis"], "SYSTEM_CAPTURE_ASSUMPTION")
            self.assertIn("not a check", quality["transactions"]["message"])
        with self.scoped(self.b), self.assertRaisesMessage(ValueError, "Workspace"):
            loan_evidence_quality(self.direct, as_of_date=self.on)

    def test_native_origin_does_not_override_staff_report_of_missing_paper_activity(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=self.on):
            data = dict(through_date=self.on, confirmed_complete=False,
                source_reference="Synthetic book has an unentered receipt", request_key="native-missing-paper")
            _, token = preview_transaction_review(self.direct.pk, actor=self.actor, **data)
            confirm_transaction_review(self.direct.pk, actor=self.actor, **data,
                review_token=token, acknowledged=True)
            quality = loan_evidence_quality(self.direct, as_of_date=self.on, calculation_status="SUPPORTED")
            self.assertEqual(quality["transactions"]["status"], "INCOMPLETE")
            self.assertFalse(quality["transactions"]["complete"])
            self.assertEqual(quality["calculation"]["status"], "SUPPORTED")

    def test_reports_and_export_formats_retain_quality_and_checkpoint_unknowns(self):
        with self.scoped():
            refresh_loan_risk_snapshot(self.opening.pk, as_of_date=self.on)
            report = get_pawn_loan_reports(as_of_date=self.on)
            dataset = build_pawn_loan_report_dataset(report, "active")
            headers = dataset.columns
            row = next(row for row in dataset.rows if row[0] == self.opening.loan_number)
            self.assertEqual(row[headers.index("Saved assessment")], "CURRENT")
            self.assertEqual(row[headers.index("Valuation availability")], "UNAVAILABLE")
            self.assertIn("STALE_APPRAISAL", row[headers.index("Valuation blockers")])
            self.assertEqual(row[headers.index("Calculation support")], "SUPPORTED")
            self.assertEqual(row[headers.index("Financial history from")], self.cutover)
            self.assertEqual(row[headers.index("Principal history basis")], "OPENING_CHECKPOINT")
            for fmt in ("csv", "xlsx", "pdf"):
                content, _ = render_report_dataset(dataset, fmt)
                self.assertTrue(content)
                if fmt == "csv":
                    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
                    self.assertIn("Calculation support", rows[0])
            statement = get_pawn_party_statement(party_id=self.opening.borrower_id, as_of_date=self.on)
            exported = build_party_statement_dataset(statement)
            self.assertTrue(all(len(row) == len(exported.columns) for row in exported.rows))
            self.assertIn("Principal history basis", exported.columns)
