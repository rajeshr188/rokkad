import csv
import io
from xml.sax.saxutils import escape
from dataclasses import dataclass
from decimal import Decimal

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class PawnLoanReportExportError(ValueError):
    pass


@dataclass(frozen=True)
class PawnLoanReportDataset:
    key: str
    title: str
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    notes: str = ""


QUALITY_COLUMNS = ("Saved assessment", "Valuation availability", "Calculation support",
    "Financial history from", "Principal history basis", "Capture basis", "Valuation blockers")


def _quality_cells(row):
    quality = getattr(row, "evidence_quality", None) or {}
    return (quality.get("assessment", {}).get("status", "UNASSESSED"),
        quality.get("valuation", {}).get("status", "UNASSESSED"),
        quality.get("calculation", {}).get("status", "UNASSESSED"),
        quality.get("history", {}).get("from_date") or "",
        quality.get("history", {}).get("principal_basis") or "",
        quality.get("transactions", {}).get("capture_basis") or "",
        ", ".join(quality.get("valuation", {}).get("blockers", [])))


def build_pawn_loan_report_dataset(report, section):
    builders = {
        "active": _active,
        "daily": _daily,
        "interest_due": _interest_due,
        "overdue": _overdue,
        "releases_renewals": _releases_renewals,
        "storage": _storage,
        "license_expiry": _license_expiry,
    }
    try:
        return builders[section](report)
    except KeyError as exc:
        raise PawnLoanReportExportError("Unknown PawnLoan report section.") from exc


def build_party_statement_dataset(statement):
    rows = []
    for loan_row in statement.loans:
        balance = loan_row.balance
        completeness = getattr(loan_row, "transaction_completeness", None)
        rows.append((
            "LOAN POSITION",
            loan_row.loan.loan_number,
            loan_row.loan.loan_date,
            loan_row.status,
            balance.principal_outstanding if balance else "ERROR",
            balance.interest_outstanding if balance else loan_row.balance_error,
            balance.fees_outstanding if balance else "",
            balance.total_due if balance else "",
            "", "", "",
            completeness.status if completeness else "", completeness.through_date if completeness else "",
        ) + _quality_cells(loan_row))
    transaction_rows = getattr(statement, "transaction_rows", None)
    if transaction_rows is None:
        transaction_rows = tuple(
            (
                event, event.get_event_kind_display(), "CURRENT", None,
                (event.payload.get("values") or {}).get("principal", "0"),
                (event.payload.get("values") or {}).get("interest", "0"),
                (event.payload.get("values") or {}).get("fees", "0"),
            )
            for event in statement.transactions
        )
    else:
        transaction_rows = tuple(
            (
                row.event, row.activity, row.correction_status,
                row.correction_event_id,
                row.principal, row.interest, row.fees,
            )
            for row in transaction_rows
        )
    for (
        event, activity, correction_status, correction_event_id,
        principal, interest, fees,
    ) in transaction_rows:
        transaction_total = sum(
            (Decimal(str(value)) for value in (principal, interest, fees)),
            Decimal("0"),
        )
        rows.append((
            "TRANSACTION",
            event.loan.loan_number,
            event.effective_date,
            activity,
            principal,
            interest,
            fees,
            transaction_total,
            getattr(event, "pk", ""),
            correction_status,
            correction_event_id or "",
            "", "", *([""] * len(QUALITY_COLUMNS)),
        ))
    return PawnLoanReportDataset(
        "party_statement",
        f"Party statement — {statement.party.display_name} — {statement.as_of_date}",
        (
            "Row type", "Loan", "Date", "State / kind", "Principal", "Interest",
            "Fees", "Total", "Event ID", "Correction status", "Correction event",
            "Transaction review", "Paper records through",
        ) + QUALITY_COLUMNS,
        tuple(rows),
        notes="Recorded positions exclude collection interest awaiting recognition. Paper coverage is shown separately; unconfirmed histories are provisional.",
    )


def render_report_dataset(dataset, export_format):
    if export_format == "csv":
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(dataset.columns)
        writer.writerows(dataset.rows)
        return stream.getvalue().encode("utf-8-sig"), "text/csv"
    if export_format == "xlsx":
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet(title=dataset.key[:31])
        sheet.append(dataset.columns)
        for row in dataset.rows:
            sheet.append(tuple(_cell(value) for value in row))
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if export_format == "pdf":
        output = io.BytesIO()
        document = SimpleDocTemplate(
            output, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
            topMargin=10 * mm, bottomMargin=10 * mm, title=dataset.title,
        )
        styles = getSampleStyleSheet()
        cell_style = styles["BodyText"].clone("ReportCell")
        if len(dataset.columns) >= 10:
            cell_style.fontSize = 7
            cell_style.leading = 9
        data = [
            [Paragraph(escape(str(value)), cell_style) for value in dataset.columns]
        ]
        data.extend(
            [Paragraph(escape(str(_cell(value))), cell_style) for value in row]
            for row in dataset.rows
        )
        table = Table(data, repeatRows=1, hAlign="LEFT",
            colWidths=[document.width / len(dataset.columns)] * len(dataset.columns) if len(dataset.columns) >= 10 else None)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
        ]))
        story = [Paragraph(escape(dataset.title), styles["Title"])]
        if dataset.notes:
            story.extend([Paragraph(escape(dataset.notes), styles["BodyText"]), Spacer(1, 8)])
        story.extend([Spacer(1, 8), table])
        document.build(story)
        return output.getvalue(), "application/pdf"
    raise PawnLoanReportExportError("Report export format must be csv, xlsx, or pdf.")


def _active(report):
    return _portfolio_dataset("active", "Active loans", report.active_loans)


def _interest_due(report):
    return _portfolio_dataset("interest_due", "Interest due", report.interest_due)


def _overdue(report):
    return _portfolio_dataset("overdue", "Overdue loans", report.overdue_loans)


def _portfolio_dataset(key, title, rows):
    return PawnLoanReportDataset(
        key, title,
        ("Loan", "Party", "Due date", "Principal", "Interest", "Fees", "Total due", "Status", "Transaction review", "Paper records through") + QUALITY_COLUMNS,
        tuple((
            row.loan.loan_number, row.loan.borrower.display_name,
            row.balance.due_date if row.balance else "",
            row.balance.principal_outstanding if row.balance else "",
            row.balance.interest_outstanding if row.balance else "",
            row.balance.fees_outstanding if row.balance else "",
            row.balance.total_due if row.balance else row.balance_error,
            row.status,
            row.transaction_completeness.status if row.transaction_completeness else "",
            row.transaction_completeness.through_date if row.transaction_completeness else "",
        ) + _quality_cells(row) for row in rows),
        notes="Amounts derive from entered transactions. Unconfirmed paper histories are provisional. Transaction coverage is separate from valuation freshness.",
    )


def _daily(report):
    rows = [
        (
            row.event.effective_date,
            row.activity,
            row.event.loan.loan_number,
            row.event.loan.borrower.display_name,
            row.amount,
            row.event.pk,
            row.correction_status,
            row.correction_event_id or "",
        )
        for row in report.daily_activity
    ]
    return PawnLoanReportDataset(
        "daily", f"Daily disbursals and repayments — {report.as_of_date}",
        (
            "Date", "Kind", "Loan", "Party", "Amount", "Event ID",
            "Correction status", "Correction event",
        ), tuple(rows),
    )


def _releases_renewals(report):
    rows = [
        (
            row.effective_date, "RELEASE", row.loan.loan_number,
            row.release_number, row.settlement_amount,
            "REVERSED" if hasattr(row, "reversal") else getattr(row, "correction_status", "") or "COMPLETED",
            "",
        )
        for row in report.releases
    ]
    rows.extend(
        (
            row.renewal_date, "RENEWAL", row.source_loan.loan_number,
            row.renewal_number, row.successor_loan.loan_number,
            "REVERSED" if hasattr(row, "reversal") else getattr(row, "correction_status", "") or "COMPLETED",
            _recorded_renewal_cash(row),
        )
        for row in report.renewals
    )
    return PawnLoanReportDataset(
        "releases_renewals", "Releases and renewals",
        (
            "Date", "Kind", "Source loan", "Reference",
            "Settlement / successor", "Status", "Recorded renewal cash / custody",
        ), tuple(rows),
    )


def _recorded_renewal_cash(renewal):
    cash = (getattr(renewal, "valuation_snapshot", None) or {}).get("cash_evidence")
    if not cash:
        return ""
    method = "Full principal repayment / fresh advance" if cash["method"] == "REPAY_REDRAW" else "Principal carry"
    custody = "stayed held" if cash["custody"] == "HELD" else "returned and repledged"
    return (f"{method}; received {cash['cash_received']}; paid {cash['cash_paid']}; "
            f"old interest offset {cash['interest_offset']}; principal carried {cash['principal_carried']}; "
            f"gross advance {cash['gross_advance']}; collateral {custody}")


def _storage(report):
    return PawnLoanReportDataset(
        "storage", "Collateral storage inventory",
        ("Loan", "Item", "Metal", "Net weight", "Custody", "Storage path", "Placement"),
        tuple((
            item.loan.loan_number, item.description, item.metal, item.net_weight,
            item.custody_state,
            item.current_storage_location.path_label if item.current_storage_location_id else "",
            "PLACED" if item.current_storage_location_id else "AWAITING_PLACEMENT",
        ) for item in report.storage_inventory),
    )


def _license_expiry(report):
    return PawnLoanReportDataset(
        "license_expiry", "Regulatory license expiry",
        ("License", "Number", "Authority", "Expires", "Days remaining", "Status"),
        tuple((
            row.license.name, row.license.license_number, row.license.issuing_authority,
            row.license.expires_on, row.days_remaining, row.status,
        ) for row in report.license_expiry),
    )


def _cell(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


__all__ = [
    "PawnLoanReportDataset",
    "PawnLoanReportExportError",
    "build_party_statement_dataset",
    "build_pawn_loan_report_dataset",
    "render_report_dataset",
]
