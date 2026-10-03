"""One fixed-size, audited label for a loan's complete collateral list."""
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from django.db import transaction
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.tenant_apps.loans.models import PawnLoan, PawnCollateralItem, PawnCollateralLabelIssue, current_tenant_workspace_id
from .action_access import require_loan_action
from .collateral_media import PawnCollateralMediaError


@transaction.atomic
def render_loan_collateral_label(loan_id, *, qr_target, action, actor):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnCollateralMediaError("Loan labels require an active workspace.")
    try:
        loan = PawnLoan.objects.select_for_update().select_related("borrower").get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise PawnCollateralMediaError("Loan was not found in the active workspace.") from exc
    require_loan_action(loan, actor, "data.view")
    try:
        action = PawnCollateralLabelIssue.Action(action)
    except ValueError as exc:
        raise PawnCollateralMediaError("Unknown collateral-label action.") from exc
    items = list(PawnCollateralItem.objects.select_for_update().filter(loan=loan, workspace_id=workspace_id).order_by("pk"))
    content = loan_collateral_label_pdf(loan, items, qr_target)
    digest = sha256(content).hexdigest()
    # Each included identity points to the same combined PDF and loan QR target.
    for item in items:
        PawnCollateralLabelIssue.objects.create(collateral_item=item, action=action,
            qr_target=qr_target, payload_sha256=digest, issued_by=actor)
    return content


def _fit_story(text, rect, maximum):
    fonts = Path(__file__).resolve().parents[4] / "static/fonts"
    for size in range(maximum, 5, -1):
        css = f"""@font-face {{font-family: label; src: url(NotoSansTamil-Regular.ttf);}}
            body {{margin:0; font-family:label,sans-serif; font-size:{size}pt; line-height:1.15;}}
            p {{margin:0 0 2pt; overflow-wrap:break-word;}}"""
        story = fitz.Story(html=text, user_css=css, archive=fitz.Archive(str(fonts)))
        more, filled = story.place(rect)
        if not more and fitz.Rect(filled).x1 <= rect.x1 + .1:
            return story
    raise PawnCollateralMediaError(
        "The complete collateral details do not fit a 100 x 60 mm label at a readable size. "
        "Use the individual item labels; no text has been omitted."
    )


def loan_collateral_label_pdf(loan, items, qr_target):
    """Render without persistence, also used for read-only verification."""
    if not items:
        raise PawnCollateralMediaError("This loan has no collateral to label.")
    if any(item.loan_id != loan.pk or item.workspace_id != loan.workspace_id for item in items):
        raise PawnCollateralMediaError("Every label item must belong to this loan and workspace.")
    totals = defaultdict(lambda: Decimal("0"))
    labels = {}
    rows = []
    for index, item in enumerate(items, 1):
        totals[item.metal] += item.net_weight
        labels[item.metal] = item.get_metal_display()
        quantity = str(item.quantity) if item.quantity is not None else "not recorded"
        rows.append(f"{index}. {item.description} ({item.get_metal_display()}; qty {quantity})")
    rows.append("Net weight totals:")
    rows.extend(f"{labels[metal]}: {weight:.4f} g" for metal, weight in sorted(totals.items()))
    paragraphs = lambda values: "".join("<p>" + escape(str(value)).replace("\n", "<br/>") + "</p>" for value in values)
    page_rect = fitz.Rect(0, 0, 100 * mm, 60 * mm)
    header = _fit_story(paragraphs([f"{loan.loan_number} | {loan.loan_date:%d/%m/%Y}", loan.borrower.display_name]), fitz.Rect(4*mm, 3*mm, 96*mm, 14*mm), 10)
    body = _fit_story(paragraphs(rows), fitz.Rect(4*mm, 17*mm, 67*mm, 55*mm), 9)
    summary = _fit_story(paragraphs([f"{len(items)} entries", "All recorded collateral", "Scan for current custody"]), fitz.Rect(72*mm, 16*mm, 97*mm, 30*mm), 7)
    buffer = BytesIO()
    writer = fitz.DocumentWriter(buffer)
    device = writer.begin_page(page_rect)
    for story in (header, body, summary):
        story.draw(device)
    writer.end_page(); writer.close()
    qr = QrCodeWidget(qr_target)
    bounds = qr.getBounds(); size = 25 * mm
    drawing = Drawing(size, size, transform=[size/(bounds[2]-bounds[0]), 0, 0, size/(bounds[3]-bounds[1]), 0, 0])
    drawing.add(qr)
    qr_buffer = BytesIO(); qr_canvas = canvas.Canvas(qr_buffer, pagesize=(size, size))
    renderPDF.draw(drawing, qr_canvas, 0, 0); qr_canvas.showPage(); qr_canvas.save()
    with fitz.open(stream=buffer.getvalue(), filetype="pdf") as pdf, fitz.open(stream=qr_buffer.getvalue(), filetype="pdf") as qr_pdf:
        pdf[0].show_pdf_page(fitz.Rect(72*mm, 31*mm, 97*mm, 56*mm), qr_pdf, 0)
        return pdf.tobytes(garbage=4, deflate=True)
