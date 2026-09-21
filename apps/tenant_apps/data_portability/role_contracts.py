"""Party role exchange and explicit source-key to destination-key binding."""
from datetime import date

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.party.forms import PartyRoleForm
from apps.tenant_apps.party.models import PartyRoleType
from .contracts import digest, issue, validate_record

PROFILE = "party-role/1"
FIELDS = ("role_type_key", "segment", "status", "effective_from", "effective_to")


def definition(obj):
    return {"id": obj.pk, "key": obj.key, "label": obj.label, "description_sha256": digest(obj.description),
            "is_active": obj.is_active, "is_system": obj.is_system, "sort_order": obj.sort_order}


def form_for(record):
    return PartyRoleForm(data={"role_type": record.get("_role_type", {}).get("id"),
        **{k: record.get(k) or "" for k in FIELDS if k != "role_type_key"}})


def semantic(obj):
    return {"role_type_key": obj.role_type.key, "segment": obj.segment or None, "status": obj.status,
            "effective_from": obj.effective_from.isoformat() if obj.effective_from else None,
            "effective_to": obj.effective_to.isoformat() if obj.effective_to else None}


def validate(record, role_map, canonical_source):
    allowed = set(FIELDS) | {"party_source_system", "party_external_id", "id", "recorded_at", "source_recorded_at", "source_refs"}
    errors = []
    if set(record) - allowed:
        errors.append(issue("UNKNOWN_FIELD", "", "Unsupported role fields are present."))
    for key, limit in (("party_source_system", 120), ("party_external_id", 255), ("role_type_key", 64)):
        value = record.get(key)
        if not isinstance(value, str) or not value or len(value) > limit or value != value.strip() or any(ord(c) < 32 for c in value):
            errors.append(issue("INVALID_REFERENCE", key, "Use an exact nonempty source reference."))
    for key in ("segment", "status"):
        if record.get(key) is not None and not isinstance(record[key], str):
            errors.append(issue("INVALID_TEXT", key, "Expected text."))
    for key in ("effective_from", "effective_to"):
        value = record.get(key)
        if value not in (None, ""):
            try:
                if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append(issue("INVALID_DATE", key, "Use YYYY-MM-DD or null."))
    envelope = {k: record[k] for k in ("id", "recorded_at", "source_recorded_at", "source_refs") if k in record}
    _, issues = validate_record({"name": "Envelope", "kind": "INDIVIDUAL", "status": "ACTIVE", "credit_hold": False, **envelope}, canonical_source=canonical_source)
    errors += [i for i in issues if i["severity"] == "ERROR"]
    if errors:
        return record, errors
    target = PartyRoleType.objects.filter(workspace_id=current_workspace_id(), key=role_map.get(record["role_type_key"]), is_active=True).first()
    if target is None:
        return record, [issue("ROLE_TYPE_MAPPING_REQUIRED", "role_type_key", "Explicitly map this source role to an active role type in this Workspace.")]
    result = {**record, "_role_type": definition(target)}
    form = form_for(result)
    if not form.is_valid():
        return record, [issue("PARTY_ROLE_VALIDATION", k, str(e.messages[0])) for k, es in form.errors.as_data().items() for e in es]
    for key in FIELDS:
        if key == "role_type_key":
            continue
        value = form.cleaned_data[key]
        if isinstance(value, date):
            value = value.isoformat()
        value = value or None
        if value != record.get(key):
            errors.append(issue("PARTY_NORMALIZED", key, "Applied existing Party validation.", "INFO", record.get(key), value))
        result[key] = value
    result.setdefault("source_recorded_at", None)
    errors.append(issue("ROLE_TYPE_MAPPED", "role_type_key", "Explicit destination role type selected.", "INFO", record["role_type_key"], target.key + " — " + target.label))
    return result, errors


def schema():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": PROFILE,
        "type": "object", "additionalProperties": False,
        "required": ["id", "party_source_system", "party_external_id", "role_type_key", "status"],
        "properties": {"id": {"type": "string", "format": "uuid"},
            "party_source_system": {"type": "string", "minLength": 1, "maxLength": 120},
            "party_external_id": {"type": "string", "minLength": 1, "maxLength": 255},
            "role_type_key": {"type": "string", "minLength": 1, "maxLength": 64},
            "status": {"type": "string", "enum": ["ACTIVE", "INACTIVE", "ENDED"]},
            "segment": {"type": ["string", "null"], "maxLength": 64},
            **{k: {"type": ["string", "null"], "format": "date"} for k in ("effective_from", "effective_to")},
            **{k: {"type": ["string", "null"], "format": "date-time"} for k in ("recorded_at", "source_recorded_at")},
            "source_refs": {"type": "array", "maxItems": 10, "items": {"type": "object", "additionalProperties": False,
                "required": ["system", "external_id"], "properties": {k: {"type": "string", "maxLength": 255} for k in ("system", "external_id", "legacy_number")}}}}}
