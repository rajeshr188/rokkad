"""Girvi loan ticket PDF rendering.

This module owns the GivenLoan -> PDF ticket flow driven by `LoanTemplate`
and `TemplateFrame`. The logic lives inside the `girvi` app because it is
business-specific and tightly coupled to Girvi models and template metadata.
"""

import io
import logging
import os

import fitz
import qrcode
from django.http import HttpResponse
from num2words import num2words
from PIL import Image as PILImage
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, KeepInFrame, Paragraph, Table, TableStyle

from apps.tenant_apps.girvi.models.template import LoanTemplate, TemplateFrame

logger = logging.getLogger(__name__)


def merge_pdfs(base_template_bytes, content_pdf_bytes):
    """Overlay a content PDF onto the first page of a base template."""
    base_doc = fitz.open(stream=base_template_bytes, filetype="pdf")
    content_doc = fitz.open(stream=content_pdf_bytes, filetype="pdf")

    base_page = base_doc[0]
    base_page.show_pdf_page(base_page.rect, content_doc, 0, overlay=True)

    output_buffer = base_doc.write()
    base_doc.close()
    content_doc.close()
    return output_buffer


def merge_pdfs_double_sided(front_template, content, back_template):
    """Build a two-page PDF for double-sided printing."""
    try:
        output_doc = fitz.open()

        front_doc = fitz.open("pdf", front_template)
        content_doc = fitz.open("pdf", content)
        front_page = front_doc[0]
        front_page.show_pdf_page(front_page.rect, content_doc, 0, overlay=True)
        output_doc.insert_pdf(front_doc, from_page=0, to_page=0)

        back_doc = fitz.open("pdf", back_template)
        output_doc.insert_pdf(back_doc)

        output_buffer = io.BytesIO()
        output_doc.save(output_buffer)
        merged_content = output_buffer.getvalue()

        front_doc.close()
        content_doc.close()
        back_doc.close()
        output_doc.close()
        output_buffer.close()
        return merged_content
    except Exception as exc:
        logger.exception("Error creating double-sided PDF: %s", exc)
        return None


def merge_multiple_pdfs(pdf_contents):
    """Merge several PDF byte strings into a single PDF."""
    try:
        output_doc = fitz.open()
        for content in pdf_contents:
            doc = fitz.open("pdf", content)
            output_doc.insert_pdf(doc)
            doc.close()

        output_buffer = io.BytesIO()
        output_doc.save(output_buffer)
        merged_content = output_buffer.getvalue()

        output_doc.close()
        output_buffer.close()
        return merged_content
    except Exception as exc:
        logger.exception("Error merging multiple PDFs: %s", exc)
        return None


def merge_pdfs_side_by_side(left_pdf, right_pdf):
    """Place two A5 PDFs side by side on a single A4 landscape page."""
    try:
        output_doc = fitz.open()
        width = A4[1]
        height = A4[0]
        output_page = output_doc.new_page(width=width, height=height)

        left_doc = fitz.open("pdf", left_pdf)
        right_doc = fitz.open("pdf", right_pdf)

        left_rect = fitz.Rect(0, 0, width / 2, height)
        right_rect = fitz.Rect(width / 2, 0, width, height)

        output_page.show_pdf_page(left_rect, left_doc, 0, rotate=0)
        output_page.show_pdf_page(right_rect, right_doc, 0, rotate=0)

        output_buffer = io.BytesIO()
        output_doc.save(output_buffer)
        merged_content = output_buffer.getvalue()

        left_doc.close()
        right_doc.close()
        output_doc.close()
        output_buffer.close()
        return merged_content
    except Exception as exc:
        logger.exception("Error merging PDFs side by side: %s", exc)
        return None


def _resolve_party(loan):
    return getattr(loan, "borrower", None) or getattr(loan, "customer", None)


def _path_or_none(file_obj):
    return getattr(file_obj, "path", None) if file_obj else None


def _first_loan_item(loan):
    return loan.loanitems.first() if hasattr(loan, "loanitems") else None


def _has_template_file(template_file):
    return bool(template_file and getattr(template_file, "name", None))


def _call_or_value(value, *args, **kwargs):
    return value(*args, **kwargs) if callable(value) else value


def _loan_items(loan):
    loanitems = getattr(loan, "loanitems", None)
    if not loanitems or not hasattr(loanitems, "all"):
        return []
    return list(loanitems.all())


def _get_item_description(loan):
    item_desc = getattr(loan, "item_desc", None)
    if item_desc not in (None, ""):
        return _call_or_value(item_desc)

    description = getattr(loan, "get_item_description", None)
    if description not in (None, ""):
        resolved = _call_or_value(description)
        if resolved not in (None, ""):
            return resolved

    return ", ".join(
        filter(None, [getattr(item, "itemdesc", "") for item in _loan_items(loan)])
    )


def _get_weight_text(loan, joiner=", "):
    formatter = getattr(loan, "formatted_weight", None)
    if formatter:
        return _call_or_value(formatter, joiner=joiner)

    summary = _call_or_value(getattr(loan, "get_weight_summary", None)) or []
    parts = [
        f"{item.get('itemtype', '')} {item.get('total_weight', 0)}g"
        for item in summary
        if item.get("total_weight") not in (None, "")
    ]
    return joiner.join(parts)


def _get_pure_text(loan, joiner=", "):
    legacy_formatter = getattr(loan, "formatted_pure", None)
    if legacy_formatter:
        return _call_or_value(legacy_formatter, joiner=joiner)

    refactored_formatter = getattr(loan, "formatted_pure_weight", None)
    if refactored_formatter:
        return _call_or_value(refactored_formatter, joiner=joiner)

    summary = _call_or_value(getattr(loan, "get_weight_summary", None)) or []
    parts = [
        f"{item.get('itemtype', '')} {item.get('pure_weight', 0)}g"
        for item in summary
        if item.get("pure_weight") not in (None, "")
    ]
    return joiner.join(parts)


def _get_current_value(loan):
    legacy_method = getattr(loan, "get_current_value", None)
    if callable(legacy_method):
        return legacy_method()

    current_value = getattr(loan, "current_value", None)
    if current_value is not None:
        return _call_or_value(current_value)

    return sum(
        item.current_value()
        for item in _loan_items(loan)
        if hasattr(item, "current_value") and callable(item.current_value)
    )


def _build_label_text(loan, party):
    return (
        f"{loan.loan_id} - {loan.loan_date.strftime('%d-%m-%Y')} <br/>"
        f"{loan.loan_amount} - {_get_weight_text(loan)} <br/>"
        f"{party.name if party else ''} - {_get_item_description(loan)}"
    )


def _build_frame_context(loan, party):
    return {
        "loan": loan,
        "party": party,
        "first_item": _first_loan_item(loan),
        "default_pic": (
            party.get_default_pic()
            if party and hasattr(party, "get_default_pic")
            else None
        ),
    }


def _frame_license_no(context):
    return context["loan"].series.license.license_number


def _frame_license_name(context):
    return context["loan"].series.license.shopname


def _frame_license_address(context):
    return context["loan"].series.license.address


def _frame_license_phone(context):
    return getattr(context["loan"].series.license, "phone", "")


def _frame_license_propreitor(context):
    return f"Prop:{context['loan'].series.license.propreitor}"


def _frame_logo(context):
    return _path_or_none(
        getattr(getattr(context["loan"].series, "license", None), "logo", None)
    )


def _frame_customer_pic(context):
    return _path_or_none(context.get("default_pic"))


def _frame_loanitem_pic(context):
    return _path_or_none(getattr(context.get("first_item"), "pic", None))


def _frame_loan_id(context):
    return context["loan"].loan_id


def _frame_loan_date(context):
    return context["loan"].loan_date.strftime("%d-%m-%Y")


def _frame_customer_name(context):
    party = context.get("party")
    return party.name if party else ""


def _frame_customer_info(context):
    party = context.get("party")
    if not party:
        return ""
    return (
        f"{party.name}, {party.get_relatedas_display()} {party.relatedto}<br/>"
        f"{party.get_address()}<br/>Ph: {party.get_contactno()}"
    )


def _frame_loan_desc(context):
    loan = context["loan"]
    return "<br/>".join(
        [
            f"{index + 1}) {item.itemdesc}, Qty: {item.quantity}"
            for index, item in enumerate(_loan_items(loan))
        ]
    )


def _frame_weight(context):
    return f"{_get_weight_text(context['loan'], joiner=', ')}"


def _frame_pure(context):
    return f"{_get_pure_text(context['loan'], joiner=', ')}"


def _frame_value(context):
    return f"{_get_current_value(context['loan'])}"


def _frame_address(context):
    party = context.get("party")
    return party.get_address() if party and hasattr(party, "get_address") else ""


def _frame_phone(context):
    party = context.get("party")
    return party.get_contactno() if party and hasattr(party, "get_contactno") else ""


def _frame_amount(context):
    return f"{context['loan'].loan_amount}"


def _frame_amount_words(context):
    return num2words(context["loan"].loan_amount, lang="en_IN") + " rupees only"


def _frame_loan_qr(context):
    return context["loan"].loan_id


def _frame_label(context):
    return _build_label_text(context["loan"], context.get("party"))


FRAME_VALUE_PROVIDERS = {
    "license_no": _frame_license_no,
    "license_name": _frame_license_name,
    "license_address": _frame_license_address,
    "license_phone": _frame_license_phone,
    "license_propreitor": _frame_license_propreitor,
    "logo": _frame_logo,
    "customer_pic": _frame_customer_pic,
    "loanitem_pic": _frame_loanitem_pic,
    "loan_id": _frame_loan_id,
    "loan_date": _frame_loan_date,
    "customer_name": _frame_customer_name,
    "customer_info": _frame_customer_info,
    "loan_desc": _frame_loan_desc,
    "weight": _frame_weight,
    "pure": _frame_pure,
    "value": _frame_value,
    "address": _frame_address,
    "phone": _frame_phone,
    "amount": _frame_amount,
    "amount_words": _frame_amount_words,
    "loan_qr": _frame_loan_qr,
    "label": _frame_label,
}


def resolve_frame_value(frame_name, loan, party=None, context=None):
    active_context = context or _build_frame_context(loan, party)
    provider = FRAME_VALUE_PROVIDERS.get(frame_name)
    if not provider:
        return None
    return provider(active_context)


def _build_frame_mapping(loan, party):
    context = _build_frame_context(loan, party)
    return {
        frame_name: (lambda fn=frame_name: resolve_frame_value(fn, loan, party, context))
        for frame_name in FRAME_VALUE_PROVIDERS
    }


def _render_text_frame(reportlab_frame, frame, frame_data, canvas_obj):
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


def _render_image_frame(reportlab_frame, frame_data, canvas_obj):
    if not frame_data or not os.path.exists(frame_data):
        return

    img = PILImage.open(frame_data)
    img_w, img_h = img.size
    aspect = img_w / float(img_h)

    if reportlab_frame._width / float(reportlab_frame._height) > aspect:
        width = reportlab_frame._height * aspect
        height = reportlab_frame._height
    else:
        width = reportlab_frame._width
        height = reportlab_frame._width / aspect

    x_pos = reportlab_frame._x + (reportlab_frame._width - width) / 2
    y_pos = reportlab_frame._y + (reportlab_frame._height - height) / 2
    canvas_obj.drawImage(
        frame_data,
        x_pos,
        y_pos,
        width=width,
        height=height,
        preserveAspectRatio=True,
    )


def _render_qr_frame(reportlab_frame, frame_data, canvas_obj):
    qr_img = qrcode.make(frame_data)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    qr_width = reportlab_frame._width * 0.9
    qr_height = reportlab_frame._height * 0.9
    qr_x = reportlab_frame._x + (reportlab_frame._width - qr_width) / 2
    qr_y = reportlab_frame._y + (reportlab_frame._height - qr_height) / 2

    canvas_obj.drawImage(
        ImageReader(qr_buffer),
        qr_x,
        qr_y,
        width=qr_width,
        height=qr_height,
        preserveAspectRatio=True,
    )
    qr_buffer.close()


def _render_table_frame(reportlab_frame, loan, canvas_obj):
    rows = [["Description"]]
    rows.extend(
        [[f"{index + 1}) {item.itemdesc} (Qty: {item.quantity})"] for index, item in enumerate(loan.loanitems.all())]
    )
    if len(rows) == 1:
        return

    table = Table(rows)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    keep_frame = KeepInFrame(
        reportlab_frame._width,
        reportlab_frame._height,
        [table],
        mode="shrink",
    )
    reportlab_frame.addFromList([keep_frame], canvas_obj)


def _render_frame(frame, loan, party, canvas_obj, frame_mapping=None, x_offset=0, y_offset=0):
    frame_mapping = frame_mapping or _build_frame_mapping(loan, party)
    frame_data = frame_mapping.get(frame.frame_name, lambda: None)()
    if not frame_data and frame.field_type != "table":
        return

    reportlab_frame = Frame(
        x_offset + float(frame.x_pos) * cm,
        y_offset + float(frame.y_pos) * cm,
        float(frame.width) * cm,
        float(frame.height) * cm,
        showBoundary=frame.show_boundary,
    )

    if frame.field_type == "text":
        _render_text_frame(reportlab_frame, frame, frame_data, canvas_obj)
    elif frame.field_type == "image":
        _render_image_frame(reportlab_frame, frame_data, canvas_obj)
    elif frame.field_type == "qr":
        _render_qr_frame(reportlab_frame, frame_data, canvas_obj)
    elif frame.field_type == "table":
        _render_table_frame(reportlab_frame, loan, canvas_obj)


def _resolve_template(template_id=None):
    return (
        LoanTemplate.objects.filter(id=template_id, is_active=True).first()
        if template_id
        else LoanTemplate.objects.filter(is_default=True, is_active=True).first()
    )


def _render_page_content_to_canvas(template, loan, party, canvas_obj, template_type, x_offset=0):
    frames = template.templateframe_set.filter(
        template_type__in=[template_type, TemplateFrame.TemplateType.BOTH]
    )
    frame_mapping = _build_frame_mapping(loan, party)

    for frame in frames:
        try:
            _render_frame(
                frame,
                loan,
                party,
                canvas_obj,
                frame_mapping=frame_mapping,
                x_offset=x_offset,
            )
        except Exception:
            logger.exception(
                "Error rendering frame '%s' for loan=%s template_id=%s print_option=%s field_type=%s template_type=%s",
                getattr(frame, "frame_name", None),
                getattr(loan, "loan_id", None),
                getattr(template, "pk", None),
                getattr(template, "print_option", None),
                getattr(frame, "field_type", None),
                getattr(frame, "template_type", None),
            )
            raise


def _build_canvas_pdf(page_size, template, loan, party, template_type):
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=page_size)
    _render_page_content_to_canvas(template, loan, party, pdf_canvas, template_type)
    pdf_canvas.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _blank_pdf(page_size):
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=page_size)
    pdf_canvas.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _merge_with_front_template(template_file, content_pdf):
    return (
        merge_pdfs(template_file.read(), content_pdf)
        if _has_template_file(template_file)
        else content_pdf
    )


def _merge_double_sided_if_available(front_template, content_pdf, back_template):
    if _has_template_file(front_template) and _has_template_file(back_template):
        return merge_pdfs_double_sided(
            front_template.read(),
            content_pdf,
            back_template.read(),
        )
    return content_pdf


def _render_side_by_side_a4_output(template, loan, party, include_back_page=False):
    page_width, page_height = landscape(A4)
    half_page_size = (page_width / 2, page_height)

    original_pdf = _build_canvas_pdf(
        half_page_size,
        template,
        loan,
        party,
        TemplateFrame.TemplateType.ORIGINAL,
    )
    duplicate_pdf = _build_canvas_pdf(
        half_page_size,
        template,
        loan,
        party,
        TemplateFrame.TemplateType.DUPLICATE,
    )

    front_page = merge_pdfs_side_by_side(
        _merge_with_front_template(template.base_template, original_pdf),
        _merge_with_front_template(template.dup_template, duplicate_pdf),
    )

    if (
        include_back_page
        and _has_template_file(template.terms_template)
        and _has_template_file(template.form_d3_template)
    ):
        back_page = merge_pdfs_side_by_side(
            template.terms_template.read(),
            template.form_d3_template.read(),
        )
        return merge_multiple_pdfs([front_page, back_page])

    return front_page


def _render_standard_a5_output(template, loan, party):
    page_size = (A5[0], A5[1])
    print_option = template.print_option

    if print_option == "O":
        content_pdf = _build_canvas_pdf(
            page_size,
            template,
            loan,
            party,
            TemplateFrame.TemplateType.ORIGINAL,
        )
        return _merge_with_front_template(template.base_template, content_pdf)

    if print_option == "OT":
        content_pdf = _build_canvas_pdf(
            page_size,
            template,
            loan,
            party,
            TemplateFrame.TemplateType.ORIGINAL,
        )
        return _merge_double_sided_if_available(
            template.base_template,
            content_pdf,
            template.terms_template,
        )

    if print_option == "D":
        content_pdf = _build_canvas_pdf(
            page_size,
            template,
            loan,
            party,
            TemplateFrame.TemplateType.DUPLICATE,
        )
        return _merge_with_front_template(template.dup_template, content_pdf)

    if print_option == "DF":
        content_pdf = _build_canvas_pdf(
            page_size,
            template,
            loan,
            party,
            TemplateFrame.TemplateType.DUPLICATE,
        )
        return _merge_double_sided_if_available(
            template.dup_template,
            content_pdf,
            template.form_d3_template,
        )

    if print_option == "BS":
        original_pdf = _build_canvas_pdf(
            page_size,
            template,
            loan,
            party,
            TemplateFrame.TemplateType.ORIGINAL,
        )
        duplicate_pdf = _build_canvas_pdf(
            page_size,
            template,
            loan,
            party,
            TemplateFrame.TemplateType.DUPLICATE,
        )
        return merge_multiple_pdfs(
            [
                _merge_with_front_template(template.base_template, original_pdf),
                _merge_with_front_template(template.dup_template, duplicate_pdf),
            ]
        )

    if print_option == "BD":
        original_pdf = _build_canvas_pdf(
            page_size,
            template,
            loan,
            party,
            TemplateFrame.TemplateType.ORIGINAL,
        )
        duplicate_pdf = _build_canvas_pdf(
            page_size,
            template,
            loan,
            party,
            TemplateFrame.TemplateType.DUPLICATE,
        )
        return merge_multiple_pdfs(
            [
                _merge_double_sided_if_available(
                    template.base_template,
                    original_pdf,
                    template.terms_template,
                ),
                _merge_double_sided_if_available(
                    template.dup_template,
                    duplicate_pdf,
                    template.form_d3_template,
                ),
            ]
        )

    return _blank_pdf(page_size)


def build_loan_ticket_pdf(loan, template_id=None):
    """Generate a Girvi loan ticket PDF from `LoanTemplate` frame metadata."""
    template = None
    try:
        template = _resolve_template(template_id=template_id)
        if not template:
            return None

        party = _resolve_party(loan)
        if not party:
            logger.error("Loan object has neither 'borrower' nor 'customer' attribute")
            return None

        if template.print_option in ["BA", "BDA"]:
            return _render_side_by_side_a4_output(
                template,
                loan,
                party,
                include_back_page=template.print_option == "BDA",
            )

        return _render_standard_a5_output(template, loan, party)
    except Exception as exc:
        logger.exception(
            "Error generating PDF for loan=%s template_id=%s print_option=%s: %s",
            getattr(loan, "loan_id", None),
            getattr(template, "pk", template_id),
            getattr(template, "print_option", None),
            exc,
        )
        return None


get_custom_jcl = build_loan_ticket_pdf


def grid_template(page_size=A5, grid_spacing_cm=1, show_margins=True, margin_cm=1):
    """Generate a measurement grid PDF for template design."""
    page_width, page_height = page_size
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=page_size)

    grid_color = (0.3, 0.3, 0.3)
    margin_color = (1, 0.8, 0.8)
    text_color = (0.3, 0.3, 0.3)

    pdf_canvas.setFont("Helvetica", 6)
    pdf_canvas.setStrokeColorRGB(*grid_color)
    pdf_canvas.setLineWidth(0.1)

    for x_pos in range(0, int(page_width), int(grid_spacing_cm * cm)):
        pdf_canvas.line(x_pos, 0, x_pos, page_height)
        pdf_canvas.setFillColorRGB(*text_color)
        pdf_canvas.drawString(x_pos + 2, 2, f"{x_pos / cm:.1f}")
        pdf_canvas.drawString(x_pos + 2, page_height - 8, f"{x_pos / cm:.1f}")

    for y_pos in range(0, int(page_height), int(grid_spacing_cm * cm)):
        pdf_canvas.line(0, y_pos, page_width, y_pos)
        pdf_canvas.setFillColorRGB(*text_color)
        pdf_canvas.drawString(2, y_pos + 2, f"{y_pos / cm:.1f}")
        pdf_canvas.drawString(page_width - 20, y_pos + 2, f"{y_pos / cm:.1f}")

    if show_margins:
        pdf_canvas.setStrokeColorRGB(*margin_color)
        pdf_canvas.setLineWidth(0.5)
        margin = margin_cm * cm
        pdf_canvas.line(margin, 0, margin, page_height)
        pdf_canvas.line(page_width - margin, 0, page_width - margin, page_height)
        pdf_canvas.line(0, page_height - margin, page_width, page_height - margin)
        pdf_canvas.line(0, margin, page_width, margin)

    pdf_canvas.setFillColorRGB(0, 0, 0)
    pdf_canvas.setFont("Helvetica", 8)
    pdf_canvas.drawString(
        10,
        page_height - 20,
        f"Page Size: {page_width / cm:.1f}cm x {page_height / cm:.1f}cm",
    )

    pdf_canvas.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def draw_qr_code(loan_id, pdf_canvas, x_offset, y_offset, label_width):
    """Render a QR code in the label grid."""
    qr_code = qr.QrCodeWidget(loan_id)
    bounds = qr_code.getBounds()
    qr_width = bounds[2] - bounds[0]
    qr_height = bounds[3] - bounds[1]

    drawing = Drawing(45, 45, transform=[45.0 / qr_width, 0, 0, 45.0 / qr_height, 0, 0])
    drawing.add(qr_code)

    qr_x_offset = x_offset + label_width - 55
    qr_y_offset = y_offset - 55
    renderPDF.draw(drawing, pdf_canvas, qr_x_offset, qr_y_offset)


def print_labels_pdf(loans, labels_per_row=3, labels_per_column=10):
    """Return an inline PDF response with printable loan labels."""
    page_width, page_height = A4
    label_width = page_width / labels_per_row
    label_height = page_height / labels_per_column

    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=A4)

    pdf_canvas.setDash(1, 2)
    for row in range(labels_per_column):
        y_pos = page_height - row * label_height - 10
        pdf_canvas.line(0, y_pos, page_width, y_pos)

    for col in range(labels_per_row):
        x_pos = col * label_width
        pdf_canvas.line(x_pos, 0, x_pos, page_height)

    pdf_canvas.setDash()

    for index, loan in enumerate(loans):
        row = index // labels_per_row
        col = index % labels_per_row
        x_offset = col * label_width
        y_offset = page_height - (row + 1) * label_height + 60

        details_x = x_offset + 10
        details_y = y_offset - 10
        party = _resolve_party(loan)

        pdf_canvas.setFont("Helvetica-Bold", 10)
        pdf_canvas.drawString(details_x, details_y, f"Loan ID: {loan.loan_id}")
        pdf_canvas.drawString(details_x, details_y - 10, f"Date: {loan.loan_date.date()}")
        pdf_canvas.drawString(details_x, details_y - 20, f"Amount: {loan.loan_amount}")
        pdf_canvas.drawString(
            details_x,
            details_y - 30,
            f"Weight: {_get_weight_text(loan, joiner=', ')}",
        )
        pdf_canvas.drawString(
            details_x,
            details_y - 40,
            f"Customer: {party.name if party else ''}",
        )
        pdf_canvas.drawString(
            details_x,
            details_y - 50,
            f"Item: {_get_item_description(loan)}",
        )

        draw_qr_code(loan.loan_id, pdf_canvas, x_offset, y_offset, label_width)

        if (index + 1) % (labels_per_row * labels_per_column) == 0:
            pdf_canvas.showPage()

    pdf_canvas.save()
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = "inline; filename=labels.pdf"
    return response
