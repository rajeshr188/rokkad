import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _as_display_amount(value):
    if value is None:
        return "0.00"
    amount = getattr(value, "amount", value)
    currency = getattr(value, "currency", None)
    currency_code = getattr(currency, "code", "INR") if currency else "INR"
    return f"{amount} {currency_code}"


def generate_payment_receipt_pdf(payment):
    """Build a simple payment receipt PDF for a posted or draft payment voucher."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    borrower = getattr(getattr(payment, "source_document", None), "borrower", None)
    borrower_name = getattr(borrower, "name", None) or str(borrower or "Customer")

    details = [
        ["Payment ID", getattr(payment, "payment_id", "—")],
        ["Payment Date", str(getattr(payment, "payment_date", "—"))],
        ["Payment Method", getattr(payment, "get_payment_method_display", lambda: getattr(payment, "payment_method", "—"))()],
        ["Reference Number", getattr(payment, "reference_number", "") or "—"],
        ["Principal", _as_display_amount(getattr(payment, "principal_amount", None))],
        ["Interest", _as_display_amount(getattr(payment, "interest_amount", None))],
        ["Total", _as_display_amount(getattr(payment, "total_amount", None))],
        ["Status", "Posted" if getattr(payment, "posted", False) else "Draft"],
    ]

    content = [
        Paragraph("Payment Receipt", styles["Title"]),
        Spacer(1, 8),
        Paragraph(f"Received from: <b>{borrower_name}</b>", styles["Normal"]),
        Spacer(1, 12),
    ]

    table = Table(details, colWidths=[170, 320])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ]
        )
    )
    content.append(table)

    doc.build(content)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
