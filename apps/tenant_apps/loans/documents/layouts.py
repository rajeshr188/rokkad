"""Constrained, database-free layout contracts for PawnLoan documents."""

import hashlib
import json
from dataclasses import dataclass

from .payloads import PawnLoanDocumentProjectionBuilder


class LayoutValidationError(ValueError):
    pass


ALLOWED_BLOCK_TYPES = frozenset(
    {"title", "field", "field_group", "table", "image", "qr", "verification", "signature", "spacer", "page_break"}
)
ALLOWED_PAGE_SIZES = frozenset({"A4", "A5", "LETTER"})
ALLOWED_COPY_MODES = frozenset({"SINGLE", "ORIGINAL_DUPLICATE", "ORIGINAL_DUPLICATE_DUPLEX"})

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

    def canonical_dict(self):
        def block_dict(block):
            return {
                "type": block.type, "binding": block.binding,
                "bindings": list(block.bindings), "text": block.text,
                "height_mm": block.height_mm,
                "asset_key": block.asset_key, "width_mm": block.width_mm,
            }
        return {
            "schema_version": self.schema_version, "document_type": self.document_type,
            "name": self.name, "page_size": self.page_size, "copy_mode": self.copy_mode,
            "blocks": [block_dict(block) for block in self.blocks],
            "back_blocks": [block_dict(block) for block in self.back_blocks],
            "background_asset_key": self.background_asset_key,
        }

    @property
    def content_hash(self):
        encoded = json.dumps(self.canonical_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class DocumentLayoutValidator:
    SCHEMA_VERSION = 1

    @classmethod
    def load(cls, definition):
        if not isinstance(definition, dict):
            raise LayoutValidationError("Layout must be a JSON object.")
        allowed_keys = {"schema_version", "document_type", "name", "page_size", "copy_mode", "blocks", "back_blocks", "background_asset_key"}
        unknown = set(definition) - allowed_keys
        if unknown:
            raise LayoutValidationError(f"Unknown layout properties: {', '.join(sorted(unknown))}.")
        if definition.get("schema_version") != cls.SCHEMA_VERSION:
            raise LayoutValidationError("Unsupported layout schema version.")
        document_type = definition.get("document_type")
        if document_type not in REQUIRED_BINDINGS:
            raise LayoutValidationError("Unsupported document type.")
        page_size = definition.get("page_size", "A4")
        copy_mode = definition.get("copy_mode", "SINGLE")
        if page_size not in ALLOWED_PAGE_SIZES:
            raise LayoutValidationError("Unsupported page size.")
        if copy_mode not in ALLOWED_COPY_MODES:
            raise LayoutValidationError("Unsupported copy mode.")
        blocks = cls._blocks(definition.get("blocks"), document_type)
        back_blocks = cls._blocks(definition.get("back_blocks", []), document_type)
        if not blocks:
            raise LayoutValidationError("A layout requires at least one front-page block.")
        if copy_mode == "ORIGINAL_DUPLICATE_DUPLEX" and not back_blocks:
            raise LayoutValidationError("Duplex layouts require back-page blocks.")
        bound = cls._bindings(blocks + back_blocks)
        missing = REQUIRED_BINDINGS[document_type] - bound
        if missing:
            raise LayoutValidationError(f"Required bindings are missing: {', '.join(sorted(missing))}.")
        missing_sections = REQUIRED_SECTIONS[document_type] - bound
        if missing_sections:
            raise LayoutValidationError(f"Required tables are missing: {', '.join(sorted(missing_sections))}.")
        if not any(block.type == "verification" for block in blocks + back_blocks):
            raise LayoutValidationError("Every official layout requires a verification block.")
        name = str(definition.get("name") or "").strip()
        if not name or len(name) > 100:
            raise LayoutValidationError("Layout name must contain 1 to 100 characters.")
        background = str(definition.get("background_asset_key") or "")
        if background and not background.replace(".", "").replace("-", "").replace("_", "").isalnum():
            raise LayoutValidationError("Background asset key is invalid.")
        return DocumentLayout(cls.SCHEMA_VERSION, document_type, name, page_size, copy_mode, blocks, back_blocks, background)

    @classmethod
    def _blocks(cls, values, document_type):
        if not isinstance(values, list) or len(values) > 100:
            raise LayoutValidationError("Blocks must be a list containing at most 100 entries.")
        field_keys = frozenset(PawnLoanDocumentProjectionBuilder.FIELD_KEYS.values())
        section_keys = frozenset(PawnLoanDocumentProjectionBuilder.SECTION_KEYS.values())
        result = []
        for value in values:
            if not isinstance(value, dict):
                raise LayoutValidationError("Each block must be an object.")
            unknown = set(value) - {"type", "binding", "bindings", "text", "height_mm", "asset_key", "width_mm"}
            if unknown:
                raise LayoutValidationError(f"Unknown block properties: {', '.join(sorted(unknown))}.")
            block_type = value.get("type")
            if block_type not in ALLOWED_BLOCK_TYPES:
                raise LayoutValidationError(f"Unsupported block type: {block_type}.")
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
            if block_type not in {"title", "signature"} and value.get("text"):
                raise LayoutValidationError(f"Block type {block_type} does not accept free text.")
            height = value.get("height_mm", 4)
            if not isinstance(height, int) or not 1 <= height <= 100:
                raise LayoutValidationError("Spacer/signature height must be between 1 and 100 mm.")
            width = value.get("width_mm", 30)
            if not isinstance(width, int) or not 5 <= width <= 180:
                raise LayoutValidationError("Image/QR width must be between 5 and 180 mm.")
            result.append(LayoutBlock(block_type, binding, bindings, str(value.get("text") or ""), height, asset_key, width))
        return tuple(result)

    @staticmethod
    def _bindings(blocks):
        result = set()
        for block in blocks:
            if block.binding:
                result.add(block.binding)
            result.update(block.bindings)
        return frozenset(result)


def starter_layout(document_type):
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
        "schema_version": 1, "document_type": document_type,
        "name": names[document_type],
        "page_size": "A4", "copy_mode": "SINGLE",
        "blocks": blocks,
    }
    return DocumentLayoutValidator.load(definition)


__all__ = ["DocumentLayout", "DocumentLayoutValidator", "LayoutBlock", "LayoutValidationError", "REQUIRED_BINDINGS", "starter_layout"]
