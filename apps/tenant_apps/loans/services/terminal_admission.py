"""Verified closed position, without reconstructing unavailable transactions."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from dateutil.relativedelta import relativedelta
from django.core import signing
from django.db import connection, transaction
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from .history_contract import digest
from .history_setup import require_history_setup_access
from .recorded_history import _amount, _text, _intent, _make_contract
from .recorded_items import validate_items, effective_rate
from .import_identity import source_binding_id, find_source_origin

PROFILE = "loan-terminal-admission/1"
ARCHIVE_PROFILE = "archive-terminal-admission/1"
EVIDENCE_PROFILE = "loan-terminal-evidence/1"
REVIEW_PROFILE = "loan-terminal-review/1"
SALT = "loans.terminal-admission.review.v1"


def validate_input(data):
    required = {"borrower_id", "series_id", "product_version_id", "number", "date", "tenure", "currency_quantum",
        "source_reference", "monitoring_method", "monitoring_ltv", "monitoring_reason", "collateral", "closed_on",
        "closure_reference", "custody", "confirmed_agreement", "confirmed_closed"}
    if type(data) is not dict or set(data) not in (required, required | {"license_revision_id"}):
        raise ValueError("Supply the verified agreement and closed position; complete receipt history is not claimed.")
    value = deepcopy(data)
    for key in ("borrower_id", "series_id", "product_version_id", "tenure"):
        if type(value[key]) is not int or value[key] <= 0:
            raise ValueError("Select valid agreement references and original tenure.")
    if value["tenure"] > 600:
        raise ValueError("Original tenure exceeds the supported contract.")
    if "license_revision_id" in value and (type(value["license_revision_id"]) is not int or value["license_revision_id"] <= 0):
        raise ValueError("Select existing source licence evidence or leave it unknown.")
    for key, maximum in (("number", 64), ("source_reference", 160), ("closure_reference", 1000), ("monitoring_reason", 255)):
        value[key] = _text(value[key], key.replace("_", " "), maximum)
    original, closed = date.fromisoformat(value["date"]), date.fromisoformat(value["closed_on"])
    if not original <= closed <= timezone.localdate():
        raise ValueError("Verified closure must be on or after the original date and no later than today.")
    if value["currency_quantum"] not in ("0.01", "1") or value["custody"] not in ("RETURNED", "UNKNOWN"):
        raise ValueError("Confirm actual interest rounding and known or unknown handover.")
    if value["confirmed_agreement"] is not True or value["confirmed_closed"] is not True:
        raise ValueError("Confirm the supported original agreement and verified zero principal, interest and fees at closure.")
    if value["monitoring_method"] not in ("CALCULATED_METAL_VALUE", "LATEST_APPRAISAL", "LOWER_OF_CALCULATED_AND_APPRAISAL"):
        raise ValueError("Select a supported monitoring method.")
    value["monitoring_ltv"] = _amount(value["monitoring_ltv"], "monitoring LTV", places=6, positive=True)
    if Decimal(value["monitoring_ltv"]) > 1:
        raise ValueError("Monitoring LTV cannot exceed 100%.")
    value["collateral"] = validate_items(value["collateral"], _amount, _text)
    return value


def _contract_data(data):
    principal = sum((Decimal(i["principal"]) for i in data["collateral"]), Decimal(0))
    return {**data, **{k: data["collateral"][0][k] for k in ("description", "metal", "quantity", "gross_weight", "net_weight", "purity")},
        "principal": str(principal), "rate": str(effective_rate(data["collateral"])),
        "complete_through": data["closed_on"], "confirmed_history": False, "advance_months": 0,
        "events": [{"kind": "CLOSE", "date": data["closed_on"]}]}


def _prepare(workspace, actor, data, intent_token, evidence_id=None):
    require_history_setup_access(workspace.pk, actor)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    for action in ("data.create", "loan.release"):
        access.require(action)
    data = validate_input(data)
    key = _intent(intent_token, workspace, actor)
    Company.all_objects.select_for_update().get(pk=workspace.pk)
    archive = None
    if evidence_id:
        from .archive import get_evidence
        from .archive_admission import source_snapshots, _claims
        evidence = get_evidence(workspace_id=workspace.pk, actor=actor, evidence_id=evidence_id)
        snapshots = source_snapshots(evidence)
        for source in snapshots:
            _claims(source, _contract_data(data), complete_receipts=False)
        archive = dict(id=evidence.pk, public_id=str(evidence.public_id), sha256=evidence.source_sha256,
            namespace=str(evidence.source_namespace), system=evidence.source_system, source_id=evidence.source_id,
            snapshots=[[row.pk, row.source_sha256] for row in snapshots], snapshot_ids=[row.pk for row in snapshots])
        namespace = evidence.source_namespace
        source_id = source_binding_id(namespace, evidence.source_id, evidence.source_system)
    else:
        namespace = uuid5(NAMESPACE_URL, f"rokkad:workspace:{workspace.pk}:terminal")
        source_id = f"paper:{key}"
    document = dict(profile=ARCHIVE_PROFILE if archive else PROFILE, data=data, archive=archive)
    return data, key, namespace, source_id, document


def _write(workspace, actor, data, key, namespace, source_id, document):
    checksum = digest(document)
    existing = m.HistoricalLoanImport.objects.filter(workspace=workspace, source_namespace=namespace, source_id=source_id).first()
    if existing:
        if existing.source_sha256 != checksum or existing.document != document:
            raise ValueError("This source already has a different accepted position. Open its existing loan.")
        return existing.loan, deepcopy(existing.references["summary"]), False
    archive = document["archive"]
    if archive:
        existing = find_source_origin(workspace_id=workspace.pk, namespace=namespace,
            source_id=archive["source_id"], borrower_source_system=archive["system"])
        if existing:
            raise ValueError("This source already has an ordinary loan. Reconcile its accepted financial origin.")
    values = _contract_data(data)
    loan, _, policy, _, _, _ = _make_contract(workspace, actor, values, key, number=data["number"],
        day=date.fromisoformat(data["date"]), principal=Decimal(values["principal"]), rate=Decimal(values["rate"]),
        tenure=data["tenure"], advance=Decimal(0), custody_state="WITH_CUSTOMER" if data["custody"] == "RETURNED" else "PAPER_CLOSED",
        archive_ids=archive["snapshot_ids"] if archive else (), terminal=True)
    loan.state = "CLOSED"
    loan.policy_snapshot = policy
    loan.save(update_fields=["state", "policy_snapshot", "updated_by", "updated_at"])
    items = list(loan.collateral_items.order_by("pk"))
    mapping = {str(index): item.pk for index, item in enumerate(items, 1)}
    review = dict(profile=REVIEW_PROFILE, data=data, archive=archive, admission_sha256=checksum,
        mapping={name: getattr(loan, field) for name, field in (("workspace_id", "workspace_id"), ("borrower_id", "borrower_id"),
            ("licence_revision_id", "license_revision_id"), ("series_id", "series_id"), ("product_version_id", "product_version_id"))},
        terms=dict(original_date=data["date"], maturity_date=(loan.loan_date + relativedelta(months=loan.tenure_months)).isoformat()),
        cutover=dict(date=data["closed_on"]), balances=dict(principal="0", interest="0", fees="0"),
        source=dict(item_ids=list(mapping)), collateral=[dict(id=str(index), remaining_principal="0", monthly_rate=str(item.monthly_interest_rate))
            for index, item in enumerate(items, 1)])
    payload = dict(contract_version=1, event_kind="MIGRATION_OPENING", effective_date=data["closed_on"], currency="INR",
        source_identity=dict(app="loans", model="PawnLoan", loan_id=loan.pk), values=review["balances"],
        opening=dict(profile=EVIDENCE_PROFILE, review=review, item_mapping=mapping))
    from .event_recording import _persist_locked_event
    event, _ = _persist_locked_event(loan, kind="MIGRATION_OPENING", effective_date=date.fromisoformat(data["closed_on"]), payload=payload, actor=actor)
    from .opening_evidence import read_opening_evidence
    read_opening_evidence(loan, event)
    summary = dict(state="CLOSED", loan_number=loan.loan_number, closed_on=data["closed_on"], collateral=len(items),
        financial_history_from=data["closed_on"], balance=review["balances"], earlier_receipts="UNAVAILABLE", custody=data["custody"])
    m.HistoricalLoanImport.objects.create(workspace=workspace, loan=loan, source_namespace=namespace, source_id=source_id,
        source_sha256=checksum, document=document, archive_evidence_id=archive["id"] if archive else None,
        references=dict(summary=summary, events=dict(opening=event.pk), items=mapping), imported_by=actor)
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor, content_object=loan,
        description="Admitted verified closed position without reconstructing unavailable receipts or payout.",
        data=dict(profile=document["profile"], sha256=checksum, loan=loan.pk))
    connection.check_constraints()
    return loan, summary, True


@transaction.atomic
def preview_terminal_admission(*, workspace, actor, data, intent_token, evidence_id=None):
    values = _prepare(workspace, actor, data, intent_token, evidence_id)
    with transaction.atomic():
        _, summary, _ = _write(workspace, actor, *values)
        transaction.set_rollback(True)
    return summary, signing.dumps(dict(workspace=workspace.pk, actor=actor.pk, key=str(values[1]),
        sha256=digest(values[-1]), date=timezone.localdate().isoformat(), summary=summary), salt=SALT, compress=True)


@transaction.atomic
def admit_terminal_position(*, workspace, actor, data, intent_token, review_token, confirmed=False, evidence_id=None):
    values = _prepare(workspace, actor, data, intent_token, evidence_id)
    if confirmed is not True:
        raise ValueError("Confirm the reviewed terminal position before admission.")
    existing = m.HistoricalLoanImport.objects.filter(workspace=workspace, source_namespace=values[2], source_id=values[3]).first()
    if existing:
        if existing.document != values[-1] or existing.source_sha256 != digest(values[-1]):
            raise ValueError("This source already has different accepted position facts.")
        return existing.loan, False
    try:
        approved = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except (signing.BadSignature, TypeError, ValueError):
        raise ValueError("Preview this closed position again; the review is missing or expired.") from None
    expected = dict(workspace=workspace.pk, actor=actor.pk, key=str(values[1]), sha256=digest(values[-1]), date=timezone.localdate().isoformat())
    if any(approved.get(k) != v for k, v in expected.items()):
        raise ValueError("Agreement, closure, source or operator changed. Preview again.")
    loan, summary, created = _write(workspace, actor, *values)
    if approved.get("summary") != summary:
        raise ValueError("The resulting closed position changed. Preview again.")
    return loan, created


def read_terminal_review(loan, opening):
    review = opening["review"]
    fields = {"profile", "data", "archive", "admission_sha256", "mapping", "terms", "cutover", "balances", "source", "collateral"}
    if type(review) is not dict or set(review) != fields or review["profile"] != REVIEW_PROFILE or loan.state != "CLOSED":
        raise ValueError("Terminal admission requires a verified closed loan and supported evidence.")
    data = validate_input(review["data"])
    for key, attr in (("borrower_id", "borrower_id"), ("series_id", "series_id"),
            ("product_version_id", "product_version_id"), ("license_revision_id", "license_revision_id")):
        if data.get(key) != getattr(loan, attr, None):
            raise ValueError("Terminal agreement destination references do not match its loan.")
    policy = loan.policy_snapshot
    if policy is None or policy.currency_quantum.normalize() != Decimal(data["currency_quantum"]) or loan.monthly_interest_rate != effective_rate(data["collateral"]):
        raise ValueError("Terminal agreement terms differ from its frozen policy.")
    if (data != review["data"] or data["number"] != loan.loan_number or Decimal(_contract_data(data)["principal"]) != loan.principal_amount
            or date.fromisoformat(data["date"]) != loan.loan_date or data["tenure"] != loan.tenure_months
            or review["cutover"] != {"date": data["closed_on"]} or review["balances"] != dict(principal="0", interest="0", fees="0")
            or review["terms"] != dict(original_date=data["date"], maturity_date=(loan.loan_date + relativedelta(months=loan.tenure_months)).isoformat())):
        raise ValueError("Terminal agreement or zero closing position does not match its loan.")
    document = dict(profile=ARCHIVE_PROFILE if review["archive"] else PROFILE, data=data, archive=review["archive"])
    if digest(document) != review["admission_sha256"]:
        raise ValueError("Terminal position fingerprint does not reconcile.")
    expected = [dict(id=str(index), remaining_principal="0", monthly_rate=str(Decimal(item["rate"]))) for index, item in enumerate(data["collateral"], 1)]
    if review["collateral"] != expected or review["source"] != dict(item_ids=[i["id"] for i in expected]):
        raise ValueError("Terminal item positions must be zero without invented allocations.")
    return review
