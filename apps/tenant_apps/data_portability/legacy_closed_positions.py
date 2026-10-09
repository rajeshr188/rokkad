"""Prepare a known closed position from retained legacy claims, without financial replay."""
from copy import deepcopy
from decimal import Decimal
from uuid import UUID

from apps.tenant_apps.loans.services import archive_contract, closed_position_contract
from apps.tenant_apps.loans.services.import_identity import source_binding_id
from apps.tenant_apps.loans.services.portability_validation import PortabilityValidationError

SOURCE_NAMESPACE = "6ca968d6-2647-4dbb-8e39-24f0c1a12ed6"
SOURCE_SCHEMAS = {"jcl", "jsk", "lakshmipawnbroker"}
OWNER_RETURN_REFERENCE = "owner-confirmation-2026-10-09:jcl-190-owner-closed-zero-all-collateral-returned-to-borrower"
RELEASE_MEANING_REFERENCE = "owner-confirmation-2026-10-09:released-zero-debt-all-collateral-returned-to-borrower"


def prepare_closed_position(document, *, as_of, release_meaning_reference):
    """Return a portable candidate, not owner approval or financial admission.

    Exact Party/register resolution and snapshot/collision checks are performed
    by the review/admission boundary. Raw mutable amounts are not promoted to
    original principal, and absent receipts do not block a closed position.
    """
    archive_contract.validate_document(document)
    source, facts = document["source"], document["facts"]
    prefix = f"legacy:{UUID(SOURCE_NAMESPACE).hex}:"
    schema = source["system"][len(prefix):] if source["system"].startswith(prefix) else ""
    if source["namespace"] != SOURCE_NAMESPACE or schema not in SOURCE_SCHEMAS:
        raise ValueError("The accepted release interpretation applies only to the reviewed legacy installation and three source schemas.")
    if not isinstance(release_meaning_reference, str) or not release_meaning_reference.strip():
        raise ValueError("Identify the owner-accepted source release meaning before preparing positions.")
    source_binding_id(source["namespace"], source["loan_id"], source["system"])
    if facts["borrower_reference"] is None or facts["borrower_reference"]["system"] != source["system"]:
        raise ValueError("Resolve the exact source borrower identity; names cannot establish the mapping.")
    if facts["reported_balance"] is not None and Decimal(facts["reported_balance"]) != 0:
        raise ValueError("A nonzero reported closing balance requires explicit conflict review.")
    records = [row for row in document["source_records"] if isinstance(row.get("source"), dict)
        and row["source"].get("source_system") == source["system"]]
    loans = [row for row in records if row["source"].get("table") == "girvi_loan"
        and row["source"].get("external_id") == source["loan_id"]]
    if len(loans) != 1:
        raise ValueError("Retained evidence must identify one exact source loan.")
    loan_id = loans[0]["source"]["id"]
    if source["loan_id"] != f"girvi_loan:{loan_id}":
        raise ValueError("The retained source loan ID and table identity disagree.")
    if facts["borrower_reference"]["id"] != f"contact_customer:{loans[0]['facts'].get('customer_id')}":
        raise ValueError("The retained borrower reference must belong to this source loan.")
    releases = [row for row in records if row["source"].get("table") == "girvi_release"
        and row["source"].get("external_id") == f"girvi_release:{row['source'].get('id')}"
        and row["facts"].get("loan_id") == loan_id]
    if facts["raw_status"] == "RELEASE_ROW_PRESENT" and len(releases) == 1:
        basis, custody, reference = "SOURCE_RELEASE_MEANING", "RETURNED_TO_BORROWER", release_meaning_reference
    elif (facts["raw_status"] == "NO_RELEASE_ROW; OWNER_REPORTS_CLOSED"
            and facts["reported_balance"] is not None and Decimal(facts["reported_balance"]) == 0
            and any(row.get("owner_decision") for row in document["source_records"])):
        # Separate owner confirmation covers JCL's 190 no-release-row cohort only.
        basis, custody, reference = "OWNER_CLOSED_POSITION", "UNKNOWN", "Retained owner closed-position decision; original closure date and handover unavailable."
        if schema == "jcl":
            custody, reference = "RETURNED_TO_BORROWER", OWNER_RETURN_REFERENCE
    else:
        raise ValueError("Resolve ambiguous release claims or supply an accepted closed-position decision.")
    candidate = dict(profile=closed_position_contract.PROFILE,
        source={key: source[key] for key in ("namespace", "system", "loan_id")},
        loan=dict(number=facts["loan_number"], borrower_reference=deepcopy(facts["borrower_reference"]),
            original_date=facts["opened_on"], closed_on=facts["closed_on"],
            original_principal=facts["original_principal"], monthly_rate=None, tenure_months=None),
        position=dict(state="CLOSED", as_of=as_of.isoformat(), currency="INR", principal="0", interest="0", fees="0",
            custody=custody, basis=basis, evidence_reference=reference),
        earlier_history="UNAVAILABLE", retained_evidence=deepcopy(document))
    closed_position_contract.validate_document(candidate)
    return candidate


def classify_closed_position(document, *, as_of, release_meaning_reference):
    """Prepare eligible facts and expose exceptions; no evidence is changed or dropped."""
    try:
        candidate = prepare_closed_position(document, as_of=as_of, release_meaning_reference=release_meaning_reference)
    except (ValueError, PortabilityValidationError) as exc:
        return dict(status="REVIEW", document=None, reason=str(exc))
    return dict(status="CANDIDATE", document=candidate, reason=None)
