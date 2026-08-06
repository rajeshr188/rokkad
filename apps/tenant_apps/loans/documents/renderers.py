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
        required_assets = {block.asset_key for block in layout.all_blocks() if block.asset_key}
        if layout.background_asset_key:
            required_assets.add(layout.background_asset_key)
        missing_assets = required_assets - set(asset_map)
        if missing_assets:
            raise DocumentAssetError(f"Required document assets are missing: {', '.join(sorted(missing_assets))}.")
        cls._assert_bindings(layout, fields, sections)
        buffer = io.BytesIO()
        header_height = layout.header.height_mm if layout.header else 0
        footer_height = layout.footer.height_mm if layout.footer else 0
        document = SimpleDocTemplate(buffer, pagesize=cls.PAGE_SIZES[layout.page_size],
                                     leftMargin=layout.margin_mm * mm, rightMargin=layout.margin_mm * mm,
                                     topMargin=(layout.margin_mm + header_height) * mm,
                                     bottomMargin=(layout.margin_mm + footer_height) * mm,
                                     pageCompression=0, title=payload.title)
        styles = cls._styles(layout)
        story = []
        available_width = cls.PAGE_SIZES[layout.page_size][0] - (2 * layout.margin_mm * mm)
        copies = ("ORIGINAL", "DUPLICATE") if layout.copy_mode != "SINGLE" else ("ORIGINAL",)
        for copy_index, copy_name in enumerate(copies):
            if copy_index:
                story.append(PageBreak())
            cls._append_blocks(story, layout.blocks, payload, fields, sections, styles, copy_name, preview, asset_map, layout, available_width)
            if layout.copy_mode == "ORIGINAL_DUPLICATE_DUPLEX":
                story.append(PageBreak())
                cls._append_blocks(story, layout.back_blocks, payload, fields, sections, styles, copy_name, preview, asset_map, layout, available_width)
        def draw_regions(canvas, _document):
            cls._draw_page_region(canvas, layout.header, top=True, payload=payload, fields=fields,
                                  sections=sections, styles=styles, assets=asset_map,
                                  layout=layout, available_width=available_width)
            cls._draw_page_region(canvas, layout.footer, top=False, payload=payload, fields=fields,
                                  sections=sections, styles=styles, assets=asset_map,
                                  layout=layout, available_width=available_width)
        document.build(story, onFirstPage=draw_regions, onLaterPages=draw_regions)
        pdf = buffer.getvalue()
        buffer.close()
        if layout.background_asset_key:
            pdf = cls._apply_background(pdf, asset_map[layout.background_asset_key])
        renderer_version = cls.VERSION if layout.schema_version == 1 else "layout-reportlab-v2"
        return LayoutRenderResult(pdf, layout.content_hash, cls._payload_hash(payload), renderer_version, layout.page_size, layout.copy_mode,
                                  tuple(sorted((key, asset.sha256) for key, asset in asset_map.items())))

    @classmethod
    def _append_blocks(cls, story, blocks, payload, fields, sections, styles, copy_name, preview, assets, layout, available_width, *, nested=False):
        if not nested:
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
                if block.table_columns:
                    if any(column.index >= len(row) for column in block.table_columns for row in section.rows):
                        raise ValueError(f"Table {block.binding} does not contain every configured column index.")
                    rows = [[column.label for column in block.table_columns]]
                    rows.extend([[row[column.index] for column in block.table_columns] for row in section.rows[1:]])
                    widths = [available_width * column.width_percent / 100 for column in block.table_columns]
                else:
                    rows = section.rows
                    widths = None
                table = Table([[Paragraph(escape(str(cell)), styles["BodyText"]) for cell in row] for row in rows],
                              colWidths=widths, repeatRows=1 if block.repeat_header else 0)
                commands = list(cls._table_style(True).getCommands())
                if block.style_variant == "MINIMAL":
                    commands = [("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor(layout.border_color)), ("VALIGN", (0, 0), (-1, -1), "TOP")]
                elif block.style_variant == "STRIPED":
                    for row_index in range(2, len(rows), 2):
                        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#f8fafc")))
                for column_index, column in enumerate(block.table_columns):
                    commands.append(("ALIGN", (column_index, 0), (column_index, -1), column.align))
                table.setStyle(TableStyle(commands)); story.extend([table, Spacer(1, 6)])
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
            elif block.type == "field_grid":
                cells = [Paragraph(f"<b>{escape(fields[key].label)}</b><br/>{escape(str(fields[key].value))}", styles["BodyText"]) for key in block.bindings]
                while len(cells) % block.grid_columns:
                    cells.append("")
                rows = [cells[index:index + block.grid_columns] for index in range(0, len(cells), block.grid_columns)]
                table = Table(rows, colWidths=[available_width / block.grid_columns] * block.grid_columns)
                table.setStyle(cls._table_style(False)); story.extend([table, Spacer(1, 6)])
            elif block.type == "section":
                inner = []
                if block.text:
                    inner.extend([Paragraph(escape(block.text), styles["Heading2"]), Spacer(1, 3)])
                cls._append_blocks(inner, block.blocks, payload, fields, sections, styles, copy_name, False, assets, layout, available_width - 12, nested=True)
                section = Table([[inner]], colWidths=[available_width])
                commands = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]
                if block.style_variant in {"OUTLINED", "TINTED"}:
                    commands.append(("BOX", (0, 0), (-1, -1), .6, colors.HexColor(layout.border_color)))
                if block.style_variant == "TINTED":
                    commands.append(("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")))
                section.setStyle(TableStyle(commands)); story.extend([section, Spacer(1, 6)])
            elif block.type == "columns":
                cells = []
                widths = []
                for column in block.columns:
                    column_width = available_width * column.width_percent / 100
                    inner = []
                    cls._append_blocks(inner, column.blocks, payload, fields, sections, styles, copy_name, False, assets, layout, column_width - 8, nested=True)
                    cells.append(inner); widths.append(column_width)
                columns = Table([cells], colWidths=widths)
                columns.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
                story.extend([columns, Spacer(1, 6)])

    @classmethod
    def _draw_page_region(cls, canvas, region, *, top, payload, fields, sections, styles, assets, layout, available_width):
        if region is None:
            return
        flowables = []
        cls._append_blocks(flowables, region.blocks, payload, fields, sections, styles, "", False,
                           assets, layout, available_width, nested=True)
        page_height = cls.PAGE_SIZES[layout.page_size][1]
        y = page_height - (layout.margin_mm * mm) if top else (layout.margin_mm + region.height_mm) * mm
        minimum_y = y - region.height_mm * mm
        for flowable in flowables:
            width, height = flowable.wrap(available_width, region.height_mm * mm)
            y -= height
            if y < minimum_y:
                raise ValueError("Page region content exceeds its configured height.")
            flowable.drawOn(canvas, layout.margin_mm * mm, y)

    @staticmethod
    def _assert_bindings(layout, fields, sections):
        for block in layout.all_blocks():
            if block.type == "field" and block.binding not in fields:
                raise ValueError(f"Payload does not contain field {block.binding}.")
            if block.type == "field_group":
                missing = set(block.bindings) - set(fields)
                if missing: raise ValueError(f"Payload does not contain fields: {', '.join(sorted(missing))}.")
            if block.type == "field_grid":
                missing = set(block.bindings) - set(fields)
                if missing: raise ValueError(f"Payload does not contain fields: {', '.join(sorted(missing))}.")
            if block.type == "qr" and block.binding not in {"", "document.verification_id"} and block.binding not in fields:
                raise ValueError(f"Payload does not contain field {block.binding}.")
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
