"""Explicit aggregate approval over existing Party commands and staged evidence."""
from copy import deepcopy

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from . import bundles, child_contracts, contracts, services
from .access import require_access
from .models import ImportBatch, ImportBundle
from .parsers import PortabilityError

RECEIPT_SALT = "party-bundle-staging"
APPROVAL_SALT = "party-bundle-approval-v1"


def receipt_batches(*, workspace_id, actor, receipt, lock=False):
    require_access(workspace_id, actor, "import")
    try:
        payload = signing.loads(receipt, salt=RECEIPT_SALT, max_age=86400)
        if payload["workspace"] != workspace_id:
            raise PermissionDenied("Bundle belongs to another Workspace.")
        entries = payload["batches"]
        if payload.get("history"):
            history = ImportBundle.objects.select_related(*ImportBundle.PROFILE_FIELDS).filter(
                workspace_id=workspace_id, public_id=payload["history"]).first()
            if history is None or entries != [list(entry) for entry in history.receipt_entries()]:
                raise ValueError()
        if [entry[0] for entry in entries] != list(bundles.PROFILES):
            raise ValueError()
        ids = [key for profile, key in entries if key]
        if len(set(ids)) != len(ids):
            raise ValueError()
        query = ImportBatch.objects.filter(workspace_id=workspace_id, public_id__in=ids).order_by("pk")
        if lock:
            query = query.select_for_update()
        found = {str(batch.public_id): batch for batch in query}
        if len(found) != len(ids):
            raise ValueError()
        result = [found[key] for profile, key in entries if key]
        if any(found[key].contract_version != profile or found[key].source_type != "jsonl" for profile, key in entries if key):
            raise ValueError()
        if len({batch.source_system for batch in result}) > 1:
            raise ValueError()
        if lock:
            for batch in result:
                list(batch.rows.select_for_update().order_by("pk"))
        return result
    except (signing.BadSignature, ValueError, KeyError, TypeError) as exc:
        raise PortabilityError("The bundle receipt is invalid or expired. Individual batches remain in Recent imports.") from exc


def _authorize(workspace_id, actor, batches):
    for batch in batches:
        require_access(workspace_id, actor, "commit" if batch.contract_version == contracts.PROFILE else "child_commit")


def _input_digest(batches):
    return contracts.digest([{ "id": str(batch.public_id), "state": batch.state,
        "revision": batch.revision, "mapping": batch.mapping, "approval": batch.approval_digest,
        "source": [batch.source_system, batch.source_sha256, batch.source_bytes, batch.contract_version],
        "rows": list(batch.rows.order_by("source_row").values("source_row", "raw", "canonical", "issues", "disposition", "external_id"))}
        for batch in batches])


def _run(workspace_id, actor, batches, role_map, marker=""):
    plan = []
    for batch in batches:
        mapping = {"role_type_map": role_map} if batch.contract_version == child_contracts.ROLE else {}
        batch = services.validate_import(workspace_id=workspace_id, actor=actor, batch_id=batch.public_id, mapping=mapping)
        rows = []
        for row in batch.rows.order_by("source_row"):
            canonical = deepcopy(row.canonical)
            # Newly simulated parent database IDs vary after savepoint rollback.
            # Their immutable portable references remain in the signed plan.
            canonical.pop("_parties", None)
            rows.append({"number": row.source_row, "canonical": canonical,
                         "issues": deepcopy(row.issues), "disposition": row.disposition})
        plan.append({"profile": batch.contract_version, "batch": str(batch.public_id),
                     "summary": deepcopy(batch.summary), "rows": rows})
        if batch.summary["rows_with_errors"]:
            break
        if marker:
            batch.summary["bundle_approval"] = marker
            batch.save(update_fields=["summary"])
        services.commit_import(workspace_id=workspace_id, actor=actor, batch_id=batch.public_id,
                               approval_digest=batch.approval_digest, acknowledge_warnings=True)
    connection.check_constraints()
    return plan


def preview_bundle(*, workspace_id, actor, receipt, role_map):
    require_access(workspace_id, actor, "import")
    try:
        with transaction.atomic():
            Company.all_objects.select_for_update().get(pk=workspace_id)
            batches = receipt_batches(workspace_id=workspace_id, actor=actor, receipt=receipt, lock=True)
            _authorize(workspace_id, actor, batches)
            if not batches or any(b.state not in {"READY", "NEEDS_MAPPING"} for b in batches):
                raise PortabilityError("Combined review requires nonempty, unfinished batches. Use individual previews for a partially committed bundle.")
            before = _input_digest(batches)
            with transaction.atomic():
                plan = _run(workspace_id, actor, batches, role_map)
                # This savepoint discards business rows, identities, audits,
                # batch changes and any transaction.on_commit callbacks.
                transaction.set_rollback(True)
            ready = len(plan) == len(batches) and not any(p["summary"]["rows_with_errors"] for p in plan)
            approval = signing.dumps({"workspace": workspace_id, "actor": actor.pk,
                "receipt": receipt, "input": before, "plan": contracts.digest(plan), "role_map": role_map},
                salt=APPROVAL_SALT, compress=True) if ready else ""
            return {"profiles": plan, "approval": approval, "ready": ready}
    except (IntegrityError, ValidationError) as exc:
        raise PortabilityError("The combined import violates current Party rules. No changes were retained; review the individual profiles.") from exc


def commit_bundle(*, workspace_id, actor, approval, acknowledge_warnings=False, expected_bundle_id=None):
    require_access(workspace_id, actor, "import")
    try:
        payload = signing.loads(approval, salt=APPROVAL_SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise PortabilityError("Combined approval is invalid or expired. Generate a fresh preview.") from exc
    if payload["workspace"] != workspace_id or payload["actor"] != actor.pk:
        raise PermissionDenied("This combined approval belongs to another Workspace or operator.")
    if acknowledge_warnings is not True:
        raise PortabilityError("Confirm that you reviewed all profiles and warnings before committing.")
    if expected_bundle_id is not None:
        source = signing.loads(payload["receipt"], salt=RECEIPT_SALT)
        if source.get("history") != str(expected_bundle_id):
            raise PermissionDenied("This approval belongs to another bundle.")
    marker = contracts.digest(approval)
    try:
        with transaction.atomic():
            Company.all_objects.select_for_update().get(pk=workspace_id)
            batches = receipt_batches(workspace_id=workspace_id, actor=actor, receipt=payload["receipt"], lock=True)
            _authorize(workspace_id, actor, batches)  # Also required before idempotent replay.
            if batches and all(b.state == "COMPLETED" and b.summary.get("bundle_approval") == marker for b in batches):
                return batches
            if not batches or any(b.state not in {"READY", "NEEDS_MAPPING"} for b in batches) or _input_digest(batches) != payload["input"]:
                raise PortabilityError("A staged profile changed or finished. Generate a fresh combined preview.")
            plan = _run(workspace_id, actor, batches, payload["role_map"], marker)
            if len(plan) != len(batches) or any(p["summary"]["rows_with_errors"] for p in plan) or contracts.digest(plan) != payload["plan"]:
                raise PortabilityError("Destination data changed since combined review. Nothing was committed; generate a fresh preview.")
            AuditLog.log("DATA_IMPORT", company=Company.all_objects.get(pk=workspace_id), user=actor,
                description="Committed all Party bundle profiles in one approved transaction.",
                data={"profile": bundles.PROFILE, "bundle_approval": marker,
                      "batches": [str(batch.public_id) for batch in batches]})
            return list(ImportBatch.objects.filter(workspace_id=workspace_id, pk__in=[b.pk for b in batches]).order_by("pk"))
    except (IntegrityError, ValidationError) as exc:
        raise PortabilityError("The combined import violates current Party rules. Nothing was committed; generate a fresh preview.") from exc
