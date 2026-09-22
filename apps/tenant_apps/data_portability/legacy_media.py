"""Bounded admission of preserved branch photographs, with durable replay receipts."""
import hashlib
import json
import re
from pathlib import PurePosixPath
from uuid import UUID, uuid5

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.orgs.models import Company
from apps.tenant_apps.loans.models import HistoricalLoanEvidence, HistoricalLoanImport, PawnCollateralItem
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from apps.tenant_apps.loans.services.legacy_media import attach_legacy_media
from apps.tenant_apps.party.services.legacy_media import attach_legacy_photo
from .models import LegacyMediaReceipt, LoanHistoryBatch, SourceIdentity


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_evidence(evidence):
    """Never accept a filename-only candidate or a storage key outside its branch."""
    namespace = UUID(evidence["namespace"])
    source, original = evidence["source"], evidence["verified_source_file"]
    schema = source["schema"]
    if evidence.get("status") != "EXACT_SOURCE_FILE_PRESERVED" or not original:
        raise ValidationError("Only verified branch originals may be attached.")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema) or schema == "public":
        raise ValidationError("Invalid source schema.")
    for key in ("source_id", "parent_id"):
        if not re.fullmatch(r"[1-9][0-9]*", source[key]):
            raise ValidationError("Invalid source record identity.")
    expected_fields = {"contact_customerpic": ("customer_id", "image"), "girvi_loanitem": ("loan_id", "pic")}
    if expected_fields.get(source["table"]) != (source["parent_field"], source["field"]):
        raise ValidationError("Unsupported media source field.")
    path = PurePosixPath(source["stored_path"])
    if path.is_absolute() or ".." in path.parts or "\\" in source["stored_path"] or str(path) != source["stored_path"]:
        raise ValidationError("Invalid source path.")
    for value in (evidence["archive_sha256"], original["sha256"]):
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValidationError("Invalid evidence checksum.")
    expected = f"media/legacy/{namespace.hex}/branch/{schema}/{original['sha256']}/{path}"
    if original["object_key"] != expected:
        raise ValidationError("Preserved object is not bound to this source branch, path and hash.")
    if original["content_type"] not in {"image/png", "image/jpeg", "image/webp"} or not 0 < original["byte_size"] <= 10 * 1024 * 1024:
        raise ValidationError("Unsupported or oversized source photograph.")
    return f"legacy:{namespace.hex}:{schema}", f"{source['table']}:{source['source_id']}"


def _source_item(records, evidence):
    source = evidence["source"]
    matches = [r for r in records if r.get("source", {}).get("external_id") == f"girvi_loanitem:{source['source_id']}"]
    if len(matches) != 1:
        raise ValidationError("Photo item is absent or ambiguous in the accepted source records.")
    row = matches[0]
    if (row["source"]["schema"] != source["schema"] or row["facts"]["loan_id"] != source["parent_id"]
            or row["facts"]["pic"] != source["stored_path"]):
        raise ValidationError("Photo reference disagrees with the accepted item and loan.")


def resolve_target(*, workspace_id, actor, evidence):
    require_history_setup_access(workspace_id, actor)
    system, _ = validate_evidence(evidence)
    source = evidence["source"]
    namespace = UUID(evidence["namespace"])
    if source["table"] == "contact_customerpic":
        raw = evidence.get("customer_source", {})
        row = raw.get("source_row", {})
        if (raw.get("schema") != source["schema"] or raw.get("archive_sha256") != evidence["archive_sha256"]
                or row.get("id") != source["source_id"] or row.get("customer_id") != source["parent_id"]
                or row.get("image") != source["stored_path"] or row.get("is_default") not in {"t", "f"}):
            raise ValidationError("Customer photo and default flag require matching source evidence.")
        external_id = str(uuid5(uuid5(namespace, source["schema"]), "contact_customer:" + source["parent_id"]))
        identity = SourceIdentity.objects.select_related("identity__party").get(
            workspace_id=workspace_id, source_system=system, external_id=external_id)
        party = identity.identity.party
        if party.workspace_id != workspace_id or party.status == "ARCHIVED":
            raise ValidationError("Imported Party is unavailable or changed locally.")
        return "party", party
    source_loan = "girvi_loan:" + source["parent_id"]
    origin = HistoricalLoanImport.objects.filter(workspace_id=workspace_id, source_namespace=namespace,
                                                source_id=source["schema"] + ":" + source_loan).first()
    archives = HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id, source_namespace=namespace,
        source_system=system, source_id=source_loan, document__source__snapshot_reference="sha256:" + evidence["archive_sha256"])
    if origin:
        if archives.exists():
            raise ValidationError("Ambiguous active and archived source loan.")
        batch = LoanHistoryBatch.objects.get(workspace_id=workspace_id, state="COMPLETED", result=origin)
        source_evidence = batch.document["source_evidence"]
        if source_evidence["archive_sha256"] != evidence["archive_sha256"]:
            raise ValidationError("Opening and media come from different database snapshots.")
        _source_item(source_evidence["records"], evidence)
        item_id = origin.references["items"]["girvi_loanitem:" + source["source_id"]]
        return "collateral", PawnCollateralItem.objects.get(workspace_id=workspace_id, pk=item_id, loan_id=origin.loan_id)
    archive = archives.get()
    _source_item(archive.document["source_records"], evidence)
    return "archive", archive


def application_names(*, workspace_id, evidence, kind):
    # Compact names fit Party's existing 100-character FileFields. Different fields
    # always have different objects, even when their original content is identical.
    stem = f"legacy_import/{workspace_id}/{digest(evidence)}"
    suffix = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[evidence["verified_source_file"]["content_type"]]
    names = {"file": f"{stem}.{suffix}"}
    if kind == "party" and evidence["customer_source"]["source_row"]["is_default"] == "t":
        names["profile"] = f"{stem}-profile.{suffix}"
    return names


@transaction.atomic
def attach(*, workspace_id, actor, evidence, storage):
    """The storage adapter verifies every copy before any FileField is assigned."""
    require_history_setup_access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    system, source_id = validate_evidence(evidence)
    receipt = LegacyMediaReceipt.objects.filter(workspace_id=workspace_id, source_system=system, source_id=source_id).first()
    if receipt:
        if receipt.evidence_sha256 != digest(evidence) or receipt.source_evidence != evidence:
            raise ValidationError("This source photo was already admitted with different evidence.")
        # Explicit user removal/replacement is not undone by a migration retry.
        return receipt, False
    kind, target = resolve_target(workspace_id=workspace_id, actor=actor, evidence=evidence)
    names = application_names(workspace_id=workspace_id, evidence=evidence, kind=kind)
    for name in names.values():
        storage.verify(name, evidence["verified_source_file"])
    if kind == "party":
        result = attach_legacy_photo(workspace_id=workspace_id, actor=actor, party_id=target.pk,
            document_name=names["file"], profile_name=names.get("profile", ""), evidence=evidence)
    else:
        result = attach_legacy_media(workspace_id=workspace_id, actor=actor, target=target,
                                    file_name=names["file"], evidence=evidence)
    receipt = LegacyMediaReceipt.objects.create(workspace_id=workspace_id, source_system=system, source_id=source_id,
        evidence_sha256=digest(evidence), source_evidence=evidence, target=result, imported_by=actor)
    return receipt, True
