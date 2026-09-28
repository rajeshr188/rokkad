"""Printable invoice from saved financial evidence, never current seller settings."""
from io import BytesIO
from xml.sax.saxutils import escape


def render_invoice_pdf(invoice):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from .provider_configuration import invoice_mode

    output = BytesIO()
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    body.fontSize, body.leading = 10, 15
    story = []

    def paragraph(value, style=body):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), style)

    story.extend([paragraph("Rokkad", styles["Title"]), paragraph("INVOICE", styles["Heading1"])])
    if invoice_mode(invoice) == "test":
        story.append(paragraph("TEST MODE - simulated payment. No real money was charged."))
    seller = invoice.billing_seller
    if seller:
        story.extend([paragraph("Seller", styles["Heading2"]), paragraph(seller["name"]),
                      paragraph(seller["address"])])
    story.extend([Spacer(1, 12), paragraph(f"Invoice: {invoice.invoice_number}"),
                  paragraph(f"Date: {invoice.invoice_date}"),
                  paragraph(f"Status: {invoice.get_status_display()}"),
                  paragraph("Bill to", styles["Heading2"]), paragraph(invoice.billing_contact_name),
                  paragraph(invoice.billing_contact_email), Spacer(1, 14),
                  paragraph(invoice.billed_plan_name, styles["Heading2"])])
    if invoice.checkout_snapshot.get("kind") == "recurring":
        cycle = invoice.recurring_cycle
        story.append(paragraph(f"Billing period: {cycle.period_start.isoformat()} to {cycle.period_end.isoformat()}"))
    else:
        cycle = invoice.checkout_snapshot.get("billing_cycle")
        if cycle in {"monthly", "yearly"}:
            story.append(paragraph("One-month subscription term" if cycle == "monthly" else "One-year subscription term"))
    rows = [["Subtotal", f"INR {invoice.subtotal:.2f}"]]
    if not seller:
        rows.append([f"GST ({invoice.gst_rate}%)", f"INR {invoice.gst_amount:.2f}"])
    rows.append(["Total paid" if invoice.status == "paid" else "Total amount due", f"INR {invoice.total_amount:.2f}"])
    table = Table(rows, colWidths=[330, 150], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.7, colors.HexColor("#103f3a")),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    story.extend([Spacer(1, 12), table])
    if seller:
        story.extend([Spacer(1, 12), paragraph(invoice.billing_tax_note)])
    SimpleDocTemplate(output, pagesize=A4, leftMargin=48, rightMargin=48,
                      topMargin=42, bottomMargin=42, title=f"Invoice {invoice.invoice_number}").build(story)
    return output.getvalue()
