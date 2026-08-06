from django.test import SimpleTestCase
import fitz
import io
from PIL import Image as PillowImage

from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer,
    DocumentAssetError,
    DocumentAssetValidator,
    DocumentLayoutValidator,
    LayoutValidationError,
    starter_layout,
)
from apps.tenant_apps.loans.documents.payloads import (
    DocumentField,
    DocumentPayload,
    DocumentSection,
)


class ConfigurableDocumentLayoutTests(SimpleTestCase):
    def setUp(self):
        values = {
            "workspace.name": "Rokkad Test Workspace",
            "workspace.source_id": "Workspace:7",
            "license.display": "Pawnbroker License (PBL-77)",
            "license.source_id": "LoanLicense:11",
            "loan.source_id": "PawnLoan:19",
            "loan.number": "PL-A-00019",
            "loan.date": "2026-07-18",
            "loan.principal": "INR 10000.00",
            "loan.monthly_interest_rate": "2%",
            "loan.tenure": "3 months",
            "borrower.display": "Asha Devi (P-000013)",
            "borrower.source_id": "Party:13",
            "approval.source_id": "PawnLoanApprovalSnapshot:21",
            "approval.fingerprint": "approval-fingerprint-1",
        }
        self.payload = DocumentPayload(
            schema_version=1,
            document_type="loan_ticket",
            title="Pawn Loan Ticket",
            file_name="pawn_loan_ticket_PL-A-00019.pdf",
            verification_id="ROKKAD|workspace:7|loan:19|approval:21",
            fields=tuple(DocumentField(key, key, value) for key, value in values.items()),
            sections=(
                DocumentSection(
                    "collateral.items",
                    "Collateral",
                    (("Item", "Description"), ("17", "Gold chain")),
                ),
            ),
        )

    @staticmethod
    def _png_bytes(color="red"):
        buffer = io.BytesIO()
        PillowImage.new("RGB", (80, 40), color=color).save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _pdf_bytes():
        document = fitz.open()
        page = document.new_page()
        page.insert_text((30, 30), "BACKGROUND")
        value = document.tobytes()
        document.close()
        return value

    def test_starter_layout_renders_with_deterministic_evidence(self):
        layout = starter_layout("loan_ticket")

        first = ConfigurableDocumentRenderer.render(self.payload, layout)
        second = ConfigurableDocumentRenderer.render(self.payload, layout)

        self.assertTrue(first.pdf.startswith(b"%PDF"))
        self.assertEqual(first.layout_hash, second.layout_hash)
        self.assertEqual(first.payload_hash, second.payload_hash)
        self.assertEqual(first.renderer_version, "layout-reportlab-v1")
        self.assertIn(b"Gold chain", first.pdf)

    def test_schema_v1_remains_canonical_and_uses_v1_renderer(self):
        definition = starter_layout("loan_ticket").canonical_dict()

        layout = DocumentLayoutValidator.load(definition)
        result = ConfigurableDocumentRenderer.render(self.payload, layout)

        self.assertEqual(layout.schema_version, 1)
        self.assertNotIn("layout_mode", layout.canonical_dict())
        self.assertEqual(result.renderer_version, "layout-reportlab-v1")

    def test_schema_v2_flow_theme_and_margin_are_validated_and_rendered(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition.update({
            "schema_version": 2,
            "layout_mode": "FLOW",
            "page": {"margin_mm": 10},
            "theme": {
                "primary_color": "#7c2d12",
                "border_color": "#d6d3d1",
                "font_family": "HELVETICA",
                "body_font_size_pt": 9,
                "heading_font_size_pt": 16,
            },
        })

        layout = DocumentLayoutValidator.load(definition)
        result = ConfigurableDocumentRenderer.render(self.payload, layout)

        self.assertEqual(layout.layout_mode, "FLOW")
        self.assertEqual(layout.margin_mm, 10)
        self.assertEqual(layout.primary_color, "#7c2d12")
        self.assertEqual(result.renderer_version, "layout-reportlab-v2")

    def test_schema_v2_starter_is_available_without_changing_v1_default(self):
        legacy = starter_layout("loan_ticket")
        current = starter_layout("loan_ticket", schema_version=2)

        self.assertEqual(legacy.schema_version, 1)
        self.assertEqual(current.schema_version, 2)
        self.assertEqual(current.layout_mode, "FLOW")
        self.assertIn("theme", current.canonical_dict())

    def test_schema_v2_rejects_unsafe_theme_values(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition.update({"schema_version": 2, "theme": {"font_family": "../../evil.ttf"}})
        with self.assertRaisesMessage(LayoutValidationError, "not approved"):
            DocumentLayoutValidator.load(definition)

    def test_absolute_overlay_renders_bounded_content_over_pdf_background(self):
        background = DocumentAssetValidator.validate(
            key="form.background", kind="BACKGROUND", content=self._pdf_bytes(), workspace_id=7,
        )
        layout = starter_layout("loan_ticket", schema_version=2, layout_mode="ABSOLUTE_OVERLAY")

        result = ConfigurableDocumentRenderer.render(
            self.payload, layout, assets=(background,), preview=True,
        )

        self.assertEqual(result.renderer_version, "layout-reportlab-overlay-v1")
        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        text = pdf[0].get_text()
        self.assertIn("BACKGROUND", text)
        self.assertIn("PL-A-00019", text)
        self.assertIn("PREVIEW / NOT AN OFFICIAL ISSUE", text)
        loan_rect = pdf[0].search_for("PL-A-00019")[0]
        self.assertGreater(loan_rect.x0, 25)
        self.assertGreater(loan_rect.y0, 150)
        self.assertLess(loan_rect.y0, 220)
        pdf.close()

    def test_absolute_overlay_duplicate_and_duplex_page_counts(self):
        background = DocumentAssetValidator.validate(
            key="form.background", kind="BACKGROUND", content=self._pdf_bytes(), workspace_id=7,
        )
        definition = starter_layout("loan_ticket", schema_version=2, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        definition["copy_mode"] = "ORIGINAL_DUPLICATE_DUPLEX"
        definition["back_blocks"] = [
            {"type": "verification", "x_mm": 10, "y_mm": 20, "width_mm": 190, "height_mm": 12},
        ]
        layout = DocumentLayoutValidator.load(definition)

        result = ConfigurableDocumentRenderer.render(self.payload, layout, assets=(background,))

        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        self.assertEqual(len(pdf), 4)
        for page in pdf:
            self.assertIn("BACKGROUND", page.get_text())
        pdf.close()

    def test_absolute_overlay_geometry_and_background_requirements_fail_closed(self):
        definition = starter_layout("loan_ticket", schema_version=2, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        definition["background_asset_key"] = ""
        with self.assertRaisesMessage(LayoutValidationError, "require a background asset key"):
            DocumentLayoutValidator.load(definition)

        definition = starter_layout("loan_ticket", schema_version=2, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        definition["blocks"][0].update({"x_mm": 200, "width_mm": 20})
        with self.assertRaisesMessage(LayoutValidationError, "beyond the A4 page boundary"):
            DocumentLayoutValidator.load(definition)

        definition = starter_layout("loan_ticket", schema_version=2, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
        definition["blocks"].insert(1, {"type": "spacer", "x_mm": 1, "y_mm": 1, "width_mm": 10, "height_mm": 10})
        with self.assertRaisesMessage(LayoutValidationError, "not supported in absolute overlay"):
            DocumentLayoutValidator.load(definition)

    def test_schema_v2_sections_columns_and_field_grids_render(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["blocks"].insert(1, {
            "type": "section",
            "text": "Ticket summary",
            "style_variant": "OUTLINED",
            "blocks": [{
                "type": "field_grid", "grid_columns": 2,
                "bindings": ["loan.number", "loan.date", "loan.principal", "borrower.display"],
            }],
        })
        definition["blocks"].insert(2, {
            "type": "columns",
            "columns": [
                {"width_percent": 65, "blocks": [{"type": "field", "binding": "license.display"}]},
                {"width_percent": 35, "blocks": [{"type": "qr", "binding": "document.verification_id", "width_mm": 18}]},
            ],
        })

        layout = DocumentLayoutValidator.load(definition)
        result = ConfigurableDocumentRenderer.render(self.payload, layout)

        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        text = "".join(page.get_text() for page in pdf)
        pdf.close()
        self.assertIn("Ticket summary", text)
        self.assertIn("PL-A-00019", text)
        self.assertEqual(layout.canonical_dict()["blocks"][1]["type"], "section")

    def test_schema_v2_container_geometry_and_v1_use_fail_closed(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["blocks"].insert(1, {
            "type": "columns",
            "columns": [
                {"width_percent": 60, "blocks": [{"type": "field", "binding": "loan.number"}]},
                {"width_percent": 30, "blocks": [{"type": "field", "binding": "loan.date"}]},
            ],
        })
        with self.assertRaisesMessage(LayoutValidationError, "must total 100"):
            DocumentLayoutValidator.load(definition)

        definition = starter_layout("loan_ticket").canonical_dict()
        definition["blocks"].insert(1, {
            "type": "field_grid",
            "bindings": ["loan.number", "loan.date"],
        })
        with self.assertRaisesMessage(LayoutValidationError, "require layout schema version 2"):
            DocumentLayoutValidator.load(definition)

    def test_nested_assets_are_discovered_and_rendered(self):
        logo = DocumentAssetValidator.validate(
            key="business.logo", kind="IMAGE", content=self._png_bytes("blue"), workspace_id=7
        )
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["blocks"].insert(1, {
            "type": "columns",
            "columns": [
                {"width_percent": 50, "blocks": [{"type": "image", "asset_key": logo.key, "width_mm": 20}]},
                {"width_percent": 50, "blocks": [{"type": "field", "binding": "loan.number"}]},
            ],
        })
        layout = DocumentLayoutValidator.load(definition)

        with self.assertRaisesMessage(DocumentAssetError, "assets are missing"):
            ConfigurableDocumentRenderer.render(self.payload, layout)
        result = ConfigurableDocumentRenderer.render(self.payload, layout, assets=(logo,))
        self.assertEqual(dict(result.asset_hashes)[logo.key], logo.sha256)

    def test_configurable_table_columns_render_selected_labels_and_widths(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        table = next(block for block in definition["blocks"] if block["type"] == "table")
        table.update({
            "style_variant": "STRIPED",
            "repeat_header": True,
            "table_columns": [
                {"index": 0, "label": "Line", "width_percent": 25, "align": "CENTER"},
                {"index": 1, "label": "Pledged article", "width_percent": 75, "align": "LEFT"},
            ],
        })

        layout = DocumentLayoutValidator.load(definition)
        result = ConfigurableDocumentRenderer.render(self.payload, layout)

        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        text = "".join(page.get_text() for page in pdf)
        pdf.close()
        self.assertIn("Pledged article", text)
        self.assertIn("Gold chain", text)
        self.assertEqual(layout.canonical_dict()["blocks"][2]["table_columns"][1]["width_percent"], 75)

    def test_header_and_footer_repeat_on_every_flow_page(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["header"] = {"height_mm": 15, "blocks": [{"type": "title", "text": "REPEATING HEADER"}]}
        definition["footer"] = {"height_mm": 12, "blocks": [{"type": "field", "binding": "loan.number"}]}
        rows = (("Item", "Description"),) + tuple(
            (str(index), f"Long collateral row {index}") for index in range(1, 90)
        )
        payload = DocumentPayload(
            self.payload.schema_version, self.payload.document_type, self.payload.title,
            self.payload.file_name, self.payload.verification_id, self.payload.fields,
            (DocumentSection("collateral.items", "Collateral", rows),),
        )

        layout = DocumentLayoutValidator.load(definition)
        result = ConfigurableDocumentRenderer.render(payload, layout)

        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        self.assertGreater(len(pdf), 1)
        for page in pdf:
            text = page.get_text()
            self.assertIn("REPEATING HEADER", text)
            self.assertIn("PL-A-00019", text)
        pdf.close()

    def test_table_and_page_region_constraints_fail_closed(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        table = next(block for block in definition["blocks"] if block["type"] == "table")
        table["table_columns"] = [
            {"index": 0, "label": "A", "width_percent": 40, "align": "LEFT"},
            {"index": 1, "label": "B", "width_percent": 40, "align": "LEFT"},
        ]
        with self.assertRaisesMessage(LayoutValidationError, "must total 100"):
            DocumentLayoutValidator.load(definition)

        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["header"] = {"height_mm": 20, "blocks": [{"type": "table", "binding": "collateral.items"}]}
        with self.assertRaisesMessage(LayoutValidationError, "compact, non-repeating"):
            DocumentLayoutValidator.load(definition)

        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        table = next(block for block in definition["blocks"] if block["type"] == "table")
        table["table_columns"] = [
            {"index": 0, "label": "A", "width_percent": 50, "align": "LEFT"},
            {"index": 2, "label": "Missing", "width_percent": 50, "align": "LEFT"},
        ]
        layout = DocumentLayoutValidator.load(definition)
        with self.assertRaisesMessage(ValueError, "does not contain every configured column index"):
            ConfigurableDocumentRenderer.render(self.payload, layout)

    def test_safe_value_formats_and_visibility_conditions_render(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["blocks"].insert(1, {
            "type": "field", "binding": "loan.date", "value_format": "DATE_DMY",
        })
        definition["blocks"].insert(2, {
            "type": "section", "text": "MATCHED CONDITION", "style_variant": "TINTED",
            "visible_when": {"binding": "loan.number", "operator": "EQUALS", "value": "PL-A-00019"},
            "blocks": [{"type": "field", "binding": "loan.number", "value_format": "UPPER"}],
        })
        definition["blocks"].insert(3, {
            "type": "title", "text": "HIDDEN CONDITION",
            "visible_when": {"binding": "loan.number", "operator": "EQUALS", "value": "OTHER"},
        })

        result = ConfigurableDocumentRenderer.render(
            self.payload, DocumentLayoutValidator.load(definition)
        )

        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        text = "".join(page.get_text() for page in pdf)
        pdf.close()
        self.assertIn("18/07/2026", text)
        self.assertIn("MATCHED CONDITION", text)
        self.assertNotIn("HIDDEN CONDITION", text)

    def test_mandatory_bindings_cannot_exist_only_in_conditional_blocks(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        required_group = next(block for block in definition["blocks"] if block["type"] == "field_group")
        required_group["visible_when"] = {
            "binding": "loan.number", "operator": "PRESENT", "value": "",
        }

        with self.assertRaisesMessage(LayoutValidationError, "must have an unconditional occurrence"):
            DocumentLayoutValidator.load(definition)

    def test_overflow_error_and_shrink_policies_are_explicit(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["blocks"].insert(1, {
            "type": "field", "binding": "borrower.display",
            "overflow_policy": "ERROR", "max_characters": 10,
        })
        layout = DocumentLayoutValidator.load(definition)
        with self.assertRaisesMessage(ValueError, "10-character overflow limit"):
            ConfigurableDocumentRenderer.render(self.payload, layout)

        definition["blocks"][1]["overflow_policy"] = "SHRINK"
        result = ConfigurableDocumentRenderer.render(
            self.payload, DocumentLayoutValidator.load(definition)
        )
        self.assertTrue(result.pdf.startswith(b"%PDF"))

    def test_invalid_format_condition_and_overflow_configuration_fail_closed(self):
        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["blocks"].insert(1, {
            "type": "field", "binding": "loan.date", "value_format": "PYTHON_FORMAT",
        })
        with self.assertRaisesMessage(LayoutValidationError, "Value format is unsupported"):
            DocumentLayoutValidator.load(definition)

        definition = starter_layout("loan_ticket", schema_version=2).canonical_dict()
        definition["blocks"].insert(1, {
            "type": "title", "text": "Unsafe",
            "visible_when": {"binding": "loan.__class__", "operator": "EQUALS", "value": "x"},
        })
        with self.assertRaisesMessage(LayoutValidationError, "binding is not registered"):
            DocumentLayoutValidator.load(definition)

    def test_every_document_kind_has_a_valid_mandatory_starter(self):
        for kind in (
            "loan_ticket", "repayment_receipt", "release_memo",
            "auction_notice", "auction_recovery", "renewal",
        ):
            layout = starter_layout(kind)
            self.assertEqual(layout.document_type, kind)
            self.assertTrue(layout.content_hash)

    def test_preview_is_visibly_non_official(self):
        result = ConfigurableDocumentRenderer.render(
            self.payload, starter_layout("loan_ticket"), preview=True
        )

        self.assertIn(b"PREVIEW / NOT AN OFFICIAL ISSUE", result.pdf)

    def test_unknown_and_executable_bindings_fail_closed(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["blocks"][1]["bindings"].append("loan.__class__")

        with self.assertRaisesMessage(
            LayoutValidationError,
            "Field groups require only registered field bindings",
        ):
            DocumentLayoutValidator.load(definition)

        definition = starter_layout("loan_ticket").canonical_dict()
        definition["python"] = "import os"
        with self.assertRaisesMessage(LayoutValidationError, "Unknown layout properties"):
            DocumentLayoutValidator.load(definition)

    def test_required_regulatory_binding_cannot_be_removed(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["blocks"][1]["bindings"].remove("approval.fingerprint")

        with self.assertRaisesMessage(LayoutValidationError, "Required bindings are missing"):
            DocumentLayoutValidator.load(definition)

    def test_long_table_flows_across_pages(self):
        rows = (("Item", "Description"),) + tuple(
            (str(index), f"Collateral item {index} with a deliberately long description")
            for index in range(1, 90)
        )
        payload = DocumentPayload(
            schema_version=self.payload.schema_version,
            document_type=self.payload.document_type,
            title=self.payload.title,
            file_name=self.payload.file_name,
            verification_id=self.payload.verification_id,
            fields=self.payload.fields,
            sections=(DocumentSection("collateral.items", "Collateral", rows),),
        )

        result = ConfigurableDocumentRenderer.render(payload, starter_layout("loan_ticket"))

        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        self.assertGreater(len(pdf), 1)
        self.assertIn("Collateral item 89", "".join(page.get_text() for page in pdf))
        pdf.close()

    def test_original_duplicate_and_duplex_modes_have_expected_pages(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["copy_mode"] = "ORIGINAL_DUPLICATE_DUPLEX"
        definition["back_blocks"] = [
            {"type": "field_group", "bindings": sorted(definition["blocks"][1]["bindings"])},
            {"type": "verification"},
        ]
        layout = DocumentLayoutValidator.load(definition)

        result = ConfigurableDocumentRenderer.render(self.payload, layout)

        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        self.assertEqual(len(pdf), 4)
        pdf.close()

    def test_validated_logo_qr_and_background_render_with_asset_evidence(self):
        logo = DocumentAssetValidator.validate(
            key="business.logo", kind="IMAGE", content=self._png_bytes("blue"), workspace_id=7
        )
        background = DocumentAssetValidator.validate(
            key="ticket.background", kind="BACKGROUND", content=self._png_bytes("white"), workspace_id=7
        )
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["background_asset_key"] = background.key
        definition["blocks"].insert(1, {"type": "image", "asset_key": logo.key, "width_mm": 25})
        definition["blocks"].insert(2, {"type": "qr", "binding": "document.verification_id", "width_mm": 22})
        layout = DocumentLayoutValidator.load(definition)

        result = ConfigurableDocumentRenderer.render(
            self.payload, layout, assets=(logo, background)
        )

        self.assertTrue(result.pdf.startswith(b"%PDF"))
        self.assertEqual(dict(result.asset_hashes)[logo.key], logo.sha256)
        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        self.assertGreaterEqual(len(pdf[0].get_images(full=True)), 2)
        pdf.close()

    def test_missing_cross_workspace_and_corrupt_assets_fail_closed(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["blocks"].insert(1, {"type": "image", "asset_key": "business.logo"})
        layout = DocumentLayoutValidator.load(definition)

        with self.assertRaisesMessage(DocumentAssetError, "assets are missing"):
            ConfigurableDocumentRenderer.render(self.payload, layout)

        foreign_logo = DocumentAssetValidator.validate(
            key="business.logo", kind="IMAGE", content=self._png_bytes(), workspace_id=8
        )
        with self.assertRaisesMessage(DocumentAssetError, "another workspace"):
            ConfigurableDocumentRenderer.render(self.payload, layout, assets=(foreign_logo,))

        with self.assertRaisesMessage(DocumentAssetError, "corrupt or unsupported"):
            DocumentAssetValidator.validate(
                key="business.logo", kind="IMAGE", content=b"not-an-image", workspace_id=7
            )

        with self.assertRaisesMessage(DocumentAssetError, "corrupt or unreadable"):
            DocumentAssetValidator.validate(
                key="ticket.background", kind="BACKGROUND",
                content=b"%PDF-corrupt", workspace_id=7,
            )

    def test_pdf_background_is_applied_to_every_duplex_copy_page(self):
        background = DocumentAssetValidator.validate(
            key="ticket.background", kind="BACKGROUND",
            content=self._pdf_bytes(), workspace_id=7,
        )
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["copy_mode"] = "ORIGINAL_DUPLICATE_DUPLEX"
        definition["background_asset_key"] = background.key
        definition["back_blocks"] = [
            {"type": "field_group", "bindings": sorted(definition["blocks"][1]["bindings"])},
            {"type": "verification"},
        ]
        layout = DocumentLayoutValidator.load(definition)

        result = ConfigurableDocumentRenderer.render(
            self.payload, layout, assets=(background,)
        )

        pdf = fitz.open(stream=result.pdf, filetype="pdf")
        self.assertEqual(len(pdf), 4)
        for page in pdf:
            self.assertIn("BACKGROUND", page.get_text())
        pdf.close()

    def test_bundled_unicode_font_renders_regional_text(self):
        fields = list(self.payload.fields)
        fields[3] = type(fields[3])(fields[3].key, "கடன் எண்", "கடன்-௧௯")
        payload = DocumentPayload(
            self.payload.schema_version, self.payload.document_type,
            "அடகு கடன் சீட்டு", self.payload.file_name,
            self.payload.verification_id, tuple(fields), self.payload.sections,
        )

        result = ConfigurableDocumentRenderer.render(payload, starter_layout("loan_ticket"))

        self.assertTrue(result.pdf.startswith(b"%PDF"))
        self.assertGreater(len(result.pdf), 1000)
