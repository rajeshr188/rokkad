"""Constrained, database-free layout contracts for PawnLoan documents."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .payloads import PawnLoanDocumentProjectionBuilder


class LayoutValidationError(ValueError):
    pass


ALLOWED_BLOCK_TYPES = frozenset(
    {"title", "field", "field_group", "table", "image", "qr", "verification", "signature", "spacer", "page_break", "section", "columns", "field_grid"}
)
ALLOWED_PAGE_SIZES = frozenset({"A4", "A5", "LETTER"})
ALLOWED_COPY_MODES = frozenset({"SINGLE", "ORIGINAL_DUPLICATE", "ORIGINAL_DUPLICATE_DUPLEX"})
ALLOWED_LAYOUT_MODES = frozenset({"FLOW", "ABSOLUTE_OVERLAY"})
ALLOWED_FONT_FAMILIES = frozenset({"HELVETICA", "NOTO_SANS_TAMIL"})
ALLOWED_VALUE_FORMATS = frozenset({"DEFAULT", "UPPER", "LOWER", "DATE_DMY", "DATE_MDY", "DECIMAL_2"})
ALLOWED_OVERFLOW_POLICIES = frozenset({"WRAP", "SHRINK", "ERROR"})
ALLOWED_COPY_SCOPES = frozenset({"BOTH", "ORIGINAL", "DUPLICATE"})
ALLOWED_SHEET_COMPOSITIONS = frozenset({
    "A5_ORIGINAL", "A5_ORIGINAL_TERMS_DUPLEX", "A5_DUPLICATE",
    "A5_DUPLICATE_D3_DUPLEX", "A5_BOTH_SIMPLEX", "A5_BOTH_DUPLEX",
    "A4_SIDE_BY_SIDE", "A4_SIDE_BY_SIDE_DUPLEX",
})

REQUIRED_BINDINGS = {
    "loan_ticket": frozenset({"workspace.name", "workspace.source_id", "license.display", "license.source_id", "loan.source_id", "loan.number", "loan.date", "loan.principal", "loan.monthly_interest_rate", "loan.tenure", "borrower.display", "borrower.source_id", "approval.source_id", "approval.fingerprint"}),
    "repayment_receipt": frozenset({"workspace.name", "workspace.source_id", "license.display", "loan.number", "borrower.display", "repayment.source_id", "event.fingerprint", "event.effective_date", "repayment.amount_received", "amounts.fees", "amounts.total_interest", "loan.principal", "accounting.delivery", "accounting.references"}),
    "release_memo": frozenset({"workspace.name", "workspace.source_id", "license.display", "loan.number", "borrower.display", "release.source_id", "release.number", "document.status", "event.fingerprint", "event.effective_date", "release.type", "amounts.principal_settled", "amounts.interest_settled", "amounts.fees_settled", "amounts.total_settlement", "accounting.delivery", "accounting.references"}),
    "auction_notice": frozenset({"workspace.name", "workspace.source_id", "license.display", "loan.number", "borrower.display", "auction.source_id", "auction.number", "document.status", "auction.notice_date", "auction.scheduled_date"}),
    "auction_recovery": frozenset({"workspace.name", "workspace.source_id", "license.display", "auction.source_id", "auction.number", "document.status", "event.effective_date", "auction.buyer", "amounts.principal_recovered", "amounts.interest_recovered", "amounts.fees_recovered", "amounts.total_recovery", "accounting.delivery", "accounting.references"}),
    "renewal": frozenset({"workspace.name", "workspace.source_id", "license.display", "renewal.source_id", "renewal.number", "document.status", "renewal.date", "renewal.mode", "renewal.source_loan", "renewal.successor_loan", "borrower.display", "renewal.source_principal_settled", "amounts.interest_settled", "amounts.fees_settled", "renewal.principal_paid", "renewal.top_up_disbursed", "renewal.successor_principal", "renewal.settlement_accounting", "renewal.successor_opening"}),
}
REQUIRED_SECTIONS = {
    "loan_ticket": frozenset({"collateral.items"}),
    "repayment_receipt": frozenset(),
    "release_memo": frozenset({"release.collateral_returned"}),
    "auction_notice": frozenset(),
    "auction_recovery": frozenset({"auction.collateral_disposed"}),
    "renewal": frozenset({"renewal.collateral_movement"}),
}


@dataclass(frozen=True)
class LayoutBlock:
    type: str
    binding: str = ""
    bindings: tuple[str, ...] = ()
    text: str = ""
    height_mm: int = 4
    asset_key: str = ""
    width_mm: int = 30
    blocks: tuple[LayoutBlock, ...] = ()
    columns: tuple[LayoutColumn, ...] = ()
    grid_columns: int = 2
    style_variant: str = "PLAIN"
    table_columns: tuple[TableColumn, ...] = ()
    repeat_header: bool = True
    value_format: str = "DEFAULT"
    overflow_policy: str = "WRAP"
    max_characters: int = 120
    visible_when: VisibilityCondition | None = None
    x_mm: int = 0
    y_mm: int = 0
    font_size_pt: int = 10
    align: str = "LEFT"
    copy_scope: str = "BOTH"


@dataclass(frozen=True)
class LayoutColumn:
    width_percent: int
    blocks: tuple[LayoutBlock, ...]


@dataclass(frozen=True)
class TableColumn:
    index: int
    label: str
    width_percent: int
    align: str = "LEFT"
    value_format: str = "DEFAULT"
    overflow_policy: str = "WRAP"
    max_characters: int = 120


@dataclass(frozen=True)
class VisibilityCondition:
    binding: str
    operator: str
    value: str = ""


@dataclass(frozen=True)
class PageRegion:
    height_mm: int
    blocks: tuple[LayoutBlock, ...]


@dataclass(frozen=True)
class SheetComposition:
    composition: str
    backgrounds: tuple[tuple[str, str], ...]

    def background(self, surface):
        return dict(self.backgrounds).get(surface, "")


@dataclass(frozen=True)
class DocumentLayout:
    schema_version: int
    document_type: str
    name: str
    page_size: str
    copy_mode: str
    blocks: tuple[LayoutBlock, ...]
    back_blocks: tuple[LayoutBlock, ...] = ()
    background_asset_key: str = ""
    layout_mode: str = "FLOW"
    margin_mm: int = 14
    primary_color: str = "#000000"
    border_color: str = "#cbd5e1"
    font_family: str = "NOTO_SANS_TAMIL"
    body_font_size_pt: int = 10
    heading_font_size_pt: int = 14
    header: PageRegion | None = None
    footer: PageRegion | None = None
    sheet: SheetComposition | None = None

    def canonical_dict(self):
        def block_dict(block):
            value = {
                "type": block.type, "binding": block.binding,
                "bindings": list(block.bindings), "text": block.text,
                "height_mm": block.height_mm,
                "asset_key": block.asset_key, "width_mm": block.width_mm,
            }
            if self.schema_version >= 2:
                value.update({
                    "blocks": [block_dict(child) for child in block.blocks],
                    "columns": [
                        {"width_percent": column.width_percent,
                         "blocks": [block_dict(child) for child in column.blocks]}
                        for column in block.columns
                    ],
                    "grid_columns": block.grid_columns,
                    "style_variant": block.style_variant,
                    "table_columns": [
                        {"index": column.index, "label": column.label,
                         "width_percent": column.width_percent, "align": column.align,
                         "value_format": column.value_format,
                         "overflow_policy": column.overflow_policy,
                         "max_characters": column.max_characters}
                        for column in block.table_columns
                    ],
                    "repeat_header": block.repeat_header,
                    "value_format": block.value_format,
                    "overflow_policy": block.overflow_policy,
                    "max_characters": block.max_characters,
                    "visible_when": (
                        {"binding": block.visible_when.binding,
                         "operator": block.visible_when.operator,
                         "value": block.visible_when.value}
                        if block.visible_when else None
                    ),
                    "x_mm": block.x_mm,
                    "y_mm": block.y_mm,
                    "font_size_pt": block.font_size_pt,
                    "align": block.align,
                    "copy_scope": block.copy_scope,
                })
            return value
        value = {
            "schema_version": self.schema_version, "document_type": self.document_type,
            "name": self.name, "page_size": self.page_size, "copy_mode": self.copy_mode,
            "blocks": [block_dict(block) for block in self.blocks],
            "back_blocks": [block_dict(block) for block in self.back_blocks],
            "background_asset_key": self.background_asset_key,
        }
        if self.schema_version >= 2:
            value.update({
                "layout_mode": self.layout_mode,
                "page": {"margin_mm": self.margin_mm},
                "theme": {
                    "primary_color": self.primary_color,
                    "border_color": self.border_color,
                    "font_family": self.font_family,
                    "body_font_size_pt": self.body_font_size_pt,
                    "heading_font_size_pt": self.heading_font_size_pt,
                },
                "header": self._region_dict(self.header, block_dict),
                "footer": self._region_dict(self.footer, block_dict),
                "sheet": (
                    {"composition": self.sheet.composition,
                     "backgrounds": dict(self.sheet.backgrounds)}
                    if self.sheet else None
                ),
            })
        return value

    @staticmethod
    def _region_dict(region, block_dict):
        if region is None:
            return None
        return {"height_mm": region.height_mm, "blocks": [block_dict(block) for block in region.blocks]}

    def all_blocks(self):
        def walk(blocks):
            for block in blocks:
                yield block
                yield from walk(block.blocks)
                for column in block.columns:
                    yield from walk(column.blocks)
        region_blocks = tuple(self.header.blocks if self.header else ()) + tuple(self.footer.blocks if self.footer else ())
        return tuple(walk(self.blocks + self.back_blocks + region_blocks))

    def background_asset_keys(self):
        keys = {self.background_asset_key} if self.background_asset_key else set()
        if self.sheet:
            keys.update(key for _, key in self.sheet.backgrounds if key)
        return frozenset(keys)

    @property
    def content_hash(self):
        encoded = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class DocumentLayoutValidator:
    SCHEMA_VERSION = 2
    SUPPORTED_SCHEMA_VERSIONS = frozenset({1, 2})

    @classmethod
    def load(cls, definition):
        if not isinstance(definition, dict):
            raise LayoutValidationError("Layout must be a JSON object.")
        schema_version = definition.get("schema_version")
        if schema_version not in cls.SUPPORTED_SCHEMA_VERSIONS:
            raise LayoutValidationError("Unsupported layout schema version.")
        allowed_keys = {"schema_version", "document_type", "name", "page_size", "copy_mode", "blocks", "back_blocks", "background_asset_key"}
        if schema_version >= 2:
            allowed_keys.update({"layout_mode", "page", "theme", "header", "footer", "sheet"})
        unknown = set(definition) - allowed_keys
        if unknown:
            raise LayoutValidationError(f"Unknown layout properties: {', '.join(sorted(unknown))}.")
        document_type = definition.get("document_type")
        if document_type not in REQUIRED_BINDINGS:
            raise LayoutValidationError("Unsupported document type.")
        page_size = definition.get("page_size", "A4")
        copy_mode = definition.get("copy_mode", "SINGLE")
        if page_size not in ALLOWED_PAGE_SIZES:
            raise LayoutValidationError("Unsupported page size.")
        if copy_mode not in ALLOWED_COPY_MODES:
            raise LayoutValidationError("Unsupported copy mode.")
        layout_mode, margin_mm, theme = cls._composition_settings(definition, schema_version)
        blocks = cls._blocks(definition.get("blocks"), document_type, schema_version, layout_mode=layout_mode)
        back_blocks = cls._blocks(definition.get("back_blocks", []), document_type, schema_version, layout_mode=layout_mode)
        header = cls._region(definition.get("header"), document_type, schema_version, "Header")
        footer = cls._region(definition.get("footer"), document_type, schema_version, "Footer")
        sheet = cls._sheet(
            definition.get("sheet"), schema_version, layout_mode, page_size,
            document_type,
        )
        if not blocks:
            raise LayoutValidationError("A layout requires at least one front-page block.")
        if copy_mode == "ORIGINAL_DUPLICATE_DUPLEX" and not back_blocks and not definition.get("sheet"):
            raise LayoutValidationError("Duplex layouts require back-page blocks.")
        region_blocks = tuple(header.blocks if header else ()) + tuple(footer.blocks if footer else ())
        all_layout_blocks = blocks + back_blocks + region_blocks
        bound = cls._bindings(all_layout_blocks)
        missing = REQUIRED_BINDINGS[document_type] - bound
        if missing:
            raise LayoutValidationError(f"Required bindings are missing: {', '.join(sorted(missing))}.")
        missing_sections = REQUIRED_SECTIONS[document_type] - bound
        if missing_sections:
            raise LayoutValidationError(f"Required tables are missing: {', '.join(sorted(missing_sections))}.")
        unconditional = cls._unconditional_bindings(all_layout_blocks)
        conditionally_hidden = (REQUIRED_BINDINGS[document_type] | REQUIRED_SECTIONS[document_type]) - unconditional
        if conditionally_hidden:
            raise LayoutValidationError(f"Mandatory bindings must have an unconditional occurrence: {', '.join(sorted(conditionally_hidden))}.")
        if not cls._has_unconditional_type(all_layout_blocks, "verification"):
            raise LayoutValidationError("Every official layout requires a verification block.")
        name = str(definition.get("name") or "").strip()
        if not name or len(name) > 100:
            raise LayoutValidationError("Layout name must contain 1 to 100 characters.")
        background = str(definition.get("background_asset_key") or "")
        if background and not background.replace(".", "").replace("-", "").replace("_", "").isalnum():
            raise LayoutValidationError("Background asset key is invalid.")
        if layout_mode == "ABSOLUTE_OVERLAY":
            if not background and sheet is None:
                raise LayoutValidationError("Absolute overlay layouts require a background asset key.")
            if header or footer:
                raise LayoutValidationError("Absolute overlay layouts do not use Flow page regions.")
            cls._validate_overlay_geometry(blocks + back_blocks, page_size)
            if sheet:
                cls._validate_sheet_copy_evidence(sheet, blocks, document_type)
        return DocumentLayout(
            schema_version, document_type, name, page_size, copy_mode, blocks,
            back_blocks, background, layout_mode, margin_mm,
            theme["primary_color"], theme["border_color"], theme["font_family"],
            theme["body_font_size_pt"], theme["heading_font_size_pt"],
            header, footer, sheet,
        )

    @classmethod
    def _sheet(cls, value, schema_version, layout_mode, page_size, document_type):
        if value is None:
            return None
        if document_type != "loan_ticket":
            raise LayoutValidationError("Sheet composition is available only for loan ticket documents.")
        if schema_version < 2 or layout_mode != "ABSOLUTE_OVERLAY":
            raise LayoutValidationError("Sheet composition is available only for schema-v2 absolute overlays.")
        if page_size != "A5":
            raise LayoutValidationError("Sheet composition requires A5 logical pages.")
        if not isinstance(value, dict) or set(value) != {"composition", "backgrounds"}:
            raise LayoutValidationError("Sheet composition requires composition and backgrounds.")
        composition = value["composition"]
        backgrounds = value["backgrounds"]
        if composition not in ALLOWED_SHEET_COMPOSITIONS:
            raise LayoutValidationError("Sheet composition mode is unsupported.")
        allowed_surfaces = {"original_front", "duplicate_front", "original_back", "duplicate_back"}
        if not isinstance(backgrounds, dict) or set(backgrounds) - allowed_surfaces:
            raise LayoutValidationError("Sheet backgrounds contain unsupported surfaces.")
        normalized = {surface: str(key or "") for surface, key in backgrounds.items()}
        for key in normalized.values():
            if key and not key.replace(".", "").replace("-", "").replace("_", "").isalnum():
                raise LayoutValidationError("Sheet background asset key is invalid.")
        required = {
            "A5_ORIGINAL": {"original_front"},
            "A5_ORIGINAL_TERMS_DUPLEX": {"original_front", "original_back"},
            "A5_DUPLICATE": {"duplicate_front"},
            "A5_DUPLICATE_D3_DUPLEX": {"duplicate_front", "duplicate_back"},
            "A5_BOTH_SIMPLEX": {"original_front", "duplicate_front"},
            "A5_BOTH_DUPLEX": {"original_front", "original_back", "duplicate_front", "duplicate_back"},
            "A4_SIDE_BY_SIDE": {"original_front", "duplicate_front"},
            "A4_SIDE_BY_SIDE_DUPLEX": {"original_front", "original_back", "duplicate_front", "duplicate_back"},
        }[composition]
        missing = sorted(surface for surface in required if not normalized.get(surface))
        if missing:
            raise LayoutValidationError(f"Sheet composition is missing background surfaces: {', '.join(missing)}.")
        return SheetComposition(composition, tuple(sorted(normalized.items())))

    @classmethod
    def _validate_sheet_copy_evidence(cls, sheet, blocks, document_type):
        copies = []
        if sheet.composition in {"A5_ORIGINAL", "A5_ORIGINAL_TERMS_DUPLEX", "A5_BOTH_SIMPLEX", "A5_BOTH_DUPLEX", "A4_SIDE_BY_SIDE", "A4_SIDE_BY_SIDE_DUPLEX"}:
            copies.append("ORIGINAL")
        if sheet.composition in {"A5_DUPLICATE", "A5_DUPLICATE_D3_DUPLEX", "A5_BOTH_SIMPLEX", "A5_BOTH_DUPLEX", "A4_SIDE_BY_SIDE", "A4_SIDE_BY_SIDE_DUPLEX"}:
            copies.append("DUPLICATE")
        required = REQUIRED_BINDINGS[document_type] | REQUIRED_SECTIONS[document_type]
        for copy_scope in copies:
            present = cls._unconditional_bindings_for_scope(blocks, copy_scope)
            missing = required - present
            if missing:
                raise LayoutValidationError(f"{copy_scope.title()} front is missing mandatory bindings: {', '.join(sorted(missing))}.")
            if not cls._has_unconditional_type_for_scope(blocks, "verification", copy_scope):
                raise LayoutValidationError(f"{copy_scope.title()} front requires an unconditional verification block.")

    @classmethod
    def _region(cls, value, document_type, schema_version, label):
        if value is None:
            return None
        if schema_version == 1:
            raise LayoutValidationError(f"{label} regions require layout schema version 2.")
        if not isinstance(value, dict) or set(value) != {"height_mm", "blocks"}:
            raise LayoutValidationError(f"{label} region requires height_mm and blocks.")
        height = value["height_mm"]
        if not isinstance(height, int) or not 8 <= height <= 40:
            raise LayoutValidationError(f"{label} height must be between 8 and 40 mm.")
        blocks = cls._blocks(value["blocks"], document_type, schema_version, depth=1, region=True, layout_mode="FLOW")
        if not blocks:
            raise LayoutValidationError(f"{label} region requires at least one block.")
        return PageRegion(height, blocks)

    @classmethod
    def _composition_settings(cls, definition, schema_version):
        defaults = {
            "primary_color": "#000000", "border_color": "#cbd5e1",
            "font_family": "NOTO_SANS_TAMIL", "body_font_size_pt": 10,
            "heading_font_size_pt": 14,
        }
        if schema_version == 1:
            return "FLOW", 14, defaults
        layout_mode = definition.get("layout_mode", "FLOW")
        if layout_mode not in ALLOWED_LAYOUT_MODES:
            raise LayoutValidationError("Layout mode is unsupported.")
        page = definition.get("page", {})
        if not isinstance(page, dict) or set(page) - {"margin_mm"}:
            raise LayoutValidationError("Page settings may contain only margin_mm.")
        margin_mm = page.get("margin_mm", 14)
        if not isinstance(margin_mm, int) or not 5 <= margin_mm <= 30:
            raise LayoutValidationError("Page margin must be between 5 and 30 mm.")
        supplied_theme = definition.get("theme", {})
        if not isinstance(supplied_theme, dict) or set(supplied_theme) - set(defaults):
            raise LayoutValidationError("Theme contains unsupported properties.")
        theme = {**defaults, **supplied_theme}
        for key in ("primary_color", "border_color"):
            value = theme[key]
            if not isinstance(value, str) or len(value) != 7 or value[0] != "#" or any(character not in "0123456789abcdefABCDEF" for character in value[1:]):
                raise LayoutValidationError(f"Theme {key} must be a six-digit hexadecimal color.")
        if theme["font_family"] not in ALLOWED_FONT_FAMILIES:
            raise LayoutValidationError("Theme font family is not approved.")
        for key, minimum, maximum in (("body_font_size_pt", 7, 14), ("heading_font_size_pt", 10, 24)):
            if not isinstance(theme[key], int) or not minimum <= theme[key] <= maximum:
                raise LayoutValidationError(f"Theme {key} is outside the supported range.")
        return layout_mode, margin_mm, theme

    @classmethod
    def _blocks(cls, values, document_type, schema_version, *, depth=0, region=False, layout_mode="FLOW"):
        if not isinstance(values, list) or len(values) > 100:
            raise LayoutValidationError("Blocks must be a list containing at most 100 entries.")
        if depth > 3:
            raise LayoutValidationError("Flow containers may be nested at most three levels.")
        field_keys = frozenset(PawnLoanDocumentProjectionBuilder.FIELD_KEYS.values())
        section_keys = frozenset(PawnLoanDocumentProjectionBuilder.SECTION_KEYS.values())
        result = []
        for value in values:
            if not isinstance(value, dict):
                raise LayoutValidationError("Each block must be an object.")
            allowed = {"type", "binding", "bindings", "text", "height_mm", "asset_key", "width_mm"}
            if schema_version >= 2:
                allowed.update({"blocks", "columns", "grid_columns", "style_variant", "table_columns", "repeat_header", "value_format", "overflow_policy", "max_characters", "visible_when", "x_mm", "y_mm", "font_size_pt", "align", "copy_scope"})
            unknown = set(value) - allowed
            if unknown:
                raise LayoutValidationError(f"Unknown block properties: {', '.join(sorted(unknown))}.")
            block_type = value.get("type")
            if block_type not in ALLOWED_BLOCK_TYPES:
                raise LayoutValidationError(f"Unsupported block type: {block_type}.")
            if schema_version == 1 and block_type in {"section", "columns", "field_grid"}:
                raise LayoutValidationError("Flow containers require layout schema version 2.")
            if layout_mode == "ABSOLUTE_OVERLAY" and block_type not in {"title", "field", "table", "image", "qr", "verification", "signature"}:
                raise LayoutValidationError(f"Block type {block_type} is not supported in absolute overlay mode.")
            if depth and block_type == "page_break":
                raise LayoutValidationError("Page breaks cannot be nested inside flow containers.")
            if region and block_type not in {"title", "field", "field_grid", "image", "qr", "verification", "spacer"}:
                raise LayoutValidationError("Page regions contain only compact, non-repeating blocks.")
            binding = str(value.get("binding") or "")
            bindings = tuple(value.get("bindings") or ())
            if block_type == "field" and binding not in field_keys:
                raise LayoutValidationError(f"Unknown field binding: {binding}.")
            if block_type == "table" and binding not in section_keys:
                raise LayoutValidationError(f"Unknown table binding: {binding}.")
            if block_type == "field_group" and (not bindings or any(item not in field_keys for item in bindings)):
                raise LayoutValidationError("Field groups require only registered field bindings.")
            if block_type == "qr" and binding and binding not in field_keys and binding != "document.verification_id":
                raise LayoutValidationError(f"Unknown QR binding: {binding}.")
            asset_key = str(value.get("asset_key") or "")
            if block_type == "image" and not asset_key:
                raise LayoutValidationError("Image blocks require an asset key.")
            if block_type not in {"title", "signature", "section"} and value.get("text"):
                raise LayoutValidationError(f"Block type {block_type} does not accept free text.")
            height = value.get("height_mm", 4)
            if not isinstance(height, int) or not 1 <= height <= 100:
                raise LayoutValidationError("Spacer/signature height must be between 1 and 100 mm.")
            width = value.get("width_mm", 30)
            maximum_width = 216 if layout_mode == "ABSOLUTE_OVERLAY" else 180
            if not isinstance(width, int) or not 5 <= width <= maximum_width:
                raise LayoutValidationError(f"Block width must be between 5 and {maximum_width} mm.")
            child_blocks = ()
            columns = ()
            grid_columns = value.get("grid_columns", 2)
            style_variant = str(value.get("style_variant") or "PLAIN")
            table_columns = ()
            repeat_header = value.get("repeat_header", True)
            value_format = value.get("value_format", "DEFAULT")
            overflow_policy = value.get("overflow_policy", "WRAP")
            max_characters = value.get("max_characters", 120)
            if value_format not in ALLOWED_VALUE_FORMATS:
                raise LayoutValidationError("Value format is unsupported.")
            if overflow_policy not in ALLOWED_OVERFLOW_POLICIES:
                raise LayoutValidationError("Overflow policy is unsupported.")
            if not isinstance(max_characters, int) or not 10 <= max_characters <= 500:
                raise LayoutValidationError("Maximum characters must be between 10 and 500.")
            visible_when = cls._visibility_condition(value.get("visible_when"), field_keys)
            x_mm = value.get("x_mm", 0)
            y_mm = value.get("y_mm", 0)
            font_size_pt = value.get("font_size_pt", 10)
            align = value.get("align", "LEFT")
            copy_scope = value.get("copy_scope", "BOTH")
            if not isinstance(x_mm, int) or not isinstance(y_mm, int) or x_mm < 0 or y_mm < 0:
                raise LayoutValidationError("Block X/Y coordinates must be non-negative whole millimetres.")
            if not isinstance(font_size_pt, int) or not 6 <= font_size_pt <= 24:
                raise LayoutValidationError("Block font size must be between 6 and 24 points.")
            if align not in {"LEFT", "CENTER", "RIGHT"}:
                raise LayoutValidationError("Block alignment is unsupported.")
            if copy_scope not in ALLOWED_COPY_SCOPES:
                raise LayoutValidationError("Block copy scope is unsupported.")
            if block_type == "section":
                child_blocks = cls._blocks(value.get("blocks"), document_type, schema_version, depth=depth + 1, layout_mode=layout_mode)
                if not child_blocks:
                    raise LayoutValidationError("Sections require at least one child block.")
                if style_variant not in {"PLAIN", "OUTLINED", "TINTED"}:
                    raise LayoutValidationError("Section style variant is unsupported.")
            elif block_type == "columns":
                raw_columns = value.get("columns")
                if not isinstance(raw_columns, list) or not 2 <= len(raw_columns) <= 4:
                    raise LayoutValidationError("Column containers require two to four columns.")
                parsed_columns = []
                for raw_column in raw_columns:
                    if not isinstance(raw_column, dict) or set(raw_column) != {"width_percent", "blocks"}:
                        raise LayoutValidationError("Each column requires width_percent and blocks.")
                    percent = raw_column["width_percent"]
                    if not isinstance(percent, int) or not 10 <= percent <= 90:
                        raise LayoutValidationError("Column width must be between 10 and 90 percent.")
                    children = cls._blocks(raw_column["blocks"], document_type, schema_version, depth=depth + 1, layout_mode=layout_mode)
                    if not children:
                        raise LayoutValidationError("Each column requires at least one child block.")
                    parsed_columns.append(LayoutColumn(percent, children))
                if sum(column.width_percent for column in parsed_columns) != 100:
                    raise LayoutValidationError("Column widths must total 100 percent.")
                columns = tuple(parsed_columns)
            elif block_type == "field_grid":
                if not bindings or any(item not in field_keys for item in bindings):
                    raise LayoutValidationError("Field grids require only registered field bindings.")
                if not isinstance(grid_columns, int) or not 1 <= grid_columns <= 4:
                    raise LayoutValidationError("Field grids support one to four columns.")
            elif block_type == "table":
                if not isinstance(repeat_header, bool):
                    raise LayoutValidationError("Table repeat_header must be true or false.")
                if style_variant not in {"GRID", "MINIMAL", "STRIPED", "PLAIN"}:
                    raise LayoutValidationError("Table style variant is unsupported.")
                raw_table_columns = value.get("table_columns", [])
                if not isinstance(raw_table_columns, list) or len(raw_table_columns) > 12:
                    raise LayoutValidationError("Table columns must be a list of at most 12 entries.")
                parsed_table_columns = []
                for raw_column in raw_table_columns:
                    required_column_keys = {"index", "label", "width_percent", "align"}
                    allowed_column_keys = required_column_keys | {"value_format", "overflow_policy", "max_characters"}
                    if not isinstance(raw_column, dict) or not required_column_keys <= set(raw_column) or set(raw_column) - allowed_column_keys:
                        raise LayoutValidationError("Each table column requires index, label, width_percent, and align.")
                    index, label, percent, align = raw_column["index"], str(raw_column["label"]).strip(), raw_column["width_percent"], raw_column["align"]
                    if not isinstance(index, int) or not 0 <= index <= 11 or not label or len(label) > 40:
                        raise LayoutValidationError("Table column index or label is invalid.")
                    if not isinstance(percent, int) or not 5 <= percent <= 90 or align not in {"LEFT", "CENTER", "RIGHT"}:
                        raise LayoutValidationError("Table column width or alignment is invalid.")
                    column_format = raw_column.get("value_format", "DEFAULT")
                    column_overflow = raw_column.get("overflow_policy", "WRAP")
                    column_maximum = raw_column.get("max_characters", 120)
                    if column_format not in ALLOWED_VALUE_FORMATS or column_overflow not in ALLOWED_OVERFLOW_POLICIES:
                        raise LayoutValidationError("Table column format or overflow policy is unsupported.")
                    if not isinstance(column_maximum, int) or not 10 <= column_maximum <= 500:
                        raise LayoutValidationError("Table column maximum characters must be between 10 and 500.")
                    parsed_table_columns.append(TableColumn(index, label, percent, align, column_format, column_overflow, column_maximum))
                if parsed_table_columns:
                    if len({column.index for column in parsed_table_columns}) != len(parsed_table_columns):
                        raise LayoutValidationError("Table column indexes must be unique.")
                    if sum(column.width_percent for column in parsed_table_columns) != 100:
                        raise LayoutValidationError("Table column widths must total 100 percent.")
                table_columns = tuple(parsed_table_columns)
            elif value.get("blocks") or value.get("columns"):
                raise LayoutValidationError(f"Block type {block_type} cannot contain child blocks.")
            result.append(LayoutBlock(
                block_type, binding, bindings, str(value.get("text") or ""),
                height, asset_key, width, child_blocks, columns, grid_columns,
                style_variant, table_columns, repeat_header, value_format,
                overflow_policy, max_characters, visible_when, x_mm, y_mm,
                font_size_pt, align, copy_scope,
            ))
        return tuple(result)

    @staticmethod
    def _validate_overlay_geometry(blocks, page_size):
        page_dimensions = {"A4": (210, 297), "A5": (148, 210), "LETTER": (216, 279)}
        page_width, page_height = page_dimensions[page_size]
        for block in blocks:
            if block.x_mm + block.width_mm > page_width or block.y_mm + block.height_mm > page_height:
                raise LayoutValidationError(
                    f"Overlay block {block.type} extends beyond the {page_size} page boundary."
                )

    @staticmethod
    def _visibility_condition(value, field_keys):
        if value is None:
            return None
        if not isinstance(value, dict) or set(value) != {"binding", "operator", "value"}:
            raise LayoutValidationError("Visibility condition requires binding, operator, and value.")
        binding, operator, expected = value["binding"], value["operator"], str(value["value"])
        if binding not in field_keys:
            raise LayoutValidationError("Visibility condition binding is not registered.")
        if operator not in {"PRESENT", "EMPTY", "EQUALS", "NOT_EQUALS"}:
            raise LayoutValidationError("Visibility condition operator is unsupported.")
        if operator in {"PRESENT", "EMPTY"} and expected:
            raise LayoutValidationError("Present/empty visibility conditions require an empty value.")
        return VisibilityCondition(binding, operator, expected)

    @staticmethod
    def _bindings(blocks):
        result = set()
        for block in blocks:
            if block.binding:
                result.add(block.binding)
            result.update(block.bindings)
            result.update(DocumentLayoutValidator._bindings(block.blocks))
            for column in block.columns:
                result.update(DocumentLayoutValidator._bindings(column.blocks))
        return frozenset(result)

    @staticmethod
    def _has_block_type(blocks, block_type):
        for block in blocks:
            if block.type == block_type:
                return True
            if DocumentLayoutValidator._has_block_type(block.blocks, block_type):
                return True
            if any(DocumentLayoutValidator._has_block_type(column.blocks, block_type) for column in block.columns):
                return True
        return False

    @staticmethod
    def _unconditional_bindings(blocks, inherited_conditional=False):
        result = set()
        for block in blocks:
            conditional = inherited_conditional or block.visible_when is not None
            if not conditional:
                if block.binding:
                    result.add(block.binding)
                result.update(block.bindings)
            result.update(DocumentLayoutValidator._unconditional_bindings(block.blocks, conditional))
            for column in block.columns:
                result.update(DocumentLayoutValidator._unconditional_bindings(column.blocks, conditional))
        return frozenset(result)

    @staticmethod
    def _has_unconditional_type(blocks, block_type, inherited_conditional=False):
        for block in blocks:
            conditional = inherited_conditional or block.visible_when is not None
            if not conditional and block.type == block_type:
                return True
            if DocumentLayoutValidator._has_unconditional_type(block.blocks, block_type, conditional):
                return True
            if any(DocumentLayoutValidator._has_unconditional_type(column.blocks, block_type, conditional) for column in block.columns):
                return True
        return False

    @staticmethod
    def _unconditional_bindings_for_scope(blocks, copy_scope, inherited_conditional=False):
        result = set()
        for block in blocks:
            if block.copy_scope not in {"BOTH", copy_scope}:
                continue
            conditional = inherited_conditional or block.visible_when is not None
            if not conditional:
                if block.binding:
                    result.add(block.binding)
                result.update(block.bindings)
            result.update(DocumentLayoutValidator._unconditional_bindings_for_scope(block.blocks, copy_scope, conditional))
            for column in block.columns:
                result.update(DocumentLayoutValidator._unconditional_bindings_for_scope(column.blocks, copy_scope, conditional))
        return frozenset(result)

    @staticmethod
    def _has_unconditional_type_for_scope(blocks, block_type, copy_scope, inherited_conditional=False):
        for block in blocks:
            if block.copy_scope not in {"BOTH", copy_scope}:
                continue
            conditional = inherited_conditional or block.visible_when is not None
            if not conditional and block.type == block_type:
                return True
            if DocumentLayoutValidator._has_unconditional_type_for_scope(block.blocks, block_type, copy_scope, conditional):
                return True
            if any(DocumentLayoutValidator._has_unconditional_type_for_scope(column.blocks, block_type, copy_scope, conditional) for column in block.columns):
                return True
        return False


def starter_layout(document_type, *, schema_version=1, layout_mode="FLOW"):
    if schema_version not in DocumentLayoutValidator.SUPPORTED_SCHEMA_VERSIONS:
        raise LayoutValidationError("Unsupported starter layout schema version.")
    if schema_version == 1 and layout_mode != "FLOW":
        raise LayoutValidationError("Absolute overlay starters require schema version 2.")
    required = sorted(REQUIRED_BINDINGS[document_type])
    names = {
        "loan_ticket": "Starter loan ticket",
        "repayment_receipt": "Starter repayment receipt",
        "release_memo": "Starter release memo",
        "auction_notice": "Starter auction notice",
        "auction_recovery": "Starter auction recovery memo",
        "renewal": "Starter renewal memo",
    }
    tables = {
        "loan_ticket": "collateral.items",
        "release_memo": "release.collateral_returned",
        "auction_recovery": "auction.collateral_disposed",
        "renewal": "renewal.collateral_movement",
    }
    if layout_mode == "ABSOLUTE_OVERLAY":
        blocks = [{"type": "title", "x_mm": 10, "y_mm": 8, "width_mm": 190, "height_mm": 12, "font_size_pt": 16, "align": "CENTER"}]
        for index, binding in enumerate(required):
            blocks.append({
                "type": "field", "binding": binding,
                "x_mm": 10 if index % 2 == 0 else 110,
                "y_mm": 25 + (index // 2) * 10,
                "width_mm": 90, "height_mm": 8, "font_size_pt": 8,
            })
        if document_type in tables:
            blocks.append({"type": "table", "binding": tables[document_type], "x_mm": 10, "y_mm": 105, "width_mm": 190, "height_mm": 90, "font_size_pt": 8})
        blocks.extend([
            {"type": "verification", "x_mm": 10, "y_mm": 205, "width_mm": 190, "height_mm": 12, "font_size_pt": 8},
            {"type": "signature", "text": "Borrower / customer | Authorized pawnbroker", "x_mm": 10, "y_mm": 230, "width_mm": 190, "height_mm": 25, "font_size_pt": 9},
        ])
    else:
        blocks = [
            {"type": "title"},
            {"type": "field_group", "bindings": required},
        ]
        if document_type in tables:
            blocks.append({"type": "table", "binding": tables[document_type]})
        blocks.extend([
            {"type": "verification"},
            {"type": "signature", "text": "Borrower / customer | Authorized pawnbroker", "height_mm": 18},
        ])
    definition = {
        "schema_version": schema_version, "document_type": document_type,
        "name": names[document_type],
        "page_size": "A4", "copy_mode": "SINGLE",
        "blocks": blocks,
    }
    if schema_version >= 2:
        definition.update({
            "layout_mode": layout_mode,
            "page": {"margin_mm": 14},
            "theme": {
                "primary_color": "#000000", "border_color": "#cbd5e1",
                "font_family": "NOTO_SANS_TAMIL", "body_font_size_pt": 10,
                "heading_font_size_pt": 14,
            },
        })
    if layout_mode == "ABSOLUTE_OVERLAY":
        definition["background_asset_key"] = "form.background"
    return DocumentLayoutValidator.load(definition)


__all__ = ["DocumentLayout", "DocumentLayoutValidator", "LayoutBlock", "LayoutValidationError", "REQUIRED_BINDINGS", "starter_layout"]
