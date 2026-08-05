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
        allocation_manager = cls._related_or_none(event, "repayment_allocation_lines")
        allocation_rows = []
        if allocation_manager is not None:
            allocations = allocation_manager.select_related("collateral_item").order_by(
                "allocation_order"
            )
            allocation_rows = [
                ("Item", "Description", "Rate", "Before", "Principal", "After")
            ] + [
                (
                    line.collateral_item_id,
                    line.collateral_item.description,
                    f"{line.monthly_interest_rate}%",
                    cls._money(line.balance_before),
                    cls._money(line.principal_applied),
                    cls._money(line.balance_after),
                )
                for line in allocations
            ]
        pdf = cls._build_pdf(
            title="Pawn Loan Repayment Receipt",
            details=details,
            verification_id=verification,
            sections=(
                (("Collateral principal allocation", allocation_rows),)
                if allocation_rows
                else ()
            ),
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
        outbox = cls._related_or_none(event, "outbox")
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
            (
                "Accounting delivery",
                outbox.get_status_display() if outbox else "Not required",
            ),
            (
                "DEA voucher / journal",
                (
                    f"{outbox.dea_voucher_id or 'Not available'} / "
                    f"{outbox.dea_journal_entry_id or 'Not available'}"
                    if outbox
                    else "Not applicable"
                ),
            ),
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

    @classmethod
    def render_auction_notice(cls, auction):
        loan = auction.loan
        reversal = cls._related_or_none(auction, "reversal")
        verification = cls._verification(
            loan,
            f"auction-notice:{auction.pk}:{auction.auction_number}",
        )
        details = cls._identity_rows(loan) + [
            ("Document", "Pawn loan auction notice"),
            ("Auction source ID", f"PawnLoanAuction:{auction.pk}"),
            ("Auction number", auction.auction_number),
            ("Document status", f"Recovery reversed by {reversal.pk}" if reversal else auction.get_state_display()),
            ("Official loan number", loan.loan_number),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Notice date", auction.notice_date),
            ("Scheduled auction date", auction.scheduled_date),
            ("Notice delivery job", getattr(auction.notice, "notification_job_id", "Not available")),
        ]
        pdf = cls._build_pdf(
            title="Pawn Loan Auction Notice",
            details=details,
            verification_id=verification,
        )
        return PawnLoanDocumentResult(
            "auction_notice",
            f"pawn_auction_notice_{auction.auction_number}.pdf",
            verification,
            pdf,
        )

    @classmethod
    def render_auction_recovery_memo(cls, auction):
        if not auction.accounting_event_id:
            raise PawnLoanDocumentError(
                "Auction recovery memo is available only after completion."
            )
        loan = auction.loan
        event = auction.accounting_event
        outbox = event.outbox
        reversal = cls._related_or_none(auction, "reversal")
        verification = cls._verification(
            loan,
            f"auction-recovery:{auction.pk}:{event.payload_fingerprint}",
        )
        details = cls._identity_rows(loan) + [
            ("Document", "Pawn loan auction recovery memo"),
            ("Auction source ID", f"PawnLoanAuction:{auction.pk}"),
            ("Auction number", auction.auction_number),
            ("Document status", f"Reversed by auction reversal {reversal.pk}" if reversal else "Completed"),
            ("Effective date", event.effective_date),
            ("Buyer", auction.buyer_name),
            ("Buyer reference", auction.buyer_reference or "Not recorded"),
            ("Principal recovered", cls._money(auction.principal_amount)),
            ("Interest recovered", cls._money(auction.interest_amount)),
            ("Fees recovered", cls._money(auction.fee_amount)),
            ("Total recovery", cls._money(auction.recovery_amount)),
            ("Accounting delivery", outbox.get_status_display()),
            ("DEA voucher / journal", f"{outbox.dea_voucher_id or 'Not available'} / {outbox.dea_journal_entry_id or 'Not available'}"),
        ]
        rows = [["Item ID", "Description", "Metal", "Net weight", "Purity"]]
        for auction_item in auction.items.select_related("collateral_item"):
            snapshot = auction_item.snapshot or {}
            rows.append(
                [
                    str(auction_item.collateral_item_id),
                    snapshot.get("description", auction_item.collateral_item.description),
                    snapshot.get("metal", ""),
                    snapshot.get("net_weight", ""),
                    snapshot.get("purity_percentage", ""),
                ]
            )
        pdf = cls._build_pdf(
            title="Pawn Loan Auction Recovery Memo",
            details=details,
            verification_id=verification,
            sections=(("Collateral disposed", rows),),
        )
        return PawnLoanDocumentResult(
            "auction_recovery",
            f"pawn_auction_recovery_{auction.auction_number}.pdf",
            verification,
            pdf,
        )

    @classmethod
    def render_renewal_memo(cls, renewal):
        source = renewal.source_loan
        successor = renewal.successor_loan
        reversal = cls._related_or_none(renewal, "reversal")
        verification = cls._verification(
            source,
            f"renewal:{renewal.pk}:{renewal.settlement_event.payload_fingerprint}",
        )
        details = cls._identity_rows(source) + [
            ("Document", "Pawn loan renewal memo"),
            ("Renewal source ID", f"PawnLoanRenewal:{renewal.pk}"),
            ("Renewal number", renewal.renewal_number),
            ("Document status", f"Reversed by {reversal.pk}" if reversal else "Completed"),
            ("Renewal date", renewal.renewal_date),
            ("Mode", renewal.get_mode_display()),
            ("Source loan", source.loan_number),
            ("Successor loan", successor.loan_number),
            ("Borrower", f"{source.borrower.display_name} ({source.borrower.party_code})"),
            ("Source principal settled", cls._money(renewal.source_principal_amount)),
            ("Interest settled", cls._money(renewal.interest_settled)),
            ("Fees settled", cls._money(renewal.fees_settled)),
            ("Principal paid", cls._money(renewal.principal_paid)),
            ("Top-up disbursed", cls._money(renewal.top_up_amount)),
            ("Successor principal", cls._money(renewal.successor_principal_amount)),
            ("Settlement accounting", renewal.settlement_event.outbox.get_status_display()),
            ("Successor opening", renewal.opening_event.outbox.get_status_display()),
        ]
        rows = [["Source item", "Successor item", "Description", "Value"]]
        successor_by_source = {
            item.renewed_from_id: item
            for item in successor.collateral_items.select_related("renewed_from")
        }
        values = {
            item["source_item_id"]: item
            for item in (renewal.valuation_snapshot.get("items") or [])
        }
        for source_item in source.collateral_items.order_by("pk"):
            successor_item = successor_by_source.get(source_item.pk)
            value = values.get(source_item.pk) or {}
            rows.append(
                [
                    str(source_item.pk),
                    str(successor_item.pk) if successor_item else "Not linked",
                    source_item.description,
                    cls._money(value.get("valuation_amount")),
                ]
            )
        pdf = cls._build_pdf(
            title="Pawn Loan Renewal Memo",
            details=details,
            verification_id=verification,
            sections=(("Collateral lineage", rows),),
        )
        return PawnLoanDocumentResult(
            "renewal",
            f"pawn_renewal_{renewal.renewal_number}.pdf",
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
