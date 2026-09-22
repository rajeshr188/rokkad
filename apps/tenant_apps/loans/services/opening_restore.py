"""Bounded, owner-confirmed restoration of opening and supported servicing evidence.

Rebuild through the Loans writers, reconcile every financial/supporting row, then
commit. Source database keys and actor identities never become destination keys.
"""
import hashlib
import json
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans import models as m
from .event_recording import _fingerprint
from .history_contract import HistoryError, MAX_BYTES, _pairs, digest, dump
from .history_setup import _number, require_history_setup_access
from .import_identity import source_binding_id, find_source_origin
from .opening_evidence import read_opening_evidence
from .opening_continuation import preview_opening_collection
from .opening_import import _document, _write
from .opening_export import _export_opening
from .opening_contract import (
    FIELDS, FIELDS_V2, PAYMENT_PROFILE, MAX_RECORDS, PROFILE as EXPORT_PROFILE, MANIFEST_FIELDS, EXTRA_FIELDS, decode_row,
)

PROFILE = "loan-opening-restore/1"
MAPPING = {"borrower_id", "revision_id", "series_id", "product_version_id"}


def _require(condition, message):
    if not condition:
        raise HistoryError(message)




def parse_opening_export(content):
    """Parse and validate a source-local export without trusting its checksum alone."""
    try:
        _require(type(content) is bytes and 0 < len(content) <= MAX_BYTES, "Use an opening export of at most 5 MiB.")
        lines = content.decode("utf-8-sig").splitlines()
        _require(len(lines) == 2, "Use exactly two JSONL records: manifest and opening evidence.")
        def invalid_number(value):
            raise HistoryError("Non-finite JSON is not supported.")
        manifest, evidence = [json.loads(line, object_pairs_hook=_pairs, parse_constant=invalid_number) for line in lines]
        _require(type(manifest) is dict and set(manifest) == MANIFEST_FIELDS, "Unexpected opening manifest fields.")
        _require(manifest["profile"] in {EXPORT_PROFILE, PAYMENT_PROFILE} and manifest["coverage"] == "OPENING_AND_SUPPORTED_SERVICING" and
            manifest["history_before_cutover"] == "UNAVAILABLE" and type(manifest["restore_supported"]) is bool,
            "Use the supported opening evidence profile.")
        _require(manifest["exclusions"] == ["pre_cutover_transactions", "binary_files", "workspace_configuration", "party_master"],
            "Opening export coverage must be explicit.")
        fields = FIELDS_V2 if manifest["profile"] == PAYMENT_PROFILE else FIELDS
        _require(type(evidence) is dict and set(evidence) == set(fields) | EXTRA_FIELDS, "Unexpected opening evidence sections.")
        _require(manifest["sha256"] == digest(evidence), "Opening export checksum does not match.")
        count = 0
        objects = {}
        for kind in fields:
            rows = [evidence[kind]] if kind in {"loan", "origin", "policy"} else evidence[kind]
            _require(type(rows) is list and len(rows) <= MAX_RECORDS, "Opening evidence exceeds record bounds.")
            count += len(rows)
            objects[kind] = [decode_row(kind, row, profile=manifest["profile"]) for row in rows]
            ids = [row.id for row in objects[kind]]
            _require(len(ids) == len(set(ids)), "Duplicate source identity in " + kind)
            if kind != "events":
                _require(ids == sorted(ids), "Source evidence must preserve record order.")
        _require(count <= MAX_RECORDS and 1 <= len(objects["items"]) <= 20 and 1 <= len(objects["events"]) <= 240,
            "Opening export exceeds item, event or record bounds.")
        _require(type(evidence["source_verifications"]) is list and len(evidence["source_verifications"]) <= 20 and
            count + len(evidence["source_verifications"]) <= MAX_RECORDS,
            "Too many source verifications.")
        loan, origin = objects["loan"][0], objects["origin"][0]
        _require(manifest["reference_scope"] == {"workspace_id": loan.workspace_id, "ids": "SOURCE_DATABASE_LOCAL"},
            "Source Workspace scope does not match.")
        doc = origin.document
        _require(doc == _document(doc["review"], doc["setup"]) and origin.source_sha256 == digest(doc), "Accepted opening provenance is invalid.")
        review = doc["review"]
        _require(str(origin.source_namespace) == review["source"]["namespace"] and origin.source_id == source_binding_id(
            origin.source_namespace, review["source"]["loan_id"], review["mapping"]["borrower_source_system"]), "Opening source identity does not match.")
        events = objects["events"]
        _require((manifest["profile"] == PAYMENT_PROFILE) == any(e.event_kind == "REPAYMENT" for e in events),
                 "Opening payment history requires the version 2 row contract.")
        _require(events == sorted(events, key=lambda row: (row.effective_date, row.pk)), "Opening events are not chronological.")
        opening = read_opening_evidence(loan, events[0])
        _require(events[0].event_kind == "MIGRATION_OPENING" and opening["review"] == review and
            origin.references["mapping"] == review["mapping"] and
            origin.references["items"] == opening["item_mapping"] and
            origin.references["events"]["opening"] == events[0].pk and
            set(opening["item_mapping"].values()) == {row.pk for row in objects["items"]}, "Opening graph identity does not match.")
        schedules = objects["schedules"]
        schedule_hash = hashlib.sha256(json.dumps({"contract": "loan-opening-obligations/1", "opening": opening},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        _require(len(schedules) == 1 and schedules[0].pk == origin.references["schedule_id"] and
            schedules[0].source_event_id == events[0].pk and schedules[0].fingerprint == schedule_hash,
            "Reviewed opening schedule binding or fingerprint does not match.")
        as_of = date.fromisoformat(manifest["as_of"])
        _require(manifest["financial_history_from"] == review["cutover"]["date"] and events[-1].effective_date <= as_of <= timezone.localdate(),
            "Opening export dates are inconsistent or in the future.")
        for event in events:
            _require(event.payload_fingerprint == _fingerprint(event.payload) and
                event.idempotency_key == f"loans:{loan.pk}:{event.event_kind}:{event.payload_fingerprint}", "Event fingerprint does not match its evidence.")
        preview_opening_collection(loan, events=events, as_of_date=as_of)
        # Resolve every internal reference before creating any destination records.
        semantic_evidence(evidence)
        return {"manifest": manifest, "evidence": evidence}
    except (KeyError, TypeError, ValueError, AttributeError, ValidationError, RecursionError) as exc:
        if isinstance(exc, HistoryError):
            raise
        raise HistoryError("Invalid bounded opening export: " + str(exc)) from exc


# Metadata remains in the immutable source snapshot. Local audit actors/times and
# fingerprints are newly recorded, and must not be impersonated or copied as FKs.
LOCAL_METADATA = {"id", "public_id", "created_at", "updated_at", "created_by_id", "updated_by_id",
    "finalized_by_id", "finalized_at", "actor_id", "payload_fingerprint", "idempotency_key", "fingerprint"}
REFERENCES = {"loan_id": "loan", "collateral_item_id": "items", "opening_event_id": "events",
    "original_event_id": "events", "source_event_id": "events", "loan_event_id": "events", "reversal_event_id": "events",
    "catch_up_reversal_event_id": "events", "release_id": "releases", "release_reversal_id": "release_reversals",
    "catch_up_accrual_id": "accruals", "accrual_id": "accruals", "schedule_version_id": "schedules", "obligation_id": "obligations"}


def semantic_evidence(evidence):
    """Financial/physical graph comparison with explicit reference normalization."""
    maps = {kind: {row["id"]: f"{kind}:{index}" for index, row in enumerate(value)}
        for kind, value in evidence.items() if kind in FIELDS_V2 and isinstance(value, list)}
    maps["loan"] = {evidence["loan"]["id"]: "loan"}
    source_items = evidence["origin"]["references"]["items"]
    maps["items"] = {pk: "item:" + key for key, pk in source_items.items()}
    event_keys = {row["idempotency_key"]: maps["events"][row["id"]] for row in evidence["events"]}
    numbers = {row["release_number"]: maps["releases"][row["id"]] for row in evidence["releases"]}
    external = {key: evidence["loan"][key] for key in (
        "workspace_id", "borrower_id", "license_id", "license_revision_id", "series_id", "product_version_id")}
    external.update(party_id=external["borrower_id"], licence_revision_id=external["license_revision_id"])

    def ref(kind, value):
        if value is None:
            return None
        _require(type(value) is int and value in maps[kind], "Unresolved source graph reference: " + kind)
        return maps[kind][value]

    def walk(value, kind):
        if isinstance(value, list):
            return [walk(item, kind) for item in value]
        if not isinstance(value, dict):
            return value
        out = {}
        for key, item in value.items():
            if key == "valuation_context":
                # A frozen reference quote is not a destination Rates row. The
                # restoring Workspace annotation does not change its economics.
                _require(type(item) is dict, "Appraisal reference context must be an object.")
                if "source_workspace_id" in item:
                    _require(type(item["source_workspace_id"]) is int and item["source_workspace_id"] > 0,
                        "Frozen appraisal quote scope must identify its source Workspace.")
                out[key] = {name: val for name, val in item.items() if name != "source_workspace_id"}
            elif key == "source":
                # The original legacy identity inside the review is source text,
                # not the exporting Workspace's foreign-key namespace.
                out[key] = deepcopy(item)
            elif key in REFERENCES:
                out[key] = ref(REFERENCES[key], item)
            elif key in {"reversal_of_id", "supersedes_id"}:
                out[key] = ref(kind, item)
            elif key in external:
                _require(item == external[key], "Source external reference differs from loan: " + key)
                out[key] = key
            elif key == "item_mapping":
                out[key] = {source: ref("items", pk) for source, pk in item.items()}
            elif key == "original_idempotency_key":
                _require(item in event_keys, "Reversal idempotency reference is missing.")
                out[key] = event_keys[item]
            elif key == "loan_number":
                _require(item == evidence["loan"]["loan_number"], "Loan number evidence is inconsistent.")
                out[key] = "loan-number"
            elif key == "release_number":
                _require(item in numbers, "Release number evidence is inconsistent.")
                out[key] = numbers[item]
            else:
                out[key] = walk(item, kind)
        return out

    result = {}
    for kind in (FIELDS_V2 if "repayment_lines" in evidence else FIELDS):
        if kind == "origin":
            continue
        rows = evidence[kind] if isinstance(evidence[kind], list) else [evidence[kind]]
        normalized = [walk({key: value for key, value in row.items() if key not in LOCAL_METADATA}, kind) for row in rows]
        result[kind] = sorted(normalized, key=dump)
    result["recorded_balance"] = evidence["recorded_balance"]
    result["interest_conceded"] = evidence["interest_conceded"]
    result["collection_preview"] = walk(evidence["collection_preview"], "events")
    return result


def _restore_servicing(loan, *, actor, evidence, item_mapping):
    """Called inside the opening writer's transaction, before immutable provenance."""
    from .pawn_release import _release_pawn_loan_in_full_at
    from .pawn_reversal import _reverse_pawn_loan_event_at
    from .pawn_repayment import _record_pawn_loan_repayment_at
    items = {pk: item_mapping[source] for source, pk in evidence["origin"]["references"]["items"].items()}
    source_review = evidence["origin"]["document"]["review"]
    has_opening_appraisal = {item_mapping[row["id"]] for row in source_review["collateral"]
                            if row["valuation"].get("status") != "UNVERIFIED"}
    # Unknown opening values create no appraisal. A later first assessment must
    # be restored too, rather than mistaken for an already-created version 1.
    for row in evidence["appraisals"]:
        if row["version"] == 1 and items[row["collateral_item_id"]] in has_opening_appraisal:
            continue
        _require(row["supersedes_id"] is None or any(old["id"] == row["supersedes_id"] and
            old["collateral_item_id"] == row["collateral_item_id"] and old["version"] < row["version"] for old in evidence["appraisals"]),
            "Appraisal replacement evidence is inconsistent.")
        supersedes = None
        if row["supersedes_id"] is not None:
            old = next(old for old in evidence["appraisals"] if old["id"] == row["supersedes_id"])
            supersedes = m.CollateralAppraisal.objects.get(collateral_item_id=items[old["collateral_item_id"]], version=old["version"])
        values = {key: row[key] for key in ("version", "appraised_value", "status", "method", "evidence_reference", "review_notes", "valuation_context")}
        values["valuation_context"] = deepcopy(values["valuation_context"])
        if values["valuation_context"].get("rate_id") is not None:
            values["valuation_context"].setdefault("source_workspace_id", evidence["loan"]["workspace_id"])
        value = m.CollateralAppraisal(workspace_id=loan.workspace_id, collateral_item_id=items[row["collateral_item_id"]],
            effective_at=datetime.fromisoformat(row["effective_at"]), supersedes=supersedes, created_by=actor, **values)
        value.full_clean()
        value.save()
    event_map = {}
    releases = {row["loan_event_id"]: row for row in evidence["releases"]}
    source = evidence["origin"]["document"]["review"]["source"]
    for event in evidence["events"]:
        if event["event_kind"] == "REPAYMENT":
            detail = event["payload"]["repayment"]
            result = _record_pawn_loan_repayment_at(loan.pk, actor=actor, effective_date=date.fromisoformat(event["effective_date"]),
                amount=detail["amount_received"], request_key=detail["request_key"])
            event_map[event["id"]] = result.loan_event.pk
        elif event["event_kind"] == "RELEASE_RECEIPT":
            row = releases[event["id"]]
            returns = {item["returned_at"] for item in evidence["release_items"] if item["release_id"] == row["id"]}
            _require(len(returns) == 1, "Full release must have one evidenced return timestamp.")
            detail = event["payload"]["release"]
            number = _number(UUID(source["namespace"]), evidence["origin"]["source_id"] + ":release:" + row["request_key"], "PAWN_LOAN_RELEASE")
            result = _release_pawn_loan_in_full_at(loan.pk, actor=actor, effective_date=date.fromisoformat(row["effective_date"]),
                settlement_amount=row["settlement_amount"], request_key=row["request_key"],
                interest_concession=event["payload"]["values"].get("interest_concession", "0"),
                concession_reason=detail.get("interest_concession_reason", ""),
                historical_number=number, returned_at=datetime.fromisoformat(next(iter(returns))))
            event_map[event["id"]] = result.loan_event.pk
        elif event["event_kind"] == "REVERSAL" and event["reversal_of_id"] in event_map:
            _reverse_pawn_loan_event_at(event_map[event["reversal_of_id"]], actor=actor,
                effective_date=date.fromisoformat(event["effective_date"]), reason=event["payload"]["reversal"]["reason"])


def _access(workspace_id, actor):
    workspace = require_history_setup_access(workspace_id, actor)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    # The command can restore release, concession and reversal evidence. It never
    # grants these actions merely because the caller possesses an export file.
    access.require("data.export")
    access.require("loan.release")
    access.require("workspace.settings.manage")
    return workspace


def _request(*, workspace_id, actor, content, mapping):
    workspace = _access(workspace_id, actor)
    _require(type(mapping) is dict and set(mapping) == MAPPING and all(type(value) is int and value > 0 for value in mapping.values()),
        "Select explicit destination borrower, licence revision, series and product version.")
    document = parse_opening_export(content)
    if document["manifest"]["profile"] == PAYMENT_PROFILE:
        resolve_workspace_access(actor=actor, workspace=workspace).require("loan.repay")
    request = {"profile": PROFILE, "document": document, "mapping": mapping, "workspace_id": workspace_id}
    return request


def _restore(request, actor):
    workspace_id, mapping = request["workspace_id"], request["mapping"]
    _access(workspace_id, actor)
    source = request["document"]["evidence"]
    review = deepcopy(source["origin"]["document"]["review"])
    review["mapping"].update(workspace_id=workspace_id, borrower_id=mapping["borrower_id"],
        licence_revision_id=mapping["revision_id"], series_id=mapping["series_id"], product_version_id=mapping["product_version_id"])
    document = _document(review, source["origin"]["document"]["setup"])
    # Lock before permission recheck, shared-origin replay and financial writes.
    from apps.orgs.models import Company
    Company.all_objects.select_for_update().get(pk=workspace_id)
    _access(workspace_id, actor)
    existing = find_source_origin(workspace_id=workspace_id, namespace=review["source"]["namespace"],
        source_id=review["source"]["loan_id"], borrower_source_system=review["mapping"]["borrower_source_system"])
    origin, summary = _write(workspace_id=workspace_id, actor=actor, document=document, restoration=request)
    if existing is None:
        actual = json.loads(_export_opening(workspace_id=workspace_id, actor=actor, loan_id=origin.loan_id,
            as_of_date=date.fromisoformat(request["document"]["manifest"]["as_of"]), audit=False).splitlines()[1])
        expected, rebuilt = semantic_evidence(source), semantic_evidence(actual)
        for section in expected:
            _require(expected[section] == rebuilt[section], "Restored opening does not reconcile: " + section)
        AuditLog.log("DATA_IMPORT", company=origin.loan.workspace, user=actor,
            description="Restored and reconciled opening plus supported servicing from immutable source evidence.",
            data={"loan": origin.loan_id, "profile": PROFILE, "sha256": digest(request)})
    return origin, summary


def preview_opening_restore(*, workspace_id, actor, content, mapping):
    request = _request(workspace_id=workspace_id, actor=actor, content=content, mapping=mapping)
    with transaction.atomic():
        _, summary = _restore(request, actor)
        transaction.set_rollback(True)
    return {"sha256": digest(request), "summary": summary}


@transaction.atomic
def commit_opening_restore(*, workspace_id, actor, content, mapping, expected_sha256, confirmed=False):
    request = _request(workspace_id=workspace_id, actor=actor, content=content, mapping=mapping)
    _require(confirmed is True and expected_sha256 == digest(request), "Confirm the exact opening restore preview fingerprint.")
    return _restore(request, actor)
