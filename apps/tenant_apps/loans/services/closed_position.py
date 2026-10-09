"""Owner-reviewed position admission. No earlier financial actions are inferred."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid5

from django.core import signing
from django.db import connection, transaction
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.party.models import Party
from . import closed_position_contract as contract
from .history_contract import digest
from .history_setup import require_history_setup_access
from .import_identity import find_source_origin, source_binding_id

EVIDENCE_PROFILE = "loan-closed-position-evidence/1"
ADMISSION_PROFILE = "loan-closed-position-admission/1"
SALT = "loans.closed-position.review.v1"


def position_source_id(source):
    if source["system"].startswith("legacy:"):
        return source_binding_id(source["namespace"], source["loan_id"], source["system"])
    # Source systems within one external installation can reuse table-local IDs.
    # Length-prefixing is unambiguous even when identities contain punctuation.
    material = f"{len(source['system'])}:{source['system']}{source['loan_id']}"
    return "closed:" + sha256(material.encode("utf-8")).hexdigest()


def _prepare(workspace_id, actor, document, borrower_id, series_id, evidence_id=None):
    workspace = require_history_setup_access(workspace_id, actor)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    for action in ("data.create", "loan.release"):
        access.require(action)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    # Authority is current even after waiting for the aggregate lock.
    require_history_setup_access(workspace_id, actor)
    contract.validate_document(document)
    if date.fromisoformat(document["position"]["as_of"]) > timezone.localdate():
        raise ValueError("A future closed position cannot be admitted.")
    details = document["loan"]
    for key, places in (("original_principal", 2), ("monthly_rate", 6)):
        if details[key] is not None and (abs(Decimal(details[key])) >= Decimal(10) ** (16 if key == "original_principal" else 3)
                or Decimal(details[key]) != Decimal(details[key]).quantize(Decimal(10) ** -places)):
            raise ValueError("Known original terms must fit the loan's stored precision without rounding.")
    Party.objects.get(workspace_id=workspace_id, pk=borrower_id)
    series = m.LoanSeries.objects.select_related("license").get(workspace_id=workspace_id, pk=series_id)
    from apps.tenant_apps.data_portability.children import parent_for
    reference = details["borrower_reference"]
    refs = [reference["id"]]
    prefix = f"legacy:{UUID(document['source']['namespace']).hex}:"
    if reference["system"].startswith(prefix):
        refs.append(str(uuid5(uuid5(UUID(document["source"]["namespace"]), reference["system"][len(prefix):]), reference["id"])))
    parents = [parent_for(dict(party_source_system=reference["system"], party_external_id=external), workspace_id) for external in refs]
    if not any(parents) or any(parent and parent.party_id != borrower_id for parent in parents):
        raise ValueError("Import the exact source Party mapping first; borrower names cannot establish identity.")
    archive = None
    if evidence_id is not None:
        from .archive import get_evidence
        from .archive_admission import source_snapshots
        evidence = get_evidence(workspace_id=workspace_id, actor=actor, evidence_id=evidence_id)
        snapshots = source_snapshots(evidence)
        for row in snapshots:
            if digest(row.document) != row.source_sha256:
                raise ValueError("Retained source fingerprint differs; review the source first.")
            contract.validate_document({**document, "retained_evidence": row.document})
        if evidence.document != document["retained_evidence"]:
            raise ValueError("The accepted position must retain the exact selected source snapshot.")
        archive = dict(id=evidence.pk, sha256=evidence.source_sha256,
            snapshots=[[row.pk, row.source_sha256] for row in snapshots])
    elif document["retained_evidence"] is not None:
        from .archive import accept_evidence
        evidence = accept_evidence(workspace_id=workspace_id, actor=actor, document=document["retained_evidence"],
            expected_sha256=digest(document["retained_evidence"]), confirmed=True)
        archive = dict(id=evidence.pk, sha256=evidence.source_sha256, snapshots=[[evidence.pk, evidence.source_sha256]])
    accepted = dict(profile=ADMISSION_PROFILE, position=deepcopy(document), archive=archive,
        mapping=dict(workspace_id=workspace_id, borrower_id=borrower_id, series_id=series.pk, license_id=series.license_id))
    return workspace, series, accepted


def _write(workspace, series, actor, accepted):
    document = accepted["position"]
    source, terms = document["source"], document["loan"]
    namespace = UUID(source["namespace"])
    origin = m.HistoricalLoanImport.objects.select_related("loan").filter(workspace_id=workspace.pk,
        source_namespace=namespace, source_id=position_source_id(source)).first()
    if origin is None:
        # Existing older financial profiles retain their original bindings. An
        # ambiguous older origin is held rather than silently imported twice.
        origin = find_source_origin(workspace_id=workspace.pk, namespace=namespace,
            source_id=source["loan_id"], borrower_source_system=source["system"])
    checksum = digest(accepted)
    if origin:
        if origin.source_sha256 != checksum or origin.document != accepted:
            raise ValueError("This source already has a different accepted financial origin. Open that loan.")
        read_position(origin.loan)
        return origin.loan, False
    from .recorded_numbers import claim_number
    archive = accepted["archive"]
    claim_number(series, terms["number"], kind="PAWN_LOAN", actor=actor,
        archive_ids=[row[0] for row in archive["snapshots"]] if archive else ())
    loan = m.PawnLoan.objects.create(workspace=workspace, license=series.license, series=series,
        borrower_id=accepted["mapping"]["borrower_id"], loan_number=terms["number"], state="CLOSED",
        is_imported_closed_position=True, product_version=None, policy_snapshot=None,
        principal_amount=Decimal(terms["original_principal"]) if terms["original_principal"] is not None else None,
        monthly_interest_rate=Decimal(terms["monthly_rate"]) if terms["monthly_rate"] is not None else None,
        loan_date=date.fromisoformat(terms["original_date"]) if terms["original_date"] else None,
        tenure_months=terms["tenure_months"], created_by=actor, updated_by=actor)
    day = date.fromisoformat(document["position"]["as_of"])
    payload = dict(contract_version=1, currency="INR", event_kind="MIGRATION_OPENING", effective_date=day.isoformat(),
        source_identity=dict(app="loans", model="PawnLoan", loan_id=loan.pk),
        values=dict(principal="0", interest="0", fees="0"),
        opening=dict(profile=EVIDENCE_PROFILE, review=accepted, item_mapping={}))
    from .event_recording import _persist_locked_event
    event, _ = _persist_locked_event(loan, kind="MIGRATION_OPENING", effective_date=day, payload=payload, actor=actor)
    m.HistoricalLoanImport.objects.create(workspace=workspace, loan=loan, source_namespace=namespace,
        source_id=position_source_id(source), source_sha256=checksum,
        document=accepted, archive_evidence_id=archive["id"] if archive else None,
        references=dict(events=dict(opening=event.pk)), imported_by=actor)
    read_position(loan)
    connection.check_constraints()
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor, content_object=loan,
        description="Accepted closed zero-debt position; earlier transactions unavailable.",
        data=dict(profile=contract.PROFILE, sha256=checksum, loan=loan.pk))
    return loan, True


@transaction.atomic
def preview_closed_position(*, workspace_id, actor, document, borrower_id, series_id, evidence_id=None):
    with transaction.atomic():
        workspace, series, accepted = _prepare(workspace_id, actor, document, borrower_id, series_id, evidence_id)
        _write(workspace, series, actor, accepted)
        # Do not sign rolled-back PKs allocated when importing new retained evidence.
        checksum = digest(dict(document=document, borrower_id=borrower_id, series_id=series_id,
            evidence_id=str(evidence_id) if evidence_id else None,
            archive=accepted["archive"] if evidence_id else None))
        summary = contract.review_document(document)
        summary["admission_authorized"] = True
        token = signing.dumps(dict(workspace=workspace_id, actor=actor.pk, sha256=checksum,
            date=timezone.localdate().isoformat()), salt=SALT)
        transaction.set_rollback(True)
    return summary, token


@transaction.atomic
def admit_closed_position(*, workspace_id, actor, document, borrower_id, series_id,
        review_token, confirmed=False, evidence_id=None):
    if confirmed is not True:
        raise ValueError("Confirm the reviewed closed position.")
    workspace, series, accepted = _prepare(workspace_id, actor, document, borrower_id, series_id, evidence_id)
    try:
        approved = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValueError("Review this closed position again; review is missing or expired.") from None
    expected = dict(workspace=workspace_id, actor=actor.pk, date=timezone.localdate().isoformat(),
        sha256=digest(dict(document=document, borrower_id=borrower_id, series_id=series_id,
            evidence_id=str(evidence_id) if evidence_id else None,
            archive=accepted["archive"] if evidence_id else None)))
    if approved != expected:
        raise ValueError("Position, mapping or operator changed. Review again.")
    return _write(workspace, series, actor, accepted)


def read_position(loan):
    events = list(loan.loan_events.all())
    if len(events) != 1:
        raise ValueError("Accepted closed position must have its sole immutable position event.")
    from .opening_evidence import read_opening_evidence
    return read_opening_evidence(loan, events[0])["review"]["position"]


def read_closed_evidence(loan, event):
    payload = event.payload
    opening = payload["opening"]
    accepted = opening["review"]
    if type(accepted) is not dict or set(accepted) != {"profile", "position", "archive", "mapping"} or accepted["profile"] != ADMISSION_PROFILE:
        raise ValueError("Unsupported closed-position admission evidence.")
    document = contract.validate_document(accepted["position"])
    terms = document["loan"]
    mapping = dict(workspace_id=loan.workspace_id, borrower_id=loan.borrower_id, series_id=loan.series_id, license_id=loan.license_id)
    original = date.fromisoformat(terms["original_date"]) if terms["original_date"] else None
    if (not loan.is_imported_closed_position or loan.state != "CLOSED" or accepted["mapping"] != mapping
        or loan.product_version_id or loan.policy_snapshot_id or loan.disbursal_snapshot_id or loan.license_revision_id
        or loan.loan_number != terms["number"] or loan.loan_date != original or loan.tenure_months != terms["tenure_months"]
        or loan.principal_amount != (Decimal(terms["original_principal"]) if terms["original_principal"] else None)
        or loan.monthly_interest_rate != (Decimal(terms["monthly_rate"]) if terms["monthly_rate"] is not None else None)
        or opening["item_mapping"] != {} or event.event_kind != "MIGRATION_OPENING"
        or payload.get("event_kind") != "MIGRATION_OPENING" or payload.get("effective_date") != document["position"]["as_of"]
        or event.effective_date.isoformat() != document["position"]["as_of"]
        or payload.get("source_identity") != dict(app="loans", model="PawnLoan", loan_id=loan.pk)
        or payload.get("values") != dict(principal="0", interest="0", fees="0")):
        raise ValueError("Closed position, original details or destination identity differ from accepted evidence.")
    origin = m.HistoricalLoanImport.objects.filter(workspace_id=loan.workspace_id, loan_id=loan.pk).first()
    if origin is None or origin.document != accepted or origin.source_sha256 != digest(accepted):
        raise ValueError("Closed position must retain its immutable financial-origin provenance.")
    source = document["source"]
    if str(origin.source_namespace) != source["namespace"] or origin.source_id != position_source_id(source):
        raise ValueError("Closed-position source identity differs from its provenance.")
    archive = accepted["archive"]
    if origin.archive_evidence_id != (archive["id"] if archive else None):
        raise ValueError("Retained source binding differs from admission.")
    if archive:
        evidence = origin.archive_evidence
        if evidence.document != document["retained_evidence"] or evidence.source_sha256 != archive["sha256"] or digest(evidence.document) != archive["sha256"]:
            raise ValueError("Retained source evidence differs from the accepted position.")
    return opening
