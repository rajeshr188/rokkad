"""Directional Party relationships with two explicit portable references."""
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.party.forms import PartyRelationshipForm
from apps.tenant_apps.party.models import Party, PartyRelationship
from .contracts import issue, validate_record

PROFILE = "party-relationship/1"
FIELDS = ("relationship_type", "notes", "is_active")
REFERENCES = ("party_source_system", "party_external_id", "to_party_source_system", "to_party_external_id")


def form_for(record):
    binding = record["_parties"]
    parent = Party.objects.get(workspace_id=current_workspace_id(), pk=binding["from"])
    # Field validation also runs for idempotent replay. Duplicate disposition is
    # decided separately against the immutable source identity, never auto-bound.
    existing = PartyRelationship.objects.filter(workspace_id=parent.workspace_id,
        from_party=parent, to_party_id=binding["to"], relationship_type=record.get("relationship_type")).first()
    return PartyRelationshipForm(from_party=parent, instance=existing, data={
        "to_party": binding["to"], "relationship_type": record.get("relationship_type"),
        "notes": record.get("notes") or "", "is_active": record.get("is_active")})


def semantic(obj):
    return {"relationship_type": obj.relationship_type, "notes": obj.notes or None, "is_active": obj.is_active}


def validate(record, canonical_source):
    from .children import parent_for, related_parent_for
    errors = []
    envelope_keys = {"id", "recorded_at", "source_recorded_at", "source_refs"}
    if set(record) - (set(FIELDS) | set(REFERENCES) | envelope_keys):
        errors.append(issue("UNKNOWN_FIELD", "", "Unsupported relationship fields are present."))
    for key in REFERENCES:
        value = record.get(key)
        if not isinstance(value, str) or not value or len(value) > (120 if key.endswith("system") else 255) or value != value.strip() or any(ord(c) < 32 for c in value):
            errors.append(issue("INVALID_REFERENCE", key, "Use an exact nonempty Party source reference."))
    if type(record.get("is_active")) is not bool:
        errors.append(issue("INVALID_BOOLEAN", "is_active", "Use explicit true or false."))
    for key in ("notes", "relationship_type"):
        if record.get(key) is not None and not isinstance(record[key], str):
            errors.append(issue("INVALID_TEXT", key, "Expected text or null."))
    _, issues = validate_record({"name": "Envelope", "kind": "INDIVIDUAL", "status": "ACTIVE", "credit_hold": False,
        **{k: v for k, v in record.items() if k in envelope_keys}}, canonical_source=canonical_source)
    errors += [i for i in issues if i["severity"] == "ERROR"]
    if errors:
        return record, errors
    parent = parent_for(record, current_workspace_id())
    related = related_parent_for(record, current_workspace_id())
    if parent is None or related is None:
        return record, [issue("MISSING_PARENT", "party_external_id" if parent is None else "to_party_external_id",
                              "Import both Party masters first, using their exact source references.")]
    result = {**record, "_parties": {"from": parent.party_id, "to": related.party_id,
                                    "from_identity": parent.pk, "to_identity": related.pk}}
    form = form_for(result)
    if not form.is_valid():
        return record, [issue("PARTY_RELATIONSHIP_VALIDATION", k, str(e.messages[0])) for k, es in form.errors.as_data().items() for e in es]
    for key in FIELDS:
        value = form.cleaned_data[key]
        if key != "is_active":
            value = value or None
        if value != record.get(key):
            errors.append(issue("PARTY_NORMALIZED", key, "Applied existing Party validation.", "INFO", record.get(key), value))
        result[key] = value
    result.setdefault("source_recorded_at", None)
    return result, errors


def schema():
    from .role_contracts import schema as role_schema
    properties = {k: v for k, v in role_schema()["properties"].items()
                  if k in {"id", "recorded_at", "source_recorded_at", "source_refs"}}
    properties.update({k: {"type": "string", "minLength": 1, "maxLength": 120 if k.endswith("system") else 255} for k in REFERENCES})
    properties.update(relationship_type={"type": "string", "enum": list(PartyRelationship.RelationshipType.values)},
                      notes={"type": ["string", "null"]}, is_active={"type": "boolean"})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": PROFILE,
            "type": "object", "additionalProperties": False, "properties": properties,
            "required": ["id", *REFERENCES, "relationship_type", "is_active"]}
