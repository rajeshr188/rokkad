import io
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.template.loader import get_template
from django.urls import reverse
from openpyxl import load_workbook

from apps.tenant_apps.loans.services import (
    PawnLoanReportDataset,
    PawnLoanReportExportError,
    build_party_statement_dataset,
    build_pawn_loan_report_dataset,
    render_report_dataset,
)


class PawnLoanReportExportTests(SimpleTestCase):
    dataset = PawnLoanReportDataset(
        key="active",
        title="Active loans",
        columns=("Loan", "Amount"),
        rows=(("PL-A-00001", "1000.00"),),
    )

    def test_csv_xlsx_and_pdf_render_from_same_dataset(self):
        csv_content, csv_type = render_report_dataset(self.dataset, "csv")
        self.assertEqual(csv_type, "text/csv")
        self.assertIn(b"PL-A-00001", csv_content)

        xlsx_content, xlsx_type = render_report_dataset(self.dataset, "xlsx")
        self.assertIn("spreadsheetml", xlsx_type)
        workbook = load_workbook(io.BytesIO(xlsx_content), read_only=True)
        self.assertEqual(workbook.active["A2"].value, "PL-A-00001")

        pdf_content, pdf_type = render_report_dataset(self.dataset, "pdf")
        self.assertEqual(pdf_type, "application/pdf")
        self.assertTrue(pdf_content.startswith(b"%PDF"))

    def test_party_statement_export_contains_positions_and_immutable_transactions(self):
        balance = SimpleNamespace(
            principal_outstanding="800.00",
            interest_outstanding="40.00",
            fees_outstanding="10.00",
            total_due="850.00",
        )
        loan = SimpleNamespace(loan_number="PL-A-00001", loan_date=date(2026, 8, 1))
        event = SimpleNamespace(
            loan=loan,
            effective_date=date(2026, 8, 2),
            payload={"values": {"principal": "200.00", "interest": "40.00", "fees": "10.00"}},
            get_event_kind_display=lambda: "Repayment",
        )
        statement = SimpleNamespace(
            party=SimpleNamespace(display_name="Asha Devi"),
            as_of_date=date(2026, 8, 3),
            loans=(SimpleNamespace(loan=loan, status="ACTIVE", balance=balance, balance_error=""),),
            transactions=(event,),
        )

        dataset = build_party_statement_dataset(statement)

        self.assertEqual(dataset.rows[0][0], "LOAN POSITION")
        self.assertEqual(dataset.rows[1][0], "TRANSACTION")
        self.assertEqual(dataset.rows[1][3], "Repayment")
        self.assertIn("Correction status", dataset.columns)
        self.assertEqual(dataset.rows[1][9], "CURRENT")
        self.assertEqual(dataset.rows[1][7], Decimal("250.00"))

    def test_daily_export_retains_correction_evidence(self):
        event = SimpleNamespace(
            pk=22,
            effective_date=date(2026, 8, 3),
            loan=SimpleNamespace(
                loan_number="PL-A-00001",
                borrower=SimpleNamespace(display_name="Asha Devi"),
            ),
        )
        report = SimpleNamespace(
            as_of_date=date(2026, 8, 3),
            daily_activity=(
                SimpleNamespace(
                    event=event,
                    activity="Reversal of Repayment",
                    amount="-500.00",
                    correction_status="COMPENSATION",
                    correction_event_id=21,
                ),
            ),
        )

        dataset = build_pawn_loan_report_dataset(report, "daily")

        self.assertIn("Correction status", dataset.columns)
        self.assertEqual(dataset.rows[0][6:], ("COMPENSATION", 21))

    def test_unknown_export_format_is_rejected(self):
        with self.assertRaises(PawnLoanReportExportError):
            render_report_dataset(self.dataset, "json")

    def test_report_templates_and_export_routes_are_registered(self):
        self.assertIsNotNone(get_template("loans/pawn/reports.html"))
        self.assertIsNotNone(get_template("loans/pawn/party_statement.html"))
        self.assertEqual(
            reverse("loans:pawn_loan_report_export", args=("active", "csv")),
            "/loans/internal/reports/export/active.csv",
        )
        self.assertEqual(
            reverse("loans:pawn_party_statement_export", args=(17, "pdf")),
            "/loans/internal/reports/party/17/pdf/",
        )
