"""Synthetic precision-overlay contracts; no production fixtures or media."""

import copy
import json

import fitz
from django.test import SimpleTestCase
from reportlab.lib.units import mm

from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer, DocumentAssetError, DocumentAssetValidator,
    DocumentLayoutValidator, LayoutValidationError, PrintProfileValidator, built_in_print_profile, starter_layout,
)
from apps.tenant_apps.loans.documents.layouts import REQUIRED_BINDINGS
from apps.tenant_apps.loans.documents.payloads import DocumentField, DocumentPayload, DocumentSection
from apps.tenant_apps.loans.web.document_forms import (
    LoanDocumentLayoutCreateForm, LoanDocumentOverlayBlockForm, LoanDocumentOverlayLogicalSettingsForm,
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

    def render(self, definition=None, assets=()):
        return ConfigurableDocumentRenderer.render_with_print_profile(
            self.payload, DocumentLayoutValidator.load(definition or self.definition), self.profile, assets=assets,
        )

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
