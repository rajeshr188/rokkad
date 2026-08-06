"""ReportLab renderer for validated PawnLoan document layouts."""

import hashlib
import io
import json
from pathlib import Path
from dataclasses import dataclass
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A5, LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import fitz

from .assets import DocumentAssetError, validate_asset_set


@dataclass(frozen=True)
class LayoutRenderResult:
    pdf: bytes
    layout_hash: str
    payload_hash: str
    renderer_version: str
    page_size: str
    copy_mode: str
    asset_hashes: tuple[tuple[str, str], ...] = ()


class ConfigurableDocumentRenderer:
    VERSION = "layout-reportlab-v1"
    PAGE_SIZES = {"A4": A4, "A5": A5, "LETTER": LETTER}

    @classmethod
    def render(cls, payload, layout, *, preview=False, assets=()):
        if payload.document_type != layout.document_type:
            raise ValueError("Layout document type does not match the payload.")
        fields = {field.key: field for field in payload.fields}
        sections = {section.key: section for section in payload.sections}
        workspace_field = fields.get("workspace.source_id")
        try:
            workspace_id = int(str(workspace_field.value).split(":", 1)[1])
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise DocumentAssetError("Payload has no valid workspace asset boundary.") from exc
        asset_map = validate_asset_set(assets, workspace_id=workspace_id)
        required_assets = {block.asset_key for block in layout.blocks + layout.back_blocks if block.asset_key}
        if layout.background_asset_key:
            required_assets.add(layout.background_asset_key)
        missing_assets = required_assets - set(asset_map)
        if missing_assets:
            raise DocumentAssetError(f"Required document assets are missing: {', '.join(sorted(missing_assets))}.")
        cls._assert_bindings(layout, fields, sections)
        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=cls.PAGE_SIZES[layout.page_size],
                                     leftMargin=layout.margin_mm * mm, rightMargin=layout.margin_mm * mm,
                                     topMargin=layout.margin_mm * mm, bottomMargin=layout.margin_mm * mm,
                                     pageCompression=0, title=payload.title)
        styles = cls._styles(layout)
        story = []
        copies = ("ORIGINAL", "DUPLICATE") if layout.copy_mode != "SINGLE" else ("ORIGINAL",)
        for copy_index, copy_name in enumerate(copies):
            if copy_index:
                story.append(PageBreak())
            cls._append_blocks(story, layout.blocks, payload, fields, sections, styles, copy_name, preview, asset_map)
            if layout.copy_mode == "ORIGINAL_DUPLICATE_DUPLEX":
                story.append(PageBreak())
                cls._append_blocks(story, layout.back_blocks, payload, fields, sections, styles, copy_name, preview, asset_map)
        document.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        if layout.background_asset_key:
            pdf = cls._apply_background(pdf, asset_map[layout.background_asset_key])
        renderer_version = cls.VERSION if layout.schema_version == 1 else "layout-reportlab-v2"
        return LayoutRenderResult(pdf, layout.content_hash, cls._payload_hash(payload), renderer_version, layout.page_size, layout.copy_mode,
                                  tuple(sorted((key, asset.sha256) for key, asset in asset_map.items())))

    @classmethod
    def _append_blocks(cls, story, blocks, payload, fields, sections, styles, copy_name, preview, assets):
        if preview:
            story.extend([Paragraph("PREVIEW / NOT AN OFFICIAL ISSUE", styles["Heading2"]), Spacer(1, 4)])
        story.extend([Paragraph(copy_name, styles["Heading3"]), Spacer(1, 3)])
        for block in blocks:
            if block.type == "title":
                story.extend([Paragraph(escape(block.text or payload.title), styles["Title"]), Spacer(1, 6)])
            elif block.type == "field":
                field = fields[block.binding]
                story.append(Paragraph(f"<b>{escape(field.label)}</b>: {escape(str(field.value))}", styles["BodyText"]))
            elif block.type == "field_group":
                rows = [[Paragraph(f"<b>{escape(fields[key].label)}</b>", styles["BodyText"]), Paragraph(escape(str(fields[key].value)), styles["BodyText"])] for key in block.bindings]
                table = Table(rows, colWidths=[52 * mm, 120 * mm])
                table.setStyle(cls._table_style(False)); story.extend([table, Spacer(1, 6)])
            elif block.type == "table":
                section = sections[block.binding]
                story.append(Paragraph(escape(section.heading), styles["Heading2"]))
                table = Table([[Paragraph(escape(str(cell)), styles["BodyText"]) for cell in row] for row in section.rows], repeatRows=1)
                table.setStyle(cls._table_style(True)); story.extend([table, Spacer(1, 6)])
            elif block.type == "image":
                asset = assets[block.asset_key]
                if asset.mime_type == "application/pdf":
                    raise DocumentAssetError("PDF assets cannot be used in image blocks.")
                story.append(Image(io.BytesIO(asset.content), width=block.width_mm * mm,
                                   height=block.width_mm * mm * asset.height / asset.width))
            elif block.type == "qr":
                value = payload.verification_id if block.binding in {"", "document.verification_id"} else fields[block.binding].value
                widget = QrCodeWidget(str(value)); bounds = widget.getBounds()
                size = block.width_mm * mm
                drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
                drawing.add(widget); story.append(drawing)
            elif block.type == "verification":
                story.extend([Paragraph("Verification ID", styles["Heading3"]), Paragraph(escape(payload.verification_id), styles["Code"])])
            elif block.type == "signature":
                labels = (block.text or "Signature").split("|", 1)
                table = Table([[item.strip() for item in labels]], rowHeights=[block.height_mm * mm])
                table.setStyle(cls._table_style(False)); story.append(table)
            elif block.type == "spacer":
                story.append(Spacer(1, block.height_mm * mm))
            elif block.type == "page_break":
                story.append(PageBreak())

    @staticmethod
    def _assert_bindings(layout, fields, sections):
        for block in layout.blocks + layout.back_blocks:
            if block.type == "field" and block.binding not in fields:
                raise ValueError(f"Payload does not contain field {block.binding}.")
            if block.type == "field_group":
                missing = set(block.bindings) - set(fields)
                if missing: raise ValueError(f"Payload does not contain fields: {', '.join(sorted(missing))}.")
            if block.type == "table" and block.binding not in sections:
                raise ValueError(f"Payload does not contain table {block.binding}.")

    @staticmethod
    def _payload_hash(payload):
        value = {"schema_version": payload.schema_version, "document_type": payload.document_type,
                 "verification_id": payload.verification_id,
                 "fields": [(field.key, str(field.value)) for field in payload.fields],
                 "sections": [(section.key, [[str(cell) for cell in row] for row in section.rows]) for section in payload.sections]}
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _styles(layout):
        styles = getSampleStyleSheet()
        styles["BodyText"].fontSize = layout.body_font_size_pt
        styles["BodyText"].leading = layout.body_font_size_pt + 2
        styles["Title"].fontSize = layout.heading_font_size_pt
        styles["Title"].textColor = colors.HexColor(layout.primary_color)
        styles["Heading2"].textColor = colors.HexColor(layout.primary_color)
        font_path = Path(__file__).resolve().parents[4] / "static" / "fonts" / "NotoSansTamil-Regular.ttf"
        if layout.font_family == "NOTO_SANS_TAMIL" and font_path.exists():
            name = "RokkadUnicodeTamil"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(font_path)))
            for style_name in ("BodyText", "Title", "Heading2", "Heading3", "Code"):
                styles[style_name].fontName = name
        return styles

    @staticmethod
    def _apply_background(content_pdf, asset):
        content = fitz.open(stream=content_pdf, filetype="pdf")
        if asset.mime_type == "application/pdf":
            background = fitz.open(stream=asset.content, filetype="pdf")
        else:
            background = fitz.open()
            page = background.new_page(width=content[0].rect.width, height=content[0].rect.height)
            page.insert_image(page.rect, stream=asset.content)
        output = fitz.open()
        for index, content_page in enumerate(content):
            page = output.new_page(width=content_page.rect.width, height=content_page.rect.height)
            background_index = min(index, len(background) - 1)
            page.show_pdf_page(page.rect, background, background_index)
            page.show_pdf_page(page.rect, content, index)
        value = output.tobytes(garbage=4, deflate=True)
        output.close(); background.close(); content.close()
        return value

    @staticmethod
    def _table_style(header):
        commands = [("GRID", (0, 0), (-1, -1), .4, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
        if header: commands.extend([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")])
        return TableStyle(commands)


__all__ = ["ConfigurableDocumentRenderer", "LayoutRenderResult"]
