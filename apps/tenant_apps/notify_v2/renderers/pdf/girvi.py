from __future__ import annotations

import io
from collections import OrderedDict
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_LAYOUT_PROFILES = {
    "loan.first_reminder_due": {
        "title": "Loan Reminder Notice",
        "banner_label": "Friendly Reminder",
        "accent_hex": "#0D6EFD",
        "body_copy": "This is a reminder regarding the following Girvi loan account(s). Please visit the branch for renewal or settlement.",
        "highlight_title": "Suggested Action",
        "highlight_body": "Please renew or settle the account at the branch to keep the loan in good standing.",
        "footer_note": "Please carry the loan ticket while visiting the branch for payment, renewal, or clarification.",
        "signature_label": "Branch In-Charge",
    },
    "loan.second_reminder_due": {
        "title": "Second Reminder Notice",
        "banner_label": "Urgent Follow-up",
        "accent_hex": "#FD7E14",
        "body_copy": "This is a second reminder. Immediate follow-up is requested for the following loan account(s).",
        "highlight_title": "Urgency Note",
        "highlight_body": "Kindly contact the branch without delay to avoid the notice escalating to final action.",
        "footer_note": "If you have already paid or renewed, please share the receipt with the branch for update.",
        "signature_label": "Loans Desk",
    },
    "loan.final_notice_due": {
        "title": "Final Notice",
        "banner_label": "Final Action Required",
        "accent_hex": "#DC3545",
        "body_copy": "This is the final notice before further recovery action. Please regularise the following loan account(s) immediately.",
        "highlight_title": "Immediate Attention Required",
        "highlight_body": "If the account is not settled or renewed promptly, branch recovery steps may continue as per policy.",
        "footer_note": "Treat this notice as time-sensitive and contact the branch manager immediately for resolution.",
        "signature_label": "Branch Manager",
    },
    "loan.auction_notice_due": {
        "title": "Auction Notice",
        "banner_label": "Auction Workflow",
        "accent_hex": "#6F42C1",
        "body_copy": "The following loan account(s) are in the auction recovery workflow. Contact the branch immediately to avoid further action.",
        "highlight_title": "Auction Process Alert",
        "highlight_body": "The pledged items may move further in the auction workflow if the dues are not addressed within the branch timeline.",
        "footer_note": "For final settlement or objection handling, please contact the branch before the auction schedule is confirmed.",
        "signature_label": "Recovery Officer",
    },
}


def _get_layout_profile(layout_key: str):
    default_profile = {
        "title": "Girvi Notice Bundle",
        "banner_label": "Loan Notice",
        "accent_hex": "#198754",
        "body_copy": "Please review the following loan account(s).",
        "highlight_title": "Next Step",
        "highlight_body": "Please contact the branch for guidance on the listed loan account(s).",
        "footer_note": "Please keep this notice for your records.",
        "signature_label": "Authorized Signatory",
    }
    profile = default_profile.copy()
    profile.update(_LAYOUT_PROFILES.get(layout_key, {}))
    return profile


def _borrower_name(borrower) -> str:
    if borrower is None:
        return "Unknown Borrower"
    for attr in ("name", "fullname", "full_name"):
        value = getattr(borrower, attr, None)
        if value:
            return str(value)
    first = getattr(borrower, "firstname", "")
    last = getattr(borrower, "lastname", "")
    full = f"{first} {last}".strip()
    return full or str(borrower)


def _loan_amount(loan) -> Decimal:
    amount = getattr(loan, "get_loan_amount", None)
    if callable(amount):
        amount = amount()
    elif amount is None:
        amount = getattr(loan, "loanamount", None)
    if amount in (None, ""):
        return Decimal("0")
    return Decimal(str(amount))


def _loan_due_display(loan) -> str:
    due_date = getattr(loan, "maturity_date", None) or getattr(loan, "loan_date", None)
    if due_date is None:
        return "—"
    if hasattr(due_date, "strftime"):
        return due_date.strftime("%d %b %Y")
    return str(due_date)


def _group_loans(loans):
    grouped = OrderedDict()
    for loan in loans:
        borrower = getattr(loan, "borrower", None)
        key = getattr(borrower, "pk", None) or id(borrower)
        bucket = grouped.setdefault(key, {"borrower": borrower, "loans": []})
        bucket["loans"].append(loan)
    return list(grouped.values())


def render_girvi_notice_bundle(*, loans, template=None, event_key: str = ""):
    """Render a merged printable PDF bundle for a Girvi reminder batch without relying on the legacy loan-pdf helper."""
    loan_list = list(loans or [])
    if not loan_list:
        return None

    layout_key = getattr(template, "layout_key", "") or event_key or "loan.first_reminder_due"
    profile = _get_layout_profile(layout_key)
    title = getattr(template, "name", "") or profile["title"]
    body_copy = profile["body_copy"]
    custom_body = (getattr(template, "body_template", "") or "").strip()
    renderer_type = getattr(template, "renderer_type", "")
    if custom_body and renderer_type != "PDF":
        body_copy = custom_body

    accent_color = colors.HexColor(profile["accent_hex"])
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    heading = styles["Heading1"]
    heading.alignment = 1
    subheading = styles["Heading4"]
    body = styles["BodyText"]
    small = ParagraphStyle("NotifyV2Small", parent=styles["BodyText"], fontSize=9, leading=11)
    callout = ParagraphStyle(
        "NotifyV2Callout",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#212529"),
    )

    story = []
    grouped_loans = _group_loans(loan_list)
    generated_label = getattr(getattr(loan_list[0], "loan_date", None), "strftime", lambda _fmt: None)("%d %b %Y")

    for index, payload in enumerate(grouped_loans):
        borrower = payload["borrower"]
        borrower_loans = payload["loans"]
        total_amount = sum((_loan_amount(loan) for loan in borrower_loans), Decimal("0"))

        banner = Table([[profile["banner_label"]]], colWidths=[145 * mm])
        banner.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), accent_color),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(banner)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(title, heading))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(f"<b>To:</b> {_borrower_name(borrower)}", subheading))
        story.append(Paragraph(f"<b>Generated:</b> {generated_label or 'Today'}", small))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(body_copy, body))
        story.append(Spacer(1, 4 * mm))

        notice_box = Table(
            [[Paragraph(f"<b>{profile['highlight_title']}</b><br/>{profile['highlight_body']}", callout)]],
            colWidths=[145 * mm],
        )
        notice_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
                    ("BOX", (0, 0), (-1, -1), 1, accent_color),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(notice_box)
        story.append(Spacer(1, 4 * mm))

        table_data = [["Loan ID", "Due / Loan Date", "Amount (₹)"]]
        for loan in borrower_loans:
            table_data.append(
                [
                    getattr(loan, "loan_id", str(getattr(loan, "pk", "—"))),
                    _loan_due_display(loan),
                    f"{_loan_amount(loan):,.2f}",
                ]
            )

        table = Table(table_data, colWidths=[55 * mm, 55 * mm, 35 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), accent_color),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ADB5BD")),
                    ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"<b>Total Due Amount:</b> ₹{total_amount:,.2f}", body))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(profile["footer_note"], small))
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(profile["signature_label"], small))

        if index < len(grouped_loans) - 1:
            story.append(PageBreak())

    doc.build(story)
    return buffer.getvalue()
