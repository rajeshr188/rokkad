"""Fixed-size Unicode custody labels, with complete text or an explicit refusal."""
from collections import defaultdict
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

import fitz
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.tenant_apps.loans.services.loan_collateral_label import _fit_story
from apps.tenant_apps.loans.services.collateral_media import PawnCollateralMediaError

VERSION = "khata-label-v1"


def _paragraphs(values):
    return "".join("<p>" + escape(str(v)).replace("\n", "<br/>") + "</p>" for v in values)


def _page(payload, items, target):
    rows = []
    totals = defaultdict(lambda: Decimal(0))
    for item in items:
        totals[item["metal"]] += Decimal(item["net_weight"])
        rows.append(f'{item["description"]} ({item["metal"].title()}; qty {item["quantity"]})')
        rows.append(f'Item: {item["public_id"]}')
        rows.append(f'Gross/net: {item["gross_weight"]}/{item["net_weight"]} g; purity {item["purity"]}%')
        rows.append(f'{item["custody"]} | Store: {item["storage_reference"]}')
    rows.append("Net totals: " + "; ".join(f"{m.title()} {v:.3f} g" for m, v in sorted(totals.items())))
    try:
        header = _fit_story(_paragraphs([f'Khata {payload["account_number"]}', payload["borrower"]["name"]]), fitz.Rect(4*mm, 3*mm, 96*mm, 14*mm), 10)
        body = _fit_story(_paragraphs(rows), fitz.Rect(4*mm, 16*mm, 67*mm, 56*mm), 9)
        note = _fit_story(_paragraphs([payload["as_of"], f'{len(items)} held item(s)', "Scan for current custody"]), fitz.Rect(72*mm, 16*mm, 97*mm, 30*mm), 7)
    except PawnCollateralMediaError as exc:
        raise ValueError("Complete khata collateral details do not fit a 100 x 60 mm label at the 6 pt minimum. "
            "Use individual labels. If one item still cannot fit, use its full collateral document; no text was omitted.") from exc
    output = BytesIO()
    writer = fitz.DocumentWriter(output)
    device = writer.begin_page(fitz.Rect(0, 0, 100*mm, 60*mm))
    for story in (header, body, note):
        story.draw(device)
    writer.end_page()
    writer.close()
    qr = QrCodeWidget(target)
    bounds = qr.getBounds()
    size = 25 * mm
    drawing = Drawing(size, size, transform=[size/(bounds[2]-bounds[0]), 0, 0, size/(bounds[3]-bounds[1]), 0, 0])
    drawing.add(qr)
    qr_buffer = BytesIO()
    qr_canvas = canvas.Canvas(qr_buffer, pagesize=(size, size))
    renderPDF.draw(drawing, qr_canvas, 0, 0)
    qr_canvas.showPage()
    qr_canvas.save()
    with fitz.open(stream=output.getvalue(), filetype="pdf") as pdf, fitz.open(stream=qr_buffer.getvalue(), filetype="pdf") as qr_pdf:
        pdf[0].show_pdf_page(fitz.Rect(72*mm, 31*mm, 97*mm, 56*mm), qr_pdf, 0)
        return pdf.tobytes(garbage=4, deflate=True)


def render_labels(payload):
    with fitz.open() as output:
        groups = [[item] for item in payload["items"]] if payload["mode"] in ("EACH", "SELECTED") else [payload["items"]]
        for group in groups:
            target = payload["origin"] + (group[0]["scan_path"] if payload["mode"] in ("EACH", "ONE", "SELECTED") else payload["scan_path"])
            content = _page(payload, group, target)
            with fitz.open(stream=content, filetype="pdf") as page:
                output.insert_pdf(page)
        return output.tobytes(garbage=4, deflate=True)
