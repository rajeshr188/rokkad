"""Reconcile retained archive claims through the ordinary recorded-history writer."""
from decimal import Decimal
from uuid import uuid5

from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from .archive import get_evidence
from .history_contract import digest
from .history_setup import require_history_setup_access
from .import_identity import source_binding_id, find_source_origin
from .recorded_numbers import identity
from .recorded_history import validate_input, _authorize, _intent, _admit, _text, _digest

PROFILE = "archive-admission/1"
SALT = "loans.archive-admission.review.v1"


def archive_origin(evidence):
    return find_source_origin(workspace_id=evidence.workspace_id, namespace=evidence.source_namespace,
        source_id=evidence.source_id, borrower_source_system=evidence.source_system)


def source_snapshots(evidence):
    binding = source_binding_id(evidence.source_namespace, evidence.source_id, evidence.source_system)
    rows = []
    for row in m.HistoricalLoanEvidence.objects.filter(workspace_id=evidence.workspace_id,
            source_namespace=evidence.source_namespace,
            source_id__in={evidence.source_id, binding, binding.partition(":")[2]}).order_by("pk"):
        try:
            candidate = source_binding_id(row.source_namespace, row.source_id, row.source_system)
        except ValueError:
            continue
        if candidate == binding:
            rows.append(row)
    return rows


def _claims(evidence, data):
    if digest(evidence.document) != evidence.source_sha256:
        raise ValueError("The retained archive fingerprint does not match. Reconcile its evidence first.")
    facts = evidence.document["facts"]
    closure = data["events"][-1]
    for field, actual in (("loan_number", data["number"]), ("opened_on", data["date"]), ("closed_on", closure["date"])):
        if facts[field] is not None and identity(facts[field]) != identity(actual):
            raise ValueError(f"Archive {evidence.pk}: {field.replace('_', ' ')} differs from the entered history.")
    if facts["original_principal"] is not None and Decimal(facts["original_principal"]) != Decimal(data["principal"]):
        raise ValueError("The entered original principal conflicts with retained archive evidence.")
    if facts["reported_balance"] is not None and Decimal(facts["reported_balance"]):
        raise ValueError("The archive reports a nonzero closing balance; resolve that conflict before admission.")
    collateral = facts["collateral"]
    if collateral is not None:
        if len(collateral) != 1:
            raise ValueError("Archive admission currently requires one collateral group.")
        item = collateral[0]
        for field in ("quantity", "gross_weight", "net_weight"):
            if item[field] is not None and Decimal(str(item[field])) != Decimal(str(data[field])):
                raise ValueError(f"Entered collateral {field.replace('_', ' ')} conflicts with the archive.")
        if identity(item["description"]) != identity(data["description"]):
            raise ValueError("The collateral description must identify the retained archive item.")
    payments = facts["payments"]
    if payments is not None:
        ids = [identity(p["id"]) for p in payments]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate archived payment identities require reconciliation.")
        entered = {identity(row["reference"]): row for row in data["events"]}
        for payment in payments:
            row = entered.get(identity(payment["id"]))
            if row is None:
                raise ValueError(f"Include archived receipt {payment['id']} using its source ID as the transaction reference.")
            if ((payment["date"] is not None and payment["date"] != row["date"]) or
                    (payment["amount"] is not None and Decimal(payment["amount"]) != Decimal(row["amount"]))):
                raise ValueError(f"Archived receipt {payment['id']} date or total differs from the entered transaction.")
    reference = facts["borrower_reference"]
    if reference:
        from apps.tenant_apps.data_portability.children import parent_for
        refs = [reference["id"]]
        prefix = f"legacy:{evidence.source_namespace.hex}:"
        if reference["system"].startswith(prefix):
            schema = reference["system"][len(prefix):]
            refs.append(str(uuid5(uuid5(evidence.source_namespace, schema), reference["id"])))
        for external in refs:
            parent = parent_for(dict(party_source_system=reference["system"], party_external_id=external), evidence.workspace_id)
            if parent is not None and parent.party_id != data["borrower_id"]:
                raise ValueError("The selected borrower differs from the retained source Party mapping.")


def _prepare(workspace, actor, evidence_id, data, intent_token, reconciliation):
    require_history_setup_access(workspace.pk, actor)
    data = validate_input(data)
    _authorize(workspace, actor, data)
    key = _intent(intent_token, workspace, actor)
    reconciliation = _text(reconciliation, "the checked sources supporting original terms, financial history and known custody", 1000)
    if data["final_state"] != "CLOSED" or any(row["kind"] == "RENEW" for row in data["events"]):
        raise ValueError("This archive review admits one fully closed loan; renewal chains need linked source reconciliation.")
    Company.all_objects.select_for_update().get(pk=workspace.pk)
    evidence = get_evidence(workspace_id=workspace.pk, actor=actor, evidence_id=evidence_id)
    snapshots = source_snapshots(evidence)
    for row in snapshots:
        _claims(row, data)
    archive = dict(id=evidence.pk, public_id=str(evidence.public_id), sha256=evidence.source_sha256,
        snapshot_ids=[row.pk for row in snapshots], snapshots=[[row.pk, row.source_sha256] for row in snapshots],
        namespace=str(evidence.source_namespace), system=evidence.source_system, source_id=evidence.source_id,
        reconciliation=reconciliation)
    document = dict(profile=PROFILE, archive=archive, history=data)
    return data, key, evidence, archive, document


@transaction.atomic
def preview_archive_admission(*, workspace, actor, evidence_id, data, intent_token, reconciliation):
    data, key, evidence, archive, document = _prepare(workspace, actor, evidence_id, data, intent_token, reconciliation)
    if archive_origin(evidence):
        raise ValueError("This source already has an ordinary loan. Open the linked financial history.")
    with transaction.atomic():
        _, review = _admit(workspace, actor, data, key, archive=archive)
        transaction.set_rollback(True)
    review["archive"] = archive
    token = signing.dumps(dict(workspace=workspace.pk, actor=actor.pk, key=str(key), data=_digest(document),
        date=timezone.localdate().isoformat(), review=review), salt=SALT, compress=True)
    return review, token


@transaction.atomic
def admit_archive_history(*, workspace, actor, evidence_id, data, intent_token, reconciliation, review_token, confirmed=False):
    data, key, evidence, archive, document = _prepare(workspace, actor, evidence_id, data, intent_token, reconciliation)
    if confirmed is not True:
        raise ValueError("Confirm the reconciled archive history before admission.")
    existing = archive_origin(evidence)
    if existing:
        if existing.archive_evidence_id == evidence.pk and existing.source_sha256 == _digest(document):
            return existing.loan, False
        raise ValueError("This source already has different accepted history. Open its existing loan.")
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValueError("Preview the archive admission again; review is missing or expired.") from None
    expected = dict(workspace=workspace.pk, actor=actor.pk, key=str(key), data=_digest(document), date=timezone.localdate().isoformat())
    if any(signed.get(k) != v for k, v in expected.items()):
        raise ValueError("Source snapshots, entered facts or recording context changed. Preview again.")
    loan, review = _admit(workspace, actor, data, key, archive=archive)
    review["archive"] = archive
    if signed.get("review") != review:
        raise ValueError("Numbering or calculated results changed. Preview again.")
    m.HistoricalLoanImport.objects.create(workspace=workspace, loan=loan, archive_evidence=evidence,
        source_namespace=evidence.source_namespace,
        source_id=source_binding_id(evidence.source_namespace, evidence.source_id, evidence.source_system),
        source_sha256=_digest(document), document=document, references=dict(summary=review), imported_by=actor)
    return loan, True
