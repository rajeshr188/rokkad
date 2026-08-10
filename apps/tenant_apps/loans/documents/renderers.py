"""ReportLab renderer for validated PawnLoan document layouts."""

import hashlib
import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation
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
from reportlab.graphics import renderPDF
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfgen import canvas as pdf_canvas
import fitz

from .assets import DocumentAssetError, validate_asset_set
from .layouts import DocumentLayoutValidator, REQUIRED_BINDINGS, REQUIRED_SECTIONS


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
    def render_with_print_profile(
        cls, payload, layout, print_profile, *, preview=False, assets=()
    ):
        """Render logical ticket surfaces, then package them using a profile."""
        if payload.document_type != "loan_ticket" or layout.document_type != "loan_ticket":
            raise ValueError("Print-profile rendering supports loan tickets only.")
        if print_profile.document_type != payload.document_type:
            raise ValueError("Print profile document type does not match the payload.")
        fields, sections, asset_map = cls._validated_context(
            payload, layout, assets
        )
        cls.assert_print_profile_compatible(layout, print_profile)
        rendered_surfaces = {}
        for surface in print_profile.included_surfaces:
            rendered_surfaces[surface] = cls._render_logical_surface(
                payload, layout, fields, sections, asset_map, surface, preview
            )
        pdf = cls._package_surfaces(rendered_surfaces, print_profile)
        output_page_size = (
            f"{print_profile.paper_size}_LANDSCAPE"
            if print_profile.orientation == "LANDSCAPE"
            else print_profile.paper_size
        )
        return LayoutRenderResult(
            pdf, layout.content_hash, cls._payload_hash(payload),
            "layout-reportlab-profile-v1", output_page_size,
            print_profile.composition,
            tuple(sorted((key, asset.sha256) for key, asset in asset_map.items())),
        )

    @classmethod
    def render(cls, payload, layout, *, preview=False, assets=()):
        if payload.document_type != layout.document_type:
            raise ValueError("Layout document type does not match the payload.")
        if layout.schema_version >= 3 and layout.document_type == "loan_ticket":
            raise ValueError(
                "Schema-v3 loan-ticket layouts require an explicit print profile."
            )
        fields = {field.key: field for field in payload.fields}
        sections = {section.key: section for section in payload.sections}
        workspace_field = fields.get("workspace.source_id")
        try:
            workspace_id = int(str(workspace_field.value).split(":", 1)[1])
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise DocumentAssetError("Payload has no valid workspace asset boundary.") from exc
        asset_map = validate_asset_set(assets, workspace_id=workspace_id)
        required_assets = {block.asset_key for block in layout.all_blocks() if block.asset_key}
        required_assets.update(layout.background_asset_keys())
        missing_assets = required_assets - set(asset_map)
        if missing_assets:
            raise DocumentAssetError(f"Required document assets are missing: {', '.join(sorted(missing_assets))}.")
        cls._assert_bindings(layout, fields, sections)
        if layout.layout_mode == "ABSOLUTE_OVERLAY":
            if layout.sheet:
                pdf, output_page_size, output_copy_mode = cls._render_sheet_composition(
                    payload, layout, fields, sections, asset_map, preview,
                )
                return LayoutRenderResult(
                    pdf, layout.content_hash, cls._payload_hash(payload), "layout-reportlab-sheet-v1",
                    output_page_size, output_copy_mode,
                    tuple(sorted((key, asset.sha256) for key, asset in asset_map.items())),
                )
            pdf = cls._render_absolute_overlay(payload, layout, fields, sections, asset_map, preview)
            pdf = cls._apply_background(pdf, asset_map[layout.background_asset_key])
            return LayoutRenderResult(
                pdf, layout.content_hash, cls._payload_hash(payload), "layout-reportlab-overlay-v1",
                layout.page_size, layout.copy_mode,
                tuple(sorted((key, asset.sha256) for key, asset in asset_map.items())),
            )
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
    def _validated_context(cls, payload, layout, assets):
        fields = {field.key: field for field in payload.fields}
        sections = {section.key: section for section in payload.sections}
        workspace_field = fields.get("workspace.source_id")
        try:
            workspace_id = int(str(workspace_field.value).split(":", 1)[1])
        except (AttributeError, IndexError, TypeError, ValueError) as exc:
            raise DocumentAssetError(
                "Payload has no valid workspace asset boundary."
            ) from exc
        asset_map = validate_asset_set(assets, workspace_id=workspace_id)
        required_assets = {
            block.asset_key for block in layout.all_blocks() if block.asset_key
        }
        required_assets.update(layout.background_asset_keys())
        missing_assets = required_assets - set(asset_map)
        if missing_assets:
            raise DocumentAssetError(
                f"Required document assets are missing: {', '.join(sorted(missing_assets))}."
            )
        cls._assert_bindings(layout, fields, sections)
        return fields, sections, asset_map

    @classmethod
    def assert_print_profile_compatible(cls, layout, profile):
        logical_paper_size = (
            "A5" if any(len(sheet) == 2 for sheet in profile.sheets)
            else profile.paper_size
        )
        if (
            profile.scaling_policy == "ACTUAL_SIZE"
            and layout.page_size != logical_paper_size
        ):
            raise ValueError(
                "Actual-size print profile does not match the logical layout page; "
                "use a matching layout or FIT_PRINTABLE_AREA."
            )
        for surface in profile.included_surfaces:
            if surface.endswith("FRONT"):
                copy_scope = "ORIGINAL" if surface.startswith("ORIGINAL") else "DUPLICATE"
                required = REQUIRED_BINDINGS[layout.document_type] | REQUIRED_SECTIONS[layout.document_type]
                present = DocumentLayoutValidator._unconditional_bindings_for_scope(
                    layout.blocks, copy_scope
                )
                missing = required - present
                if missing:
                    raise ValueError(
                        f"Print profile cannot select {surface}: mandatory evidence is missing: "
                        f"{', '.join(sorted(missing))}."
                    )
                if not DocumentLayoutValidator._has_unconditional_type_for_scope(
                    layout.blocks, "verification", copy_scope
                ):
                    raise ValueError(
                        f"Print profile cannot select {surface}: verification evidence is missing."
                    )
                continue
            surface_key = {
                "ORIGINAL_TERMS": "original_back",
                "DUPLICATE_D3": "duplicate_back",
            }[surface]
            has_background = bool(
                (layout.surfaces and layout.surfaces.background(surface_key))
                or (layout.sheet and layout.sheet.background(surface_key))
            )
            if not layout.back_blocks and not has_background:
                raise ValueError(
                    f"Print profile cannot select {surface}: the layout has no logical back surface."
                )

    @classmethod
    def _render_logical_surface(
        cls, payload, layout, fields, sections, assets, surface, preview
    ):
        copy_scope = "ORIGINAL" if surface.startswith("ORIGINAL") else "DUPLICATE"
        is_front = surface.endswith("FRONT")
        blocks = layout.blocks if is_front else layout.back_blocks
        if layout.layout_mode == "ABSOLUTE_OVERLAY":
            pdf = cls._render_overlay_surface(
                payload, layout, fields, sections, assets, preview,
                blocks=blocks, copy_scope=copy_scope,
            )
        else:
            pdf = cls._render_flow_surface(
                payload, layout, fields, sections, assets, preview,
                blocks=blocks, copy_scope=copy_scope,
            )
        background_key = layout.surface_background(surface)
        return cls._apply_background(pdf, assets[background_key]) if background_key else pdf

    @classmethod
    def _render_flow_surface(
        cls, payload, layout, fields, sections, assets, preview, *, blocks,
        copy_scope,
    ):
        buffer = io.BytesIO()
        header_height = layout.header.height_mm if layout.header else 0
        footer_height = layout.footer.height_mm if layout.footer else 0
        document = SimpleDocTemplate(
            buffer, pagesize=cls.PAGE_SIZES[layout.page_size],
            leftMargin=layout.margin_mm * mm, rightMargin=layout.margin_mm * mm,
            topMargin=(layout.margin_mm + header_height) * mm,
            bottomMargin=(layout.margin_mm + footer_height) * mm,
            pageCompression=0, title=payload.title,
        )
        styles = cls._styles(layout)
        available_width = cls.PAGE_SIZES[layout.page_size][0] - (2 * layout.margin_mm * mm)
        story = []
        cls._append_blocks(
            story, blocks, payload, fields, sections, styles, copy_scope,
            preview, assets, layout, available_width, enforce_copy_scope=True,
        )

        def draw_regions(canvas, _document):
            cls._draw_page_region(
                canvas, layout.header, top=True, payload=payload, fields=fields,
                sections=sections, styles=styles, assets=assets, layout=layout,
                available_width=available_width, copy_name=copy_scope,
                enforce_copy_scope=True,
            )
            cls._draw_page_region(
                canvas, layout.footer, top=False, payload=payload, fields=fields,
                sections=sections, styles=styles, assets=assets, layout=layout,
                available_width=available_width, copy_name=copy_scope,
                enforce_copy_scope=True,
            )

        document.build(story, onFirstPage=draw_regions, onLaterPages=draw_regions)
        value = buffer.getvalue()
        buffer.close()
        return value

    @classmethod
    def _package_surfaces(cls, surfaces, profile):
        output = fitz.open()
        page_size = cls.PAGE_SIZES[profile.paper_size]
        if profile.orientation == "LANDSCAPE":
            page_size = (page_size[1], page_size[0])
        try:
            for sheet in profile.sheets:
                if len(sheet) == 1:
                    normalized = cls._normalize_pdf_pages(
                        surfaces[sheet[0]], page_size, profile.scaling_policy
                    )
                    source = fitz.open(stream=normalized, filetype="pdf")
                    try:
                        output.insert_pdf(source)
                    finally:
                        source.close()
                    continue
                left_size = (page_size[0] / 2, page_size[1])
                left = cls._normalize_pdf_pages(
                    surfaces[sheet[0]], left_size, profile.scaling_policy
                )
                right = cls._normalize_pdf_pages(
                    surfaces[sheet[1]], left_size, profile.scaling_policy
                )
                left_doc = fitz.open(stream=left, filetype="pdf")
                right_doc = fitz.open(stream=right, filetype="pdf")
                try:
                    if len(left_doc) != 1 or len(right_doc) != 1:
                        raise ValueError(
                            "Side-by-side print profiles require each logical surface to fit one page."
                        )
                    page = output.new_page(width=page_size[0], height=page_size[1])
                    page.show_pdf_page(
                        fitz.Rect(0, 0, page_size[0] / 2, page_size[1]), left_doc, 0
                    )
                    page.show_pdf_page(
                        fitz.Rect(page_size[0] / 2, 0, page_size[0], page_size[1]),
                        right_doc, 0,
                    )
                finally:
                    left_doc.close()
                    right_doc.close()
            return output.tobytes(garbage=4, deflate=True)
        finally:
            output.close()

    @staticmethod
    def _normalize_pdf_pages(content, target_size, scaling_policy):
        source = fitz.open(stream=content, filetype="pdf")
        output = fitz.open()
        try:
            for source_page in source:
                source_size = (source_page.rect.width, source_page.rect.height)
                if scaling_policy == "ACTUAL_SIZE" and (
                    abs(source_size[0] - target_size[0]) > 2
                    or abs(source_size[1] - target_size[1]) > 2
                ):
                    raise ValueError(
                        "Actual-size print profile does not match the logical layout page; "
                        "use a matching layout or FIT_PRINTABLE_AREA."
                    )
                page = output.new_page(width=target_size[0], height=target_size[1])
                if scaling_policy == "ACTUAL_SIZE":
                    target = fitz.Rect(
                        (target_size[0] - source_size[0]) / 2,
                        (target_size[1] - source_size[1]) / 2,
                        (target_size[0] + source_size[0]) / 2,
                        (target_size[1] + source_size[1]) / 2,
                    )
                else:
                    scale = min(
                        target_size[0] / source_size[0],
                        target_size[1] / source_size[1],
                    )
                    width = source_size[0] * scale
                    height = source_size[1] * scale
                    target = fitz.Rect(
                        (target_size[0] - width) / 2,
                        (target_size[1] - height) / 2,
                        (target_size[0] + width) / 2,
                        (target_size[1] + height) / 2,
                    )
                page.show_pdf_page(target, source, source_page.number)
            return output.tobytes(garbage=4, deflate=True)
        finally:
            source.close()
            output.close()

    @classmethod
    def _render_absolute_overlay(cls, payload, layout, fields, sections, assets, preview):
        buffer = io.BytesIO()
        page_size = cls.PAGE_SIZES[layout.page_size]
        canvas = pdf_canvas.Canvas(buffer, pagesize=page_size, pageCompression=0)
        canvas.setTitle(payload.title)
        styles = cls._styles(layout)
        if layout.copy_mode == "SINGLE":
            pages = (("ORIGINAL", layout.blocks),)
        elif layout.copy_mode == "ORIGINAL_DUPLICATE":
            pages = (("ORIGINAL", layout.blocks), ("DUPLICATE", layout.blocks))
        else:
            pages = (("ORIGINAL", layout.blocks), ("ORIGINAL", layout.back_blocks),
                     ("DUPLICATE", layout.blocks), ("DUPLICATE", layout.back_blocks))
        for copy_name, blocks in pages:
            for block in blocks:
                if block.copy_scope in {"BOTH", copy_name} and cls._is_visible(block, fields):
                    cls._draw_overlay_block(canvas, block, payload, fields, sections, assets, styles, layout, page_size)
            if preview:
                canvas.saveState()
                canvas.setFillColor(colors.Color(0.75, 0.1, 0.1, alpha=0.25))
                canvas.setFont("Helvetica-Bold", 24)
                canvas.translate(page_size[0] / 2, page_size[1] / 2)
                canvas.rotate(35)
                canvas.drawCentredString(0, 0, "PREVIEW / NOT AN OFFICIAL ISSUE")
                canvas.restoreState()
            canvas.setAuthor(f"Rokkad {copy_name}")
            canvas.showPage()
        canvas.save()
        value = buffer.getvalue()
        buffer.close()
        return value

    @classmethod
    def _render_sheet_composition(cls, payload, layout, fields, sections, assets, preview):
        sheet = layout.sheet

        def surface(name, copy_scope, blocks):
            content = cls._render_overlay_surface(
                payload, layout, fields, sections, assets, preview,
                blocks=blocks, copy_scope=copy_scope,
            )
            return cls._apply_background(content, assets[sheet.background(name)])

        cache = {}
        def get(name):
            if name not in cache:
                scope = "ORIGINAL" if name.startswith("original") else "DUPLICATE"
                blocks = layout.blocks if name.endswith("front") else layout.back_blocks
                cache[name] = surface(name, scope, blocks)
            return cache[name]

        composition = sheet.composition
        sequences = {
            "A5_ORIGINAL": ("original_front",),
            "A5_ORIGINAL_TERMS_DUPLEX": ("original_front", "original_back"),
            "A5_DUPLICATE": ("duplicate_front",),
            "A5_DUPLICATE_D3_DUPLEX": ("duplicate_front", "duplicate_back"),
            "A5_BOTH_SIMPLEX": ("original_front", "duplicate_front"),
            "A5_BOTH_DUPLEX": ("original_front", "original_back", "duplicate_front", "duplicate_back"),
        }
        if composition in sequences:
            return cls._merge_pdf_pages([get(name) for name in sequences[composition]]), "A5", composition
        front = cls._impose_a5_side_by_side(get("original_front"), get("duplicate_front"))
        if composition == "A4_SIDE_BY_SIDE":
            return front, "A4_LANDSCAPE", composition
        back = cls._impose_a5_side_by_side(get("original_back"), get("duplicate_back"))
        return cls._merge_pdf_pages([front, back]), "A4_LANDSCAPE", composition

    @classmethod
    def _render_overlay_surface(cls, payload, layout, fields, sections, assets, preview, *, blocks, copy_scope):
        buffer = io.BytesIO()
        page_size = cls.PAGE_SIZES[layout.page_size]
        canvas = pdf_canvas.Canvas(buffer, pagesize=page_size, pageCompression=0)
        canvas.setTitle(payload.title)
        styles = cls._styles(layout)
        for block in blocks:
            if block.copy_scope in {"BOTH", copy_scope} and cls._is_visible(block, fields):
                cls._draw_overlay_block(canvas, block, payload, fields, sections, assets, styles, layout, page_size)
        if preview:
            canvas.saveState()
            canvas.setFillColor(colors.Color(0.75, 0.1, 0.1, alpha=0.25))
            canvas.setFont("Helvetica-Bold", 20)
            canvas.translate(page_size[0] / 2, page_size[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "PREVIEW / NOT AN OFFICIAL ISSUE")
            canvas.restoreState()
        canvas.showPage(); canvas.save()
        value = buffer.getvalue(); buffer.close()
        return value

    @staticmethod
    def _merge_pdf_pages(pages):
        output = fitz.open()
        try:
            for value in pages:
                source = fitz.open(stream=value, filetype="pdf")
                try:
                    output.insert_pdf(source)
                finally:
                    source.close()
            return output.tobytes(garbage=4, deflate=True)
        finally:
            output.close()

    @staticmethod
    def _impose_a5_side_by_side(original, duplicate):
        output = fitz.open()
        left = fitz.open(stream=original, filetype="pdf")
        right = fitz.open(stream=duplicate, filetype="pdf")
        try:
            width, height = A4[1], A4[0]
            page = output.new_page(width=width, height=height)
            page.show_pdf_page(fitz.Rect(0, 0, width / 2, height), left, 0)
            page.show_pdf_page(fitz.Rect(width / 2, 0, width, height), right, 0)
            return output.tobytes(garbage=4, deflate=True)
        finally:
            left.close(); right.close(); output.close()

    @classmethod
    def _draw_overlay_block(cls, canvas, block, payload, fields, sections, assets, styles, layout, page_size):
        x = block.x_mm * mm
        height = block.height_mm * mm
        width = block.width_mm * mm
        y = page_size[1] - (block.y_mm * mm) - height
        style = styles["BodyText"].clone(f"overlay-{block.type}-{block.x_mm}-{block.y_mm}")
        style.fontSize = block.font_size_pt
        style.leading = block.font_size_pt + 2
        style.alignment = {"LEFT": 0, "CENTER": 1, "RIGHT": 2}[block.align]
        if block.type == "image":
            asset = assets[block.asset_key]
            if asset.mime_type == "application/pdf":
                raise DocumentAssetError("PDF assets cannot be used in image blocks.")
            image = Image(io.BytesIO(asset.content))
            image._restrictSize(width, height)
            image.drawOn(canvas, x + (width - image.drawWidth) / 2, y + (height - image.drawHeight) / 2)
            return
        if block.type == "qr":
            raw = payload.verification_id if block.binding in {"", "document.verification_id"} else fields[block.binding].value
            widget = QrCodeWidget(str(raw)); bounds = widget.getBounds()
            size = min(width, height)
            drawing = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
            drawing.add(widget); renderPDF.draw(drawing, canvas, x + (width - size) / 2, y + (height - size) / 2)
            return
        if block.type == "table":
            cls._draw_overlay_table(canvas, block, sections[block.binding], styles, layout, x, y, width, height)
            return
        if block.type == "title":
            text = escape(block.text or payload.title)
        elif block.type == "field":
            field = fields[block.binding]
            value, style = cls._display_value(field.value, block, style)
            text = f"<b>{escape(field.label)}</b>: {escape(value)}"
        elif block.type == "verification":
            text = f"<b>Verification ID</b>: {escape(payload.verification_id)}"
        else:
            text = escape(block.text or "Signature")
        try:
            cls._draw_overlay_paragraph(canvas, text, style, x, y, width, height, block.overflow_policy)
        except ValueError as exc:
            identity = block.binding or block.text or block.type
            raise ValueError(
                f"Overlay block '{identity}' exceeds its configured rectangle "
                f"at ({block.x_mm}, {block.y_mm}) mm."
            ) from exc

    @staticmethod
    def _draw_overlay_paragraph(canvas, text, style, x, y, width, height, overflow_policy):
        paragraph = Paragraph(text, style)
        _, required_height = paragraph.wrap(width, height)
        if required_height > height and overflow_policy == "SHRINK":
            while required_height > height and style.fontSize > 6:
                style.fontSize -= 1
                style.leading = style.fontSize + 2
                paragraph = Paragraph(text, style)
                _, required_height = paragraph.wrap(width, height)
        if required_height > height:
            raise ValueError("Absolute overlay content exceeds its configured rectangle.")
        paragraph.drawOn(canvas, x, y + height - required_height)

    @classmethod
    def _draw_overlay_table(cls, canvas, block, section, styles, layout, x, y, width, height):
        if block.table_columns:
            if any(column.index >= len(row) for column in block.table_columns for row in section.rows):
                raise ValueError(f"Table {block.binding} does not contain every configured column index.")
            rows = [[column.label for column in block.table_columns]]
            rows.extend([[row[column.index] for column in block.table_columns] for row in section.rows[1:]])
            widths = [width * column.width_percent / 100 for column in block.table_columns]
        else:
            rows, widths = section.rows, None
        base_style = styles["BodyText"].clone(f"overlay-table-{block.x_mm}-{block.y_mm}")
        base_style.fontSize = block.font_size_pt; base_style.leading = block.font_size_pt + 2
        rendered = []
        for row_index, row in enumerate(rows):
            rendered_row = []
            for column_index, cell in enumerate(row):
                config = block.table_columns[column_index] if block.table_columns and row_index else block
                value, cell_style = cls._display_value(cell, config, base_style)
                rendered_row.append(Paragraph(escape(value), cell_style))
            rendered.append(rendered_row)
        table = Table(rendered, colWidths=widths, repeatRows=1 if block.repeat_header else 0)
        commands = list(cls._table_style(True).getCommands())
        for column_index, column in enumerate(block.table_columns):
            commands.append(("ALIGN", (column_index, 0), (column_index, -1), column.align))
        table.setStyle(TableStyle(commands))
        required_width, required_height = table.wrap(width, height)
        if required_width > width or required_height > height:
            raise ValueError("Absolute overlay table exceeds its configured rectangle.")
        table.drawOn(canvas, x, y + height - required_height)

    @classmethod
    def _append_blocks(cls, story, blocks, payload, fields, sections, styles, copy_name, preview, assets, layout, available_width, *, nested=False, enforce_copy_scope=False):
        if not nested:
            if preview:
                story.extend([Paragraph("PREVIEW / NOT AN OFFICIAL ISSUE", styles["Heading2"]), Spacer(1, 4)])
            story.extend([Paragraph(copy_name, styles["Heading3"]), Spacer(1, 3)])
        for block in blocks:
            if enforce_copy_scope and block.copy_scope not in {"BOTH", copy_name}:
                continue
            if not cls._is_visible(block, fields):
                continue
            if block.type == "title":
                story.extend([Paragraph(escape(block.text or payload.title), styles["Title"]), Spacer(1, 6)])
            elif block.type == "field":
                field = fields[block.binding]
                value, style = cls._display_value(field.value, block, styles["BodyText"])
                story.append(Paragraph(f"<b>{escape(field.label)}</b>: {escape(value)}", style))
            elif block.type == "field_group":
                rows = []
                for key in block.bindings:
                    value, style = cls._display_value(fields[key].value, block, styles["BodyText"])
                    rows.append([Paragraph(f"<b>{escape(fields[key].label)}</b>", styles["BodyText"]), Paragraph(escape(value), style)])
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
                rendered_rows = []
                for row_index, row in enumerate(rows):
                    rendered_row = []
                    for column_index, cell in enumerate(row):
                        config = block.table_columns[column_index] if block.table_columns and row_index else block
                        value, style = cls._display_value(cell, config, styles["BodyText"])
                        rendered_row.append(Paragraph(escape(value), style))
                    rendered_rows.append(rendered_row)
                table = Table(rendered_rows,
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
                cells = []
                for key in block.bindings:
                    value, style = cls._display_value(fields[key].value, block, styles["BodyText"])
                    cells.append(Paragraph(f"<b>{escape(fields[key].label)}</b><br/>{escape(value)}", style))
                while len(cells) % block.grid_columns:
                    cells.append("")
                rows = [cells[index:index + block.grid_columns] for index in range(0, len(cells), block.grid_columns)]
                table = Table(rows, colWidths=[available_width / block.grid_columns] * block.grid_columns)
                table.setStyle(cls._table_style(False)); story.extend([table, Spacer(1, 6)])
            elif block.type == "section":
                inner = []
                if block.text:
                    inner.extend([Paragraph(escape(block.text), styles["Heading2"]), Spacer(1, 3)])
                cls._append_blocks(inner, block.blocks, payload, fields, sections, styles, copy_name, False, assets, layout, available_width - 12, nested=True, enforce_copy_scope=enforce_copy_scope)
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
                    cls._append_blocks(inner, column.blocks, payload, fields, sections, styles, copy_name, False, assets, layout, column_width - 8, nested=True, enforce_copy_scope=enforce_copy_scope)
                    cells.append(inner); widths.append(column_width)
                columns = Table([cells], colWidths=widths)
                columns.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
                story.extend([columns, Spacer(1, 6)])

    @staticmethod
    def _is_visible(block, fields):
        condition = block.visible_when
        if condition is None:
            return True
        value = str(fields[condition.binding].value or "")
        if condition.operator == "PRESENT":
            return bool(value.strip())
        if condition.operator == "EMPTY":
            return not value.strip()
        if condition.operator == "EQUALS":
            return value == condition.value
        return value != condition.value

    @staticmethod
    def _display_value(raw_value, config, base_style):
        value = str(raw_value)
        value_format = config.value_format
        if value_format == "UPPER":
            value = value.upper()
        elif value_format == "LOWER":
            value = value.lower()
        elif value_format in {"DATE_DMY", "DATE_MDY"}:
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"Value {value!r} is not a valid ISO date for {value_format}.") from exc
            value = parsed.strftime("%d/%m/%Y" if value_format == "DATE_DMY" else "%m/%d/%Y")
        elif value_format == "DECIMAL_2":
            try:
                value = f"{Decimal(value):,.2f}"
            except InvalidOperation as exc:
                raise ValueError(f"Value {value!r} is not a valid decimal.") from exc
        maximum = config.max_characters
        if config.overflow_policy == "ERROR" and len(value) > maximum:
            raise ValueError(f"Formatted value exceeds the {maximum}-character overflow limit.")
        style = base_style
        if config.overflow_policy == "SHRINK" and len(value) > maximum:
            style = base_style.clone(f"{base_style.name}-shrink-{maximum}")
            style.fontSize = max(6, base_style.fontSize * maximum / len(value))
            style.leading = style.fontSize + 2
        return value, style

    @classmethod
    def _draw_page_region(cls, canvas, region, *, top, payload, fields, sections, styles, assets, layout, available_width, copy_name="", enforce_copy_scope=False):
        if region is None:
            return
        flowables = []
        cls._append_blocks(flowables, region.blocks, payload, fields, sections, styles, copy_name, False,
                           assets, layout, available_width, nested=True,
                           enforce_copy_scope=enforce_copy_scope)
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
