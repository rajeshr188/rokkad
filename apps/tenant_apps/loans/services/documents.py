"""Stable, source-linked PawnLoan PDF documents."""

import io
from dataclasses import dataclass
from decimal import Decimal
from xml.sax.saxutils import escape

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.tenant_apps.loans.domain import PawnLoanState, TransactionKind


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
    @classmethod
    def render_loan_ticket(cls, loan):
        if loan.state == PawnLoanState.DRAFT.value:
            raise PawnLoanDocumentError(
                "Loan ticket is unavailable while the loan is an editable draft."
            )
        approval = loan.approval_snapshots.order_by("-version").first()
        if approval is None:
            raise PawnLoanDocumentError(
                "Loan ticket is available only after the loan has an approval snapshot."
            )
        payload = approval.payload
        verification = cls._verification(
            loan,
            f"approval:{approval.pk}:v{approval.version}:{approval.fingerprint}",
        )
        details = cls._identity_rows(loan) + [
            ("Document", "Pawn loan ticket"),
            ("Loan source ID", f"PawnLoan:{loan.pk}"),
            ("Approval source ID", f"PawnLoanApprovalSnapshot:{approval.pk}"),
            ("Approval version", approval.version),
            ("Official loan number", payload["loan_number"]),
            ("Loan date", payload["loan_date"]),
            ("Lifecycle state", loan.get_state_display()),
            ("Principal", cls._money(payload["principal_amount"])),
            ("Monthly interest rate", f"{payload['monthly_interest_rate']}%"),
            ("Tenure", f"{payload['tenure_months']} months"),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Borrower source ID", f"Party:{payload['borrower_id']}"),
            ("Approval fingerprint", approval.fingerprint),
        ]
        collateral_rows = [
            ["Item ID", "Description", "Metal", "Net weight", "Purity", "Appraisal", "Custody"]
        ]
        for item in payload["collateral"]:
            collateral_rows.append(
                [
                    str(item["item_id"]),
                    item["description"],
                    item["metal"].title(),
                    item["net_weight"],
                    f"{item['purity_percentage']}%",
                    cls._money(item["latest_appraised_value"]) if item["latest_appraised_value"] is not None else "—",
                    "At approval",
                ]
            )
        pdf = cls._build_pdf(
            title="Pawn Loan Ticket",
            details=details,
            verification_id=verification,
            sections=(("Collateral", collateral_rows),),
        )
        return PawnLoanDocumentResult(
            "loan_ticket",
            f"pawn_loan_ticket_{payload['loan_number']}.pdf",
            verification,
            pdf,
        )

    @classmethod
    def render_repayment_receipt(cls, event):
        if event.event_kind != TransactionKind.REPAYMENT.value:
            raise PawnLoanDocumentError("A repayment receipt requires a repayment event.")
        loan = event.loan
        values = event.payload.get("values") or {}
        repayment = event.payload.get("repayment") or {}
        reversed_by = cls._related_or_none(event, "reversed_by_event")
        verification = cls._verification(
            loan,
            f"repayment:{event.pk}:{event.payload_fingerprint}",
        )
        details = cls._identity_rows(loan) + [
            ("Document", "Repayment receipt"),
            ("Repayment source ID", f"PawnLoanAccountingEvent:{event.pk}"),
            ("Document status", f"Reversed by event {reversed_by.pk}" if reversed_by else "Recorded"),
            ("Event fingerprint", event.payload_fingerprint),
            ("Effective date", event.effective_date),
            ("Official loan number", loan.loan_number),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Amount received", cls._money(repayment.get("amount_received"))),
            ("Fees", cls._money(values.get("fees"))),
            ("Overdue interest", cls._money(values.get("overdue_interest"))),
            ("Current interest", cls._money(values.get("current_interest"))),
            ("Total interest", cls._money(values.get("interest"))),
            ("Principal", cls._money(values.get("principal"))),
            ("Accounting delivery", event.outbox.get_status_display()),
            ("DEA voucher / journal", f"{event.outbox.dea_voucher_id or '—'} / {event.outbox.dea_journal_entry_id or '—'}"),
        ]
        pdf = cls._build_pdf(
            title="Pawn Loan Repayment Receipt",
            details=details,
            verification_id=verification,
        )
        return PawnLoanDocumentResult(
            "repayment_receipt",
            f"pawn_repayment_{loan.loan_number}_{event.pk}.pdf",
            verification,
            pdf,
        )

    @classmethod
    def render_release_memo(cls, release):
        loan = release.loan
        event = release.accounting_event
        reversal = cls._related_or_none(release, "reversal")
        verification = cls._verification(
            loan,
            f"release:{release.pk}:{release.release_number}:{event.payload_fingerprint}",
        )
        details = cls._identity_rows(loan) + [
            ("Document", "Release memo / Form H equivalent"),
            ("Release source ID", f"PawnLoanRelease:{release.pk}"),
            ("Document status", f"Reversed by release reversal {reversal.pk}" if reversal else "Completed"),
            ("Release number", release.release_number),
            ("Accounting event ID", f"PawnLoanAccountingEvent:{event.pk}"),
            ("Event fingerprint", event.payload_fingerprint),
            ("Effective date", release.effective_date),
            ("Release type", "Full" if release.is_full_release else "Partial"),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Principal settled", cls._money(release.principal_amount)),
            ("Interest settled", cls._money(release.interest_amount)),
            ("Fees settled", cls._money(release.fee_amount)),
            ("Total settlement", cls._money(release.settlement_amount)),
            ("Accounting delivery", event.outbox.get_status_display()),
            ("DEA voucher / journal", f"{event.outbox.dea_voucher_id or '—'} / {event.outbox.dea_journal_entry_id or '—'}"),
        ]
        item_rows = [["Item ID", "Description", "Value at release", "Returned at"]]
        for release_item in release.items.all():
            snapshot = release_item.valuation_snapshot or {}
            item_rows.append(
                [
                    str(release_item.collateral_item_id),
                    release_item.collateral_item.description,
                    cls._money(snapshot.get("valuation_amount")),
                    str(release_item.returned_at),
                ]
            )
        pdf = cls._build_pdf(
            title="Pawn Loan Release Memo",
            details=details,
            verification_id=verification,
            sections=(("Collateral returned", item_rows),),
        )
        return PawnLoanDocumentResult(
            "release_memo",
            f"pawn_release_{release.release_number}.pdf",
            verification,
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
    def _identity_rows(cls, loan):
        license = loan.license
        return [
            ("Workspace", loan.workspace.name),
            ("Workspace source ID", f"Workspace:{loan.workspace_id}"),
            ("Regulatory license", f"{license.name} ({license.license_number})"),
            ("License source ID", f"LoanLicense:{license.pk}"),
            ("License authority", license.issuing_authority or "—"),
            ("License validity", f"{license.issued_on} to {license.expires_on}"),
        ]

    @staticmethod
    def _verification(loan, source):
        return f"ROKKAD|workspace:{loan.workspace_id}|loan:{loan.pk}|{source}"

    @staticmethod
    def _related_or_none(source, name):
        try:
            return getattr(source, name)
        except (AttributeError, ObjectDoesNotExist):
            return None

    @staticmethod
    def _money(value):
        amount = Decimal(str(value or "0")).quantize(Decimal("0.01"))
        return f"INR {amount}"

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
            [[Paragraph(f"<b>{escape(str(label))}</b>", styles["BodyText"]), Paragraph(escape(str(value)), styles["BodyText"])] for label, value in details],
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
                        [[Paragraph(escape(str(cell)), styles["BodyText"]) for cell in row] for row in rows],
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
