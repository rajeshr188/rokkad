"""Legacy compatibility module for PDF helpers.

Girvi-specific ticket rendering now lives in `apps.tenant_apps.girvi.documents`.
Keep new domain-specific PDF logic close to the owning app; this file remains only
for backward-compatible imports and shared legacy helpers.
"""

import io
import logging
import os
import time
from io import BytesIO
from itertools import groupby

import fitz
import qrcode
import reportlab.rl_config
from requests import request

logger = logging.getLogger(__name__)
from django.http import HttpResponse
from num2words import num2words
from PIL import Image as PILImage
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4, A5, landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    Frame,
    KeepInFrame,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.tenant_apps.girvi.models import LoanTemplate, TemplateFrame

reportlab.rl_config.warnOnMissingFontGlyphs = 1


class CentreLine(Flowable):
    """
    Draws a dotted line in the centre of the page vertically to tear along
    """

    def __init__(self):
        Flowable.__init__(self)

    def draw(self):
        # Set the line width and style
        self.canv.setLineWidth(0.5)
        self.canv.setDash(1, 3)  # 1pt on, 3pt off

        # Calculate the center of the page
        center_x = landscape(A4)[0] / 2
        center_y = landscape(A4)[1] / 2

        # Draw the dotted line from top to bottom at the center of the page
        self.canv.line(center_x, landscape(A4)[1], center_x, 0)


def get_frame_definitions(is_original=True):
    """Define frames and their positions for original/duplicate"""
    if is_original:
        return {
            "loan_header": Frame(12 * cm, 18.5 * cm, 4 * cm, 1 * cm, showBoundary=1),
            "customer_info": Frame(5 * cm, 13 * cm, 8 * cm, 3 * cm, showBoundary=1),
            "weights": Frame(10 * cm, 8 * cm, 4 * cm, 4 * cm, showBoundary=1),
            "items_table": Frame(2.5 * cm, 10.5 * cm, 8 * cm, 4 * cm, showBoundary=1),
            "amount": Frame(8 * cm, 6.5 * cm, 4 * cm, 1 * cm, showBoundary=1),
            "amount_words": Frame(2 * cm, 6 * cm, 8 * cm, 1 * cm, showBoundary=1),
        }
    else:
        return {
            "loan_header": Frame(3 * cm, 17.5 * cm, 4 * cm, 1 * cm, showBoundary=1),
            "customer_info": Frame(5 * cm, 14 * cm, 8 * cm, 3 * cm, showBoundary=1),
            "items": Frame(3 * cm, 10 * cm, 8 * cm, 1 * cm, showBoundary=1),
            "weights": Frame(3 * cm, 7 * cm, 10 * cm, 1 * cm, showBoundary=1),
            "summary": Frame(1 * cm, 2 * cm, 12 * cm, 2 * cm, showBoundary=1),
        }


def get_frame_content(loan, styles):
    """Map loan data to frame content"""
    # Use 'borrower' for GivenLoan, fallback to 'customer' for legacy
    party = getattr(loan, "borrower", None) or getattr(loan, "customer", None)
    customer_text = f"""
    {party.name} {party.get_relatedas_display()} {party.relatedto}
    {party.address.first()}
    Ph: {party.contactno.first()}
    """.strip()

    customer_style = ParagraphStyle(
        "CustomerInfo", parent=styles["Normal"], leading=14, spaceBefore=0, spaceAfter=0
    )

    weight = loan.formatted_weight(joiner=",")
    pure = loan.formatted_pure(joiner=",")
    amt_fig = f"{num2words(loan.loan_amount, lang='en_IN')} rupees only"

    return {
        "loan_header": [
            Paragraph(f"Loan ID: {loan.loan_id}", styles["Normal"]),
            Paragraph(f"Date: {loan.loan_date.strftime('%d-%m-%Y')}", styles["Normal"]),
        ],
        "customer_info": [Paragraph(customer_text, customer_style)],
        "weights": [
            Paragraph(f"Weight: {weight}gms", styles["Normal"]),
            Paragraph(f"Pure: {pure}gms", styles["Normal"]),
            Paragraph(f"Value: {loan.get_current_value()}", styles["Normal"]),
        ],
        "items_table": [
            Table(
                [[item.itemdesc] for item in loan.loanitems.all()],
                style=TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.black)]),
            )
        ],
        "amount": [Paragraph(str(loan.loan_amount), styles["Normal"])],
        "amount_words": [Paragraph(amt_fig, styles["Normal"])],
        "summary": [
            Paragraph(
                f"{loan.loan_id} {loan.loan_date.strftime('%d/%m/%y')} "
                f"{loan.loan_amount} {weight} {getattr(loan, 'borrower', getattr(loan, 'customer', None)).name}",
                styles["Normal"],
            ),
        ],
    }


def get_custom_jsk(loan):
    """Generate PDF with original and duplicate pages"""
    buffer = io.BytesIO()
    c = Canvas(buffer, pagesize=(14.6 * cm, 21 * cm))
    styles = getSampleStyleSheet()

    # Original page
    frames = get_frame_definitions(is_original=True)
    content = get_frame_content(loan, styles)

    for frame_name, frame in frames.items():
        if frame_name in content:
            frame_content = KeepInFrame(
                frame._width, frame._height, content[frame_name], mode="shrink"
            )
            frame.addFromList([frame_content], c)

    c.showPage()

    # Duplicate page
    frames = get_frame_definitions(is_original=False)

    for frame_name, frame in frames.items():
        if frame_name in content:
            frame_content = KeepInFrame(
                frame._width, frame._height, content[frame_name], mode="shrink"
            )
            frame.addFromList([frame_content], c)

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# def create_loan_frames(c, is_original=True):
#     """Create frames for different sections of the loan document"""
#     styles = getSampleStyleSheet()

#     # Define frame positions for original and duplicate
#     positions = {
#         'original': {
#             'loan_id': (12*cm, 18.5*cm, 4*cm, 1*cm),
#             'date': (11.5*cm, 17.5*cm, 4*cm, 1*cm),
#             'customer': (5*cm, 16*cm, 8*cm, 2*cm),
#             'photo': (2*cm, 16*cm, 2.5*cm, 2.5*cm),
#             'address': (5*cm, 14*cm, 8*cm, 1*cm),
#             'phone': (5*cm, 13*cm, 8*cm, 1*cm),
#             'items': (2.5*cm, 10.5*cm, 10*cm, 3*cm),
#             'amount': (8*cm, 6.5*cm, 4*cm, 1*cm)
#         },
#         'duplicate': {
#             'loan_id': (3*cm, 17.5*cm, 4*cm, 1*cm),
#             'date': (11*cm, 17.5*cm, 4*cm, 1*cm),
#             'customer': (5*cm, 17*cm, 8*cm, 1*cm),
#             'address': (5*cm, 15*cm, 8*cm, 1*cm),
#             'phone': (5*cm, 14*cm, 8*cm, 1*cm),
#             'items': (3*cm, 10*cm, 8*cm, 3*cm),
#             'amount': (5*cm, 13.5*cm, 4*cm, 1*cm)
#         }
#     }

#     pos = positions['original'] if is_original else positions['duplicate']

#     frames = {
#         'loan_id': Frame(*pos['loan_id'], showBoundary=0),
#         'date': Frame(*pos['date'], showBoundary=0),
#         'customer': Frame(*pos['customer'], showBoundary=0),
#         'address': Frame(*pos['address'], showBoundary=0),
#         'phone': Frame(*pos['phone'], showBoundary=0),
#         'items': Frame(*pos['items'], showBoundary=0),
#         'amount': Frame(*pos['amount'], showBoundary=0)
#     }

#     return frames

# def render_loan_content(c, loan, frames, styles):
#     """Render content in the specified frames"""
#     # Loan ID
#     frames['loan_id'].addFromList([Paragraph(loan.loan_id, styles['Normal'])], c)

#     # Date
#     frames['date'].addFromList([
#         Paragraph(loan.loan_date.strftime('%d-%m-%Y'), styles['Normal'])
#     ], c)

#     # Customer details
#     customer_text = f"{loan.customer.name} {loan.customer.get_relatedas_display()} {loan.customer.relatedto}"
#     frames['customer'].addFromList([Paragraph(customer_text, styles['Normal'])], c)

#     # Address
#     frames['address'].addFromList([
#         Paragraph(str(loan.customer.address.first()), styles['Normal'])
#     ], c)

#     # Phone
#     frames['phone'].addFromList([
#         Paragraph(str(loan.customer.contactno.first()), styles['Normal'])
#     ], c)

#     # Items
#     items_text = loan.item_desc
#     frames['items'].addFromList([Paragraph(items_text, styles['Normal'])], c)

#     # Amount
#     frames['amount'].addFromList([
#         Paragraph(str(loan.loan_amount), styles['Normal'])
#     ], c)

# def get_custom_jsk(loan):
#     # Setup canvas
#     page_width = 14.6 * cm
#     page_height = 21 * cm
#     buffer = io.BytesIO()
#     c = Canvas(buffer, pagesize=(page_width, page_height))
#     styles = getSampleStyleSheet()

#     # Original copy
#     frames = create_loan_frames(c, is_original=True)
#     render_loan_content(c, loan, frames, styles)
#     c.showPage()

#     # Duplicate copy
#     frames = create_loan_frames(c, is_original=False)
#     render_loan_content(c, loan, frames, styles)

#     c.save()
#     pdf = buffer.getvalue()
#     buffer.close()
#     return pdf


# below this is solved-------------------------------------------

# from reportlab.platypus import (
#     Paragraph,
#     Table,
#     TableStyle,
#     Frame,
#     KeepInFrame,
#     PageTemplate,
#     BaseDocTemplate
# )
# from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
# from reportlab.lib import colors
# from reportlab.lib.units import cm
# from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# class LoanDocument(BaseDocTemplate):
#     def __init__(self, buffer, loan):
#         super().__init__(buffer, pagesize=(14.6*cm, 21*cm))
#         self.loan = loan
#         self.styles = self._create_styles()
#         self.addPageTemplates(self._create_templates())

#     def _create_styles(self):
#         styles = getSampleStyleSheet()

#         # Custom styles
#         styles.add(ParagraphStyle(
#             name='CustomerName',
#             parent=styles['Normal'],
#             fontSize=12,
#             leading=14,
#             spaceAfter=6
#         ))

#         styles.add(ParagraphStyle(
#             name='Address',
#             parent=styles['Normal'],
#             fontSize=10,
#             leading=12
#         ))

#         styles.add(ParagraphStyle(
#             name='ItemsTable',
#             parent=styles['Normal'],
#             fontSize=10,
#             leading=12
#         ))

#         return styles

#     def _create_templates(self):
#         # Define frames for different content areas
#         frames = {
#             'header': Frame(
#                 12*cm, 18.5*cm, 4*cm, 1*cm,  # x, y, width, height
#                 leftPadding=0,
#                 bottomPadding=0,
#                 rightPadding=0,
#                 topPadding=0
#             ),
#             'customer': Frame(
#                 5*cm, 15*cm, 8*cm, 3*cm,
#                 showBoundary=0
#             ),
#             'items': Frame(
#                 2.5*cm, 10.5*cm, 10*cm, 4*cm,
#                 showBoundary=0
#             )
#         }

#         template = PageTemplate(
#             'normal',
#             frames=[frames[k] for k in ['header', 'customer', 'items']]
#         )
#         return [template]

# def generate_loan_document(loan):
#     buffer = io.BytesIO()
#     doc = LoanDocument(buffer, loan)

#     # Prepare content
#     story = []

#     # Header content (Loan ID, Date)
#     header = [
#         Paragraph(f"Loan ID: {loan.loan_id}", doc.styles['Normal']),
#         Paragraph(f"Date: {loan.loan_date.strftime('%d-%m-%Y')}", doc.styles['Normal'])
#     ]

#     # Customer details with controlled width/height
#     customer_content = [
#         Paragraph(loan.customer.name, doc.styles['CustomerName']),
#         Paragraph(str(loan.customer.address.first()), doc.styles['Address']),
#         Paragraph(f"Ph: {loan.customer.contactno.first()}", doc.styles['Normal'])
#     ]

#     # Items as table with auto-wrapping
#     items_data = []
#     for item in loan.loanitems.all():
#         items_data.append([
#             str(item.id),
#             Paragraph(item.itemdesc, doc.styles['ItemsTable']),
#             f"{item.weight}gms"
#         ])

#     items_table = Table(
#         items_data,
#         colWidths=[1*cm, 7*cm, 2*cm],
#         style=TableStyle([
#             ('GRID', (0,0), (-1,-1), 0.25, colors.black),
#             ('VALIGN', (0,0), (-1,-1), 'TOP'),
#             ('ALIGN', (0,0), (0,-1), 'CENTER'),
#             ('ALIGN', (-1,0), (-1,-1), 'RIGHT'),
#         ])
#     )

#     # Keep content within frames
#     story.extend([
#         KeepInFrame(
#             4*cm, 1*cm,  # maxWidth, maxHeight
#             header,
#             mode='shrink'
#         ),
#         KeepInFrame(
#             8*cm, 3*cm,
#             customer_content,
#             mode='shrink'
#         ),
#         KeepInFrame(
#             10*cm, 4*cm,
#             [items_table],
#             mode='shrink'
#         ),
#         Paragraph(
#             f"Amount: Rs. {loan.loan_amount}",
#             doc.styles['Normal']
#         )
#     ])

#     # Build document
#     doc.build(story)
#     return buffer.getvalue()


# TODO
# Consider adding a visual template designer UI.
# Let's create a visual template designer UI using Django and JavaScript. Here's the plan:

# Create template designer view
# Add drag-and-drop interface
# Build coordinate capture system
# Implement template preview
# Key features:

# Drag-and-drop field placement
# Visual field resizing
# PDF template preview
# Coordinate system conversion
# Field position persistence
# Requirements:

# Usage:

# Open template designer
# Drag fields onto template
# Resize and position fields
# Save template configuration
# Preview generated PDFs
# Consider adding:

# Field property editor
# Grid snapping
# Undo/redo
# Template versioning


def merge_pdfs(base_template_bytes, content_pdf_bytes):
    """
    Merge content PDF with base template using PyMuPDF
    Args:
        base_template_bytes: Bytes of base template PDF
        content_pdf_bytes: Bytes of content PDF with frames
    Returns:
        Merged PDF as bytes
    """

    # Create PDF documents from bytes
    base_doc = fitz.open(stream=base_template_bytes, filetype="pdf")
    content_doc = fitz.open(stream=content_pdf_bytes, filetype="pdf")

    # Get first pages
    base_page = base_doc[0]

    # Overlay content page onto base page
    base_page.show_pdf_page(
        base_page.rect,  # Target rectangle (full page)
        content_doc,  # Source document
        0,  # Source page number
        overlay=True,  # Overlay mode
    )

    # Write to bytes
    output_buffer = base_doc.write()

    # Clean up
    base_doc.close()
    content_doc.close()

    return output_buffer


def merge_pdfs_double_sided(front_template, content, back_template):
    """
    Merge PDFs for double-sided printing with front and back pages
    Args:
        front_template (bytes): Front template PDF content
        content (bytes): Content to merge with front template
        back_template (bytes): Back template PDF content
    Returns:
        bytes: Merged double-sided PDF content
    """
    try:
        # Create output document
        output_doc = fitz.open()

        # Handle front page (template + content)
        front_doc = fitz.open("pdf", front_template)
        content_doc = fitz.open("pdf", content)

        # Merge front template with content
        front_page = front_doc[0]
        content_page = content_doc[0]
        front_page.show_pdf_page(front_page.rect, content_doc, 0, overlay=True)

        # Add merged front page to output
        output_doc.insert_pdf(front_doc, from_page=0, to_page=0)

        # Add back template as second page
        back_doc = fitz.open("pdf", back_template)
        output_doc.insert_pdf(back_doc)

        # Save to buffer
        output_buffer = io.BytesIO()
        output_doc.save(output_buffer)
        merged_content = output_buffer.getvalue()

        # Cleanup
        front_doc.close()
        content_doc.close()
        back_doc.close()
        output_doc.close()
        output_buffer.close()

        return merged_content

    except Exception as e:
        logger.exception("Error creating double-sided PDF: %s", str(e))
        return None


def merge_multiple_pdfs(pdf_contents):
    """
    Merge multiple PDF contents into a single PDF using PyMuPDF
    Args:
        pdf_contents (list): List of PDF file contents in bytes
    Returns:
        bytes: Merged PDF content
    """
    try:
        # Create new output document
        output_doc = fitz.open()

        # Process each PDF content
        for content in pdf_contents:
            # Open PDF from bytes
            doc = fitz.open("pdf", content)

            # Copy all pages to output
            output_doc.insert_pdf(doc)

            # Close temporary document
            doc.close()

        # Save merged content to buffer
        output_buffer = io.BytesIO()
        output_doc.save(output_buffer)
        merged_content = output_buffer.getvalue()

        # Cleanup
        output_doc.close()
        output_buffer.close()

        return merged_content

    except Exception as e:
        logger.exception("Error merging multiple PDFs: %s", str(e))
        return None


def merge_pdfs_side_by_side(left_pdf, right_pdf):
    """
    Merge two A5 PDFs side by side into single A4 landscape
    """
    try:
        # Create output doc with A4 landscape
        output_doc = fitz.open()

        # A4 landscape dimensions
        width = A4[1]  # 842pt
        height = A4[0]  # 595pt

        output_page = output_doc.new_page(width=width, height=height)

        # Open source PDFs
        left_doc = fitz.open("pdf", left_pdf)
        right_doc = fitz.open("pdf", right_pdf)

        # Calculate target rects for A4 landscape
        # Each half should be A5 portrait
        left_rect = fitz.Rect(0, 0, width / 2, height)  # Left A5
        right_rect = fitz.Rect(width / 2, 0, width, height)  # Right A5

        # Insert pages side by side, scaling to fit
        output_page.show_pdf_page(left_rect, left_doc, 0, rotate=0)
        output_page.show_pdf_page(right_rect, right_doc, 0, rotate=0)

        # Save to buffer
        output_buffer = io.BytesIO()
        output_doc.save(output_buffer)
        merged_content = output_buffer.getvalue()

        # Cleanup
        left_doc.close()
        right_doc.close()
        output_doc.close()
        output_buffer.close()

        return merged_content

    except Exception as e:
        logger.exception("Error merging PDFs side by side: %s", str(e))
        return None


def _render_regular_image(c, frame, data, x_offset, frame_y):
    """Handle rendering of regular images"""
    img = PILImage.open(data)
    img_w, img_h = img.size
    aspect = img_w / float(img_h)

    frame_w = float(frame.width) * cm
    frame_h = float(frame.height) * cm

    # Calculate image dimensions
    if frame_w / float(frame_h) > aspect:
        w = frame_h * aspect
        h = frame_h
    else:
        w = frame_w
        h = frame_w / aspect

    # Adjust x,y position with offsets
    x = x_offset + float(frame.x_pos) * cm + (frame_w - w) / 2
    y = frame_y + (frame_h - h) / 2

    print(f"Drawing image at: x={x}, y={y}, w={w}, h={h}")
    c.drawImage(data, x, y, width=w, height=h, preserveAspectRatio=True)


def _render_qr_code(c, frame, img):
    """Handle rendering of QR codes"""
    qr_buffer = BytesIO()
    img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    # Calculate dimensions - use 90% of frame size
    qr_w = frame._width * 0.9
    qr_h = frame._height * 0.9

    # Center in frame
    qr_x = frame._x + (frame._width - qr_w) / 2
    qr_y = frame._y + (frame._height - qr_h) / 2

    # Draw using ImageReader
    c.drawImage(
        ImageReader(qr_buffer),
        qr_x,
        qr_y,
        width=qr_w,
        height=qr_h,
        preserveAspectRatio=True,
    )

    qr_buffer.close()


def get_custom_jcl(loan, template_id=None):
    """Generate PDF using user-defined template and print options"""
    try:
        template = (
            LoanTemplate.objects.get(id=template_id, is_active=True)
            if template_id
            else None
        )
        if not template:
            return None

        # Resolve borrower/customer reference for backward compatibility
        # GivenLoan uses 'borrower', legacy Loan might use 'customer'
        party = getattr(loan, "borrower", None) or getattr(loan, "customer", None)
        if not party:
            logger.error("Loan object has neither 'borrower' nor 'customer' attribute")
            return None

        def has_template(template_file):
            """Check if template file exists and is not None"""
            return bool(template_file and template_file.name)

        def render_frame(frame, x_offset, y_offset, canvas_obj):
            """
            Render individual frame with content
            Args:
                frame: TemplateFrame object
                x_offset: X position offset
                y_offset: Y position offset
                canvas_obj: ReportLab canvas object to draw on
            """
            # Data mapping for frame content
            data_mapping = {
                "license_no": lambda: loan.series.license.name,
                "license_name": lambda: loan.series.license.shopname,
                "license_address": lambda: loan.series.license.address,
                "license_propreitor": lambda: f"Prop:{loan.series.license.propreitor}",
                "customer_pic": lambda: party.get_default_pic().path
                if party.get_default_pic()
                else None,
                "loanitem_pic": lambda: loan.loanitems.first().pic.path
                if loan.loanitems.first().pic
                else None,
                "loan_id": lambda: loan.loan_id,
                "loan_date": lambda: loan.loan_date.strftime("%d-%m-%Y"),
                "customer_name": lambda: party.name,
                "customer_info": lambda: f"{party.name}, {party.get_relatedas_display()} {party.relatedto}<br/>{party.get_address()}<br/>Ph: {party.get_contactno()}",
                "loan_desc": lambda: "<br/>".join(
                    [
                        f"{i + 1}) {item.itemdesc}, Qty: {item.quantity}"
                        for i, item in enumerate(loan.loanitems.all())
                    ]
                ),
                "weight": lambda: f"{loan.formatted_weight(joiner=', ')}",
                "pure": lambda: f"{loan.formatted_pure(joiner=', ')}",
                "value": lambda: f"{loan.get_current_value()}",
                "amount": lambda: f"{loan.loan_amount}",
                "amount_words": lambda: num2words(loan.loan_amount, lang="en_IN")
                + " rupees only",
                "loan_qr": lambda: loan.loan_id,
                "label": lambda: f"{loan.loan_id} - {loan.loan_date.strftime('%d-%m-%Y')} <br/>{loan.loan_amount} - {loan.weight} <br/>{party.name} - {loan.item_desc}",
            }

            frame_data = data_mapping.get(frame.frame_name, lambda: None)()
            if not frame_data:
                return

            reportlab_frame = Frame(
                x_offset + float(frame.x_pos) * cm,
                y_offset + float(frame.y_pos) * cm,
                float(frame.width) * cm,
                float(frame.height) * cm,
                showBoundary=frame.show_boundary,
            )

            if frame.field_type == "text":
                styles = getSampleStyleSheet()
                style = ParagraphStyle(
                    f"Custom_{frame.frame_name}",
                    parent=styles["Normal"],
                    fontSize=frame.font_size,
                    fontName=frame.font_name,
                )
                content = Paragraph(frame_data, style)
                keep_frame = KeepInFrame(
                    reportlab_frame._width,
                    reportlab_frame._height,
                    [content],
                    mode="shrink",
                )
                reportlab_frame.addFromList([keep_frame], canvas_obj)

            elif frame.field_type == "image" and os.path.exists(frame_data):
                img = PILImage.open(frame_data)
                img_w, img_h = img.size
                aspect = img_w / float(img_h)

                if reportlab_frame._width / float(reportlab_frame._height) > aspect:
                    w = reportlab_frame._height * aspect
                    h = reportlab_frame._height
                else:
                    w = reportlab_frame._width
                    h = reportlab_frame._width / aspect

                x = reportlab_frame._x + (reportlab_frame._width - w) / 2
                y = reportlab_frame._y + (reportlab_frame._height - h) / 2
                canvas_obj.drawImage(
                    frame_data, x, y, width=w, height=h, preserveAspectRatio=True
                )

            elif frame.field_type == "qr":
                try:
                    qr_img = qrcode.make(frame_data)
                    qr_buffer = io.BytesIO()
                    qr_img.save(qr_buffer, format="PNG")
                    qr_buffer.seek(0)

                    qr_w = reportlab_frame._width * 0.9
                    qr_h = reportlab_frame._height * 0.9
                    qr_x = reportlab_frame._x + (reportlab_frame._width - qr_w) / 2
                    qr_y = reportlab_frame._y + (reportlab_frame._height - qr_h) / 2

                    canvas_obj.drawImage(
                        ImageReader(qr_buffer),
                        qr_x,
                        qr_y,
                        width=qr_w,
                        height=qr_h,
                        preserveAspectRatio=True,
                    )
                    qr_buffer.close()
                except Exception as e:
                    logger.exception("QR Code rendering error for frame %s: %s", frame.frame_name, str(e))

        def render_page_content_to_canvas(canvas_obj, template_type, x_offset=0):
            """Helper to render content with specific canvas"""
            frames = template.templateframe_set.filter(
                template_type__in=[template_type, TemplateFrame.TemplateType.BOTH]
            )
            for frame in frames:
                render_frame(frame, x_offset, 0, canvas_obj)

        if template.print_option in ["BA", "BDA"]:  # A4 Landscape options
            # A4 landscape for side-by-side A5
            page_width, page_height = landscape(A4)

            # Create buffers for original and duplicate
            original_buffer = io.BytesIO()
            duplicate_buffer = io.BytesIO()

            # Render original and duplicate content
            c_original = canvas.Canvas(
                original_buffer, pagesize=(page_width / 2, page_height)
            )
            render_page_content_to_canvas(
                c_original, TemplateFrame.TemplateType.ORIGINAL
            )
            c_original.save()

            c_duplicate = canvas.Canvas(
                duplicate_buffer, pagesize=(page_width / 2, page_height)
            )
            render_page_content_to_canvas(
                c_duplicate, TemplateFrame.TemplateType.DUPLICATE
            )
            c_duplicate.save()

            # Merge with templates
            original_pdf = (
                merge_pdfs(template.base_template.read(), original_buffer.getvalue())
                if has_template(template.base_template)
                else original_buffer.getvalue()
            )
            duplicate_pdf = (
                merge_pdfs(template.dup_template.read(), duplicate_buffer.getvalue())
                if has_template(template.dup_template)
                else duplicate_buffer.getvalue()
            )

            # Combine side by side for first page
            front_page = merge_pdfs_side_by_side(original_pdf, duplicate_pdf)

            # Handle double-sided A4 option
            if (
                template.print_option == "BDA"
                and has_template(template.terms_template)
                and has_template(template.form_d3_template)
            ):
                # Create second page with terms and form
                back_page = merge_pdfs_side_by_side(
                    template.terms_template.read(), template.form_d3_template.read()
                )
                result = merge_multiple_pdfs([front_page, back_page])
            else:
                result = front_page

            # Cleanup
            original_buffer.close()
            duplicate_buffer.close()
            return result

        else:  # A5 options
            page_width, page_height = A5[0], A5[1]  # A5 size
            content_buffer = io.BytesIO()
            c = canvas.Canvas(content_buffer, pagesize=(page_width, page_height))

            if template.print_option == "O":
                render_page_content_to_canvas(c, TemplateFrame.TemplateType.ORIGINAL)
                c.save()
                content_pdf = content_buffer.getvalue()
                content_buffer.close()
                return (
                    merge_pdfs(template.base_template.read(), content_pdf)
                    if has_template(template.base_template)
                    else content_pdf
                )

            elif template.print_option == "OT":
                render_page_content_to_canvas(c, TemplateFrame.TemplateType.ORIGINAL)
                c.save()
                content_pdf = content_buffer.getvalue()
                content_buffer.close()
                if has_template(template.base_template) and has_template(
                    template.terms_template
                ):
                    return merge_pdfs_double_sided(
                        template.base_template.read(),
                        content_pdf,
                        template.terms_template.read(),
                    )
                return content_pdf

            elif template.print_option == "D":
                render_page_content_to_canvas(c, TemplateFrame.TemplateType.DUPLICATE)
                c.save()
                content_pdf = content_buffer.getvalue()
                content_buffer.close()
                return (
                    merge_pdfs(template.dup_template.read(), content_pdf)
                    if has_template(template.dup_template)
                    else content_pdf
                )

            elif template.print_option == "DF":
                render_page_content_to_canvas(c, TemplateFrame.TemplateType.DUPLICATE)
                c.save()
                content_pdf = content_buffer.getvalue()
                content_buffer.close()
                if has_template(template.dup_template) and has_template(
                    template.form_d3_template
                ):
                    return merge_pdfs_double_sided(
                        template.dup_template.read(),
                        content_pdf,
                        template.form_d3_template.read(),
                    )
                return content_pdf

            elif template.print_option == "BS":
                # ============================================================================
                # OLD APPROACH (BUGGY) - Commented out for reference
                # ============================================================================
                # BUG EXPLANATION:
                # The old code rendered BOTH original and duplicate into ONE multi-page PDF:
                #   1. c.addFromList(...original...) -> page 0
                #   2. c.showPage()                  -> start new page
                #   3. c.addFromList(...duplicate..) -> page 1
                #   4. c.save()                      -> save 2-page content_pdf
                #
                # Then it tried to merge this 2-page content_pdf with templates:
                #   merge_pdfs(template.base_template.read(), content_pdf)
                #
                # BUT merge_pdfs() ONLY uses page 0 of content_pdf (see line 452):
                #   content_doc[0]  <- HARDCODED TO PAGE 0
                #
                # Result: merge_pdfs was called TWICE with the SAME 2-page content_pdf,
                # both times using only page 0 (original). Page 1 (duplicate) was IGNORED!
                # This caused duplicate content to be missing/blank when merged with dup_template.
                #
                # ---OLD CODE---
                # elif template.print_option == "BS":
                #     render_page_content_to_canvas(c, TemplateFrame.TemplateType.ORIGINAL)
                #     c.showPage()
                #     render_page_content_to_canvas(c, TemplateFrame.TemplateType.DUPLICATE)
                #     c.save()
                #     content_pdf = content_buffer.getvalue()
                #     content_buffer.close()
                #     if not (has_template(template.base_template) or has_template(template.dup_template)):
                #         return content_pdf
                #     return merge_multiple_pdfs([
                #         merge_pdfs(template.base_template.read(), content_pdf)  # Uses page 0 only
                #         if has_template(template.base_template) else content_pdf,
                #         merge_pdfs(template.dup_template.read(), content_pdf)   # ALSO uses page 0 (BUG!)
                #         if has_template(template.dup_template) else content_pdf,
                #     ])
                # ============================================================================
                #
                # NEW APPROACH (FIXED)
                # ============================================================================
                # FIX: Create TWO separate single-page PDFs instead of one 2-page PDF
                # This ensures merge_pdfs can use page 0 correctly each time:
                #   - original_pdf = 1-page PDF with original content
                #   - duplicate_pdf = 1-page PDF with duplicate content
                # Then merge each with its own template:
                #   merge_pdfs(base_template, original_pdf)   <- merges correct page
                #   merge_pdfs(dup_template, duplicate_pdf)   <- merges correct page
                #
                original_buffer_bs = io.BytesIO()
                c_original_bs = canvas.Canvas(original_buffer_bs, pagesize=(page_width, page_height))
                render_page_content_to_canvas(c_original_bs, TemplateFrame.TemplateType.ORIGINAL)
                c_original_bs.save()
                original_pdf = original_buffer_bs.getvalue()
                original_buffer_bs.close()

                duplicate_buffer_bs = io.BytesIO()
                c_duplicate_bs = canvas.Canvas(duplicate_buffer_bs, pagesize=(page_width, page_height))
                render_page_content_to_canvas(c_duplicate_bs, TemplateFrame.TemplateType.DUPLICATE)
                c_duplicate_bs.save()
                duplicate_pdf = duplicate_buffer_bs.getvalue()
                duplicate_buffer_bs.close()

                # Merge each with respective template
                merged_original = (
                    merge_pdfs(template.base_template.read(), original_pdf)
                    if has_template(template.base_template)
                    else original_pdf
                )
                merged_duplicate = (
                    merge_pdfs(template.dup_template.read(), duplicate_pdf)
                    if has_template(template.dup_template)
                    else duplicate_pdf
                )

                # Combine as separate pages
                return merge_multiple_pdfs([merged_original, merged_duplicate])

            elif template.print_option == "BD":
                # ============================================================================
                # OLD APPROACH (BUGGY) - Commented out for reference
                # ============================================================================
                # BUG EXPLANATION (same as BS):
                # The old code rendered BOTH original and duplicate into ONE multi-page PDF:
                #   1. render_page_content_to_canvas(...original...) -> page 0
                #   2. c.showPage()                  -> start new page
                #   3. render_page_content_to_canvas(...duplicate..) -> page 1
                #   4. c.save()                      -> save 2-page content_pdf
                #
                # Then it called merge_pdfs_double_sided() TWICE with the SAME content_pdf:
                #   merge_pdfs_double_sided(base_template, content_pdf, terms_template)   # Page 0 used
                #   merge_pdfs_double_sided(dup_template, content_pdf, form_d3_template)  # Page 0 again (BUG!)
                #
                # BUT merge_pdfs_double_sided() ONLY uses page 0 of content_pdf (line 488):
                #   content_doc[0]  <- HARDCODED TO PAGE 0
                #
                # Result: duplicate content in page 1 was never merged, causing output errors.
                #
                # ---OLD CODE---
                # elif template.print_option == "BD":
                #     render_page_content_to_canvas(c, TemplateFrame.TemplateType.ORIGINAL)
                #     c.showPage()
                #     render_page_content_to_canvas(c, TemplateFrame.TemplateType.DUPLICATE)
                #     c.save()
                #     content_pdf = content_buffer.getvalue()
                #     content_buffer.close()
                #     if not (has_template(template.base_template) or has_template(template.dup_template)):
                #         return content_pdf
                #     return merge_multiple_pdfs([
                #         merge_pdfs_double_sided(template.base_template.read(), content_pdf, ...)
                #         if (conditions) else content_pdf,
                #         merge_pdfs_double_sided(template.dup_template.read(), content_pdf, ...)  # ALSO Page 0 (BUG!)
                #         if (conditions) else content_pdf,
                #     ])
                # ============================================================================
                #
                # NEW APPROACH (FIXED)
                # ============================================================================
                # FIX: Create TWO separate single-page PDFs instead of one 2-page PDF
                #   - original_pdf = 1-page PDF with original content
                #   - duplicate_pdf = 1-page PDF with duplicate content
                # Then merge each with its own template using merge_pdfs_double_sided():
                #   - merge_pdfs_double_sided(base_template, original_pdf, terms_template)
                #   - merge_pdfs_double_sided(dup_template, duplicate_pdf, form_d3_template)
                # This ensures each call merges the CORRECT content page.
                #
                original_buffer_bd = io.BytesIO()
                c_original_bd = canvas.Canvas(original_buffer_bd, pagesize=(page_width, page_height))
                render_page_content_to_canvas(c_original_bd, TemplateFrame.TemplateType.ORIGINAL)
                c_original_bd.save()
                original_pdf = original_buffer_bd.getvalue()
                original_buffer_bd.close()

                duplicate_buffer_bd = io.BytesIO()
                c_duplicate_bd = canvas.Canvas(duplicate_buffer_bd, pagesize=(page_width, page_height))
                render_page_content_to_canvas(c_duplicate_bd, TemplateFrame.TemplateType.DUPLICATE)
                c_duplicate_bd.save()
                duplicate_pdf = duplicate_buffer_bd.getvalue()
                duplicate_buffer_bd.close()

                # Merge original with base + terms (double-sided)
                merged_original = (
                    merge_pdfs_double_sided(
                        template.base_template.read(),
                        original_pdf,
                        template.terms_template.read(),
                    )
                    if (
                        has_template(template.base_template)
                        and has_template(template.terms_template)
                    )
                    else original_pdf
                )

                # Merge duplicate with dup + form D3 (double-sided)
                merged_duplicate = (
                    merge_pdfs_double_sided(
                        template.dup_template.read(),
                        duplicate_pdf,
                        template.form_d3_template.read(),
                    )
                    if (
                        has_template(template.dup_template)
                        and has_template(template.form_d3_template)
                    )
                    else duplicate_pdf
                )

                # Combine into final document
                return merge_multiple_pdfs([merged_original, merged_duplicate])

    except LoanTemplate.DoesNotExist:
        logger.warning("Attempted to generate PDF with non-existent or inactive template (ID: %s)", template_id)
        return None
    except Exception as e:
        logger.exception("Error generating PDF for loan (template_id=%s): %s", template_id, str(e))
        return None


# with better oops
# from dataclasses import dataclass
# from typing import Any, Dict, Callable, Optional, Union
# from PIL import Image as PILImage
# from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# from reportlab.lib.units import cm
# from reportlab.platypus import Frame, Paragraph, KeepInFrame
# from reportlab.pdfgen import canvas
# from reportlab.lib.utils import ImageReader
# import qrcode
# import io
# from io import BytesIO
# import os
# import logging

# logger = logging.getLogger(__name__)

# @dataclass
# class FrameConfig:
#     x_pos: float
#     y_pos: float
#     width: float
#     height: float
#     font_size: int = 12
#     font_name: str = 'Helvetica'

# class PDFRenderer:
#     def __init__(self, template, loan):
#         self.template = template
#         self.loan = loan
#         self.page_width = float(template.page_width) * cm
#         self.page_height = float(template.page_height) * cm
#         self.styles = getSampleStyleSheet()

#     def _generate_qr_code(self, data: str) -> PILImage.Image:
#         qr = qrcode.QRCode(
#             version=1,
#             error_correction=qrcode.constants.ERROR_CORRECT_L,
#             box_size=10,
#             border=4,
#         )
#         qr.add_data(data)
#         qr.make(fit=True)
#         img = qr.make_image(fill_color="black", back_color="white")
#         buffer = BytesIO()
#         img.save(buffer, format="PNG")
#         return buffer.getvalue()

#     def _get_data_mapping(self) -> Dict[str, Callable[[], Any]]:
#         return {
#             'loan_id': lambda: f"Loan ID: {self.loan.loan_id} <br/>Date: {self.loan.loan_date.strftime('%d-%m-%Y')}",
#             'loan_qr': lambda: self._generate_qr_code(self.loan.loan_id),
#             'customer_name': lambda: f"{self.loan.customer.name}, {self.loan.customer.get_relatedas_display()} {self.loan.customer.relatedto}",
#             "customer_info": lambda: (f"{self.loan.customer.name}, {self.loan.customer.get_relatedas_display()} "
#                                    f"{self.loan.customer.relatedto}<br/>{self.loan.customer.address.first()}"
#                                    f"<br/>Ph: {self.loan.customer.contactno.first()}"),
#             "customer_pic": lambda: self.loan.customer.get_default_pic().path if self.loan.customer.pics else None,
#             "loanitem_pic": lambda: self.loan.loanitems.first().pic.path if self.loan.loanitems.first().pic else None,
#             'address': lambda: str(self.loan.customer.address.first()),
#             'phone': lambda: str(self.loan.customer.contactno.first()),
#             'items_table': lambda: "<br/>".join([f"{i + 1}) {item.itemdesc}, Qty: {item.quantity}"
#                                                for i, item in enumerate(self.loan.loanitems.all())]),
#             "loan_desc": lambda: "<br/>".join([f"{i + 1}) {item.itemdesc}, Qty: {item.quantity}"
#                                              for i, item in enumerate(self.loan.loanitems.all())]),
#             "weight": lambda: self.loan.formatted_weight(joiner=', '),
#             "value": lambda: str(self.loan.get_current_value()),
#             "loan_amount": lambda: str(self.loan.loan_amount),
#             "loan_amount_in_figures": lambda: num2words(self.loan.loan_amount, lang='en_IN') + " rupees only",
#         }

#     def _render_text_frame(self, canvas_obj, frame_config: FrameConfig, content: str):
#         style = ParagraphStyle(
#             'Custom',
#             parent=self.styles['Normal'],
#             fontSize=frame_config.font_size,
#             fontName=frame_config.font_name
#         )
#         paragraph = Paragraph(content, style)
#         frame = Frame(
#             frame_config.x_pos * cm,
#             frame_config.y_pos * cm,
#             frame_config.width * cm,
#             frame_config.height * cm,
#             showBoundary=1
#         )
#         keep_frame = KeepInFrame(
#             frame_config.width * cm,
#             frame_config.height * cm,
#             [paragraph],
#             mode='shrink'
#         )
#         frame.addFromList([keep_frame], canvas_obj)

#     def _render_image_frame(self, canvas_obj, frame_config: FrameConfig, image_data: Union[str, PILImage.Image]):
#         try:
#             img = (image_data if isinstance(image_data, PILImage.Image)
#                   else PILImage.open(image_data))

#             img_w, img_h = img.size
#             aspect = img_w / float(img_h)

#             frame_w = frame_config.width * cm
#             frame_h = frame_config.height * cm

#             # Calculate dimensions maintaining aspect ratio
#             if frame_w / frame_h > aspect:
#                 w, h = frame_h * aspect, frame_h
#             else:
#                 w, h = frame_w, frame_w / aspect

#             x = frame_config.x_pos * cm + (frame_w - w) / 2
#             y = frame_config.y_pos * cm + (frame_h - h) / 2

#             if isinstance(image_data, PILImage.Image):
#                 buffer = BytesIO()
#                 image_data.save(buffer, format='PNG')  # Use image_data instead of img
#                 buffer.seek(0)
#                 canvas_obj.drawImage(ImageReader(buffer), x, y, width=w, height=h, preserveAspectRatio=True)
#                 buffer.close()
#             else:
#                 canvas_obj.drawImage(image_data, x, y, width=w, height=h, preserveAspectRatio=True)

#         except Exception as e:
#             logger.error(f"Error rendering image: {e}")

#     def render_frames(self, canvas_obj, x_offset: float = 0, y_offset: float = 0):
#         data_mapping = self._get_data_mapping()

#         for frame in self.template.templateframe_set.all():
#             frame_config = FrameConfig(
#                 x_pos=float(frame.x_pos) + float(x_offset),
#                 y_pos=float(frame.y_pos) + float(y_offset),
#                 width=float(frame.width),
#                 height=float(frame.height),
#                 font_size=frame.font_size,
#                 font_name=frame.font_name
#             )

#             data = data_mapping.get(frame.frame_name, lambda: None)()
#             if not data:
#                 continue

#             if frame.field_type == 'text':
#                 self._render_text_frame(canvas_obj, frame_config, data)
#             elif frame.field_type in ('image', 'qr'):
#                 self._render_image_frame(canvas_obj, frame_config, data)

# def get_custom_jcl(loan, template_id: Optional[int] = None) -> bytes:
#     """Generate PDF using user-defined template configuration"""
#     try:
#         template = LoanTemplate.objects.get(id=template_id, is_active=True)
#     except LoanTemplate.DoesNotExist:
#         raise ValueError("Template not found or inactive")

#     content_buffer = io.BytesIO()
#     c = canvas.Canvas(content_buffer, pagesize=(float(template.page_width) * cm,
#                                               float(template.page_height) * cm))

#     renderer = PDFRenderer(template, loan)

#     if template.print_layout == LoanTemplate.PrintLayout.SINGLE_A4:
#         renderer.render_frames(c, 0, 0)
#         renderer.render_frames(c, template.page_width/2, 0)
#     else:  # SEPARATE_A5
#         renderer.render_frames(c, 0, 0)

#     c.save()
#     content_pdf = content_buffer.getvalue()
#     content_buffer.close()

#     if template.base_template:
#         return merge_pdfs(template.base_template.read(), content_pdf)

#     return content_pdf


def generate_grid_template():
    page_width, page_height = landscape(A4)
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    # Draw grid for the entire A4 landscape page
    c.setFont("Helvetica", 8)
    c.setStrokeColorRGB(0.8, 0.8, 0.8)  # Light gray for grid lines

    # Draw vertical lines
    for x in range(0, int(page_width), int(1 * cm)):
        c.line(x, 0, x, page_height)
        c.drawString(x + 2, 2, f"{x // cm}cm")

    # Draw horizontal lines
    for y in range(0, int(page_height), int(1 * cm)):
        c.line(0, y, page_width, y)
        c.drawString(2, y + 2, f"{y // cm}cm")

    # Draw a thicker line to separate the two A5 frames
    c.setStrokeColorRGB(0, 0, 0)  # Black for the separator line
    c.setLineWidth(2)
    c.line(page_width / 2, 0, page_width / 2, page_height)

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def grid_template(page_size=A5, grid_spacing_cm=1, show_margins=True, margin_cm=1):
    """
    Generate a PDF with measurement grid for template design
    Args:
        page_size: Tuple of (width, height) in points
        grid_spacing_cm: Grid spacing in centimeters
        show_margins: Show margin guides
        margin_cm: Margin size in centimeters
    Returns:
        bytes: PDF content
    """
    page_width, page_height = page_size
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=page_size)

    # Colors
    GRID_COLOR = (0.3, 0.3, 0.3)  # Light gray
    MARGIN_COLOR = (1, 0.8, 0.8)  # Light red
    TEXT_COLOR = (0.3, 0.3, 0.3)  # Dark gray

    # Draw grid
    c.setFont("Helvetica", 6)
    c.setStrokeColorRGB(*GRID_COLOR)
    c.setLineWidth(0.1)

    # Draw vertical lines and labels
    for x in range(0, int(page_width), int(grid_spacing_cm * cm)):
        c.line(x, 0, x, page_height)
        # Draw coordinate at top and bottom
        c.setFillColorRGB(*TEXT_COLOR)
        c.drawString(x + 2, 2, f"{x/cm:.1f}")
        c.drawString(x + 2, page_height - 8, f"{x/cm:.1f}")

    # Draw horizontal lines and labels
    for y in range(0, int(page_height), int(grid_spacing_cm * cm)):
        c.line(0, y, page_width, y)
        # Draw coordinate at left and right
        c.setFillColorRGB(*TEXT_COLOR)
        c.drawString(2, y + 2, f"{y/cm:.1f}")
        c.drawString(page_width - 20, y + 2, f"{y/cm:.1f}")

    # Draw margins if requested
    if show_margins:
        c.setStrokeColorRGB(*MARGIN_COLOR)
        c.setLineWidth(0.5)
        margin = margin_cm * cm
        # Left margin
        c.line(margin, 0, margin, page_height)
        # Right margin
        c.line(page_width - margin, 0, page_width - margin, page_height)
        # Top margin
        c.line(0, page_height - margin, page_width, page_height - margin)
        # Bottom margin
        c.line(0, margin, page_width, margin)

    # Add page size info
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 8)
    size_text = f"Page Size: {page_width/cm:.1f}cm x {page_height/cm:.1f}cm"
    c.drawString(10, page_height - 20, size_text)

    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# form_letter.py


def form_letter():
    doc = SimpleDocTemplate(
        "form_letter.pdf",
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    flowables = []
    # logo = "python_logo.png"
    magName = "Pythonista"
    issueNum = 12
    subPrice = "99.00"
    limitedDate = "03/05/2010"
    freeGift = "tin foil hat"

    formatted_time = time.ctime()
    full_name = "Mike Driscoll"
    address_parts = ["411 State St.", "Waterloo, IA 50158"]

    # im = Image(logo, 2*inch, 2*inch)
    # flowables.append(im)

    styles = getSampleStyleSheet()
    # Modify the Normal Style
    styles["Normal"].fontSize = 12
    styles["Normal"].leading = 14

    # Create a Justify style
    styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY))

    flowables.append(Paragraph(formatted_time, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    # Create return address
    flowables.append(Paragraph(full_name, styles["Normal"]))
    for part in address_parts:
        flowables.append(Paragraph(part.strip(), styles["Normal"]))

    flowables.append(Spacer(1, 12))
    ptext = "Dear {}:".format(full_name.split()[0].strip())
    flowables.append(Paragraph(ptext, styles["Normal"]))
    flowables.append(Spacer(1, 12))

    ptext = """
    We would like to welcome you to our subscriber
    base for {magName} Magazine! You will receive {issueNum} issues at
    the excellent introductory price of ${subPrice}. Please respond by
    {limitedDate} to start receiving your subscription and get the
    following free gift: {freeGift}.
    """.format(
        magName=magName,
        issueNum=issueNum,
        subPrice=subPrice,
        limitedDate=limitedDate,
        freeGift=freeGift,
    )
    flowables.append(Paragraph(ptext, styles["Justify"]))
    flowables.append(Spacer(1, 12))

    ptext = """Thank you very much and we look
    forward to serving you."""

    flowables.append(Paragraph(ptext, styles["Justify"]))
    flowables.append(Spacer(1, 12))
    ptext = "Sincerely,"
    flowables.append(Paragraph(ptext, styles["Normal"]))
    flowables.append(Spacer(1, 48))
    ptext = "Ima Sucker"
    flowables.append(Paragraph(ptext, styles["Normal"]))
    flowables.append(Spacer(1, 12))
    doc.build(flowables)


def generate_form_a():
    # Form A [See Section 4 (1) and rule 3] Form of Application For A Pawnbroker's Licence To The Tahsildar, Independent Deputy Tahsildar,  .........Taluk                                                                                        1. Name in full of the applicant. 2. Address in full (any subsequent change should be notified). 3. Father's name. 4. Is the applicant a citizen of India? If the applicant has a residence outside the State of Tamil Nadu (1) Full address of such residence; and (2) A list of the properties owned by him in places outside the State of Tamil Nadu. 5. Address of shop or place of business in respect of which the licence is applied for. 6. If the applicant has more than one shop or place of business, the address of each such shop or place of business. 7. Has the applicant applied for a separate licence in respect of each shop or place of business mentioned against item 6, and if so, with what result? 8. Is the present application made for the grant of a new licence or for the renewal of a licence granted in the previous year? 9. The financial year for which the licence is applied for. 10. Has the applicant paid the prescribed fee for the licence. (The treasury receipt should be enclosed).      Passport size         photograph to be         affixed by the         applicant and         attested by the        licensing           authority.)   11. Name of the nominee with actress: (a) Age and sex. (b) Amount of solvency. (c) Is the nominee's consent letter mentioned in rule 3(2) attached ? I declare that the particulars stated above are correct to the best of my knowledge and belief.                                                                                       Signature of the applicant.  Annexure Specimen signatures of the applicant: (1)........... (2)........... (3)........... (The specimen signatures should be attested by the licensing authority)

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("pawnbroker_application_form.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    form_a_content = """
    <b>Form A </b><br/>
    [See Section 4 (1) and rule 3]<br/>
    <b>Form of Application For A Pawnbroker's Licence</b><br/>
    To The Tahsildar, Independent Deputy Tahsildar, .........Taluk<br/>
    <br/>
    1. Name in full of the applicant.<br/>
    2. Address in full (any subsequent change should be notified).<br/>
    3. Father's name.<br/>
    4. Is the applicant a citizen of India?<br/>
    If the applicant has a residence outside the State of Tamil Nadu<br/>
    (1) Full address of such residence; and<br/>
    (2) A list of the properties owned by him in places outside the State of Tamil Nadu.<br/>
    5. Address of shop or place of business in respect of which the licence is applied for.<br/>
    6. If the applicant has more than one shop or place of business, the address of each such shop or place of business.<br/>
    7. Has the applicant applied for a separate licence in respect of each shop or place of business mentioned against item 6, and if so, with what result?<br/>
    8. Is the present application made for the grant of a new licence or for the renewal of a licence granted in the previous year?<br/>
    9. The financial year for which the licence is applied for.<br/>
    10. Has the applicant paid the prescribed fee for the licence. (The treasury receipt should be enclosed).<br/>
    <br/>
    <i>Passport size photograph to be affixed by the applicant and attested by the licensing authority.</i><br/>
    <br/>
    11. Name of the nominee with address:<br/>
    (a) Age and sex.<br/>
    (b) Amount of solvency.<br/>
    (c) Is the nominee's consent letter mentioned in rule 3(2) attached?<br/>
    <br/>
    I declare that the particulars stated above are correct to the best of my knowledge and belief.<br/>
    <br/>
    Signature of the applicant.<br/>
    <br/>
    <b>Annexure</b><br/>
    Specimen signatures of the applicant:<br/>
    (1)...........<br/>
    (2)...........<br/>
    (3)...........<br/>
    <i>(The specimen signatures should be attested by the licensing authority)</i>
    """

    # Create a Paragraph object
    paragraph = Paragraph(form_a_content, styles["Normal"])

    # List of flowable elements
    elements = [paragraph, Spacer(1, 12)]

    # Build the PDF
    doc.build(elements)


def generate_form_c():
    # declaration by pawner,Transfer of owvership
    # Form C [See section 8(2) and rule 6(1)] Declaration by Fawner Tahsildar of .............. taluk -------------------------------------------- Independent Deputy Tahsildar. I,.........of........in pursuance of subjection (2) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that the right to redeem the article/articles described below pawned by me at the shop of.............Pawnbroker and covered by Pawn Ticket No............dated..........has been transferred to or is vested in and that is entitled to redeem the pledge. I also hereby declare that my right to redeem the pledge is hereby extinguished. The article/articles above referred to is/are of the following description: - 1........... 2........... Signature of the pawner. Designation. Address. Date. I, .........of........... in pursuance of sub-section (2) of section 8 of the said Act do solemnly and sincerely declare that I know the person now making the foregoing declaration to be..........of........... Signature of identifying person. Designation. Address. Date.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("loan_declaration.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form C [See section 8(2) and rule 6(1)]</b><br/>
    Declaration by Fawner Tahsildar of .............. taluk<br/>
    --------------------------------------------<br/>
    Independent Deputy Tahsildar.<br/>
    I,.........of........in pursuance of subjection (2) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that the right to redeem the article/articles described below pawned by me at the shop of.............Pawnbroker and covered by Pawn Ticket No............dated..........has been transferred to or is vested in and that is entitled to redeem the pledge. I also hereby declare that my right to redeem the pledge is hereby extinguished.<br/>
    The article/articles above referred to is/are of the following description:<br/>
    1...........<br/>
    2...........<br/>
    <br/>
    Signature of the pawner.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I, .........of........... in pursuance of sub-section (2) of section 8 of the said Act do solemnly and sincerely declare that I know the person now making the foregoing declaration to be..........of...........<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.
    """

    # Create a Paragraph object
    paragraph = Paragraph(content, styles["Normal"])

    # List of flowable elements
    elements = [paragraph, Spacer(1, 12)]

    # Build the PDF
    doc.build(elements)


def generate_form_d():
    # Form D [See section 8(2) and rule 6(1)] Declaration by the Person Entitled to Redeem The Pledge I,........of.........in pursuance of sub-section (2) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that the right to redeem the article/articles described below, the property of, and pawned by,........... at the shop of pawnbroker and covered by .............. Pawn Ticket No............... has been transferred to or is vested in me. I also do solemnly and sincerely declare that I am in possession of the said Pawn Ticket and that I am entitled to redeem the pledge. The article/articles above referred to is/are of the following description: - 1........... 2........... Signature of the pawner. Designation. Address. Date. I,........of.........in pursuance of sub-section (2) of section 8 of the said Act, to solemnly and sincerely declare that I know the person now making the foregoing declaration to be of...............of................ Signature of identifying person. Designation. Address. Date.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("declaration_form_d.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form D [See section 8(2) and rule 6(1)]</b><br/>
    Declaration by the Person Entitled to Redeem The Pledge<br/>
    I,........of.........in pursuance of sub-section (2) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that the right to redeem the article/articles described below, the property of, and pawned by,........... at the shop of pawnbroker and covered by .............. Pawn Ticket No............... has been transferred to or is vested in me. I also do solemnly and sincerely declare that I am in possession of the said Pawn Ticket and that I am entitled to redeem the pledge.<br/>
    The article/articles above referred to is/are of the following description:<br/>
    1...........<br/>
    2...........<br/>
    <br/>
    Signature of the pawner.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I,........of.........in pursuance of sub-section (2) of section 8 of the said Act, to solemnly and sincerely declare that I know the person now making the foregoing declaration to be of...............of................<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.
    """

    # Create a Paragraph object
    paragraph = Paragraph(content, styles["Normal"])

    # List of flowable elements
    elements = [paragraph, Spacer(1, 12)]

    # Build the PDF
    doc.build(elements)


def generate_form_d1():
    # Form D-1 [See section 8(3) and rule 6(1)] Declaration by Messenger/Agent I,........of.........in pursuance of sub-section (3) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), solemnly and sincerely declare that I am the messenger/agent of the pawner who has pawned the article/articles described below at the shop of.......... pawnbroker under Pawn Ticket No.............dated.........and that I have been duly authorized by the pawner to redeem the pledge. The article/articles above referred to is/are of the following description: - 1........... 2........... Signature of the messenger/agent. Designation. Address. Date. I,.........of..........in pursuance of sub-section (3) of section 8 of the said Act, do solemnly and sincerely declare that I know the person now making the above declaration. Signature of identifying person. Designation. Address. Date.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("form_d1.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form D-1 [See section 8(3) and rule 6(1)]</b><br/>
    <b>Declaration by Messenger/Agent</b><br/>
    I,........of.........in pursuance of sub-section (3) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), solemnly and sincerely declare that I am the messenger/agent of the pawner who has pawned the article/articles described below at the shop of.......... pawnbroker under Pawn Ticket No.............dated.........and that I have been duly authorized by the pawner to redeem the pledge.<br/>
    <br/>
    The article/articles above referred to is/are of the following description:<br/>
    1...........<br/>
    2...........<br/>
    <br/>
    Signature of the messenger/agent.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I,.........of..........in pursuance of sub-section (3) of section 8 of the said Act, do solemnly and sincerely declare that I know the person now making the above declaration.<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.
    """

    # Create a list to hold the flowable elements
    flowables = []

    # Create a Paragraph object and add it to the flowables list
    flowables.append(Paragraph(content, styles["Normal"]))

    # Add a spacer for spacing
    flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)


def generate_form_d2():
    # Form D-2 [See section 8(4)(a)(i) and rule 6(1)] Declaration by Legal Representative of Pawner I,........ of.......... in pursuance of sub-clause (i) of clause (a) of sub-section (4) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the legal representative of deceased pawner being his/her ..........and that I am entitled to redeem the article/articles described below and pawned by the deceased pawner at the shop of pawnbroker under Pawn Ticket No............... dated.......... I also hereby declare that the said Pawn Ticket is now in my possession. The article/articles above referred to is/are of the following description:- 1........... 2........... Signature of person. Designation. Address. Date. I,.........of......... in pursuance of sub-clause (i) of clause (a) of sub-section (4) of section 8 of the said Act, do solemnly and sincerely declare that I know the person now making foregoing declaration to be.........of......... Signature of identifying person. Designation. Address. Date. Declared before me this day of.......... Magistrate or Judge.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("form_d2.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form D-2 [See section 8(4)(a)(i) and rule 6(1)]</b><br/>
    <b>Declaration by Legal Representative of Pawner</b><br/>
    I,........ of.......... in pursuance of sub-clause (i) of clause (a) of sub-section (4) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the legal representative of deceased pawner being his/her ..........and that I am entitled to redeem the article/articles described below and pawned by the deceased pawner at the shop of pawnbroker under Pawn Ticket No............... dated.......... I also hereby declare that the said Pawn Ticket is now in my possession.<br/>
    <br/>
    The article/articles above referred to is/are of the following description:-<br/>
    1...........<br/>
    2...........<br/>
    <br/>
    Signature of person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I,.........of......... in pursuance of sub-clause (i) of clause (a) of sub-section (4) of section 8 of the said Act, do solemnly and sincerely declare that I know the person now making foregoing declaration to be.........of.........<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    Declared before me this day of..........<br/>
    Magistrate or Judge.
    """

    # Create a list to hold the flowable elements
    flowables = []

    # Create a Paragraph object and add it to the flowables list
    flowables.append(Paragraph(content, styles["Normal"]))

    # Add a spacer for spacing
    flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)


def generate_form_d3():
    # Form D-3 [See section 8(6) and rule 6(1)] Declaration by Pawner of Loss or Destruction of Pawn Ticket I,........of...........in pursuance's of sub-section (6) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I pledged at shop of ................. pawnbroker, the article/article's described below being my property and having received a pawn ticket bearing No.............. dated ......... (if known) for the same which has since been lost/destroyed "and that the pawn ticket has not been sold, assigned or transferred to any person by me to the best of my knowledge and belief. The article/articles above referred to is/are of the following description: - 1.......... 2.......... Signature of the pawner. Designation. Address. Date. I,........of.......in pursuance of sub-section (6) of section 8 of the said Act, do solemnly and sincerely declare that I know the person making the foregoing declaration........... to be................ of............... Signature of identifying person. Designation. Address. Date.

    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate("form_d3.pdf", pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Define the content
    content = """
    <b>Form D-3 [See section 8(6) and rule 6(1)]</b><br/>
    <b>Declaration by Pawner of Loss or Destruction of Pawn Ticket</b><br/>
    I,........of...........in pursuance's of sub-section (6) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I pledged at shop of ................. pawnbroker, the article/article's described below being my property and having received a pawn ticket bearing No.............. dated ......... (if known) for the same which has since been lost/destroyed "and that the pawn ticket has not been sold, assigned or transferred to any person by me to the best of my knowledge and belief.<br/>
    <br/>
    The article/articles above referred to is/are of the following description:-<br/>
    1..........<br/>
    2..........<br/>
    <br/>
    Signature of the pawner.<br/>
    Designation.<br/>
    Address.<br/>
    Date.<br/>
    <br/>
    I,........of.......in pursuance of sub-section (6) of section 8 of the said Act, do solemnly and sincerely declare that I know the person making the foregoing declaration........... to be................ of...............<br/>
    <br/>
    Signature of identifying person.<br/>
    Designation.<br/>
    Address.<br/>
    Date.
    """

    # Create a list to hold the flowable elements
    flowables = []

    # Create a Paragraph object and add it to the flowables list
    flowables.append(Paragraph(content, styles["Normal"]))

    # Add a spacer for spacing
    flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)


def generate_form_h(release):
    # create a buffer to hold the PDF
    buffer = BytesIO()
    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()
    centered_style = ParagraphStyle(
        name="Centered", parent=styles["Normal"], alignment=1
    )  # 1 is for center alignment

    # Define the table data with placeholders

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

    # Create a list to hold the flowable elements
    flowables = []

    # Create the table
    table = Table(data)

    # Apply styles to the table
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                # ('GRID', (0, 0), (-1, -1), 1, colors.black),
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

    # Add the table to the flowables list
    flowables.append(table)
    # flowables.append(Paragraph("hello", styles["Normal"]))
    # Build the PDF
    doc.build(flowables)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# Form D-4 [See section 8(7) and rule 6(1)] Declaration by Person Claiming to Be Owners of pledge I,........of.......in pursuance of sub-section (7) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the owner of the article/articles described below, pawned at shop of......... pawnbroker and that the pledge in respect of the article/articles was pawned without my knowledge or authority. The article/articles above referred to is/are of the following description: - 1........... 2........... Signature of person. Designation. Address. Date. I,..........of.......in pursuance of sub-section (7) of section 8 of the Act, do solemnly and sincerely declare that I know the person making the foregoing declaration to be......... of............ Signature of identifying person. Designation. Address. Date.
# Form D-5 [See second proviso to section 8(3) and rule 6(2)] Notice To The Pawner Notice is hereby given that ............. claiming himself to be your agent /messenger has produced on............ the pawn Ticket No dated............... issued to you for the article /articles described below pawned by you at my shop and offered to redeem the pledge. I, ............. pawnbroker propose to allow his/her claim to redeem, the pledge. You are hereby required to state your objections, if any, in respect of the above proposal. If nothing is heard from you within two weeks after the date on which this notice would in the usual course of post reach you, the person claiming to be your messenger/ agent will be allowed to redeem the pledge. The article/articles above referred to is/are of the following description:- 1........... 2........... Signature of pawnbroker. Address. Date.
# Form D-6 [See section 8(5) and rule 6(2)] Notice of Assignment To Pawnbroker Date. Notice is hereby given that I, ......... of .......... have come into possession of the pawn ticket No............dated.........as the assignee of the pawner by him at the shop of pawnbroker. You are hereby required to recognize my claim and to allow me to redeem the pledge. The article/articles above referred to is/are of the following description: - Description of the article/articles. Signature of the person. Designation. Address. Date. To Pawnbroker at..........
# Form D-7 [See section 8(5) and rule 6(2)] Notice To Pawner of Claim Made by Assignee Notice is hereby given that............claiming himself to be your assignee has produced on ................ the pawn ticket No............. dated............. given to you in respect of the article /articles described below pawned by you at the shop of........pawnbroker and he offered to redeem the pledge. I,........pawnbroker, propose to recognize his claim and to allow him to redeem pledge. You are hereby required to intimate to me the objections, if any, to the proposal. If nothing is heard from you within two weeks after the date on which this notice would in the usual course of post reach you, it will be presumed that you have no objection to the proposal and the claimant will be recognised as your assignee and allowed to redeem the pledge. The article/articles above referred to is /are of the following description. Description of the article/articles ............ ............ Signature of the pawnbroker. Address. Date.
# Form D-8 [See section 8(7) and rule 6(2)] Notice To Pawner of Claim by Owner of Pledge Date. Notice is hereby given that..........claims to the owner of the pledge in respect of the article /articles described below pawned at the shop........ of...........pawnbroker, and covered by pawn ticket No.............dated........... alleges that the pledge was pawned without his knowledge and authority. You are hereby required to intimate in writing whether you have any objection to the claim.......... or to the articles pledged by you. If no communication is received in writing within two weeks after the date on which it would in the usual course of post reach you, it will be presumed that you do not object to the claim made by the said.......... and he will be recognized as the legitimate owner of the article/articles and will be allowed to redeem the pledge. The article/articles above referred to is/are of the following description:- Description of the article/articles. ....................... ....................... ....................... Signature of the pawnbroker. Address. Date.
# Form G [See section 10(i)(b)(ii) and rule 8] Sale Book of Pledges (Date and place of sale) (Name and place of business of auctioneer) 1. Name of pledge as in the pledge book. 2. Date of pawning. 3. Name of pawner. 4. Amount of loan. 5. Amount for which pledge sold as stated by the auctioneer. 6. Signature of the auctioneer or his agent. 7. Name and address of purchaser.
# Form H [See section 10(l)(b)(v) and rule 8] Receipt Received from ............amount of loan........... on redemption of pledge, number........Interest Date. ----------- Total                 ----------- Signature of pawnbroker or his agent.
# Form I Certificate of The Pawnbroker or his Agent Under Rule 9 I certify that the above is a true copy of the account maintained under clause (a) of sub-section (1) of section 10 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), for the loan of Rs.......... taken by .........on...........(date) and that there are no alterations or erasures in the account (except the following). Signature of pawnbroker or his agent.


def generate_pdf(content, filename):
    # Create a SimpleDocTemplate
    doc = SimpleDocTemplate(filename, pagesize=letter)

    # Get the sample stylesheet
    styles = getSampleStyleSheet()

    # Create a list to hold the flowable elements
    flowables = []

    # Create a Paragraph object and add it to the flowables list
    flowables.append(Paragraph(content, styles["Normal"]))

    # Add a spacer for spacing
    flowables.append(Spacer(1, 12))

    # Build the PDF
    doc.build(flowables)


# Define the content for each form
form_d4_content = """
                    <b>Form D-4 [See section 8(7) and rule 6(1)]</b><br/>
                    <b>Declaration by Person Claiming to Be Owners of pledge</b><br/>
                    I,........of.......in pursuance of sub-section (7) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the owner of the article/articles described below, pawned at shop of......... pawnbroker and that the pledge in respect of the article/articles was pawned without my knowledge or authority.<br/>
                    <br/>
                    The article/articles above referred to is/are of the following description:<br/>
                    1...........<br/>
                    2...........<br/>
                    <br/>
                    Signature of person.<br/>
                    Designation.<br/>
                    Address.<br/>
                    Date.<br/>
                    <br/>
                    I,..........of.......in pursuance of sub-section (7) of section 8 of the Act, do solemnly and sincerely declare that I know the person making the foregoing declaration to be......... of............<br/>
                    <br/>
                    Signature of identifying person.<br/>
                    Designation.<br/>
                    Address.<br/>
                    Date.
                    """

form_d5_content = """
                    <b>Form D-5 [See second proviso to section 8(3) and rule 6(2)]</b><br/>
                    <b>Notice To The Pawner</b><br/>
                    Notice is hereby given that ............. claiming himself to be your agent /messenger has produced on............ the pawn Ticket No dated............... issued to you for the article /articles described below pawned by you at my shop and offered to redeem the pledge. I, ............. pawnbroker propose to allow his/her claim to redeem, the pledge. You are hereby required to state your objections, if any, in respect of the above proposal. If nothing is heard from you within two weeks after the date on which this notice would in the usual course of post reach you, the person claiming to be your messenger/ agent will be allowed to redeem the pledge.<br/>
                    <br/>
                    The article/articles above referred to is/are of the following description:<br/>
                    1...........<br/>
                    2...........<br/>
                    <br/>
                    Signature of pawnbroker.<br/>
                    Address.<br/>
                    Date.
                    """

form_d6_content = """
                    <b>Form D-6 [See section 8(5) and rule 6(2)]</b><br/>
                    <b>Notice of Assignment To Pawnbroker</b><br/>
                    Date.<br/>
                    Notice is hereby given that I, ......... of .......... have come into possession of the pawn ticket No............dated.........as the assignee of the pawner by him at the shop of pawnbroker. You are hereby required to recognize my claim and to allow me to redeem the pledge.<br/>
                    <br/>
                    The article/articles above referred to is/are of the following description:<br/>
                    Description of the article/articles.<br/>
                    <br/>
                    Signature of the person.<br/>
                    Designation.<br/>
                    Address.<br/>
                    Date.<br/>
                    To Pawnbroker at..........
                    """

form_d7_content = """
                    <b>Form D-7 [See section 8(5) and rule 6(2)]</b><br/>
                    <b>Notice To Pawner of Claim Made by Assignee</b><br/>
                    Notice is hereby given that............claiming himself to be your assignee has produced on ................ the pawn ticket No............. dated............. given to you in respect of the article /articles described below pawned by you at the shop of........pawnbroker and he offered to redeem the pledge. I,........pawnbroker, propose to recognize his claim and to allow him to redeem pledge. You are hereby required to intimate to me the objections, if any, to the proposal. If nothing is heard from you within two weeks after the date on which this notice would in the usual course of post reach you, it will be presumed that you have no objection to the proposal and the claimant will be recognised as your assignee and allowed to redeem the pledge.<br/>
                    <br/>
                    The article/articles above referred to is /are of the following description.<br/>
                    Description of the article/articles<br/>
                    ............<br/>
                    ............<br/>
                    <br/>
                    Signature of the pawnbroker.<br/>
                    Address.<br/>
                    Date.
                    """

form_d8_content = """
                <b>Form D-8 [See section 8(7) and rule 6(2)]</b><br/>
                <b>Notice To Pawner of Claim by Owner of Pledge</b><br/>
                Date.<br/>
                Notice is hereby given that..........claims to the owner of the pledge in respect of the article /articles described below pawned at the shop........ of...........pawnbroker, and covered by pawn ticket No.............dated........... alleges that the pledge was pawned without his knowledge and authority. You are hereby required to intimate in writing whether you have any objection to the claim.......... or to the articles pledged by you. If no communication is received in writing within two weeks after the date on which it would in the usual course of post reach you, it will be presumed that you do not object to the claim made by the said.......... and he will be recognized as the legitimate owner of the article/articles and will be allowed to redeem the pledge.<br/>
                <br/>
                The article/articles above referred to is/are of the following description:<br/>
                Description of the article/articles.<br/>
                .......................<br/>
                .......................<br/>
                .......................<br/>
                <br/>
                Signature of the pawnbroker.<br/>
                Address.<br/>
                Date.
                """

form_g_content = """
                <b>Form G [See section 10(i)(b)(ii) and rule 8]</b><br/>
                <b>Sale Book of Pledges</b><br/>
                (Date and place of sale)<br/>
                (Name and place of business of auctioneer)<br/>
                1. Name of pledge as in the pledge book.<br/>
                2. Date of pawning.<br/>
                3. Name of pawner.<br/>
                4. Amount of loan.<br/>
                5. Amount for which pledge sold as stated by the auctioneer.<br/>
                6. Signature of the auctioneer or his agent.<br/>
                7. Name and address of purchaser.
                """

form_h_content = """
            <b>Form H <br />
            [See section 10(l)(b)(v) and rule 8]</b><br/>
            <b>Receipt</b>    P.B.L No: {{license__name}}<br/>
            <b>{{company_name}}</b><br/>
            <b></b>
            Received from ............amount of loan........... on redemption of pledge, number........Interest Date.<br/>
            -----------<br/>
            Total<br/>
            -----------<br/>
            Signature of pawnbroker or his agent.
            """

form_i_content = """
            <b>Form I Certificate of The Pawnbroker or his Agent Under Rule 9</b><br/>
            I certify that the above is a true copy of the account maintained under clause (a) of sub-section (1) of section 10 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), for the loan of Rs.......... taken by .........on...........(date) and that there are no alterations or erasures in the account (except the following).<br/>
            <br/>
            Signature of pawnbroker or his agent.
            """
# Define the content for each form with placeholders
# form_d4_content = """
# <b>Form D-4 [See section 8(7) and rule 6(1)]</b><br/>
# <b>Declaration by Person Claiming to Be Owners of pledge</b><br/>
# I, {name} of {address} in pursuance of sub-section (7) of section 8 of the Tamil Nadu Pawnbrokers Act, 1943 (Tamil Nadu Act XXIII of 1943), do solemnly and sincerely declare that I am the owner of the article/articles described below, pawned at shop of {pawnbroker} pawnbroker and that the pledge in respect of the article/articles was pawned without my knowledge or authority.<br/>
# <br/>
# The article/articles above referred to is/are of the following description:<br/>
# 1. {article1}<br/>
# 2. {article2}<br/>
# <br/>
# Signature of person.<br/>
# Designation.<br/>
# Address.<br/>
# Date.<br/>
# <br/>
# I, {identifier_name} of {identifier_address} in pursuance of sub-section (7) of section 8 of the Act, do solemnly and sincerely declare that I know the person making the foregoing declaration to be {declarant_name} of {declarant_address}.<br/>
# <br/>
# Signature of identifying person.<br/>
# Designation.<br/>
# Address.<br/>
# Date.
# # Define the variables
# variables = {
#     "name": "John Doe",
#     "address": "123 Main St",
#     "pawnbroker": "ABC Pawn Shop",
#     "article1": "Gold Ring",
#     "article2": "Silver Necklace",
#     "identifier_name": "Jane Smith",
#     "identifier_address": "456 Elm St",
#     "declarant_name": "John Doe",
#     "declarant_address": "123 Main St"
# }

# # Format the content with the variables
# formatted_content = form_d4_content.format(**variables)

# # Generate the PDF with the formatted content
# generate_pdf(formatted_content, "form_d4.pdf")
# Generate PDFs for each form
# generate_pdf(form_d4_content, "form_d4.pdf")
# generate_pdf(form_d5_content, "form_d5.pdf")
# generate_pdf(form_d6_content, "form_d6.pdf")
# generate_pdf(form_d7_content, "form_d7.pdf")
# generate_pdf(form_d8_content, "form_d8.pdf")
# generate_pdf(form_g_content, "form_g.pdf")
# generate_pdf(form_h_content, "form_h.pdf")
# generate_pdf(form_i_content, "form_i.pdf")


def get_notice_pdf(selection=None):
    # TODO: paginate the pdf for better performance
    # TODO: add a progress bar
    # TODO: add page templates

    # Create a file-like buffer to receive PDF data.
    buffer = io.BytesIO()
    # Create the PDF object, using the buffer as its "file."
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    doc.title = "Notice-Group"

    # Define styles for the paragraphs
    styles = getSampleStyleSheet()
    top_style = ParagraphStyle(
        name="Normal_CENTER",
        parent=styles["Normal"],
        fontName="Helvetica",
        wordWrap="LTR",
        alignment=TA_CENTER,
        fontSize=12,
        leading=13,
        textColor=colors.black,
        borderPadding=0,
        leftIndent=0,
        rightIndent=0,
        spaceAfter=0,
        spaceBefore=0,
        splitLongWords=True,
        spaceShrinkage=0.05,
    )

    # Main story list
    story = []
    spacer = Spacer(0, 0.25 * inch)
    simple_tblstyle = TableStyle(
        [
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
        ]
    )

    # Iterate over selected loans
    # Use 'borrower' for GivenLoan, fallback to 'customer' for legacy
    def get_party(obj):
        return getattr(obj, "borrower", None) or getattr(obj, "customer", None)

    for customer, loans in groupby(selection, key=get_party):
        # Grouped loans
        loans = list(loans)

        # Append paragraphs to the story
        story.extend(
            [
                spacer,
                Paragraph("TAMILNADU PAWNBROKERS ACT, 1943", top_style),
                spacer,
                Paragraph("NOTICE TO REDEEM PLEDGE", styles["Heading1"]),
                spacer,
                Paragraph(f"To,<br/>{customer}", styles["Normal"]),
                spacer,
                Paragraph(
                    "Notice is hereby given that the Pledge of the following article(s) is now "
                    "at the Pawn Broker named below, and that unless the same is redeemed within "
                    "30 days from the date hereof, it will be sold by public auction at the Pawn "
                    "Broker's place of business, without further notice to the Pledger or his agent."
                ),
                spacer,
                Paragraph(
                    f"<br/>Name of Pawn Broker: {loans[0].series.license.shopname}",
                    styles["Normal"],
                ),
                Paragraph("<br/>Description of Articles Pledged:", styles["Normal"]),
            ]
        )

        # Create table
        table_data = [["#", "Loan ID", "Created", "Item Weight", "Item Description"]]
        table_data.extend(
            [
                [
                    i + 1,
                    loan.loan_id,
                    loan.loan_date.date(),
                    loan.formatted_weight(),
                    item.itemdesc,
                ]
                for i, (loan, item) in enumerate(
                    ((loan, item) for loan in loans for item in loan.loanitems.all())
                )
            ]
        )

        # Add table to the story
        f = Table(table_data)
        f.setStyle(simple_tblstyle)
        story.extend([spacer, f, PageBreak()])

    # Save the PDF and return the response
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def print_noticegroup(selection=None):
    pdf = get_notice_pdf(selection)
    response = HttpResponse(pdf, content_type="application/pdf")
    filename = "Notice-Group.pdf"
    content = "inline; filename='%s'" % (filename)
    download = request.GET.get("download")
    if download:
        content = "attachment; filename='%s'" % (filename)
    response["Content-Disposition"] = content
    return response


def generate_qr_code(data):
    # Generate QR code using ReportLab's QRCodeWidget
    from reportlab.graphics import renderPM
    qr_code = qr.QrCodeWidget(data)
    qr_code.barWidth = 2 * inch  # Width of the QR code
    qr_code.barHeight = 2 * inch  # Height of the QR code
    qr_code.qrVersion = 1

    # Place the QR code in a drawing
    drawing = Drawing(2 * inch, 2 * inch)
    drawing.add(qr_code)

    # Render the drawing to a PNG image in memory
    buffer = BytesIO()
    renderPM.drawToFile(drawing, buffer, fmt="PNG")
    buffer.seek(0)
    return buffer


def draw_qr_code(loan_id, canvas, x_offset, y_offset, label_width):
    """
    Generates a QR code for the given loan_id and draws it on the provided canvas.

    Parameters:
    - loan_id: The ID of the loan to generate the QR code for.
    - canvas: The ReportLab canvas to draw the QR code on.
    - x_offset: The x-coordinate offset for positioning the QR code.
    - y_offset: The y-coordinate offset for positioning the QR code.
    - label_width: The width of the label to help position the QR code.
    """
    # Create QR code widget
    qr_code = qr.QrCodeWidget(loan_id)
    bounds = qr_code.getBounds()
    qr_width = bounds[2] - bounds[0]
    qr_height = bounds[3] - bounds[1]

    # Create a drawing object with the QR code
    d = Drawing(45, 45, transform=[45.0 / qr_width, 0, 0, 45.0 / qr_height, 0, 0])
    d.add(qr_code)

    # Calculate QR code position
    qr_x_offset = x_offset + label_width - 55
    qr_y_offset = y_offset - 55

    # Draw the QR code on the canvas
    renderPDF.draw(d, canvas, qr_x_offset, qr_y_offset)


def print_labels_pdf(loans, labels_per_row=3, labels_per_column=10):
    # Page size for A4
    page_width, page_height = A4
    label_width = page_width / labels_per_row
    label_height = page_height / labels_per_column

    # Create a file-like buffer to receive PDF data.
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Draw dotted lines for cutting
    c.setDash(1, 2)  # Set dash pattern: 1 point on, 2 points off
    for row in range(labels_per_column):
        y = (
            page_height - row * label_height - 10
        )  # Move the horizontal lines a little lower
        c.line(0, y, page_width, y)  # Horizontal lines

    for col in range(labels_per_row):
        x = col * label_width
        c.line(x, 0, x, page_height)  # Vertical lines

    c.setDash()  # Reset to solid lines

    for i, loan in enumerate(loans):
        # Calculate the position for each label
        row = i // labels_per_row
        col = i % labels_per_row
        x_offset = col * label_width
        y_offset = (
            page_height - (row + 1) * label_height + 60
        )  # Adjust y_offset to reduce space between rows

        # Draw loan details in the first column of the label
        details_x_offset = x_offset + 10
        details_y_offset = y_offset - 10
        c.setFont("Helvetica-Bold", 10)  # Increase font size to 10
        c.drawString(details_x_offset, details_y_offset, f"Loan ID: {loan.loan_id}")
        c.drawString(
            details_x_offset, details_y_offset - 10, f"Date: {loan.loan_date.date()}"
        )
        c.drawString(
            details_x_offset, details_y_offset - 20, f"Amount: {loan.loan_amount}"
        )
        c.drawString(
            details_x_offset,
            details_y_offset - 30,
            f"Weight: {loan.formatted_weight(joiner=', ')}",
        )
        c.drawString(
            details_x_offset, details_y_offset - 40, f"Customer: {loan.customer.name}"
        )
        c.drawString(details_x_offset, details_y_offset - 50, f"Item: {loan.item_desc}")

        # Draw QR code in the second column of the label
        # qr_code = qr.QrCodeWidget(loan.loan_id)
        # bounds = qr_code.getBounds()
        # qr_width = bounds[2] - bounds[0]
        # qr_height = bounds[3] - bounds[1]
        # d = Drawing(45, 45, transform=[45.0 / qr_width, 0, 0, 45.0 / qr_height, 0, 0])
        # d.add(qr_code)
        # qr_x_offset = x_offset + label_width - 55
        # qr_y_offset = y_offset - 55
        # renderPDF.draw(d, c, qr_x_offset, qr_y_offset)
        label_width = page_width / labels_per_row
        draw_qr_code(loan.loan_id, c, x_offset, y_offset, label_width)

        # Start a new page if the current page is full
        if (i + 1) % (labels_per_row * labels_per_column) == 0:
            c.showPage()

    c.save()

    # Create a new HTTP response with PDF data.
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = "inline; filename=labels.pdf"
    return response

from reportlab.platypus import KeepInFrame


def draw_text_with_fitting(canvas, text, x, y, max_width, max_height):
    # Create a Paragraph object with the given text
    styles = getSampleStyleSheet()
    style = styles["Normal"]
    paragraph = Paragraph(text, style)

    # Create a KeepInFrame object to fit the paragraph within the specified dimensions
    fitting_frame = KeepInFrame(max_width, max_height, content=[paragraph])

    # Draw the fitting frame on the canvas at the specified position
    fitting_frame.wrapOn(canvas, max_width, max_height)
    fitting_frame.drawOn(canvas, x, y)
