"""Deterministic regulatory register rendering from selector rows."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_loan_license_register_pdf(*, workspace, rows, as_of_date) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Loan license register",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Loan License Register", styles["Title"]),
        Paragraph(
            f"Workspace: {workspace.name} &nbsp;&nbsp; As of: {as_of_date.isoformat()}",
            styles["Normal"],
        ),
        Spacer(1, 5 * mm),
    ]
    data = [[
        "License",
        "Authority",
        "Issued",
        "Expires",
        "Revision",
        "Evidence",
        "Status",
    ]]
    for row in rows:
        revision = row.current_revision
        data.append([
            row.license.license_number,
            row.license.issuing_authority or "-",
            row.license.issued_on.isoformat(),
            row.license.expires_on.isoformat(),
            str(revision.revision_number) if revision else "-",
            revision.sha256[:12] if revision and revision.has_document else "Missing",
            row.status.replace("_", " ").title(),
        ])
    table = Table(
        data,
        repeatRows=1,
        colWidths=[42 * mm, 52 * mm, 28 * mm, 28 * mm, 20 * mm, 34 * mm, 31 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#adb5bd")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    document.build(story)
    return buffer.getvalue()


__all__ = ["render_loan_license_register_pdf"]
