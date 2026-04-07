import io

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle


def generate_form_h(release):
    """Build the Form H receipt PDF for a loan release."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    styles = getSampleStyleSheet()
    centered_style = ParagraphStyle(
        name="Centered",
        parent=styles["Normal"],
        alignment=1,
    )

    data = [
        [
            Paragraph("Form H", centered_style),
            Paragraph("Receipt", centered_style),
            Paragraph("P.B.L No: ", centered_style),
            Paragraph(f"{release.loan.series.license.name}", centered_style),
        ],
        [Paragraph("[See section 10(l)(b)(v) and rule 8]", centered_style), "", "", ""],
        [
            Paragraph(
                f"<b>{release.loan.series.license.shopname}</b><br/>{release.loan.series.license.address}",
                centered_style,
            ),
            "",
            "",
            "",
        ],
        ["ReleaseId", f"{release.id}", "Date:", f"{release.release_date.date()}"],
        ["Received from", f"{release.released_by.name}", "", ""],
        [
            "On Pledge No",
            f"{release.loan.loan_id}",
            "Date",
            f"{release.loan.loan_date.date()}",
        ],
        [
            Paragraph("and received the articles in full satisfaction", centered_style),
            "",
            "",
            "",
        ],
        ["Amount of Loan Rs: ", "", f"{release.loan.loan_amount}", ""],
        ["Interest", "", f"{release.loan.interestdue()}", ""],
        [Paragraph("Total", centered_style), "", f"{release.loan.total()}", ""],
        ["", "", "", ""],
        [
            Paragraph("Signature ", centered_style),
            "",
            Paragraph("Sign of pawnbroker/his agent.", centered_style),
            "",
        ],
    ]

    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("SPAN", (0, 1), (-1, 1)),
                ("SPAN", (0, 2), (-1, 2)),
                ("SPAN", (1, 4), (3, 4)),
                ("SPAN", (0, 6), (-1, 6)),
                ("SPAN", (0, 7), (1, 7)),
                ("SPAN", (0, 8), (1, 8)),
                ("SPAN", (0, 9), (1, 9)),
                ("SPAN", (2, 7), (3, 7)),
                ("SPAN", (2, 8), (3, 8)),
                ("SPAN", (2, 9), (3, 9)),
                ("SPAN", (0, 10), (1, 10)),
                ("SPAN", (2, 10), (3, 10)),
                ("SPAN", (0, 11), (1, 11)),
                ("SPAN", (2, 11), (3, 11)),
            ]
        )
    )

    doc.build([table])
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
