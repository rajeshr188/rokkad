from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def create_pdf():
    doc = SimpleDocTemplate("my_document.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    flowables = []
    top_row = [["Sec 7 Rules 8", "PAWN TICKET", "P.B.L No:813/94"]]
    top_table = Table(top_row)
    top_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
            ]
        )
    )
    flowables.append(top_table)
    flowables.append(Spacer(1, 12))
    # Company info
    company_info = """
    <font size=14><b>Company Name</b></font><br/>
    Address Line 1<br/>
    Address Line 2<br/>
    City, State, Zip
    """
    flowables.append(Paragraph(company_info, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    # License info
    license_info = "License info: XXX-XXX-XXX"
    flowables.append(Paragraph(license_info, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    # Customer info
    customer_info = "Customer Name: John Doe"
    flowables.append(Paragraph(customer_info, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    # Loan info
    loan_info = "Loan Amount: $1000"
    flowables.append(Paragraph(loan_info, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    # Loan items details
    items = [["Item", "Quantity", "Price"], ["Item 1", 1, "$10"], ["Item 2", 2, "$20"]]
    table = Table(items)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 14),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )
    flowables.append(table)
    flowables.append(Spacer(1, 12))

    # Terms and conditions
    terms = "Terms and conditions: ..."
    flowables.append(Paragraph(terms, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    # Signature row
    signatures = [
        ["", "Signature (Company)", "", "Signature (Customer)"],
        ["", "_________________", "", "_________________"],
    ]
    sig_table = Table(signatures, colWidths=[100, 200, 100, 200])
    flowables.append(sig_table)

    # Build the PDF
    doc.build(flowables)


create_pdf()
