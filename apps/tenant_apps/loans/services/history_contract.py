"""Canonical loan-history/1: one manifest and one complete loan JSONL record."""
import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from .portability_validation import (
    PortabilityValidationError, MALFORMED_DATA, MISSING_EVIDENCE, OPERATIONAL_READINESS,
)

PROFILE = "loan-history/1"
MAX_BYTES = 5 * 1024 * 1024


class HistoryError(PortabilityValidationError):
    pass


def dump(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def text(limit=120):
    return {"type": "string", "minLength": 1, "maxLength": limit, "pattern": r"^[^\x00-\x1f\x7f]+$"}


def array(items, maximum, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}


def nullable(value):
    return {"oneOf": [value, {"type": "null"}]}


DECIMAL = {"type": "string", "pattern": r"^(0|[1-9][0-9]{0,11})(\.[0-9]{1,6})?$", "maxLength": 19}
DAY = {"type": "string", "format": "date"}
STAMP = {"type": "string", "format": "date-time"}
INTEGER = {"type": "integer", "minimum": 1, "maximum": 1200}
BALANCE = obj(principal=DECIMAL, interest=DECIMAL, fees=DECIMAL)
ALLOCATION = obj(item=text(), before=DECIMAL, principal=DECIMAL, after=DECIMAL)
ACCRUAL = obj(period=INTEGER, start=DAY, end=DAY, fraction=DECIMAL, base=DECIMAL,
              unrounded=DECIMAL, recognized=DECIMAL)
RELEASE = obj(number=text(), returned_at=STAMP, collector=nullable(text(255)),
              valuation=array(obj(item=text(), value=DECIMAL), 20, 1))
EVENT = obj(id=text(), kind={"enum": ["DISBURSAL", "REPAYMENT", "INTEREST_ACCRUAL", "RELEASE_RECEIPT"]},
            date=DAY, actor=text(255), principal=DECIMAL, interest=DECIMAL, fees=DECIMAL,
            balance=BALANCE, allocations=array(ALLOCATION, 20), accrual=nullable(ACCRUAL), release=nullable(RELEASE))
POLICY = obj(policy_version={"const": 1}, interest_method={"const": "SIMPLE"},
    partial_month_method={"enum": ["FULL_MONTH", "SLAB"]}, partial_month_cutoff_days={"type": "integer", "minimum": 1, "maximum": 30},
    partial_month_lower_fraction=DECIMAL, capitalization_interval_periods=INTEGER,
    valuation_method={"enum": ["CALCULATED_METAL_VALUE", "LATEST_APPRAISAL", "LOWER_OF_CALCULATED_AND_APPRAISAL"]},
    maximum_ltv_ratio=DECIMAL, rounding_method={"const": "PER_ACCRUAL_PERIOD"}, currency_quantum={"const": "0.01"})
ITEM = obj(id=text(), description=text(255), metal={"enum": ["GOLD", "SILVER", "OTHER"]},
    gross_weight=DECIMAL, net_weight=DECIMAL, purity=DECIMAL, principal=DECIMAL, monthly_rate=DECIMAL,
    metal_rate=nullable(DECIMAL), appraised_value=nullable(DECIMAL), valuation_reference=text(255))
LOAN = obj(id=text(), number=text(), state={"enum": ["ACTIVE", "CLOSED"]},
    borrower=obj(source_system=text(), id=text()), licence_number=text(100), disbursed_on=DAY,
    tenure_months={"type": "integer", "minimum": 1, "maximum": 12}, calculation_contract=text(40),
    grace_days={"type": "integer", "minimum": 0, "maximum": 30},
    approval=obj(at=STAMP, actor=text(255), reference=text(255)), policy=POLICY,
    collateral=array(ITEM, 20, 1),
    disbursal=obj(advance_periods={"type": "integer", "minimum": 0, "maximum": 12},
        fees=array(obj(code=text(40), name=text(120), kind={"enum": ["FIXED", "PERCENTAGE"]}, value=DECIMAL, deducted={"type": "boolean"}),20),
        principal=DECIMAL, monthly_interest=DECIMAL, advance_interest=DECIMAL, deducted_fees=DECIMAL, net_cash=DECIMAL),
    schedule=obj(maturity=DAY, principal=DECIMAL, interest=DECIMAL,
        obligations=array(obj(sequence=INTEGER, due=DAY, principal=DECIMAL, interest=DECIMAL), 1, 1)),
    events=array(EVENT, 240, 1), cutover=BALANCE)
MANIFEST = obj(profile={"const": PROFILE}, namespace={"type": "string", "format": "uuid"}, as_of=DAY,
    coverage={"const": "PARTIAL"}, exclusions={"const": ["binary_files", "workspace_configuration", "renewals", "auctions", "opening_positions"]})
SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", **obj(manifest=MANIFEST, loan=LOAN)}


def validate(value, schema=SCHEMA, path="document"):
    if "oneOf" in schema:
        matches = 0
        for variant in schema["oneOf"]:
            try: validate(value, variant, path); matches += 1
            except HistoryError: pass
        if matches != 1:
            raise HistoryError(
                f"{path}: invalid optional value.",
                category=MALFORMED_DATA,
                code="DOCUMENT_VALUE",
                field=path,
            )
        return
    if "const" in schema:
        if type(value) is not type(schema["const"]) or value != schema["const"]:
            raise HistoryError(
                f"{path}: unsupported contract value.",
                category=OPERATIONAL_READINESS if type(value) is type(schema["const"]) else MALFORMED_DATA,
                code="UNSUPPORTED_PROFILE_VALUE",
                field=path,
            )
    if "enum" in schema and value not in schema["enum"]:
        raise HistoryError(
            f"{path}: unsupported value.",
            category=OPERATIONAL_READINESS if any(type(value) is type(choice) for choice in schema["enum"]) else MALFORMED_DATA,
            code="UNSUPPORTED_PROFILE_VALUE",
            field=path,
        )
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool, "null": type(None)}
    if kind and type(value) is not types[kind]:
        raise HistoryError(
            f"{path}: expected {kind}.",
            category=MISSING_EVIDENCE if value is None else MALFORMED_DATA,
            code="DOCUMENT_VALUE",
            field=path,
        )
    if kind == "object":
        if set(value) != set(schema["properties"]):
            raise HistoryError(
                f"{path}: missing or unsupported fields.",
                category=MISSING_EVIDENCE if set(value) < set(schema["properties"]) else MALFORMED_DATA,
                code="DOCUMENT_FIELDS",
                field=path,
            )
        for key, spec in schema["properties"].items(): validate(value[key], spec, f"{path}.{key}")
    if kind == "array":
        if not schema["minItems"] <= len(value) <= schema["maxItems"]:
            raise HistoryError(
                f"{path}: record limit exceeded or required records missing.",
                category=MISSING_EVIDENCE if len(value) < schema["minItems"] else OPERATIONAL_READINESS,
                code="DOCUMENT_RECORD_COUNT",
                field=path,
            )
        for index, item in enumerate(value): validate(item, schema["items"], f"{path}[{index + 1}]")
    if kind == "integer" and not schema["minimum"] <= value <= schema["maximum"]:
        raise HistoryError(
            f"{path}: outside supported range.",
            category=OPERATIONAL_READINESS,
            code="SUPPORTED_RANGE",
            field=path,
        )
    if kind == "string":
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 120):
            raise HistoryError(
                f"{path}: invalid length.",
                category=MISSING_EVIDENCE if not value else MALFORMED_DATA,
                code="DOCUMENT_TEXT",
                field=path,
            )
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise HistoryError(
                f"{path}: invalid text or decimal.",
                category=MALFORMED_DATA,
                code="DOCUMENT_VALUE",
                field=path,
            )
        try:
            if schema.get("format") == "date":
                if date.fromisoformat(value).isoformat() != value: raise ValueError()
            elif schema.get("format") == "date-time":
                if datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None: raise ValueError()
            elif schema.get("format") == "uuid": UUID(value)
        except ValueError as exc:
            raise HistoryError(
                f"{path}: invalid date or identifier.",
                category=MALFORMED_DATA,
                code="DOCUMENT_VALUE",
                field=path,
            ) from exc


def canonical_document(value, schema=SCHEMA):
    """Normalize decimal spellings without altering portable IDs or source text."""
    if schema is DECIMAL:
        return decimal(value)
    if "oneOf" in schema:
        return None if value is None else canonical_document(value, schema["oneOf"][0])
    if schema.get("type") == "object":
        return {key: canonical_document(value[key], child) for key, child in schema["properties"].items()}
    if schema.get("type") == "array":
        return [canonical_document(item, schema["items"]) for item in value]
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise HistoryError(
                "Duplicate JSON property.",
                category=MALFORMED_DATA,
                code="DOCUMENT_FORMAT",
                field="document",
            )
        result[key] = value
    return result


def parse(content):
    if not isinstance(content, bytes) or not content or len(content) > MAX_BYTES:
        raise HistoryError(
            "Use a JSONL file of at most 5 MiB.",
            category=MALFORMED_DATA,
            code="DOCUMENT_FORMAT",
            field="document",
        )
    try:
        lines = content.decode("utf-8-sig").splitlines()
        if len(lines) != 2:
            raise HistoryError(
                "Use exactly two JSONL records: manifest, then one complete loan.",
                category=MALFORMED_DATA,
                code="DOCUMENT_FORMAT",
                field="document",
            )
        records = [json.loads(line, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(HistoryError("Non-finite JSON value.", category=MALFORMED_DATA, code="DOCUMENT_FORMAT", field="document"))) for line in lines]
        if isinstance(records[0], dict) and records[0].get("profile") == "loan-opening-export/1":
            raise HistoryError(
                "This is an opening evidence export. Use the dedicated opening restore command; upload a complete loan-history/1 file here.",
                category=OPERATIONAL_READINESS,
                code="UNSUPPORTED_PROFILE_VALUE",
                field="document",
            )
        result = {"manifest": records[0], "loan": records[1]}
        validate(result)
        return canonical_document(result)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise HistoryError(
            "Invalid bounded UTF-8 JSONL document.",
            category=MALFORMED_DATA,
            code="DOCUMENT_FORMAT",
            field="document",
        ) from exc


def encode(document):
    validate(document)
    document = canonical_document(document)
    result = (dump(document["manifest"]) + "\n" + dump(document["loan"]) + "\n").encode("utf-8")
    if len(result) > MAX_BYTES:
        raise HistoryError(
            "Loan history exceeds 5 MiB.",
            category=MALFORMED_DATA,
            code="DOCUMENT_FORMAT",
            field="document",
        )
    return result


def money(value):
    return Decimal(str(value))


def decimal(value):
    return format(Decimal(value).normalize(), "f")
