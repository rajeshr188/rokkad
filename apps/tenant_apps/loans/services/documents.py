"""Stable, source-linked loan PDF document facades."""

import hashlib
import io
from dataclasses import dataclass
from xml.sax.saxutils import escape

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
        return cls._project_and_render(
            PawnLoanDocumentProjectionBuilder.loan_ticket,
            loan,
            copy_labels=("Original", "Duplicate"),
        )

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
    def _project_and_render(cls, builder, source, *, copy_labels=()):
        try:
            payload = builder(source)
        except DocumentProjectionError as exc:
            raise PawnLoanDocumentError(str(exc)) from exc
        pdf = cls._build_pdf(
            title=payload.title,
            details=payload.details,
            verification_id=payload.verification_id,
            sections=tuple((section.heading, section.rows) for section in payload.sections),
            copy_labels=copy_labels,
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
    def _build_pdf(
        cls,
        *,
        title,
        details,
        verification_id,
        sections=(),
        signature_labels=("Borrower / customer signature", "Authorized pawnbroker signature"),
        copy_labels=(),
    ):
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
        story = []
        for copy_index, copy_label in enumerate(copy_labels or (None,)):
            if copy_index:
                story.append(PageBreak())
            story.extend([Paragraph(escape(title), styles["Title"]), Spacer(1, 4)])
            if copy_label:
                story.extend([
                    Paragraph(f"<b>{escape(copy_label)} copy</b>", styles["Heading3"]),
                    Spacer(1, 6),
                ])
            details_table = Table(
                [[
                    Paragraph(f"<b>{escape(str(label))}</b>", styles["BodyText"]),
                    Paragraph(escape(str(value)), styles["BodyText"]),
                ] for label, value in details],
                colWidths=[52 * mm, 125 * mm],
                repeatRows=0,
            )
            details_table.setStyle(cls._table_style(header=False))
            story.extend([details_table, Spacer(1, 12)])
            for heading, rows in sections:
                section_table = Table(
                    [[Paragraph(escape(str(cell)), styles["BodyText"]) for cell in row] for row in rows],
                    repeatRows=1,
                    hAlign="LEFT",
                )
                section_table.setStyle(cls._table_style(header=True))
                story.extend([
                    Paragraph(escape(heading), styles["Heading2"]),
                    section_table,
                    Spacer(1, 12),
                ])
            signature_table = Table(
                [[signature_labels[0], signature_labels[1]]],
                colWidths=[88 * mm, 88 * mm],
                rowHeights=[18 * mm],
            )
            signature_table.setStyle(cls._table_style(header=False))
            story.extend([
                Spacer(1, 8),
                Paragraph("Verification ID", styles["Heading3"]),
                Paragraph(escape(verification_id), styles["Code"]),
                Spacer(1, 18),
                signature_table,
            ])
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


class FundingLoanDocumentService:
    """Fixed preview documents projected from immutable FundingLoan evidence."""

    @classmethod
    def render_agreement(cls, loan, detail):
        terms = loan.terms_snapshot
        pledge = loan.pledge
        return cls._render(
            "funding_agreement",
            f"Funding agreement and collateral handoff - {loan.funding_number}",
            f"funding-{loan.funding_number}-agreement.pdf",
            f"FundingLoan:{loan.pk}:agreement:{terms.fingerprint}:{pledge.request_fingerprint}",
            (
                ("Workspace", loan.workspace.name),
                ("Funding loan", loan.funding_number),
                ("Lender", loan.lender.display_name),
                ("Activated", terms.activated_on),
                ("Maturity", terms.maturity_on),
                ("Principal", terms.principal_amount),
                ("Monthly interest rate", terms.monthly_interest_rate),
                ("Maximum LTV", terms.maximum_funding_ltv_ratio),
                ("Operational accounting", "Not posted"),
            ),
            (("Collateral handed to lender", cls._collateral_rows(detail.collateral)),),
        )

    @classmethod
    def render_repayment_receipt(cls, event):
        if event.event_kind != "REPAYMENT":
            raise PawnLoanDocumentError("Funding repayment receipt requires repayment evidence.")
        loan = event.funding_loan
        total = event.principal_amount + event.interest_amount + event.fee_amount
        return cls._render(
            "funding_repayment_receipt",
            f"Funding repayment receipt - {loan.funding_number}",
            f"funding-{loan.funding_number}-repayment-{event.pk}.pdf",
            f"FundingLoanEvent:{event.pk}:{event.request_fingerprint}",
            (
                ("Workspace", loan.workspace.name),
                ("Funding loan", loan.funding_number),
                ("Lender", loan.lender.display_name),
                ("Effective date", event.effective_date),
                ("Amount received", total),
                ("Fees", event.fee_amount),
                ("Interest", event.interest_amount),
                ("Principal", event.principal_amount),
                ("Operational accounting", "Not posted"),
            ),
        )

    @classmethod
    def render_return_receipt(cls, funding_return):
        loan = funding_return.funding_loan
        rows = (("Collateral item", "Source PawnLoan", "Selected value"),) + tuple(
            (
                item.pledge_item.collateral_item_id,
                item.pledge_item.collateral_item.loan.loan_number,
                item.pledge_item.selected_collateral_value,
            )
            for item in funding_return.items.all()
        )
        return cls._render(
            "funding_return_receipt",
            f"Funding collateral return receipt - {loan.funding_number}",
            f"funding-{loan.funding_number}-return-{funding_return.pk}.pdf",
            f"FundingReturn:{funding_return.pk}:{funding_return.request_fingerprint}",
            (
                ("Workspace", loan.workspace.name),
                ("Funding loan", loan.funding_number),
                ("Lender", loan.lender.display_name),
                ("Effective date", funding_return.effective_date),
                ("Principal outstanding", funding_return.principal_outstanding),
                ("Retained collateral value", funding_return.retained_collateral_value),
                ("Operational accounting", "Not posted"),
            ),
            (("Collateral returned to branch vault", rows),),
        )

    @classmethod
    def render_statement(cls, loan, detail):
        fingerprint = hashlib.sha256(
            "|".join(
                f"{row.source_id}:{row.sequence}:{row.operation}:{row.total_balance}"
                for row in detail.statement
            ).encode("utf-8")
        ).hexdigest()
        rows = (("Seq.", "Date", "Operation", "Principal", "Interest", "Fees", "Balance"),) + tuple(
            (
                row.sequence,
                row.effective_date,
                row.operation,
                row.principal_effect,
                row.interest_effect,
                row.fee_effect,
                row.total_balance,
            )
            for row in detail.statement
        )
        return cls._render(
            "funding_statement",
            f"Funding statement - {loan.funding_number}",
            f"funding-{loan.funding_number}-statement.pdf",
            f"FundingLoan:{loan.pk}:statement:{fingerprint}",
            (
                ("Workspace", loan.workspace.name),
                ("Funding loan", loan.funding_number),
                ("Lender", loan.lender.display_name),
                ("Lifecycle state", loan.state),
                ("Total due", detail.summary.total_due),
                ("Operational accounting", "Not posted"),
            ),
            (("Event-derived statement", rows),),
        )

    @classmethod
    def _render(cls, document_type, title, file_name, verification_id, details, sections=()):
        return PawnLoanDocumentResult(
            document_type=document_type,
            file_name=file_name,
            verification_id=verification_id,
            pdf=PawnLoanDocumentService._build_pdf(
                title=title,
                details=details,
                verification_id=verification_id,
                sections=sections,
                signature_labels=("Funding lender signature", "Authorized branch signature"),
            ),
        )

    @staticmethod
    def _collateral_rows(collateral):
        return (("Collateral item", "Source PawnLoan", "Description", "Selected value"),) + tuple(
            (
                row.collateral_item_id,
                row.source_loan_number,
                row.description,
                row.selected_collateral_value,
            )
            for row in collateral
        )


__all__ = [
    "PawnLoanDocumentError",
    "PawnLoanDocumentResult",
    "PawnLoanDocumentService",
    "FundingLoanDocumentService",
]
