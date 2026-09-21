"""Explicit party-master/1 projection, independent of Django serialization."""
import hashlib
import json
import uuid
from datetime import datetime

from apps.tenant_apps.party.forms import PartyForm
from apps.tenant_apps.party.models import Party
from .parsers import PortabilityError

PROFILE = "party-master/1"
FIELDS = {
    "name": "display_name", "legal_name": "legal_name", "kind": "party_type",
    "status": "status", "relation_kind": "relation_label", "relation_name": "relation_name",
    "primary_phone": "primary_phone", "primary_email": "primary_email", "tax_pan": "tax_pan",
    "gstin": "gstin", "risk_label": "risk_level", "credit_hold": "credit_hold",
}
OPTIONAL = {"id", "business_code", "extensions", "source_refs", "source_recorded_at", "recorded_at", "origin", "photo_ref"}
REQUIRED = {"name", "kind", "status", "credit_hold"}
MAX_LENGTH = {"name": 255, "legal_name": 255, "relation_name": 255, "primary_phone": 32,
              "primary_email": 254, "tax_pan": 16, "gstin": 24, "risk_label": 32,
              "kind": 32, "status": 16, "relation_kind": 16, "business_code": 32}


def dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(dump(value).encode("utf-8")).hexdigest()


def issue(code, field, message, severity="ERROR", before=None, after=None):
    return {"code": code, "field": field, "message": message, "severity": severity,
            "before": before, "after": after, "rule_version": 1}


def semantic(party):
    return {key: (getattr(party, field) if key == "credit_hold" else getattr(party, field) or None)
            for key, field in FIELDS.items()}


def source_digest(record):
    # Excludes transport IDs and exporter timestamps; includes source business facts.
    return digest({k: v for k, v in record.items() if k not in {"id", "recorded_at", "origin", "source_refs", "_role_type", "_parties"}})


def party_form(record):
    return PartyForm(data={field: record.get(key) if key == "credit_hold" else record.get(key) or ""
                           for key, field in FIELDS.items()})


def validate_record(record, *, canonical_source=False):
    issues = []
    if set(record) - (set(FIELDS) | OPTIONAL):
        issues.append(issue("UNKNOWN_FIELD", "", "Unsupported canonical fields are present."))
    for key in REQUIRED:
        if key not in record or record[key] is None:
            issues.append(issue("REQUIRED", key, "This field is required."))
    for key, value in record.items():
        if key in MAX_LENGTH and value is not None and (not isinstance(value, str) or len(value) > MAX_LENGTH[key]):
            issues.append(issue("INVALID_TEXT", key, "Expected text within the field length limit."))
    if type(record.get("credit_hold")) is not bool:
        issues.append(issue("INVALID_BOOLEAN", "credit_hold", "Use true or false."))
    if record.get("extensions") not in (None, {}):
        issues.append(issue("UNSUPPORTED_METADATA", "extensions", "Metadata import is not supported in this profile."))
    if record.get("photo_ref") is not None:
        issues.append(issue("UNSUPPORTED_FILE", "photo_ref", "Photo import is outside the Party master profile."))
    for key in ("recorded_at", "source_recorded_at"):
        value = record.get(key)
        if value is not None:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.utcoffset() is None:
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                issues.append(issue("INVALID_TIMESTAMP", key, "Use an ISO timestamp with a timezone."))
    if record.get("origin") not in (None, "NATIVE", "IMPORT", "BACKFILL"):
        issues.append(issue("INVALID_ORIGIN", "origin", "Unsupported provenance origin."))
    if canonical_source:
        try:
            uuid.UUID(record.get("id", ""))
        except (ValueError, TypeError, AttributeError):
            issues.append(issue("INVALID_ID", "id", "Canonical JSONL requires a UUID identity."))
    refs = record.get("source_refs", [])
    if not isinstance(refs, list) or len(refs) > 10 or any(
        not isinstance(ref, dict) or set(ref) - {"system", "external_id", "legacy_number"}
        or not isinstance(ref.get("system"), str) or not isinstance(ref.get("external_id"), str)
        or any(not isinstance(v, str) or len(v) > 255 for v in ref.values()) for ref in (refs if isinstance(refs, list) else [])
    ):
        issues.append(issue("INVALID_SOURCE_REFERENCE", "source_refs", "Invalid source provenance references."))
    if issues:
        return record, issues
    form = party_form(record)
    if not form.is_valid():
        reverse = {v: k for k, v in FIELDS.items()}
        for field, errors in form.errors.as_data().items():
            for error in errors:
                issues.append(issue("PARTY_VALIDATION", reverse.get(field, field), str(error.messages[0])))
        return record, issues
    result = dict(record)
    for key, model_field in FIELDS.items():
        cleaned = form.cleaned_data[model_field]
        if key != "credit_hold":
            cleaned = cleaned or None
        if cleaned != record.get(key):
            issues.append(issue("PARTY_NORMALIZED", key, "Applied the existing Party validation convention.",
                                "INFO", record.get(key), cleaned))
        result[key] = cleaned
    result.setdefault("extensions", {})
    result.setdefault("photo_ref", None)
    result.setdefault("business_code", None)
    result.setdefault("source_recorded_at", None)
    return result, issues


def export_record(party, identity, sources, provenance=None):
    record = semantic(party)
    references = [{"system": s.source_system, "external_id": s.external_id} for s in sources]
    record.update(id=str(identity.public_id), business_code=party.party_code, extensions={},
                  source_refs=references,
                  recorded_at=party.created_at.isoformat(), source_recorded_at=None,
                  origin="IMPORT" if provenance else "NATIVE", photo_ref=None)
    if provenance:
        original = provenance.canonical
        record["source_recorded_at"] = original.get("source_recorded_at") or original.get("recorded_at")
        if original.get("business_code"):
            for reference in references:
                if reference["system"] == provenance.batch.source_system and reference["external_id"] == provenance.external_id:
                    reference["legacy_number"] = original["business_code"]
        for reference in original.get("source_refs", []):
            if reference not in references:
                references.append(reference)
        if len(references) > 10:
            raise PortabilityError("The Party source history exceeds this profile's reference limit.")
    return record


def schema():
    properties = {key: {"type": ["string", "null"], "maxLength": limit} for key, limit in MAX_LENGTH.items()}
    properties.update({
        "id": {"type": "string", "format": "uuid"},
        "kind": {"enum": list(Party.PartyType.values)},
        "status": {"enum": list(Party.PartyStatus.values)},
        "relation_kind": {"enum": [None, *Party.RelationLabel.values]},
        "credit_hold": {"type": "boolean"}, "extensions": {"type": "object", "maxProperties": 0},
        "photo_ref": {"type": "null"}, "origin": {"enum": ["NATIVE", "IMPORT", "BACKFILL"]},
        "recorded_at": {"type": ["string", "null"], "format": "date-time"},
        "source_recorded_at": {"type": ["string", "null"], "format": "date-time"},
        "source_refs": {"type": "array", "maxItems": 10, "items": {"type": "object",
            "required": ["system", "external_id"], "additionalProperties": False,
            "properties": {k: {"type": "string", "maxLength": 255} for k in ("system", "external_id", "legacy_number")}}},
    })
    properties["name"] = {"type": "string", "minLength": 1, "maxLength": 255}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": PROFILE,
            "type": "object", "required": ["id", *sorted(REQUIRED)], "additionalProperties": False,
            "properties": properties}
