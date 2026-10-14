"""File staging and exact review around the existing Loans restore commands."""
from io import BytesIO
import json
from zipfile import ZipFile, BadZipFile

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans.services import history_contract, opening_restore, servicing_bundle
from apps.tenant_apps.loans.services import closed_position_portability as closed
from apps.tenant_apps.loans.services import closed_position_contract
from apps.tenant_apps.loans.services.history_setup import require_history_preparation_access, require_history_setup_access
from apps.tenant_apps.loans.services.history_setup import validate_preparation_mapping
from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle, sha, MAX_BYTES
from .models import LoanRestoreBatch, LoanHistoryBatch

SALT = "loan-file-restore-review-v1"
OPENINGS = {f"loan-opening-export/{n}" for n in range(1, 5)}
SUPPORTED = OPENINGS | servicing_bundle.PROFILES | {closed.PROFILE, closed_position_contract.PROFILE}


def classify(content):
    """Sniff only bounded headers; the selected published parser validates all bytes."""
    if type(content) is not bytes or not 0 < len(content) <= MAX_BYTES:
        raise history_contract.HistoryError("Upload a supported loan file of at most 32 MiB.")
    try:
        if content.startswith(b"PK"):
            with ZipFile(BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 202 or sum(r.file_size for r in entries) > MAX_BYTES:
                    raise ValueError("Package exceeds its expanded file or size limit.")
                if len({r.filename for r in entries}) != len(entries):
                    raise ValueError("Duplicate package entries.")
                manifest = archive.getinfo("manifest.json")
                if manifest.file_size > MAX_BYTES:
                    raise ValueError("Package manifest exceeds its size limit.")
                header = json.loads(archive.read(manifest), object_pairs_hook=history_contract._pairs)
        else:
            if len(content) > history_contract.MAX_BYTES:
                raise ValueError("JSON/JSONL loan files are limited to 5 MiB.")
            try:
                header = json.loads(content.decode("utf-8-sig").splitlines()[0], object_pairs_hook=history_contract._pairs)
            except (ValueError, UnicodeError, IndexError):
                # Preserve the published history parser's structured malformed-data error.
                history_contract.parse(content)
                raise
        profile = header.get("profile") if isinstance(header, dict) else None
        if profile in history_contract.PROFILES:
            history_contract.parse(content)
            return profile, None
        if profile in OPENINGS:
            doc = opening_restore.parse_opening_export(content)
            loan = doc["evidence"]["loan"]
            review_mapping = doc["evidence"]["origin"]["document"]["review"]["mapping"]
            loans = [dict(key=str(loan["id"]), number=loan["loan_number"], state=loan["state"],
                borrower=dict(system=review_mapping["borrower_source_system"], id=review_mapping["borrower_external_id"]))]
            files, exclusions = 0, doc["manifest"]["exclusions"]
        elif profile in servicing_bundle.PROFILES:
            doc, media = read_bundle(content)
            loans = [dict(key=str(row["id"]), number=row["loan_number"], state=row["state"],
                         borrower=dict(system=doc["setup"][str(row["id"])]["borrower"]["source_system"],
                                       id=doc["setup"][str(row["id"])]["borrower"]["id"]))
                     for row in doc["tables"]["PawnLoan"]]
            files, exclusions = len(media), doc["exclusions"]
        elif profile in {closed.PROFILE, closed_position_contract.PROFILE}:
            doc, claims, _ = closed.parse_closed_position_file(content)
            loans = [dict(key="position", number=doc["loan"]["number"], state="CLOSED", borrower=doc["loan"]["borrower_reference"])]
            files, exclusions = len(claims), ["earlier_transactions", "workspace_configuration", "party_master"]
        else:
            raise ValueError("This file is not a supported Rokkad loan export. Use the existing-loans template for external registers; native database recovery is an operator procedure.")
        return profile, dict(loans=loans, files=files, exclusions=exclusions)
    except (ValueError, KeyError, UnicodeError, BadZipFile, RuntimeError, RecursionError) as exc:
        if isinstance(exc, history_contract.HistoryError):
            raise
        raise history_contract.HistoryError(str(exc)) from exc


def get_batch(*, workspace_id, actor, batch_id, lock=False):
    require_history_preparation_access(workspace_id, actor, read_only=not lock)
    query = LoanRestoreBatch.objects.filter(workspace_id=workspace_id)
    if lock:
        query = query.select_for_update()
    try:
        return query.get(public_id=batch_id)
    except (LoanRestoreBatch.DoesNotExist, ValueError):
        raise PermissionDenied("Loan restore is unavailable in this Workspace.") from None


def stage(*, workspace_id, actor, content):
    require_history_preparation_access(workspace_id, actor)
    profile, metadata = classify(content)
    if profile not in SUPPORTED:
        raise history_contract.HistoryError("Use complete-history staging for this profile.")
    batch = None
    try:
        with transaction.atomic():
            Company.all_objects.select_for_update().get(pk=workspace_id)
            workspace = require_history_preparation_access(workspace_id, actor)
            existing = LoanRestoreBatch.objects.filter(workspace_id=workspace_id, source_sha256=sha(content)).exclude(state="CANCELLED").first()
            if existing:
                return existing
            unfinished = LoanRestoreBatch.objects.filter(workspace_id=workspace_id, state__in=["STAGED", "READY"]).count()
            unfinished += LoanHistoryBatch.objects.filter(workspace_id=workspace_id, state__in=["STAGED", "READY"]).count()
            if unfinished >= 20:
                raise history_contract.HistoryError("Finish or cancel an unfinished Loans import before staging another (limit 20).")
            batch = LoanRestoreBatch(workspace_id=workspace_id, created_by=actor, profile=profile,
                source_sha256=sha(content), document=metadata)
            batch.source.save("source", ContentFile(content), save=False)
            batch.save()
            AuditLog.log("DATA_IMPORT", company=workspace, user=actor, content_object=batch,
                description="Staged a bounded loan export for destination review.", data={"profile": profile, "sha256": batch.source_sha256})
            return batch
    except Exception:
        if batch and batch.source.name:
            batch.source.storage.delete(batch.source.name)
        raise


def _content(batch):
    try:
        with batch.source.open("rb") as stream:
            content = stream.read(MAX_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise history_contract.HistoryError("The staged source is unavailable. Upload the checked export again.") from exc
    if sha(content) != batch.source_sha256 or classify(content) != (batch.profile, batch.document):
        raise history_contract.HistoryError("The staged source changed. No loans were restored.")
    return content


def _mapping(batch, values):
    keys = {r["key"] for r in batch.document["loans"]}
    fields = {"borrower_id", "series_id"} if batch.profile.startswith("loan-closed-position") else {"borrower_id", "series_id", "revision_id", "product_version_id"}
    if type(values) is not dict or set(values) != keys or any(type(row) is not dict or set(row) != fields
            or any(type(v) is not int or v <= 0 for v in row.values()) for row in values.values()):
        raise history_contract.HistoryError("Choose destination customer and setup for every source loan.")
    return values


def _preview(batch, actor, content, mapping):
    if batch.profile in OPENINGS:
        return opening_restore.preview_opening_restore(workspace_id=batch.workspace_id, actor=actor,
            content=content, mapping=next(iter(mapping.values())))
    if batch.profile in servicing_bundle.PROFILES:
        value = servicing_bundle.restore_servicing_bundle(workspace_id=batch.workspace_id, actor=actor, content=content, mapping=mapping)
        return dict(sha256=value["sha256"], summary=value.get("summary", {"already_restored": True, "loans": value["loans"]}))
    summary, token = closed.preview_closed_position_file(workspace_id=batch.workspace_id, actor=actor, content=content, **next(iter(mapping.values())))
    return dict(summary=summary, review_token=token)


@transaction.atomic
def prepare(*, workspace_id, actor, batch_id, values):
    """Save tenant-scoped matches without granting financial admission."""
    require_history_preparation_access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state not in {"STAGED", "READY"}:
        raise history_contract.HistoryError("Only unfinished imports can be prepared.")
    mapping = _mapping(batch, values)
    from apps.tenant_apps.loans.models import LoanSeries
    from apps.tenant_apps.party.models import Party
    for row in mapping.values():
        if batch.profile.startswith("loan-closed-position"):
            if not LoanSeries.objects.filter(workspace_id=workspace_id, pk=row["series_id"]).exists() or not Party.objects.filter(workspace_id=workspace_id, pk=row["borrower_id"]).exists():
                raise history_contract.HistoryError("Choose destination records from this Workspace.")
        else:
            validate_preparation_mapping(workspace_id, **row)
    _content(batch)
    batch.mapping, batch.preview, batch.approval_digest, batch.state = mapping, {}, "", "STAGED"
    batch.save(update_fields=["mapping", "preview", "approval_digest", "state"])
    return batch


@transaction.atomic
def preview(*, workspace_id, actor, batch_id, values):
    require_history_setup_access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state not in {"STAGED", "READY"}:
        raise history_contract.HistoryError("Only unfinished imports can be reviewed.")
    mapping = _mapping(batch, values)
    review = _preview(batch, actor, _content(batch), mapping)
    batch.mapping, batch.preview, batch.state = mapping, review, "READY"
    batch.approval_digest = history_contract.digest(dict(source=batch.source_sha256, mapping=mapping, review=review))
    batch.save(update_fields=["mapping", "preview", "state", "approval_digest"])
    return signing.dumps(dict(workspace=workspace_id, actor=actor.pk, batch=str(batch.public_id), digest=batch.approval_digest), salt=SALT)


@transaction.atomic
def commit(*, workspace_id, actor, batch_id, approval, confirmed=False):
    require_history_setup_access(workspace_id, actor)
    if confirmed is not True:
        raise history_contract.HistoryError("Confirm the reviewed destination setup and reconciliation.")
    try:
        token = signing.loads(approval or "", salt=SALT, max_age=3600)
    except (signing.BadSignature, TypeError, ValueError):
        raise history_contract.HistoryError("Review this import again; approval is missing or expired.") from None
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if token != dict(workspace=workspace_id, actor=actor.pk, batch=str(batch.public_id), digest=batch.approval_digest):
        raise PermissionDenied("Review belongs to another operator, Workspace or changed import.")
    if batch.state == "COMPLETED":
        return batch
    if batch.state != "READY" or batch.approval_digest != history_contract.digest(dict(source=batch.source_sha256, mapping=batch.mapping, review=batch.preview)):
        raise history_contract.HistoryError("Source or mappings changed; review this import again.")
    content, mapping = _content(batch), _mapping(batch, batch.mapping)
    current = _preview(batch, actor, content, mapping)
    if current["summary"] != batch.preview["summary"]:
        raise history_contract.HistoryError("Destination changed after review. No loans were restored; review again.")
    args = dict(workspace_id=workspace_id, actor=actor, content=content)
    if batch.profile in OPENINGS:
        origin, _ = opening_restore.commit_opening_restore(**args, mapping=next(iter(mapping.values())), expected_sha256=batch.preview["sha256"], confirmed=True)
        results = [origin.loan_id]
    elif batch.profile in servicing_bundle.PROFILES:
        result = servicing_bundle.restore_servicing_bundle(**args, mapping=mapping, expected_sha256=batch.preview["sha256"], confirmed=True)
        results = result["loans"]
    else:
        loan, _ = closed.admit_closed_position_file(**args, **next(iter(mapping.values())), review_token=batch.preview["review_token"], confirmed=True)
        results = [loan.pk]
    batch.state, batch.results, batch.committed_by, batch.committed_at = "COMPLETED", results, actor, timezone.now()
    batch.save(update_fields=["state", "results", "committed_by", "committed_at"])
    return batch


@transaction.atomic
def cancel(*, workspace_id, actor, batch_id, confirmed=False):
    require_history_setup_access(workspace_id, actor)
    if confirmed is not True:
        raise history_contract.HistoryError("Confirm removal of the staged file and cancellation.")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state == "COMPLETED":
        raise history_contract.HistoryError("Completed restores cannot be cancelled or erased.")
    if batch.state == "CANCELLED":
        return
    name, storage = batch.source.name, batch.source.storage
    batch.source, batch.document, batch.mapping, batch.preview, batch.approval_digest, batch.state = "", {}, {}, {}, "", "CANCELLED"
    batch.save(update_fields=["source", "document", "mapping", "preview", "approval_digest", "state"])
    transaction.on_commit(lambda: storage.delete(name))
