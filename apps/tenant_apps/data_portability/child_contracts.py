"""Explicit Party child profiles; parent references are portable, never database keys."""
import uuid
from datetime import date, datetime

from apps.tenant_apps.party.forms import PartyAddressForm, PartyContactMethodForm, PartyIdentifierForm
from .contracts import issue, validate_record
from . import role_contracts, relationship_contracts

CONTACT = "party-contact/1"
ADDRESS = "party-address/1"
IDENTIFIER = "party-identifier/1"
ROLE = role_contracts.PROFILE
RELATIONSHIP = relationship_contracts.PROFILE
PROFILES = (CONTACT, ADDRESS, IDENTIFIER, ROLE, RELATIONSHIP)
IDENTIFIER_FIELDS = ("identifier_type", "value", "masked_value", "expires_on")
CONTACT_FIELDS = ("contact_type", "label", "value", "is_primary")
ADDRESS_FIELDS = ("address_type", "line1", "line2", "area", "city", "state", "postal_code", "country", "is_default")
PARENT_FIELDS = ("party_source_system", "party_external_id")
ENVELOPE = {"id", "source_refs", "source_recorded_at", "recorded_at", "source_is_verified"}


def fields(profile):
    return {CONTACT: CONTACT_FIELDS, ADDRESS: ADDRESS_FIELDS, IDENTIFIER: IDENTIFIER_FIELDS, ROLE: role_contracts.FIELDS, RELATIONSHIP: relationship_contracts.FIELDS}[profile]


def parent_fields(profile):
    return relationship_contracts.REFERENCES if profile == RELATIONSHIP else PARENT_FIELDS


def form_for(profile, record):
    if profile == RELATIONSHIP:
        return relationship_contracts.form_for(record)
    if profile == ROLE:
        return role_contracts.form_for(record)
    cls = {CONTACT: PartyContactMethodForm, ADDRESS: PartyAddressForm, IDENTIFIER: PartyIdentifierForm}[profile]
    return cls(data={k: record.get(k) if k in {"is_primary", "is_default"} else record.get(k) or "" for k in fields(profile)})


def semantic(profile, obj):
    if profile == RELATIONSHIP:
        return relationship_contracts.semantic(obj)
    if profile == ROLE:
        return role_contracts.semantic(obj)
    return {k: getattr(obj, k) if k in {"is_primary", "is_default"} else (getattr(obj, k).isoformat() if k == "expires_on" and getattr(obj, k) else getattr(obj, k) or None) for k in fields(profile)}


def local_state(profile, obj):
    if profile == RELATIONSHIP:
        return {**semantic(profile, obj), "from_party_pk": obj.from_party_id, "to_party_pk": obj.to_party_id}
    if profile == ROLE:
        return {**semantic(profile, obj), "party_pk": obj.party_id, "definition": role_contracts.definition(obj.role_type), "metadata": obj.metadata}
    result = {**semantic(profile, obj), "party_pk": obj.party_id, "is_verified": obj.is_verified}
    if profile == IDENTIFIER:
        result.update(verified_at=obj.verified_at.isoformat() if obj.verified_at else None, metadata=obj.metadata, value_hash=obj.value_hash)
    return result


def validate_child(record, profile, canonical_source=False, role_map=None):
    if profile == RELATIONSHIP:
        return relationship_contracts.validate(record, canonical_source)
    if profile == ROLE:
        return role_contracts.validate(record, role_map or {}, canonical_source)
    errors = []
    if set(record) - (set(fields(profile)) | set(PARENT_FIELDS) | ENVELOPE | ({"source_verified_at"} if profile == IDENTIFIER else set())):
        errors.append(issue("UNKNOWN_FIELD", "", "Unsupported child fields are present."))
    for key in PARENT_FIELDS:
        value = record.get(key)
        if not isinstance(value, str) or not value or len(value) > (120 if key == "party_source_system" else 255) or value != value.strip() or any(ord(c) < 32 for c in value):
            errors.append(issue("INVALID_PARENT_REFERENCE", key, "Provide an exact, nonempty Party source reference."))
    boolean = {CONTACT: "is_primary", ADDRESS: "is_default"}.get(profile)
    for key in ([boolean] if boolean else []) + ["source_is_verified"]:
        if type(record.get(key)) is not bool:
            errors.append(issue("INVALID_BOOLEAN", key, "Use explicit true or false."))
    for key in set(fields(profile)) - {boolean}:
        if record.get(key) is not None and not isinstance(record[key], str):
            errors.append(issue("INVALID_TEXT", key, "Expected text or null."))
    if profile == IDENTIFIER:
        expiry = record.get("expires_on")
        if expiry not in (None, ""):
            try:
                if not isinstance(expiry, str) or date.fromisoformat(expiry).isoformat() != expiry:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(issue("INVALID_DATE", "expires_on", "Use YYYY-MM-DD or null."))
        verified_at = record.get("source_verified_at")
        if verified_at is not None:
            try:
                if datetime.fromisoformat(verified_at.replace("Z", "+00:00")).utcoffset() is None:
                    raise ValueError
            except (ValueError, TypeError, AttributeError):
                errors.append(issue("INVALID_TIMESTAMP", "source_verified_at", "Use an ISO timestamp with a timezone."))
    # Reuse the v1 envelope validators without projecting a child into a Party.
    envelope = {k: v for k, v in record.items() if k in ENVELOPE - {"source_is_verified"}}
    _, envelope_issues = validate_record({"name": "Envelope", "kind": "INDIVIDUAL", "status": "ACTIVE", "credit_hold": False, **envelope}, canonical_source=canonical_source)
    errors.extend(i for i in envelope_issues if i["severity"] == "ERROR")
    if errors:
        return record, errors
    form = form_for(profile, record)
    if not form.is_valid():
        return record, [issue("PARTY_CHILD_VALIDATION", k, str(e.messages[0])) for k, es in form.errors.as_data().items() for e in es]
    result = dict(record)
    for key in fields(profile):
        value = form.cleaned_data[key]
        if key == "expires_on" and value:
            value = value.isoformat()
        if key != boolean:
            value = value or None
        if value != record.get(key):
            errors.append(issue("PARTY_NORMALIZED", key, "Applied existing Party validation.", "INFO", record.get(key), value))
        result[key] = value
    result.setdefault("source_recorded_at", None)
    if profile == IDENTIFIER:
        result.setdefault("source_verified_at", None)
    if record["source_is_verified"] or record.get("source_verified_at"):
        errors.append(issue("SOURCE_VERIFICATION_ONLY", "source_is_verified", "Source verification is retained as provenance; the new record remains locally unverified.", "WARNING"))
    if canonical_source:
        result["id"] = str(uuid.UUID(result["id"]))
    return result, errors


def schema(profile):
    if profile == RELATIONSHIP:
        return relationship_contracts.schema()
    if profile == ROLE:
        return role_contracts.schema()
    form = form_for(profile, {})
    properties = {}
    for key, field in form.fields.items():
        if key in {"is_primary", "is_default"}:
            properties[key] = {"type": "boolean"}
        elif hasattr(field, "choices") and field.choices:
            properties[key] = {"type": "string", "enum": [v for v, _ in field.choices if v]}
        else:
            properties[key] = {"type": "string" if field.required else ["string", "null"]}
            if key == "expires_on":
                properties[key]["format"] = "date"
            if getattr(field, "max_length", None):
                properties[key]["maxLength"] = field.max_length
    properties.update(id={"type": "string", "format": "uuid"}, source_is_verified={"type": "boolean"},
        party_source_system={"type": "string", "minLength": 1, "maxLength": 120},
        party_external_id={"type": "string", "minLength": 1, "maxLength": 255},
        recorded_at={"type": ["string", "null"], "format": "date-time"},
        source_recorded_at={"type": ["string", "null"], "format": "date-time"},
        source_refs={"type": "array", "maxItems": 10, "items": {"type": "object", "additionalProperties": False,
            "required": ["system", "external_id"], "properties": {k: {"type": "string", "maxLength": 255} for k in ("system", "external_id", "legacy_number")}}})
    if profile == IDENTIFIER:
        properties["source_verified_at"] = {"type": ["string", "null"], "format": "date-time"}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": profile,
        "type": "object", "additionalProperties": False, "properties": properties,
        "required": ["id", *PARENT_FIELDS, "source_is_verified", *[k for k, f in form.fields.items() if f.required or k in {"is_primary", "is_default"}]]}
