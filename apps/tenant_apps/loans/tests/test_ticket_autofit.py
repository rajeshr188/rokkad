"""Fictional PDF fixtures: preserve complete values inside their fixed frames."""
from dataclasses import replace
from pathlib import Path

import fitz
from django.test import SimpleTestCase
from reportlab.lib.units import mm

from apps.tenant_apps.loans.documents import ConfigurableDocumentRenderer as Renderer, starter_layout
from apps.tenant_apps.loans.documents.layouts import LayoutBlock
from apps.tenant_apps.loans.documents.payloads import DocumentField, DocumentSection
from .test_document_overlay_v4 import synthetic_payload


class TicketAutofitTests(SimpleTestCase):
    def render_block(self, block, text, *, section=None, schema=4):
        layout = starter_layout("loan_ticket", schema_version=schema, layout_mode="ABSOLUTE_OVERLAY")
        payload = replace(synthetic_payload(), verification_id=text,
            fields=(DocumentField("borrower.display", "Borrower", text),))
        pdf = Renderer._render_overlay_surface(payload, layout, {f.key:f for f in payload.fields},
            {section.key:section} if section else {}, {}, False, blocks=(block,), copy_scope="ORIGINAL")
        return fitz.open(stream=pdf, filetype="pdf")

    def block(self, **values):
        return LayoutBlock(**(dict(type="field", binding="borrower.display", show_label=False,
            x_mm=40, y_mm=50, width_mm=60, height_mm=30, font_size_pt=12,
            padding_pt=6, leading_pt=12, overflow_policy="SHRINK") | values))

    def spans(self, pdf):
        return [span for block in pdf[0].get_text("dict")["blocks"] for line in block.get("lines", []) for span in line["spans"]]

    def test_font_and_explicit_line_spacing_shrink_together_and_preserve_all_text(self):
        text = "\n".join(f"Complete address line {i}" for i in range(1,8))
        with self.render_block(self.block(), text) as pdf:
            self.assertEqual("".join(pdf[0].get_text().split()), "".join(text.split()))
            spans = self.spans(pdf)
            size = spans[0]["size"]
            self.assertGreaterEqual(size, 6)
            self.assertGreater(size, 10)
            self.assertLess(size, 12)
            self.assertAlmostEqual(spans[1]["origin"][1]-spans[0]["origin"][1], size, places=3)
            for span in spans:
                x0,y0,x1,y1=span["bbox"]
                self.assertGreaterEqual(x0,40*mm+6-.01)
                self.assertLessEqual(x1,100*mm-6+.01)
                self.assertGreaterEqual(y0,50*mm-.01)
                self.assertLessEqual(y1,80*mm+.01)

    def test_fitting_long_character_count_keeps_original_font(self):
        text = "i" * 130
        with self.render_block(self.block(width_mm=100, max_characters=20), text) as pdf:
            self.assertEqual("".join(pdf[0].get_text().split()), text)
            self.assertEqual({round(s["size"],3) for s in self.spans(pdf)}, {12})

    def test_all_scalar_block_types_fit_and_do_not_mutate_style_or_values(self):
        text = "One complete line\nSecond complete line\nThird complete line"
        for kind in ("field", "title", "signature", "verification"):
            with self.subTest(kind=kind):
                block = self.block(type=kind, text=text, height_mm=14, padding_pt=2, leading_pt=14)
                with self.render_block(block, text) as pdf:
                    self.assertIn("".join(text.split()), "".join(pdf[0].get_text().split()))
                    self.assertTrue(all(6<=s["size"]<12 for s in self.spans(pdf)))
                self.assertEqual(block.font_size_pt, 12)
                self.assertEqual(block.leading_pt, 14)

    def test_minimum_fails_clearly_without_clipping_and_wrap_remains_explicit(self):
        with self.assertRaisesMessage(ValueError, "Enlarge the frame"):
            self.render_block(self.block(height_mm=10), "\n".join("Full line" for _ in range(30)))
        with self.assertRaisesMessage(ValueError, "rectangle"):
            self.render_block(self.block(overflow_policy="WRAP"), "\n".join("Full line" for _ in range(7)))

    def test_table_rows_fit_without_omission(self):
        section = DocumentSection("collateral.items", "Items", tuple((f"Item {i}", f"Weight {i}") for i in range(5)))
        block = self.block(type="table", binding=section.key, width_mm=80, height_mm=27, padding_pt=0)
        with self.render_block(block, "", section=section) as pdf:
            text = pdf[0].get_text()
            for row in section.rows:
                for cell in row: self.assertIn(cell, text)
            self.assertTrue(all(6<=s["size"]<12 for s in self.spans(pdf)))
        with self.assertRaisesMessage(ValueError, "Enlarge the table frame"):
            self.render_block(replace(block, height_mm=5), "", section=section)

    def test_older_overlay_schema_keeps_fixed_leading_behavior(self):
        import io
        from reportlab.pdfgen.canvas import Canvas
        layout = starter_layout("loan_ticket", schema_version=3, layout_mode="ABSOLUTE_OVERLAY")
        style = Renderer._styles(layout)["BodyText"].clone("old-spacing")
        style.fontSize=12; style.leading=12
        with self.assertRaisesMessage(ValueError, "rectangle"):
            Renderer._draw_overlay_paragraph(Canvas(io.BytesIO()), "Line<br/>Line<br/>Line", style,
                0, 0, 100, 25, "SHRINK", fixed_leading=True, enforce_minimum=False)

    def test_new_precision_starter_uses_autofit_for_every_text_and_table_block(self):
        layout = starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY")
        self.assertTrue(all(b.overflow_policy=="SHRINK" for b in layout.all_blocks()
            if b.type in {"title","field","table","signature","verification"}))
