"""Synthetic precision-overlay contracts; no production fixtures or media."""

import copy
import json

import fitz
from django.test import SimpleTestCase
from reportlab.lib.units import mm

from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer, DocumentAssetError, DocumentAssetValidator,
    DocumentLayoutValidator, LayoutValidationError, PrintProfileValidator, PrintProfileValidationError, built_in_print_profile, starter_layout,
)
from apps.tenant_apps.loans.documents.layouts import REQUIRED_BINDINGS
from apps.tenant_apps.loans.documents.payloads import DocumentField, DocumentPayload, DocumentSection
from apps.tenant_apps.loans.web.document_forms import (
    LoanDocumentLayoutCreateForm, LoanDocumentOverlayBlockForm, LoanDocumentOverlayLogicalSettingsForm,
    LoanDocumentPrintProfileDefinitionForm,
)


def synthetic_payload():
    values = {key: "SYNTHETIC" for key in REQUIRED_BINDINGS["loan_ticket"]}
    values.update({"workspace.source_id": "Workspace:7", "loan.number": "TEST-00019"})
    return DocumentPayload(
        schema_version=1, document_type="loan_ticket", title="Synthetic ticket",
        file_name="synthetic-ticket.pdf", verification_id="TEST|workspace:7|loan:19",
        fields=tuple(DocumentField(key, key, value) for key, value in values.items()),
        sections=(DocumentSection("collateral.items", "Collateral", (("Item", "Description"), ("1", "Test chain"))),),
    )


class PrecisionOverlayTests(SimpleTestCase):
    def setUp(self):
        self.definition = starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        self.payload = synthetic_payload()
        self.profile = built_in_print_profile("LEGACY_BOTH_SIMPLEX")

    def render(self, definition=None, assets=(), **kwargs):
        return ConfigurableDocumentRenderer.render_with_print_profile(
            self.payload, DocumentLayoutValidator.load(definition or self.definition), self.profile, assets=assets, **kwargs,
        )

    def test_preprinted_guides_appear_only_in_design_preview(self):
        definition = self.profile.canonical_dict()
        definition.update(schema_version=2, stock_mode="PREPRINTED")
        self.profile = PrintProfileValidator.load(definition)
        self.definition["background_asset_key"] = "guide"
        with fitz.open() as pdf:
            pdf.new_page().insert_text((30, 20), "GUIDE-ONLY-MARKER")
            asset = DocumentAssetValidator.validate(key="guide", kind="BACKGROUND", content=pdf.tobytes(), workspace_id=7)
        for preview, design in ((False, False), (True, False), (True, True)):
            with self.subTest(preview=preview, design=design):
                result = self.render(assets=(asset,), preview=preview, design_preview=design)
                with fitz.open(stream=result.pdf, filetype="pdf") as pdf:
                    for page in pdf:
                        text = page.get_text()
                        self.assertEqual("GUIDE-ONLY-MARKER" in text, design)
                        self.assertEqual("DESIGN PREVIEW" in text, design)
                        self.assertIn("TEST-00019", text)
        with self.assertRaisesMessage(ValueError, "unofficial"):
            self.render(assets=(asset,), design_preview=True)
        definition["stock_mode"] = "PLAIN"
        self.profile = PrintProfileValidator.load(definition)
        with fitz.open(stream=self.render(assets=(asset,)).pdf, filetype="pdf") as pdf:
            self.assertIn("GUIDE-ONLY-MARKER", pdf[0].get_text())

    def test_preprinted_rejects_legacy_layout_and_background_only_backs(self):
        definition = built_in_print_profile("LEGACY_BOTH_DUPLEX").canonical_dict()
        definition.update(schema_version=2, stock_mode="PREPRINTED")
        profile = PrintProfileValidator.load(definition)
        with self.assertRaisesMessage(ValueError, "precision"):
            ConfigurableDocumentRenderer.assert_print_profile_compatible(starter_layout("loan_ticket"), profile)
        self.definition["surfaces"] = {"backgrounds": {"original_back": "terms", "duplicate_back": "d3"}}
        layout = DocumentLayoutValidator.load(self.definition)
        with self.assertRaisesMessage(ValueError, "back surface"):
            ConfigurableDocumentRenderer.assert_print_profile_compatible(layout, profile)

    def test_print_profile_stock_is_versioned_and_preserved_by_form(self):
        old = self.profile.canonical_dict()
        self.assertNotIn("stock_mode", old)
        invalid = {**old, "stock_mode": "PREPRINTED"}
        with self.assertRaises(PrintProfileValidationError):
            PrintProfileValidator.load(invalid)
        current = PrintProfileValidator.load({**invalid, "schema_version": 2})
        self.assertEqual(current.content_hash, PrintProfileValidator.load(current.canonical_dict()).content_hash)
        with self.assertRaises(PrintProfileValidationError):
            PrintProfileValidator.load({**old, "schema_version": 2, "stock_mode": "UNKNOWN"})
        with self.assertRaises(PrintProfileValidationError):
            PrintProfileValidator.load({**old, "schema_version": 2})
        data = {"composition": "A5_BOTH_SIMPLEX", "scaling_policy": "ACTUAL_SIZE", "stock_mode": "PREPRINTED", "flip_edge_guidance": "NOT_APPLICABLE"}
        form = LoanDocumentPrintProfileDefinitionForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.definition(name="Stock")["schema_version"], 2)
        data["stock_mode"] = "PLAIN"
        form = LoanDocumentPrintProfileDefinitionForm(data, schema_version=2)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.definition(name="Stock")["stock_mode"], "PLAIN")
        del data["stock_mode"]
        self.assertFalse(LoanDocumentPrintProfileDefinitionForm(data, schema_version=2).is_valid())

    def test_padding_and_explicit_line_spacing_match_legacy_text_frame_metrics(self):
        block = self.definition["blocks"][0]
        block.update(text="FIRST LINE\nSECOND <b>LINE</b>", x_mm=40, y_mm=50, width_mm=60, height_mm=30, font_size_pt=10, align="LEFT", padding_pt=6, leading_pt=12)
        with fitz.open(stream=self.render().pdf, filetype="pdf") as pdf:
            first = pdf[0].search_for("FIRST LINE")[0]
            second = pdf[0].search_for("SECOND <b>LINE</b>")[0]
            self.assertAlmostEqual(first.x0, 40 * mm + 6, places=3)
            self.assertAlmostEqual(second.y0 - first.y0, 12, places=3)
        block["padding_pt"] = 0
        with fitz.open(stream=self.render().pdf, filetype="pdf") as pdf:
            unpadded = pdf[0].search_for("FIRST LINE")[0]
            self.assertAlmostEqual(first.y0 - unpadded.y0, 6, places=3)

    def test_spacing_validation_and_overflow_do_not_silently_clip_text(self):
        for changes in ({"padding_pt": -1}, {"padding_pt": True}, {"padding_pt": 1.01}, {"leading_pt": 5}, {"leading_pt": float("inf")}, {"padding_pt": 20, "height_mm": 5}):
            with self.subTest(changes=changes), self.assertRaises(LayoutValidationError):
                definition = copy.deepcopy(self.definition)
                definition["blocks"][0].update(changes)
                DocumentLayoutValidator.load(definition)
        self.definition["blocks"][0].update(text="ONE\nTWO\nTHREE", font_size_pt=10, height_mm=10, padding_pt=6, leading_pt=12)
        with self.assertRaisesMessage(ValueError, "rectangle"):
            self.render()

    def test_default_spacing_preserves_existing_v4_hashes(self):
        before = DocumentLayoutValidator.load(self.definition).content_hash
        self.definition["blocks"][0].update(padding_pt=0, leading_pt=0)
        self.assertEqual(DocumentLayoutValidator.load(self.definition).content_hash, before)
        old = starter_layout("loan_ticket", schema_version=3, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        old["blocks"][0]["padding_pt"] = 6
        with self.assertRaises(LayoutValidationError):
            DocumentLayoutValidator.load(old)

    def test_data_only_prints_both_copies_without_assets(self):
        result = self.render()
        with fitz.open(stream=result.pdf, filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 2)
            for page in pdf:
                self.assertIn("TEST-00019", page.get_text())
        self.assertEqual(result.asset_hashes, ())
        self.assertEqual(result.renderer_version, "layout-reportlab-profile-v4")

    def test_value_only_and_literal_custom_label(self):
        block = next(b for b in self.definition["blocks"] if b["binding"] == "loan.number")
        block["show_label"] = False
        with fitz.open(stream=self.render().pdf, filetype="pdf") as pdf:
            self.assertIn("TEST-00019", pdf[0].get_text())
            self.assertNotIn("loan.number", pdf[0].get_text())
        block.update(show_label=True, field_label="Ticket <b>number</b>")
        with fitz.open(stream=self.render().pdf, filetype="pdf") as pdf:
            self.assertIn("Ticket <b>number</b>", pdf[0].get_text())
            self.assertNotIn("loan.number", pdf[0].get_text())

    def test_tenth_millimetre_position_reaches_pdf(self):
        block = next(b for b in self.definition["blocks"] if b["binding"] == "loan.number")
        block.update(show_label=False, x_mm=10.1, y_mm=25.1)
        with fitz.open(stream=self.render().pdf, filetype="pdf") as pdf:
            first = pdf[0].search_for("TEST-00019")[0]
        block.update(x_mm=10.2, y_mm=25.2)
        with fitz.open(stream=self.render().pdf, filetype="pdf") as pdf:
            second = pdf[0].search_for("TEST-00019")[0]
        self.assertAlmostEqual(second.x0 - first.x0, 0.1 * mm, places=3)
        self.assertAlmostEqual(second.y0 - first.y0, 0.1 * mm, places=3)

    def test_a5_actual_size_preserves_independent_original_and_duplicate_positions(self):
        self.definition["page_size"] = "A5"
        for block in self.definition["blocks"]:
            for key in ("x_mm", "y_mm", "width_mm", "height_mm"):
                block[key] = round(block[key] * 0.65, 1)
            block["font_size_pt"] = 6
            if block["type"] == "field":
                block["show_label"] = False
        original = next(b for b in self.definition["blocks"] if b["binding"] == "loan.number")
        original.update(copy_scope="ORIGINAL", x_mm=10.1, y_mm=25.1)
        duplicate = {**original, "copy_scope": "DUPLICATE", "x_mm": 20.2}
        self.definition["blocks"].append(duplicate)
        profile = built_in_print_profile("A5_BOTH_SIMPLEX").canonical_dict()
        profile["scaling_policy"] = "ACTUAL_SIZE"
        self.profile = PrintProfileValidator.load(profile)
        with fitz.open(stream=self.render().pdf, filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 2)
            self.assertAlmostEqual(pdf[0].rect.width / mm, 148, places=3)
            self.assertAlmostEqual(pdf[0].search_for("TEST-00019")[0].x0 / mm, 10.1, places=3)
            self.assertAlmostEqual(pdf[1].search_for("TEST-00019")[0].x0 / mm, 20.2, places=3)

    def test_canonical_geometry_normalizes_whole_values_and_round_trips(self):
        original = DocumentLayoutValidator.load(self.definition)
        self.definition["blocks"][0]["x_mm"] = 10.0
        equivalent = DocumentLayoutValidator.load(self.definition)
        self.assertEqual(original.content_hash, equivalent.content_hash)
        self.definition["blocks"][0].update(x_mm=10.1, width_mm=189.9)
        precise = DocumentLayoutValidator.load(self.definition)
        reloaded = DocumentLayoutValidator.load(json.loads(json.dumps(precise.canonical_dict())))
        self.assertEqual(precise.content_hash, reloaded.content_hash)

    def test_invalid_geometry_and_out_of_page_frames_fail_closed(self):
        for value in (True, "10.1", -0.1, 10.01, float("nan"), float("inf"), 301):
            with self.subTest(value=value), self.assertRaises(LayoutValidationError):
                definition = copy.deepcopy(self.definition)
                definition["blocks"][0]["x_mm"] = value
                DocumentLayoutValidator.load(definition)
        self.definition["blocks"][0].update(x_mm=20.2, width_mm=189.9)
        with self.assertRaises(LayoutValidationError):
            DocumentLayoutValidator.load(self.definition)
        self.definition["blocks"][0].update(x_mm=20.1)
        DocumentLayoutValidator.load(self.definition)  # Exact page edge remains valid.

    def test_background_is_optional_but_configured_assets_keep_workspace_boundary(self):
        self.definition["background_asset_key"] = "stationery"
        with self.assertRaises(DocumentAssetError):
            self.render()
        with fitz.open() as pdf:
            page = pdf.new_page()
            page.insert_text((30, 20), "SYNTHETIC BACKGROUND")
            content = pdf.tobytes()
        foreign = DocumentAssetValidator.validate(key="stationery", kind="BACKGROUND", content=content, workspace_id=8)
        with self.assertRaises(DocumentAssetError):
            self.render(assets=(foreign,))
        local = DocumentAssetValidator.validate(key="stationery", kind="BACKGROUND", content=content, workspace_id=7)
        with fitz.open(stream=self.render(assets=(local,)).pdf, filetype="pdf") as pdf:
            self.assertIn("SYNTHETIC BACKGROUND", pdf[0].get_text())
            self.assertIn("TEST-00019", pdf[0].get_text())

    def test_letter_bounds_use_actual_paper_dimensions(self):
        self.definition["page_size"] = "LETTER"
        self.definition["blocks"][0].update(x_mm=0, width_mm=215.9, y_mm=271.4, height_mm=8)
        DocumentLayoutValidator.load(self.definition)
        self.definition["blocks"][0]["width_mm"] = 216
        with self.assertRaises(LayoutValidationError):
            DocumentLayoutValidator.load(self.definition)

    def test_value_only_does_not_remove_required_business_fields(self):
        self.definition["blocks"] = [b for b in self.definition["blocks"] if b["binding"] != "loan.number"]
        with self.assertRaises(LayoutValidationError):
            DocumentLayoutValidator.load(self.definition)

    def test_old_layouts_keep_background_and_integer_contracts(self):
        old = starter_layout("loan_ticket", schema_version=3, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        self.assertNotIn("show_label", old["blocks"][0])
        for change in ({"x_mm": 10.1}, {"show_label": False}):
            definition = copy.deepcopy(old)
            definition["blocks"][1].update(change)
            with self.assertRaises(LayoutValidationError):
                DocumentLayoutValidator.load(definition)
        old["background_asset_key"] = ""
        with self.assertRaises(LayoutValidationError):
            DocumentLayoutValidator.load(old)

    def test_precision_form_serializes_decimal_positions_and_value_choice(self):
        form = LoanDocumentOverlayBlockForm({
            "block_type": "field", "binding": "loan.number", "x_mm": "10.1", "y_mm": "25.2",
            "width_mm": "90.3", "height_mm": "8.4", "font_size_pt": "8", "align": "LEFT",
            "copy_scope": "BOTH", "value_display": "VALUE_ONLY", "field_label": "Ticket",
        }, schema_version=4)
        self.assertTrue(form.is_valid(), form.errors)
        block = form.block_definition()
        self.assertEqual(json.loads(json.dumps(block))["x_mm"], 10.1)
        self.assertFalse(block["show_label"])
        self.assertNotIn("value_display", LoanDocumentOverlayBlockForm().fields)

    def test_optional_background_form_and_creation_are_explicitly_versioned(self):
        data = {"page_size": "A4"}
        self.assertTrue(LoanDocumentOverlayLogicalSettingsForm(data, schema_version=4).is_valid())
        self.assertFalse(LoanDocumentOverlayLogicalSettingsForm(data).is_valid())
        data = {"name": "Precision", "document_type": "loan_ticket", "layout_mode": "ABSOLUTE_OVERLAY", "precision_overlay": True}
        self.assertTrue(LoanDocumentLayoutCreateForm(data).is_valid())
        data["layout_mode"] = "FLOW"
        self.assertFalse(LoanDocumentLayoutCreateForm(data).is_valid())

    def test_dynamic_photo_form_and_layout_are_explicit_and_versioned(self):
        data = {"block_type": "image", "binding": "borrower.photo", "x_mm": 10, "y_mm": 10,
                "width_mm": 20, "height_mm": 20, "font_size_pt": 10, "align": "LEFT",
                "copy_scope": "BOTH", "optional_photo": True}
        form = LoanDocumentOverlayBlockForm(data, schema_version=4)
        self.assertTrue(form.is_valid(), form.errors)
        self.definition["blocks"].append(form.block_definition())
        layout = DocumentLayoutValidator.load(self.definition)
        self.assertTrue(layout.blocks[-1].optional_photo)
        self.assertFalse(LoanDocumentOverlayBlockForm(data, schema_version=3).is_valid())
        self.assertFalse(LoanDocumentOverlayBlockForm({**data, "asset_key": "logo"}, schema_version=4, asset_keys=("logo",)).is_valid())
        self.assertFalse(LoanDocumentOverlayBlockForm({**data, "block_type": "field"}, schema_version=4).is_valid())
        self.definition["blocks"][-1]["binding"] = "arbitrary.private.path"
        with self.assertRaises(LayoutValidationError):
            DocumentLayoutValidator.load(self.definition)

    def test_old_static_images_keep_ignoring_unused_scalar_binding(self):
        import io
        from PIL import Image
        image = io.BytesIO()
        Image.new("RGB", (20, 20), "blue").save(image, format="PNG")
        logo = DocumentAssetValidator.validate(key="logo", kind="IMAGE", content=image.getvalue(), workspace_id=7)
        with fitz.open() as pdf:
            pdf.new_page().insert_text((20, 20), "Legacy")
            background = DocumentAssetValidator.validate(key="form.background", kind="BACKGROUND", content=pdf.tobytes(), workspace_id=7)
        for version in (2, 3):
            with self.subTest(version=version):
                definition = starter_layout("loan_ticket", schema_version=version, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
                definition["blocks"].append({"type": "image", "asset_key": "logo", "binding": "loan.number",
                    "x_mm": 150, "y_mm": 145, "width_mm": 20, "height_mm": 20})
                layout = DocumentLayoutValidator.load(definition)
                if version == 3:
                    result = ConfigurableDocumentRenderer.render_with_print_profile(self.payload, layout, self.profile, assets=(logo, background))
                else:
                    result = ConfigurableDocumentRenderer.render(self.payload, layout, assets=(logo, background))
                with fitz.open(stream=result.pdf, filetype="pdf") as pdf:
                    self.assertTrue(pdf[0].get_images())
