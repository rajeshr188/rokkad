"""Opening-event read contract. It does not authorize or commit an import."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from .opening_validation import validate_opening

PROFILE = "loan-opening-evidence/1"
KIND = "MIGRATION_OPENING"


class OpeningEvidenceError(ValueError):
    pass


def read_opening_evidence(loan, event):
    """Check frozen reviewed amounts and their binding to this destination loan."""
    payload = event.payload
    if not isinstance(payload, dict) or not isinstance(payload.get("opening"), dict):
        raise OpeningEvidenceError("Migration opening evidence is missing.")
    if (type(payload.get("contract_version")) is not int or payload["contract_version"] != 1 or
            payload.get("currency") != "INR" or payload.get("reversal") is not None):
        raise OpeningEvidenceError("Unsupported migration opening event envelope.")
    opening = payload["opening"]
    if set(opening) != {"profile", "review", "item_mapping"} or opening["profile"] != PROFILE:
        raise OpeningEvidenceError("Unsupported migration opening evidence.")
    review = opening["review"]
    if not validate_opening(review)["document_reconciled"]:
        raise OpeningEvidenceError("Migration opening review does not reconcile.")
    mapping = review["mapping"]
    if any(mapping[key] != getattr(loan, attr, None) for key, attr in (
            ("workspace_id", "workspace_id"), ("borrower_id", "borrower_id"),
            ("licence_revision_id", "license_revision_id"), ("series_id", "series_id"),
            ("product_version_id", "product_version_id"))):
        raise OpeningEvidenceError("Migration opening destination references do not match this loan.")
    if date.fromisoformat(review["terms"]["original_date"]) != loan.loan_date:
        raise OpeningEvidenceError("Migration opening must preserve the original loan date.")
    identity = payload.get("source_identity")
    if (not isinstance(identity, dict) or event.effective_date.isoformat() != review["cutover"]["date"] or
            payload.get("effective_date") != review["cutover"]["date"] or
            payload.get("event_kind") != KIND or
            identity != {"app": "loans", "model": "PawnLoan", "loan_id": loan.pk}):
        raise OpeningEvidenceError("Migration opening date or loan identity is inconsistent.")
    values = payload.get("values")
    if not isinstance(values, dict) or set(values) != {"principal", "interest", "fees"} or any(
            values[key] != review["balances"][key] for key in values):
        raise OpeningEvidenceError("Migration opening amounts differ from the frozen review.")
    item_mapping = opening["item_mapping"]
    if (not isinstance(item_mapping, dict) or set(item_mapping) != set(review["source"]["item_ids"]) or
            any(type(pk) is not int or pk <= 0 for pk in item_mapping.values()) or
            len(set(item_mapping.values())) != len(item_mapping)):
        raise OpeningEvidenceError("Migration opening requires distinct destination item identities.")
    return opening


def opening_event_payload(loan, *, review, item_mapping):
    """Freeze reviewed evidence for the forthcoming import writer; no ORM writes."""
    from types import SimpleNamespace
    if not isinstance(review, dict) or not isinstance(review.get("cutover"), dict):
        raise OpeningEvidenceError("A reconciled opening review is required.")
    try:
        day = date.fromisoformat(review["cutover"]["date"])
        payload = {"contract_version": 1, "event_kind": KIND, "effective_date": day.isoformat(),
                   "currency": "INR", "source_identity": {"app": "loans", "model": "PawnLoan", "loan_id": loan.pk},
                   "values": {key: review["balances"][key] for key in ("principal", "interest", "fees")},
                   "opening": {"profile": PROFILE, "review": review, "item_mapping": item_mapping}}
    except (KeyError, TypeError, ValueError) as exc:
        raise OpeningEvidenceError("A reconciled opening review is required.") from exc
    read_opening_evidence(loan, SimpleNamespace(payload=payload, effective_date=day))
    return deepcopy(payload)


def opening_tranches(opening):
    return tuple({"collateral_item_id": opening["item_mapping"][item["id"]],
                  "allocated_principal": Decimal(item["remaining_principal"]),
                  "monthly_interest_rate": Decimal(item["monthly_rate"])}
                 for item in opening["review"]["collateral"])
