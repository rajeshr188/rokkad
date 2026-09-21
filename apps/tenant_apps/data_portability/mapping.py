from .contracts import FIELDS, PROFILE, issue
from . import child_contracts
from .parsers import PortabilityError
import re

TARGETS = set(FIELDS) | {"business_code", "source.external_id", "source_recorded_at"}


def validate_mapping(mapping, headers, source_type, profile=PROFILE):
    fields = set(FIELDS) if profile == PROFILE else set(child_contracts.fields(profile)) | set(child_contracts.parent_fields(profile)) | {"source_is_verified"}
    if profile == child_contracts.IDENTIFIER:
        fields.add("source_verified_at")
    if profile in {child_contracts.ROLE, child_contracts.RELATIONSHIP}:
        fields.discard("source_is_verified")
    targets = TARGETS if profile == PROFILE else fields | {"source.external_id", "source_recorded_at"}
    allowed = {"columns", "defaults", "normalization"}
    if profile == child_contracts.ROLE:
        allowed.add("role_type_map")
    if profile == PROFILE:
        allowed.add("name_reviews")
    if profile == child_contracts.ADDRESS:
        allowed.add("address_reviews")
    if not isinstance(mapping, dict) or set(mapping) - allowed:
        raise PortabilityError("Invalid mapping configuration.")
    columns, defaults, rules = mapping.get("columns", {}), mapping.get("defaults", {}), mapping.get("normalization", [])
    if not isinstance(columns, dict) or not isinstance(defaults, dict) or not isinstance(rules, list):
        raise PortabilityError("Invalid mapping configuration.")
    if source_type == "jsonl" and (columns or defaults or rules):
        raise PortabilityError("Canonical JSONL uses its own field names without a column mapping.")
    if not set(columns) <= set(headers) or any(not isinstance(v, str) or v not in targets for v in columns.values()):
        raise PortabilityError("Mappings must use source headers and supported Party fields.")
    if len(set(columns.values())) != len(columns) or not set(defaults) <= fields:
        raise PortabilityError("Duplicate field mappings or unsupported defaults.")
    if source_type in {"csv", "xlsx"} and "source.external_id" not in columns.values():
        raise PortabilityError("Map a durable source identifier before validation.")
    if len(rules) > 40:
        raise PortabilityError("Too many normalization rules.")
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"field", "rule", "version"}:
            raise PortabilityError("Each normalization requires field, rule and version.")
        if rule["field"] not in targets - {"source.external_id", "role_type_key", *child_contracts.relationship_contracts.REFERENCES} or rule["rule"] not in {"trim", "upper", "empty_to_null", "boolean"} or rule["version"] != 1:
            raise PortabilityError("Unsupported normalization rule.")
    result = {"columns": columns, "defaults": defaults, "normalization": rules}
    if "address_reviews" in mapping:
        reviews = mapping["address_reviews"]
        if not isinstance(reviews, dict) or len(reviews) > 1000:
            raise PortabilityError("Address reviews must identify at most 1,000 source records.")
        for external, review in reviews.items():
            if (not isinstance(external, str) or not external or len(external) > 255
                    or external != external.strip() or any(ord(c) < 32 for c in external)
                    or not isinstance(review, dict) or set(review) != {"record_sha256", "party_id", "address_ids", "reason"}
                    or not isinstance(review["record_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", review["record_sha256"])
                    or type(review["party_id"]) is not int or review["party_id"] <= 0
                    or not isinstance(review["reason"], str) or not review["reason"].strip() or len(review["reason"]) > 255
                    or any(ord(c) < 32 or ord(c) == 127 for c in review["reason"])
                    or not isinstance(review["address_ids"], list) or len(review["address_ids"]) > 1000
                    or any(type(pk) is not int or pk <= 0 for pk in review["address_ids"])
                    or len(set(review["address_ids"])) != len(review["address_ids"])):
                raise PortabilityError("Invalid reviewed address decision.")
        result["address_reviews"] = reviews
    if "name_reviews" in mapping:
        reviews = mapping["name_reviews"]
        if not isinstance(reviews, dict) or len(reviews) > 1000:
            raise PortabilityError("Name reviews must identify at most 1,000 source records.")
        for external, review in reviews.items():
            if (not isinstance(external, str) or not external or len(external) > 255
                    or external != external.strip() or any(ord(c) < 32 for c in external)
                    or not isinstance(review, dict) or set(review) != {"record_sha256", "party_ids", "reason"}
                    or not isinstance(review["record_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", review["record_sha256"])
                    or not isinstance(review["reason"], str) or not review["reason"].strip() or len(review["reason"]) > 255
                    or any(ord(c) < 32 or ord(c) == 127 for c in review["reason"])
                    or not isinstance(review["party_ids"], list) or len(review["party_ids"]) > 1000
                    or any(type(pk) is not int or pk <= 0 for pk in review["party_ids"])
                    or len(set(review["party_ids"])) != len(review["party_ids"])):
                raise PortabilityError("Invalid reviewed name decision.")
        result["name_reviews"] = reviews
    if profile == child_contracts.ROLE:
        role_map = mapping.get("role_type_map", {})
        if not isinstance(role_map, dict) or len(role_map) > 1000 or any(
            not isinstance(k, str) or not isinstance(v, str) or not k or not v or len(k) > 64 or len(v) > 64
            or k != k.strip() or v != v.strip() for k, v in role_map.items()):
            raise PortabilityError("Role mappings must contain exact source and destination keys.")
        result["role_type_map"] = role_map
    return result


def map_row(raw, mapping, source_type):
    if source_type == "jsonl":
        return dict(raw), raw.get("id", ""), []
    record = dict(mapping["defaults"])
    issues = [issue("EXPLICIT_DEFAULT", key, "Used the reviewed mapping default.", "INFO", None, value)
              for key, value in sorted(record.items())]
    for column, target in mapping["columns"].items():
        record[target] = raw[column]
    external = record.pop("source.external_id", "")
    unused = set(raw) - set(mapping["columns"])
    if unused:
        issues.append(issue("UNMAPPED_COLUMNS", "", "Unmapped source columns will not be imported.", "WARNING"))
    return record, external, issues
