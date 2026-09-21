"""Bounded source claims for closed loans; never a financial admission format."""
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from .history_contract import _pairs, digest, dump, nullable, obj, text, array, validate, DECIMAL, DAY
from .portability_validation import PortabilityValidationError, MALFORMED_DATA

PROFILE = "loan-closed-evidence/1"
MAX_BYTES = 1024 * 1024
MAX_SOURCE_RECORDS = 500


class ArchiveError(PortabilityValidationError):
    pass


SCHEMA = obj(
    profile={"const": PROFILE},
    source=obj(namespace={"type": "string", "format": "uuid"}, system=text(120),
               loan_id=text(255), snapshot_reference=text(255), evidence_reference=text(255)),
    facts=obj(status={"const": "CLOSED"}, loan_number=nullable(text(120)), raw_status=nullable(text(120)),
              borrower_reference=nullable(obj(system=text(120), id=text(255))), borrower_name=nullable(text(255)),
              opened_on=nullable(DAY), closed_on=nullable(DAY),
              original_principal=nullable(DECIMAL), reported_balance=nullable(DECIMAL),
              collateral=nullable(array(obj(description=text(255),
                  quantity=nullable({"type": "integer", "minimum": 1, "maximum": 10000}),
                  gross_weight=nullable(DECIMAL), net_weight=nullable(DECIMAL)), 100)),
              payments=nullable(array(obj(id=text(255), date=nullable(DAY), amount=nullable(DECIMAL)), 500))),
    # Raw source dictionaries retain fields not normalized by this small profile.
    source_records={"type": "array", "minItems": 1, "maxItems": MAX_SOURCE_RECORDS, "items": {}},
)


def validate_document(document):
    try:
        validate(document, schema=SCHEMA)
        namespace = document["source"]["namespace"]
        if str(UUID(namespace)) != namespace or UUID(namespace).int == 0:
            raise ArchiveError("Use a canonical, non-nil source namespace UUID.", category=MALFORMED_DATA)
        if any(type(row) is not dict for row in document["source_records"]):
            raise ArchiveError("Source records must be JSON objects.", category=MALFORMED_DATA)

        def check_json(value, depth=0):
            if depth > 24:
                raise ArchiveError("Source evidence exceeds the nesting limit.", category=MALFORMED_DATA)
            if type(value) is dict:
                for key, item in value.items():
                    if type(key) is not str or "\x00" in key:
                        raise ArchiveError("Source keys must be text without NUL characters.", category=MALFORMED_DATA)
                    check_json(item, depth + 1)
            elif type(value) is list:
                for item in value:
                    check_json(item, depth + 1)
            elif type(value) is str:
                if "\x00" in value:
                    raise ArchiveError("Source text cannot contain NUL characters.", category=MALFORMED_DATA)
            elif value is not None and type(value) not in {int, bool}:
                raise ArchiveError("Use decimal strings, not JSON fractional numbers, in source evidence.", category=MALFORMED_DATA)
        check_json(document)
        if len(dump(document).encode("utf-8")) > MAX_BYTES:
            raise ArchiveError("Closed-loan evidence is limited to 1 MiB.", category=MALFORMED_DATA)
        return document
    except PortabilityValidationError:
        raise
    except (ValueError, TypeError, RecursionError) as exc:
        raise ArchiveError("Invalid bounded closed-loan evidence.", category=MALFORMED_DATA) from exc


def parse(content):
    if type(content) is not bytes or not 0 < len(content) <= MAX_BYTES:
        raise ArchiveError("Upload one closed-loan evidence JSON file of at most 1 MiB.", category=MALFORMED_DATA)
    try:
        def invalid_number(value):
            raise ArchiveError("Use finite decimal strings in source evidence.", category=MALFORMED_DATA)
        document = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_pairs,
                              parse_constant=invalid_number, parse_float=invalid_number)
        return validate_document(document)
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, PortabilityValidationError):
            raise
        raise ArchiveError("Invalid closed-loan evidence JSON.", category=MALFORMED_DATA) from exc


def encode(document):
    validate_document(document)
    return dump(document).encode("utf-8")


def review_document(document):
    """Findings explain retained uncertainty; they do not certify source truth."""
    validate_document(document)
    facts = document["facts"]
    findings = []

    def note(code, category, field, message):
        findings.append(dict(code=code, category=category, field=field, message=message, rule_version=1))

    for field in ("borrower_reference", "opened_on", "closed_on", "original_principal", "reported_balance", "collateral", "payments"):
        if facts[field] is None:
            note("UNKNOWN_" + field.upper(), "MISSING_EVIDENCE", "facts." + field,
                 field.replace("_", " ").capitalize() + " is unknown in the supplied evidence.")
    if facts["borrower_reference"] is not None:
        note("UNRESOLVED_BORROWER", "OPERATIONAL_READINESS", "facts.borrower_reference",
             "The source borrower reference is retained without resolving or creating a local Party.")
    if facts["opened_on"] and facts["closed_on"] and date.fromisoformat(facts["closed_on"]) < date.fromisoformat(facts["opened_on"]):
        note("DATE_ORDER", "HISTORICAL_INCONSISTENCY", "facts.closed_on", "The reported closure precedes origination; both claims will be retained.")
    if facts["reported_balance"] is not None and Decimal(facts["reported_balance"]) != 0:
        note("CLOSED_WITH_BALANCE", "HISTORICAL_INCONSISTENCY", "facts.reported_balance", "The closed-loan claim includes a nonzero balance; no debt will be created.")
    ids = [row["id"] for row in facts["payments"] or []]
    if len(ids) != len(set(ids)):
        note("DUPLICATE_PAYMENT_CLAIM", "HISTORICAL_INCONSISTENCY", "facts.payments", "Duplicate source payment identities are retained without posting payments.")
    return {"profile": PROFILE, "source_sha256": digest(document), "findings": findings,
            "historical_retention_ready": True, "operational_admission": False,
            "coverage": "CLOSED_SOURCE_CLAIMS_ONLY"}
