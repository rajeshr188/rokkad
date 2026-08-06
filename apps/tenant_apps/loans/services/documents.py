"""Stable, source-linked PawnLoan PDF document facade."""

import io
from dataclasses import dataclass
from xml.sax.saxutils import escape

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.tenant_apps.loans.documents import PawnLoanDocumentProjectionBuilder
from apps.tenant_apps.loans.documents.payloads import DocumentProjectionError


class PawnLoanDocumentError(ValueError):
    pass


@dataclass(frozen=True)
class PawnLoanDocumentResult:
    document_type: str
    file_name: str
    verification_id: str
    pdf: bytes

    @property
    def ok(self):
        return bool(self.pdf)


class PawnLoanDocumentService:
    """Public facade that projects source facts and renders the fixed layout."""

    @classmethod
    def render_loan_ticket(cls, loan):
        return cls._project_and_render(PawnLoanDocumentProjectionBuilder.loan_ticket, loan)

    @classmethod
    def render_repayment_receipt(cls, event):
        return cls._project_and_render(
            PawnLoanDocumentProjectionBuilder.repayment_receipt, event
        )

    @classmethod
    def render_release_memo(cls, release):
        return cls._project_and_render(PawnLoanDocumentProjectionBuilder.release_memo, release)

    @classmethod
    def render_auction_notice(cls, auction):
        return cls._project_and_render(PawnLoanDocumentProjectionBuilder.auction_notice, auction)

    @classmethod
    def render_auction_recovery_memo(cls, auction):
        return cls._project_and_render(
            PawnLoanDocumentProjectionBuilder.auction_recovery_memo, auction
        )

    @classmethod
    def render_renewal_memo(cls, renewal):
        return cls._project_and_render(PawnLoanDocumentProjectionBuilder.renewal_memo, renewal)

    @classmethod
    def _project_and_render(cls, builder, source):
        try:
            payload = builder(source)
        except DocumentProjectionError as exc:
            raise PawnLoanDocumentError(str(exc)) from exc
        pdf = cls._build_pdf(
            title=payload.title,
            details=payload.details,
            verification_id=payload.verification_id,
            sections=tuple((section.heading, section.rows) for section in payload.sections),
        )
        return PawnLoanDocumentResult(
            payload.document_type,
            payload.file_name,
            payload.verification_id,
            pdf,
        )

    @staticmethod
    def build_pdf_response(result, *, inline=True):
        disposition = "inline" if inline else "attachment"
        response = HttpResponse(result.pdf, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'{disposition}; filename="{result.file_name}"'
        )
        response["X-Rokkad-Verification-ID"] = result.verification_id
        return response

    @classmethod
    def _build_pdf(cls, *, title, details, verification_id, sections=()):
        buffer = io.BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=14 * mm,
            leftMargin=14 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            pageCompression=0,
            title=title,
        )
        styles = getSampleStyleSheet()
        story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 8)]
        details_table = Table(
            [
                [
                    Paragraph(f"<b>{escape(str(label))}</b>", styles["BodyText"]),
                    Paragraph(escape(str(value)), styles["BodyText"]),
                ]
                for label, value in details
            ],
            colWidths=[52 * mm, 125 * mm],
            repeatRows=0,
        )
        details_table.setStyle(cls._table_style(header=False))
        story.extend([details_table, Spacer(1, 12)])
        for heading, rows in sections:
            story.extend(
                [
                    Paragraph(escape(heading), styles["Heading2"]),
                    Table(
                        [
                            [Paragraph(escape(str(cell)), styles["BodyText"]) for cell in row]
                            for row in rows
                        ],
                        repeatRows=1,
                        hAlign="LEFT",
                    ),
                    Spacer(1, 12),
                ]
            )
            story[-2].setStyle(cls._table_style(header=True))
        story.extend(
            [
                Spacer(1, 8),
                Paragraph("Verification ID", styles["Heading3"]),
                Paragraph(escape(verification_id), styles["Code"]),
                Spacer(1, 18),
                Table(
                    [["Borrower / customer signature", "Authorized pawnbroker signature"]],
                    colWidths=[88 * mm, 88 * mm],
                    rowHeights=[18 * mm],
                ),
            ]
        )
        story[-1].setStyle(cls._table_style(header=False))
        document.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

    @staticmethod
    def _table_style(*, header):
        commands = [
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]
        if header:
            commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ]
            )
        return TableStyle(commands)


__all__ = [
    "PawnLoanDocumentError",
    "PawnLoanDocumentResult",
    "PawnLoanDocumentService",
]
