"""Known closed loan position; earlier cash history and calculation terms are optional.

Validation describes the input. It does not authorize an import, resolve local
identities, attest source truth or persist a PawnLoan.
"""
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from . import archive_contract
from .history_contract import _pairs, digest, dump, nullable, obj, text, validate, DECIMAL, DAY
from .portability_validation import PortabilityValidationError, MALFORMED_DATA

PROFILE = "loan-closed-position/1"
MAX_BYTES = 2 * 1024 * 1024


class ClosedPositionError(PortabilityValidationError):
    pass


SCHEMA = obj(
    profile={"const": PROFILE},
    source=obj(namespace={"type": "string", "format": "uuid"}, system=text(120), loan_id=text(120)),
    loan=obj(number=text(64), borrower_reference=obj(system=text(120), id=text(255)),
        original_date=nullable(DAY), closed_on=nullable(DAY),
        original_principal=nullable(DECIMAL), monthly_rate=nullable(DECIMAL),
        tenure_months=nullable({"type": "integer", "minimum": 1, "maximum": 1200})),
    position=obj(state={"const": "CLOSED"}, as_of=DAY, currency={"const": "INR"},
        principal={"const": "0"}, interest={"const": "0"}, fees={"const": "0"},
        custody={"enum": ["RETURNED_TO_BORROWER", "UNKNOWN"]},
        basis={"enum": ["SOURCE_RELEASE_MEANING", "OWNER_CLOSED_POSITION"]},
        evidence_reference=text(1000)),
    earlier_history={"const": "UNAVAILABLE"},
    # Source rows can contain receipts without establishing a complete timeline.
    retained_evidence=nullable(archive_contract.SCHEMA),
)


def validate_document(document):
    validate(document, schema=SCHEMA)
    source, loan, position = (document[key] for key in ("source", "loan", "position"))
    namespace = source["namespace"]
    if str(UUID(namespace)) != namespace or UUID(namespace).int == 0:
        raise ClosedPositionError("Use a canonical non-nil source namespace.", category=MALFORMED_DATA)
    for value in (source["system"], source["loan_id"], loan["number"],
            loan["borrower_reference"]["system"], loan["borrower_reference"]["id"], position["evidence_reference"]):
        if not value.strip():
            raise ClosedPositionError("Loan and source identities and position basis cannot be blank.", category=MALFORMED_DATA)
    original = date.fromisoformat(loan["original_date"]) if loan["original_date"] else None
    closed = date.fromisoformat(loan["closed_on"]) if loan["closed_on"] else None
    cutoff = date.fromisoformat(position["as_of"])
    if (original and original > cutoff) or (closed and closed > cutoff) or (original and closed and original > closed):
        raise ClosedPositionError("Original and closure dates must agree with the accepted position date.", category=MALFORMED_DATA)
    if loan["original_principal"] is not None and Decimal(loan["original_principal"]) <= 0:
        raise ClosedPositionError("Unknown original principal must be null, not zero.", category=MALFORMED_DATA)
    if loan["monthly_rate"] is not None and Decimal(loan["monthly_rate"]) > 100:
        raise ClosedPositionError("Recorded monthly rate exceeds 100 percent.", category=MALFORMED_DATA)
    evidence = document["retained_evidence"]
    if evidence is not None:
        archive_contract.validate_document(evidence)
        raw_source, facts = evidence["source"], evidence["facts"]
        if any(raw_source[key] != source[key] for key in ("namespace", "system", "loan_id")):
            raise ClosedPositionError("Retained evidence must identify this exact source loan.", category=MALFORMED_DATA)
        for old, current in (("loan_number", "number"), ("opened_on", "original_date"), ("closed_on", "closed_on"),
                ("original_principal", "original_principal"), ("borrower_reference", "borrower_reference")):
            if facts[old] is not None and facts[old] != loan[current]:
                raise ClosedPositionError("Known retained loan details cannot be replaced or omitted.", category=MALFORMED_DATA)
        if facts["reported_balance"] is not None and Decimal(facts["reported_balance"]) != 0:
            raise ClosedPositionError("Resolve the retained nonzero closing balance.", category=MALFORMED_DATA)
    if len(dump(document).encode("utf-8")) > MAX_BYTES:
        raise ClosedPositionError("One closed-position document is limited to 2 MiB.", category=MALFORMED_DATA)
    return document


def parse(content):
    if type(content) is not bytes or not 0 < len(content) <= MAX_BYTES:
        raise ClosedPositionError("Supply one closed-position JSON document of at most 2 MiB.", category=MALFORMED_DATA)
    try:
        def invalid_number(value):
            raise ClosedPositionError("Use finite decimal strings, not fractional JSON numbers.", category=MALFORMED_DATA)
        document = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_pairs,
            parse_float=invalid_number, parse_constant=invalid_number)
        return validate_document(document)
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, PortabilityValidationError):
            raise
        raise ClosedPositionError("Invalid closed-position JSON document.", category=MALFORMED_DATA) from exc


def encode(document):
    validate_document(document)
    return dump(document).encode("utf-8")


def review_document(document):
    """Coverage is explicit: zero debt, unknown earlier collections, no policy requirement."""
    validate_document(document)
    return dict(profile=PROFILE, source_sha256=digest(document), state="CLOSED",
        as_of=document["position"]["as_of"], balances={key: "0" for key in ("principal", "interest", "fees")},
        custody=document["position"]["custody"], earlier_history="UNAVAILABLE",
        missing_original_details=[key for key, value in document["loan"].items() if value is None],
        requires_origination_approval=False, requires_monitoring_policy=False,
        requires_receipt_reconstruction=False, admission_authorized=False)
