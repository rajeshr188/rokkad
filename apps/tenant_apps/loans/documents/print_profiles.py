"""Validated physical packaging contracts for logical loan documents."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class PrintProfileValidationError(ValueError):
    pass


_COMPOSITIONS = {
    "A5_ORIGINAL": {
        "paper_size": "A5", "orientation": "PORTRAIT", "duplex": "SIMPLEX",
        "sheets": (("ORIGINAL_FRONT",),),
    },
    "A5_ORIGINAL_TERMS_DUPLEX": {
        "paper_size": "A5", "orientation": "PORTRAIT", "duplex": "DUPLEX",
        "sheets": (("ORIGINAL_FRONT",), ("ORIGINAL_TERMS",)),
    },
    "A5_DUPLICATE": {
        "paper_size": "A5", "orientation": "PORTRAIT", "duplex": "SIMPLEX",
        "sheets": (("DUPLICATE_FRONT",),),
    },
    "A5_DUPLICATE_D3_DUPLEX": {
        "paper_size": "A5", "orientation": "PORTRAIT", "duplex": "DUPLEX",
        "sheets": (("DUPLICATE_FRONT",), ("DUPLICATE_D3",)),
    },
    "A5_BOTH_SIMPLEX": {
        "paper_size": "A5", "orientation": "PORTRAIT", "duplex": "SIMPLEX",
        "sheets": (("ORIGINAL_FRONT",), ("DUPLICATE_FRONT",)),
    },
    "A5_BOTH_DUPLEX": {
        "paper_size": "A5", "orientation": "PORTRAIT", "duplex": "DUPLEX",
        "sheets": (
            ("ORIGINAL_FRONT",), ("ORIGINAL_TERMS",),
            ("DUPLICATE_FRONT",), ("DUPLICATE_D3",),
        ),
    },
    "A4_SIDE_BY_SIDE": {
        "paper_size": "A4", "orientation": "LANDSCAPE", "duplex": "SIMPLEX",
        "sheets": (("ORIGINAL_FRONT", "DUPLICATE_FRONT"),),
    },
    "A4_SIDE_BY_SIDE_DUPLEX": {
        "paper_size": "A4", "orientation": "LANDSCAPE", "duplex": "DUPLEX",
        "sheets": (
            ("ORIGINAL_FRONT", "DUPLICATE_FRONT"),
            ("ORIGINAL_TERMS", "DUPLICATE_D3"),
        ),
    },
    "LEGACY_ORIGINAL": {
        "paper_sizes": ("A4", "A5", "LETTER"),
        "orientation": "PORTRAIT", "duplex": "SIMPLEX",
        "sheets": (("ORIGINAL_FRONT",),),
    },
    "LEGACY_BOTH_SIMPLEX": {
        "paper_sizes": ("A4", "A5", "LETTER"),
        "orientation": "PORTRAIT", "duplex": "SIMPLEX",
        "sheets": (("ORIGINAL_FRONT",), ("DUPLICATE_FRONT",)),
    },
    "LEGACY_BOTH_DUPLEX": {
        "paper_sizes": ("A4", "A5", "LETTER"),
        "orientation": "PORTRAIT", "duplex": "DUPLEX",
        "sheets": (
            ("ORIGINAL_FRONT",), ("ORIGINAL_TERMS",),
            ("DUPLICATE_FRONT",), ("DUPLICATE_D3",),
        ),
    },
}
_SCALING_POLICIES = {"ACTUAL_SIZE", "FIT_PRINTABLE_AREA"}
_FLIP_GUIDANCE = {"NOT_APPLICABLE", "LONG_EDGE", "SHORT_EDGE", "VERIFY_ON_PRINTER"}


@dataclass(frozen=True)
class PrintProfileDefinition:
    schema_version: int
    document_type: str
    name: str
    composition: str
    paper_size: str
    orientation: str
    duplex: str
    scaling_policy: str
    flip_edge_guidance: str
    printer_guidance: str
    sheets: tuple[tuple[str, ...], ...]

    def canonical_dict(self):
        return {
            "schema_version": self.schema_version,
            "document_type": self.document_type,
            "name": self.name,
            "composition": self.composition,
            "paper_size": self.paper_size,
            "orientation": self.orientation,
            "duplex": self.duplex,
            "scaling_policy": self.scaling_policy,
            "flip_edge_guidance": self.flip_edge_guidance,
            "printer_guidance": self.printer_guidance,
        }

    @property
    def content_hash(self):
        payload = json.dumps(
            self.canonical_dict(), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    @property
    def included_surfaces(self):
        return frozenset(surface for sheet in self.sheets for surface in sheet)


class PrintProfileValidator:
    @classmethod
    def load(cls, definition):
        if not isinstance(definition, dict):
            raise PrintProfileValidationError("Print profile definition must be an object.")
        allowed = {
            "schema_version", "document_type", "name", "composition",
            "paper_size", "orientation", "duplex", "scaling_policy",
            "flip_edge_guidance", "printer_guidance",
        }
        unknown = set(definition) - allowed
        if unknown:
            raise PrintProfileValidationError(
                f"Unknown print profile properties: {', '.join(sorted(unknown))}."
            )
        if definition.get("schema_version") != 1:
            raise PrintProfileValidationError("Print profile schema_version must be 1.")
        if definition.get("document_type") != "loan_ticket":
            raise PrintProfileValidationError(
                "LPD7.1 print profiles support loan tickets only."
            )
        name = str(definition.get("name") or "").strip()
        if not name or len(name) > 100:
            raise PrintProfileValidationError("Print profile name is required and must be at most 100 characters.")
        composition = definition.get("composition")
        expected = _COMPOSITIONS.get(composition)
        if expected is None:
            raise PrintProfileValidationError("Unknown print-profile composition.")
        paper_size = definition.get("paper_size")
        allowed_paper_sizes = expected.get("paper_sizes", (expected.get("paper_size"),))
        if paper_size not in allowed_paper_sizes:
            required = expected.get("paper_size") or "/".join(allowed_paper_sizes)
            raise PrintProfileValidationError(
                f"{composition} requires paper_size={required}."
            )
        for key in ("orientation", "duplex"):
            if definition.get(key) != expected[key]:
                raise PrintProfileValidationError(
                    f"{composition} requires {key}={expected[key]}."
                )
        scaling = definition.get("scaling_policy", "ACTUAL_SIZE")
        if scaling not in _SCALING_POLICIES:
            raise PrintProfileValidationError("Unknown print scaling policy.")
        flip = definition.get("flip_edge_guidance", "NOT_APPLICABLE")
        if flip not in _FLIP_GUIDANCE:
            raise PrintProfileValidationError("Unknown flip-edge guidance.")
        if expected["duplex"] == "SIMPLEX" and flip != "NOT_APPLICABLE":
            raise PrintProfileValidationError("Simplex profiles cannot specify flip-edge guidance.")
        guidance = str(definition.get("printer_guidance") or "").strip()
        if len(guidance) > 500:
            raise PrintProfileValidationError("Printer guidance must be at most 500 characters.")
        return PrintProfileDefinition(
            schema_version=1,
            document_type="loan_ticket",
            name=name,
            composition=composition,
            paper_size=paper_size,
            orientation=expected["orientation"],
            duplex=expected["duplex"],
            scaling_policy=scaling,
            flip_edge_guidance=flip,
            printer_guidance=guidance,
            sheets=expected["sheets"],
        )


def built_in_print_profile(composition="A5_BOTH_SIMPLEX"):
    expected = _COMPOSITIONS.get(composition)
    if expected is None:
        raise PrintProfileValidationError("Unknown built-in print-profile composition.")
    return PrintProfileValidator.load({
        "schema_version": 1,
        "document_type": "loan_ticket",
        "name": f"Built-in {composition.replace('_', ' ').title()}",
        "composition": composition,
        "paper_size": expected.get("paper_size") or expected["paper_sizes"][0],
        "orientation": expected["orientation"],
        "duplex": expected["duplex"],
        "scaling_policy": "ACTUAL_SIZE",
        "flip_edge_guidance": (
            "VERIFY_ON_PRINTER" if expected["duplex"] == "DUPLEX"
            else "NOT_APPLICABLE"
        ),
        "printer_guidance": "Print at Actual size / 100% and verify physical margins.",
    })


def legacy_print_profile(layout):
    """Describe the physical packaging the existing renderer will actually use."""
    if layout.document_type != "loan_ticket":
        raise PrintProfileValidationError(
            "Legacy print-profile provenance supports loan tickets only."
        )
    if layout.sheet is not None:
        composition = layout.sheet.composition
        expected = _COMPOSITIONS.get(composition)
        if expected is None:
            raise PrintProfileValidationError(
                "The legacy sheet composition has no print-profile equivalent."
            )
        paper_size = expected.get("paper_size") or layout.page_size
    else:
        composition = {
            "SINGLE": "LEGACY_ORIGINAL",
            "ORIGINAL_DUPLICATE": "LEGACY_BOTH_SIMPLEX",
            "ORIGINAL_DUPLICATE_DUPLEX": "LEGACY_BOTH_DUPLEX",
        }.get(layout.copy_mode)
        if composition is None:
            raise PrintProfileValidationError(
                "The legacy copy mode has no print-profile equivalent."
            )
        expected = _COMPOSITIONS[composition]
        paper_size = layout.page_size
    return PrintProfileValidator.load({
        "schema_version": 1,
        "document_type": "loan_ticket",
        "name": f"Legacy embedded {composition.replace('_', ' ').title()}",
        "composition": composition,
        "paper_size": paper_size,
        "orientation": expected["orientation"],
        "duplex": expected["duplex"],
        "scaling_policy": "ACTUAL_SIZE",
        "flip_edge_guidance": (
            "VERIFY_ON_PRINTER" if expected["duplex"] == "DUPLEX"
            else "NOT_APPLICABLE"
        ),
        "printer_guidance": (
            "Compatibility profile derived from the published layout; "
            "print at Actual size / 100%."
        ),
    })


BUILT_IN_PRINT_PROFILE_COMPOSITIONS = tuple(_COMPOSITIONS)


__all__ = [
    "BUILT_IN_PRINT_PROFILE_COMPOSITIONS",
    "PrintProfileDefinition",
    "PrintProfileValidationError",
    "PrintProfileValidator",
    "built_in_print_profile",
    "legacy_print_profile",
]
