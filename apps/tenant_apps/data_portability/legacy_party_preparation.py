"""Read-only Party contract preparation for the reviewed Linode source shapes."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid5

from . import child_contracts, contracts
from .legacy_dump import source_schema
from .legacy_profiles import apply_corrections, get_profile
from .parsers import MAX_ROWS, PortabilityError

RELATIONS = {"s": "SON_OF", "so": "SON_OF", "d": "DAUGHTER_OF", "do": "DAUGHTER_OF",
             "f": "FATHER_OF", "fo": "FATHER_OF", "p": "PARENT_OF", "po": "PARENT_OF",
             "h": "HUSBAND_OF", "ho": "HUSBAND_OF", "w": "WIFE_OF", "wo": "WIFE_OF",
             "o": "OTHER", "oo": "OTHER"}


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _id(namespace, table, pk):
    return str(uuid5(namespace, f"{table}:{pk}"))


def _relation(value):
    compact = "".join(char for char in (value or "").casefold() if char.isalpha())
    return RELATIONS.get(compact)


def build_party_preparation(extracted, *, schema, source_namespace, source_profile):
    """Return canonical Party profile records, chunk-ready and without ORM writes."""
    profile = get_profile(source_profile)
    if profile.schema != schema or extracted.get("source_schema") != schema:
        raise PortabilityError("The selected legacy Party profile must match the extracted source schema.")
    source_schema(schema)
    try:
        installation = UUID(str(source_namespace))
    except (ValueError, TypeError, AttributeError) as exc:
        raise PortabilityError("Provide the stable source installation UUID used for this archive.") from exc
    tables, _corrections = apply_corrections(extracted["tables"], profile_key=profile.key)
    namespace = uuid5(installation, schema)
    system = f"legacy:{installation.hex}:{schema}"
    records = {contracts.PROFILE: [], child_contracts.CONTACT: [], child_contracts.ADDRESS: []}
    review = []
    parent = lambda pk: f"contact_customer:{pk}"
    for pk, row in sorted(tables["contact_customer"].items(), key=lambda item: int(item[0])):
        relation_kind = _relation(row["relatedas"])
        relation_name = row["relatedto"] if relation_kind else None
        if row["relatedas"] and not relation_kind:
            review.append({"code": "RELATION_MAPPING_REQUIRED", "table": "contact_customer", "id": pk,
                           "value": row["relatedas"], "message": "Preserve the source relation until its destination label is approved."})
        elif relation_kind and not relation_name:
            review.append({"code": "RELATION_NAME_REQUIRED", "table": "contact_customer", "id": pk,
                           "value": row["relatedas"], "message": "The source has a relationship label without a related-person name; do not import a partial relationship."})
            relation_kind = None
        records[contracts.PROFILE].append({
            "id": _id(namespace, "contact_customer", pk), "name": row["name"], "kind": "INDIVIDUAL",
            "status": "ACTIVE" if row["active"] == "t" else "INACTIVE", "relation_kind": relation_kind,
            "relation_name": relation_name, "credit_hold": False, "business_code": None, "extensions": {},
            "source_refs": [{"system": system, "external_id": parent(pk)}], "recorded_at": None,
            "source_recorded_at": row["created"], "origin": "IMPORT", "photo_ref": None,
        })
    primary = set()
    for pk, row in sorted(tables["contact_contact"].items(), key=lambda item: int(item[0])):
        key = (row["customer_id"], "MOBILE")
        is_primary = row["is_default"] == "t" and key not in primary
        if row["is_default"] == "t":
            if key in primary:
                review.append({"code": "MULTIPLE_SOURCE_DEFAULTS", "table": "contact_contact", "id": pk,
                               "message": "Only the first default mobile is proposed as primary; review the source defaults."})
            primary.add(key)
        records[child_contracts.CONTACT].append({
            "id": _id(namespace, "contact_contact", pk), "party_source_system": system,
            "party_external_id": parent(row["customer_id"]), "contact_type": "MOBILE", "label": None,
            "value": row["phone_number"], "is_primary": is_primary, "source_is_verified": row["is_verified"] == "t",
            "source_refs": [{"system": system, "external_id": f"contact_contact:{pk}"}], "recorded_at": None,
            "source_recorded_at": row["created"],
        })
    defaults = set()
    for pk, row in sorted(tables["contact_address"].items(), key=lambda item: int(item[0])):
        key = (row["customer_id"], "HOME")
        is_default = row["is_default"] == "t" and key not in defaults
        if row["is_default"] == "t":
            if key in defaults:
                review.append({"code": "MULTIPLE_SOURCE_DEFAULTS", "table": "contact_address", "id": pk,
                               "message": "Only the first default home address is proposed as default; review the source defaults."})
            defaults.add(key)
        line1 = " ".join(value for value in (row["doorno"], row["street"]) if value)
        records[child_contracts.ADDRESS].append({
            "id": _id(namespace, "contact_address", pk), "party_source_system": system,
            "party_external_id": parent(row["customer_id"]), "address_type": "HOME", "line1": line1,
            "line2": None, "area": row["area"], "city": row["city"], "state": None,
            "postal_code": row["zipcode"], "country": "IN", "is_default": is_default,
            "source_is_verified": row["is_verified"] == "t",
            "source_refs": [{"system": system, "external_id": f"contact_address:{pk}"}], "recorded_at": None,
            "source_recorded_at": row["created"],
        })
    invalid = Counter()
    for profile_name, rows in records.items():
        validator = contracts.validate_record if profile_name == contracts.PROFILE else child_contracts.validate_child
        for row in rows:
            _canonical, issues = validator(row, canonical_source=True, **({"profile": profile_name} if profile_name != contracts.PROFILE else {}))
            for issue in issues:
                if issue["severity"] == "ERROR":
                    invalid[profile_name] += 1
                    review.append({"code": issue["code"], "table": profile_name, "id": row["id"], "message": issue["message"]})
    return {"profile": "linode-party-preparation/1", "source_profile": profile.key, "source_system": system,
            "counts": {name: len(rows) for name, rows in records.items()}, "invalid": dict(invalid),
            "review": review, "records": records}


def write_party_preparation(output_dir, preparation):
    output = Path(output_dir)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    files = []
    for profile, rows in preparation["records"].items():
        for number, start in enumerate(range(0, len(rows), MAX_ROWS), 1):
            name = f"{profile.split('/')[0]}-{number:03d}.jsonl"
            content = "".join(_dump(row) + "\n" for row in rows[start:start + MAX_ROWS]).encode("utf-8")
            (output / name).write_bytes(content)
            files.append({"profile": profile, "path": name, "count": len(rows[start:start + MAX_ROWS]), "sha256": hashlib.sha256(content).hexdigest()})
    manifest = {key: value for key, value in preparation.items() if key != "records"}
    manifest["files"] = files
    (output / "review.json").write_text(_dump(manifest) + "\n", encoding="utf-8")
    (output / "COMPLETE").write_text("linode-party-preparation/1\n", encoding="utf-8")
    return output
