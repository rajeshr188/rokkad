"""Source-bound staging and per-loan approval for the Loans opening command."""
from copy import deepcopy
from decimal import Decimal

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import transaction, IntegrityError

from apps.orgs.models import Company
from apps.tenant_apps.loans.services.history_contract import digest, HistoryError
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from apps.tenant_apps.loans.services.opening_import import (
    PROFILE as OPENING_PROFILE, preview_opening_import, commit_opening_import,
)
from .legacy_dump import inspect_archive
from .legacy_preview import build_preview, propose_collateral_exclusions
from .opening_review import prepare_openings
from .legacy_owner_rules import COLLECTION_PROFILE, LINODE_PROFILE, maturity_tenure
from .models import LoanHistoryBatch

PROFILE = "legacy-opening/1"
SALT = "legacy-opening-approval-v1"


def source_evidence(*, archive_path, review, setup, pg_restore="pg_restore", source_profile=None, payment_review=None):
    """Re-extract a private immutable archive snapshot; never trust edited reports."""
    source = review["source"]
    extracted = inspect_archive(archive_path, schema=source["schema"], pg_restore=pg_restore)
    summary, records = build_preview(extracted, schema=source["schema"], source_namespace=source["namespace"], source_profile=source_profile)
    propose_collateral_exclusions(summary, records)
    candidates = prepare_openings(summary, records, owner_profile=LINODE_PROFILE if source_profile else COLLECTION_PROFILE)
    return _source_evidence(review, setup, summary, records, candidates, payment_review=payment_review)


def _source_evidence(review, setup, summary, records, candidates, *, payment_review=None):
    source = review["source"]
    candidate = next((row for row in candidates if row["source"]["loan_id"] == source["loan_id"]), None)
    if candidate is None or candidate["source"] != source or source["errors"]:
        raise HistoryError("The exact retained source loan, archive and exclusion selection must match; disputed loans stay held.")
    proposed = {item["id"]: item for item in candidate["collateral"]}
    if set(proposed) != {item["id"] for item in review["collateral"]}:
        raise HistoryError("Keep the complete selected source collateral set.")
    fields = ("description", "quantity", "metal", "gross_weight", "net_weight", "purity", "original_principal", "monthly_rate", "weight_reference")
    for item in review["collateral"]:
        if any(item[key] != proposed[item["id"]][key] for key in fields):
            raise HistoryError("Reviewed collateral must preserve the verified source facts and weight interpretation.")
    loan = next(row for row in records if row["source"]["external_id"] == source["loan_id"])
    raw_id = loan["source"]["id"]
    payments = [row for row in records if row["source"]["table"] == "girvi_loanpayment" and row["facts"]["loan_id"] == raw_id]
    if payments and payment_review is None:
        raise HistoryError("Source payment history requires separate reconciliation before this unchanged-principal pilot.")
    if payment_review is not None:
        if (not summary.get("source_profile") or not payments or type(payment_review) is not dict
                or set(payment_review) != {"archive_sha256", "loan_id", "loan_sha256", "payment_hashes", "reason"}
                or payment_review["archive_sha256"] != summary["archive_sha256"]
                or payment_review["loan_id"] != source["loan_id"]
                or payment_review["loan_sha256"] != loan["source_sha256"]
                or payment_review["payment_hashes"] != {p["source"]["external_id"]: p["source_sha256"] for p in payments}
                or not isinstance(payment_review["reason"], str) or not payment_review["reason"].strip()
                or len(payment_review["reason"]) > 255
                or any(ord(c) < 32 or ord(c) == 127 for c in payment_review["reason"])):
            raise HistoryError("Payment exclusion requires a reviewed decision matching this exact versioned source loan and every payment row.")
    owner_profile = LINODE_PROFILE if summary.get("source_profile") else COLLECTION_PROFILE
    tenure, maturity_reference = maturity_tenure(summary, loan["facts"], owner_profile=owner_profile)
    if setup["tenure_months"] != tenure:
        raise HistoryError("Reviewed tenure must preserve recorded terms or the owner's three-month missing-maturity rule.")
    if maturity_reference and maturity_reference not in review["terms"]["evidence_reference"].split("; "):
        raise HistoryError("Missing source maturity requires the explicit owner three-month migration evidence reference.")
    if Decimal(loan["facts"]["loan_amount"]) != Decimal(review["balances"]["principal"]):
        raise HistoryError("This pilot requires unchanged source principal.")
    selected = [loan] + [r for r in records if r["source"]["external_id"] in proposed]
    series = next(r for r in records if r["source"]["table"] == "girvi_series" and r["source"]["id"] == loan["facts"]["series_id"])
    licence = next(r for r in records if r["source"]["table"] == "girvi_license" and r["source"]["id"] == series["facts"]["license_id"])
    customer = next(r for r in records if r["source"]["external_id"] == source["borrower_id"])
    if setup.get("legacy_license_evidence") and setup["source_license_number"] != licence["facts"]["name"]:
        raise HistoryError("The legacy licence reference must retain the exact source label.")
    for item in review["collateral"]:
        valuation = item["valuation"]
        if valuation.get("status") == "UNVERIFIED":
            if valuation["source_date"] is not None:
                raise HistoryError("This dump has no dated item appraisal; retain its unknown source valuation date.")
            if valuation["source_amount"] is not None and (len(proposed) != 1 or
                    Decimal(valuation["source_amount"]) != Decimal(loan["facts"]["value"])):
                raise HistoryError("An old loan-level value can be assigned only to its sole item, unchanged; otherwise retain it in source records.")
    selected.extend((series, licence, customer))
    selected.extend(payments)  # Excluded from opening calculations, never erased from source evidence.
    transformations = [{"rule": "description-line-whitespace/1", "source_id": r["source"]["external_id"],
        "field": "itemdesc", "before": r["facts"]["itemdesc"], "after": proposed[r["source"]["external_id"]]["description"]}
        for r in selected if r["source"]["table"] == "girvi_loanitem"
        and r["facts"]["itemdesc"] != proposed[r["source"]["external_id"]]["description"]]
    return {"adapter": PROFILE, "archive_sha256": summary["archive_sha256"],
        **({"payment_exclusion": {"rule": "owner-reviewed-payment-exclusion/1", **deepcopy(payment_review)}} if payment_review is not None else {}),
        **({"transformations": transformations} if transformations else {}),
        **({"source_profile": summary["source_profile"]} if summary.get("source_profile") else {}),
        "selection_sha256": source["selection_sha256"], "selected_loan_ids": [source["loan_id"]],
        "owner_profile": owner_profile, "records": selected,
        "maturity_review": {"source_tenure": loan["facts"].get("tenure"),
            "tenure_months": tenure, "maturity_date": review["terms"]["maturity_date"],
            "basis": "OWNER_MISSING_MATURITY_RULE" if maturity_reference else "RECORDED_TENURE",
            "evidence_reference": maturity_reference or review["terms"]["evidence_reference"]}}


def get_batch(*, workspace_id, actor, batch_id, lock=False):
    require_history_setup_access(workspace_id, actor)
    query = LoanHistoryBatch.objects.filter(workspace_id=workspace_id, profile=PROFILE)
    if lock:
        query = query.select_for_update()
    try:
        return query.get(public_id=batch_id)
    except (LoanHistoryBatch.DoesNotExist, ValueError, ValidationError) as exc:
        raise PermissionDenied("Opening review is unavailable in this Workspace.") from exc


def _inputs(batch):
    opening = batch.document["opening"]
    if opening["profile"] != OPENING_PROFILE or digest(opening) != batch.source_sha256:
        raise HistoryError("Staged opening evidence changed.")
    return {"review": opening["review"], "setup": opening["setup"]}


def stage(*, workspace_id, actor, archive_path, review, setup, pg_restore="pg_restore", source_profile=None, payment_review=None):
    require_history_setup_access(workspace_id, actor)
    # Domain validation precedes expensive source extraction and retains no loans.
    preview_opening_import(workspace_id=workspace_id, actor=actor, review=review, setup=setup)
    evidence = source_evidence(archive_path=archive_path, review=review, setup=setup, pg_restore=pg_restore,
                               source_profile=source_profile, payment_review=payment_review)
    opening = {"profile": OPENING_PROFILE, "review": deepcopy(review), "setup": deepcopy(setup)}
    with transaction.atomic():
        Company.all_objects.select_for_update().get(pk=workspace_id)
        require_history_setup_access(workspace_id, actor)
        if LoanHistoryBatch.objects.filter(workspace_id=workspace_id, state__in=["STAGED", "READY"]).count() >= 20:
            raise HistoryError("Finish or cancel an unfinished Loans import before staging another (limit 20).")
        return LoanHistoryBatch.objects.create(workspace_id=workspace_id, created_by=actor, profile=PROFILE,
            source_sha256=digest(opening), document={"opening": opening, "source_evidence": evidence})


def stage_many(*, workspace_id, actor, archive_path, openings, pg_restore="pg_restore", source_profile=None, payment_reviews=None):
    """Stage at most 20 reviewed openings against one freshly extracted snapshot.

    Admission still uses each batch's ordinary signed preview and commit. Callers
    supply review/setup pairs, never extracted evidence or a reusable source cache.
    """
    require_history_setup_access(workspace_id, actor)
    if not isinstance(openings, (list, tuple)) or not 1 <= len(openings) <= 20:
        raise HistoryError("Supply between one and 20 reviewed openings.")
    openings = deepcopy(openings)
    for inputs in openings:
        if not isinstance(inputs, dict) or set(inputs) != {"review", "setup"}:
            raise HistoryError("Each opening requires exactly review and setup.")
        preview_opening_import(workspace_id=workspace_id, actor=actor, **inputs)
    sources = [inputs["review"]["source"] for inputs in openings]
    if payment_reviews is None:
        payment_reviews = {}
    if type(payment_reviews) is not dict or not set(payment_reviews) <= {s["loan_id"] for s in sources}:
        raise HistoryError("Payment reviews must identify selected source loans only.")
    first = sources[0]
    if any((s["schema"], s["namespace"]) != (first["schema"], first["namespace"]) for s in sources):
        raise HistoryError("A staging batch must use one source schema and namespace.")
    if len({s["loan_id"] for s in sources}) != len(sources):
        raise HistoryError("Select each source loan only once per staging batch.")
    extracted = inspect_archive(archive_path, schema=first["schema"], pg_restore=pg_restore)
    summary, records = build_preview(extracted, schema=first["schema"], source_namespace=first["namespace"], source_profile=source_profile)
    propose_collateral_exclusions(summary, records)
    candidates = prepare_openings(summary, records, owner_profile=LINODE_PROFILE if source_profile else COLLECTION_PROFILE)
    documents = []
    for inputs in openings:
        evidence = _source_evidence(inputs["review"], inputs["setup"], summary, records, candidates,
                                   payment_review=payment_reviews.get(inputs["review"]["source"]["loan_id"]))
        documents.append({"opening": {"profile": OPENING_PROFILE, **inputs}, "source_evidence": evidence})
    with transaction.atomic():
        Company.all_objects.select_for_update().get(pk=workspace_id)
        require_history_setup_access(workspace_id, actor)
        unfinished = LoanHistoryBatch.objects.filter(workspace_id=workspace_id, state__in=["STAGED", "READY"]).count()
        if unfinished + len(documents) > 20:
            raise HistoryError("Finish or cancel unfinished Loans imports before staging more (limit 20).")
        return [LoanHistoryBatch.objects.create(workspace_id=workspace_id, created_by=actor, profile=PROFILE,
                    source_sha256=digest(doc["opening"]), document=doc) for doc in documents]


def _approval_digest(batch):
    return digest({"document": batch.document, "source": batch.source_sha256, "preview": batch.preview})


@transaction.atomic
def preview(*, workspace_id, actor, batch_id):
    Company.all_objects.select_for_update().get(pk=require_history_setup_access(workspace_id, actor).pk)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state not in {"STAGED", "READY"}:
        raise HistoryError("Only unfinished opening imports can be previewed.")
    result = preview_opening_import(workspace_id=workspace_id, actor=actor, **_inputs(batch))
    batch.preview, batch.state = result["summary"], "READY"
    batch.approval_digest = _approval_digest(batch)
    batch.save(update_fields=["preview", "state", "approval_digest"])
    return signing.dumps({"workspace": workspace_id, "actor": actor.pk, "batch": str(batch.public_id),
                          "digest": batch.approval_digest}, salt=SALT)


@transaction.atomic
def commit(*, workspace_id, actor, batch_id, approval, confirmed=False):
    require_history_setup_access(workspace_id, actor)
    if confirmed is not True:
        raise HistoryError("Confirm the selected source loan, balances, original terms and destination mappings.")
    try:
        token = signing.loads(approval, salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise HistoryError("Opening approval is invalid or expired; preview again.") from exc
    if token.get("workspace") != workspace_id or token.get("actor") != actor.pk or token.get("batch") != str(batch_id):
        raise PermissionDenied("Approval belongs to another operator, Workspace or opening.")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state not in {"READY", "COMPLETED"} or token.get("digest") != batch.approval_digest or _approval_digest(batch) != batch.approval_digest:
        raise HistoryError("Opening review changed or is not ready; generate a fresh preview.")
    inputs = _inputs(batch)
    if batch.state == "COMPLETED":
        return batch.result
    try:
        result, summary = commit_opening_import(workspace_id=workspace_id, actor=actor, **inputs,
            expected_sha256=batch.source_sha256, confirmed=True)
    except (ValueError, ValidationError, IntegrityError, ObjectDoesNotExist) as exc:
        raise HistoryError(str(exc)) from exc
    if summary != batch.preview:
        raise HistoryError("Destination changed after approval; no opening was imported.")
    batch.result, batch.state = result, "COMPLETED"
    batch.save(update_fields=["result", "state"])
    return result


@transaction.atomic
def cancel(*, workspace_id, actor, batch_id, confirmed=False):
    Company.all_objects.select_for_update().get(pk=require_history_setup_access(workspace_id, actor).pk)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if confirmed is not True or batch.state == "COMPLETED":
        raise HistoryError("Confirm cancellation of an unfinished opening; completed imports cannot be erased.")
    if batch.state == "CANCELLED":
        return
    batch.state, batch.document, batch.mapping, batch.preview, batch.approval_digest = "CANCELLED", {}, {}, {}, ""
    batch.save(update_fields=["state", "document", "mapping", "preview", "approval_digest"])
