"""Bounded operator exchange; published Party/Loans wires remain authoritative."""
from collections import Counter
from itertools import groupby
from pathlib import Path
import hashlib
import json
import re
from uuid import UUID

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import OperationalError, connection, transaction
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.party import models as party
from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services import servicing_bundle, closed_position_portability
from apps.tenant_apps.loans.services.history_contract import _pairs
from . import child_contracts, contracts, services, loan_restore
from .access import require_access
from .models import WorkspaceNamespace, PartyIdentity, ImportBatch, LoanRestoreBatch
from .parsers import MAX_BYTES, MAX_ROWS, PortabilityError, parse_source

PROFILE = "rokkad-exchange/1"
MAX_MANIFEST = 32 * 1024 * 1024
MAX_CHUNKS = 60000
MAX_LOANS = 50000
MAX_PROFILE_ROWS = 200000
MAX_SNAPSHOT_ROWS = 1000000
MAX_TOTAL_BYTES = 20 * 1024**3
PARTY_MODELS = {contracts.PROFILE: party.Party, child_contracts.CONTACT: party.PartyContactMethod,
    child_contracts.ADDRESS: party.PartyAddress, child_contracts.IDENTIFIER: party.PartyIdentifier,
    child_contracts.ROLE: party.PartyRole, child_contracts.RELATIONSHIP: party.PartyRelationship}
EXCLUSIONS = ["Workspace configuration and access", "Party binary files and metadata",
    "Role-type definitions and mappings", "Unpaid drafts and undisbursed proposals",
    "Other business apps", "Unsupported financial graphs (export fails, never silently omitted)"]
PATH = re.compile(r"chunks/[0-9]{6}\.(jsonl|json|zip)\Z")


def sha(content):
    return hashlib.sha256(content).hexdigest()


def _require(condition, message):
    if not condition:
        raise PortabilityError(message)


def _snapshot(workspace_id, consistent_snapshot):
    if consistent_snapshot:
        services.require_export_snapshot()
    else:
        Company.all_objects.select_for_update(nowait=True).get(pk=workspace_id)
    models = set(PARTY_MODELS.values()) | {party.PartyRoleType}
    # Also lock excluded Loans rows: their presence must not change while the
    # domain exporter decides whether a graph can be represented losslessly.
    for model in apps.get_app_config("loans").get_models():
        try:
            model._meta.get_field("workspace")
        except FieldDoesNotExist:
            continue
        models.add(model)
    total = 0
    for model in sorted(models, key=lambda model: model._meta.label_lower):
        query = model.objects.filter(workspace_id=workspace_id).order_by("pk")
        if not consistent_snapshot:
            query = query.select_for_update(nowait=True)
        for _ in query.values_list("pk", flat=True).iterator(chunk_size=2000):
            total += 1
            _require(total <= MAX_SNAPSHOT_ROWS, "Exchange snapshot exceeds one million source rows.")


def _groups(model, workspace_id, master=False):
    """Never split one parent's children: primary-summary ordering is preserved."""
    parent = "pk" if master else "from_party_id" if model is party.PartyRelationship else "party_id"
    rows = model.objects.filter(workspace_id=workspace_id).order_by(parent, "pk").values_list(parent, "pk")
    pending, total = [], 0
    for _, group in groupby(rows.iterator(chunk_size=2000), key=lambda row: row[0]):
        ids = []
        for _, pk in group:
            ids.append(pk)
            _require(len(ids) <= MAX_ROWS, "One Party's child group exceeds the 1,000-row file bound.")
        total += len(ids)
        _require(total <= MAX_PROFILE_ROWS, "A Party profile exceeds 200,000 rows.")
        if pending and len(pending) + len(ids) > MAX_ROWS:
            yield pending
            pending = []
        pending.extend(ids)
    if pending:
        yield pending


def _export_party_chunks(workspace_id, actor, profile, model, ids, consistent_snapshot):
    """Split on bytes as well as rows, without splitting a parent's children."""
    try:
        if profile == contracts.PROFILE:
            result = services.export_parties(workspace_id=workspace_id, actor=actor,
                record_ids=ids, _consistent_snapshot=consistent_snapshot)
        else:
            result = services.export_children(workspace_id=workspace_id, actor=actor,
                profile=profile, record_ids=ids, _consistent_snapshot=consistent_snapshot)
    except PortabilityError as exc:
        if "5 MiB" not in str(exc):
            raise
        if profile == contracts.PROFILE:
            groups = [[pk] for pk in ids]
        else:
            parent = "from_party_id" if model is party.PartyRelationship else "party_id"
            rows = model.objects.filter(workspace_id=workspace_id, pk__in=ids).order_by(parent, "pk").values_list(parent, "pk")
            groups = [[pk for _,pk in values] for _,values in groupby(rows, key=lambda row:row[0])]
        _require(len(groups) > 1, "One Party record/child group cannot fit the 5 MiB file bound.")
        middle = len(groups)//2
        for part in (groups[:middle], groups[middle:]):
            yield from _export_party_chunks(workspace_id, actor, profile, model,
                [pk for group in part for pk in group], consistent_snapshot)
        return
    yield result


@transaction.atomic
def write_exchange(*, workspace_id, actor, directory, include_loans=True, _consistent_snapshot=False):
    """Write an unpublished directory. Caller publishes only after DB commit.

    The command owns temporary-directory cleanup and publication. No background
    task, shared-storage file or new receipt table.
    """
    workspace = require_access(workspace_id, actor, "export")
    if include_loans:
        servicing_bundle._access(workspace_id, actor, exporting=True)
    root = Path(directory).resolve()
    _require(root.is_dir() and not any(root.iterdir()), "Exchange output must be a new empty private directory.")
    try:
        _snapshot(workspace_id, _consistent_snapshot)
        require_access(workspace_id, actor, "export")
        if _consistent_snapshot:
            with connection.cursor() as cursor:
                cursor.execute("SELECT transaction_timestamp()")
                instant = cursor.fetchone()[0]
            day, captured = timezone.localdate(instant), instant.isoformat()
        else:
            day, captured = timezone.localdate(), timezone.now().isoformat()
        namespace, _ = WorkspaceNamespace.objects.get_or_create(workspace_id=workspace_id)
        (root / "chunks").mkdir(mode=0o700)
        chunks, counts, total_bytes, seen = [], {}, 0, set()

        def add(content, profile, count, extension, source_loans=()):
            nonlocal total_bytes
            _require(len(chunks) < MAX_CHUNKS, "Exchange exceeds 60,000 chunks.")
            total_bytes += len(content)
            _require(total_bytes <= MAX_TOTAL_BYTES, "Exchange exceeds 20 GiB.")
            path = f"chunks/{len(chunks)+1:06d}.{extension}"
            (root / path).write_bytes(content)
            chunks.append(dict(path=path, profile=profile, count=count, bytes=len(content),
                sha256=sha(content), source_loan_ids=list(source_loans)))

        for profile, model in PARTY_MODELS.items():
            counts[profile] = 0
            for ids in _groups(model, workspace_id, profile == contracts.PROFILE):
                if profile == contracts.PROFILE:
                    existing = set(PartyIdentity.objects.filter(workspace_id=workspace_id, party_id__in=ids).values_list("party_id", flat=True))
                    PartyIdentity.objects.bulk_create([PartyIdentity(workspace_id=workspace_id, party_id=pk) for pk in ids if pk not in existing])
                for result in _export_party_chunks(workspace_id, actor, profile, model, ids, _consistent_snapshot):
                    add(result.content, profile, result.count, "jsonl")
                    counts[profile] += result.count

        if include_loans:
            ids = list(loans.PawnLoan.objects.filter(workspace_id=workspace_id,
                state__in=["ACTIVE", "CLOSED", "CANCELLED"], loan_events__isnull=False).order_by("pk").values_list("pk", flat=True).distinct()[:MAX_LOANS+1])
            _require(len(ids) <= MAX_LOANS, "Exchange exceeds 50,000 admitted loans.")
            eligible = set(ids)
            for pk in ids:
                if pk in seen:
                    continue
                loan = loans.PawnLoan.objects.get(workspace_id=workspace_id, pk=pk)
                if loan.is_imported_closed_position:
                    content, filename = closed_position_portability.export_closed_position(workspace_id=workspace_id, actor=actor, loan_id=pk, _consistent_snapshot=_consistent_snapshot)
                    graph = {pk}
                    profile, _ = loan_restore.classify(content)
                    extension = filename.rsplit(".", 1)[1]
                else:
                    content = servicing_bundle.export_servicing_bundle(workspace_id=workspace_id, actor=actor, loan_id=pk, _consistent_snapshot=_consistent_snapshot)
                    doc, _ = servicing_bundle.read_bundle(content)
                    graph = {row["id"] for row in doc["tables"]["PawnLoan"]}
                    profile, extension = doc['profile'], "zip"
                _require(not seen.intersection(graph) and graph <= eligible,
                    "Connected financial graph overlaps a prior chunk or includes an unadmitted loan.")
                add(content, profile, len(graph), extension, sorted(graph))
                seen.update(graph)
            _require(seen == eligible, "Financial chunks do not cover the admitted source cohort.")
        _require(timezone.localdate() == day, "Exchange crossed the business-date boundary; retry.")
        manifest = dict(profile=PROFILE, scope="PARTIAL", source_namespace=str(namespace.public_id),
            snapshot=dict(consistency="repeatable-read" if _consistent_snapshot else "workspace-row-locks", captured_at=captured, as_of=day.isoformat()),
            include_loans=include_loans, counts={**counts, "loans": len(seen)}, chunks=chunks,
            exclusions=EXCLUSIONS, sha256="")
        manifest["sha256"] = sha(contracts.dump({k:v for k,v in manifest.items() if k != "sha256"}).encode())
        raw = contracts.dump(manifest).encode()
        _require(len(raw) <= MAX_MANIFEST, "Exchange manifest exceeds 32 MiB.")
        (root / "manifest.json").write_bytes(raw)
        AuditLog.log("DATA_EXPORT", company=workspace, user=actor,
            description="Prepared bounded Party/Loans exchange from one locked snapshot.",
            data=dict(profile=PROFILE, sha256=manifest["sha256"], chunks=len(chunks), counts=manifest["counts"]))
        return manifest
    except OperationalError as exc:
        if getattr(exc.__cause__, "pgcode", None) in {"55P03", "40P01"}:
            raise PortabilityError("Source data is being edited. Retry; no exchange was published.") from exc
        raise


def read_manifest(directory, *, expected_sha256=None):
    root = Path(directory).resolve()
    with (root / "manifest.json").open("rb") as stream:
        raw = stream.read(MAX_MANIFEST+1)
    _require(len(raw) <= MAX_MANIFEST, "Exchange manifest exceeds 32 MiB.")
    try:
        doc = json.loads(raw, object_pairs_hook=_pairs)
        _require(type(doc) is dict and set(doc) == {"profile", "scope", "source_namespace", "snapshot", "include_loans", "counts", "chunks", "exclusions", "sha256"}, "Invalid exchange manifest fields.")
        checksum = sha(contracts.dump({k:v for k,v in doc.items() if k != "sha256"}).encode())
        _require(doc["profile"] == PROFILE and doc["scope"] == "PARTIAL" and doc["sha256"] == checksum and
            (expected_sha256 is None or checksum == expected_sha256), "Exchange manifest changed or uses an unsupported profile.")
        UUID(doc["source_namespace"])
        _require(type(doc["include_loans"]) is bool and doc["exclusions"] == EXCLUSIONS and
            type(doc["snapshot"]) is dict and set(doc["snapshot"]) == {"consistency", "captured_at", "as_of"} and
            doc["snapshot"]["consistency"] in {"workspace-row-locks", "repeatable-read"}, "Invalid exchange snapshot or coverage.")
        _require(type(doc["chunks"]) is list and len(doc["chunks"]) <= MAX_CHUNKS, "Excessive exchange chunks.")
        totals, loan_ids, order, total_bytes = Counter(), set(), -1, 0
        for index, entry in enumerate(doc["chunks"], 1):
            _require(type(entry) is dict and set(entry) == {"path", "profile", "count", "bytes", "sha256", "source_loan_ids"}, "Invalid chunk fields.")
            profile = entry["profile"]
            rank = list(PARTY_MODELS).index(profile) if profile in PARTY_MODELS else len(PARTY_MODELS)
            _require(rank >= order, "Exchange dependency order changed.")
            order = rank
            _require(type(entry["path"]) is str and PATH.fullmatch(entry["path"]) and entry["path"].split("/")[1].split(".")[0] == f"{index:06d}", "Invalid exchange chunk path or order.")
            _require(type(entry["bytes"]) is int and 0 < entry["bytes"] <= (MAX_BYTES if rank < len(PARTY_MODELS) else 32*1024*1024), "Chunk exceeds its file bound.")
            _require(type(entry["count"]) is int and 0 < entry["count"] <= (MAX_ROWS if rank < len(PARTY_MODELS) else 20), "Invalid chunk count.")
            _require(type(entry["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), "Invalid chunk checksum.")
            _require(type(entry["source_loan_ids"]) is list, "Invalid source loan cohort.")
            if rank < len(PARTY_MODELS):
                _require(not entry["source_loan_ids"] and entry["path"].endswith(".jsonl"), "Party chunks cannot contain financial claims.")
                totals[profile] += entry["count"]
                _require(totals[profile] <= MAX_PROFILE_ROWS, "Party profile exceeds its exchange bound.")
            else:
                _require(doc["include_loans"] and profile in loan_restore.SUPPORTED and
                    not profile.startswith("loan-opening-export") and len(entry["source_loan_ids"]) == entry["count"] and
                    all(type(pk) is int and pk > 0 for pk in entry["source_loan_ids"]) and
                    len(set(entry["source_loan_ids"])) == entry["count"] and not loan_ids.intersection(entry["source_loan_ids"]), "Invalid, repeated or unsupported financial cohort.")
                loan_ids.update(entry["source_loan_ids"])
            total_bytes += entry["bytes"]
        _require(len(loan_ids) <= MAX_LOANS and total_bytes <= MAX_TOTAL_BYTES and
            doc["counts"] == {**{p:totals[p] for p in PARTY_MODELS}, "loans":len(loan_ids)}, "Manifest totals differ from bounded chunk coverage.")
        return doc
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        if isinstance(exc, PortabilityError):
            raise
        raise PortabilityError("Invalid exchange manifest.") from exc


def chunk_bytes(directory, entry):
    root = Path(directory).resolve()
    path = (root / entry["path"]).resolve()
    _require(path.is_relative_to(root) and not (root / entry["path"]).is_symlink(), "Chunk path leaves the private exchange directory.")
    with path.open("rb") as stream:
        content = stream.read(entry["bytes"]+1)
    _require(len(content) == entry["bytes"] and sha(content) == entry["sha256"], "Exchange chunk is missing, changed or truncated.")
    if entry["profile"] in PARTY_MODELS:
        _, _, _, rows = parse_source(content, entry["path"])
        _require(len(rows) == entry["count"], "Party chunk count differs from its manifest.")
    else:
        profile, metadata = loan_restore.classify(content)
        _require(profile == entry["profile"] and len(metadata["loans"]) == entry["count"], "Loan chunk differs from its manifest profile or count.")
        if profile in servicing_bundle.PROFILES:
            _require({int(row["key"]) for row in metadata["loans"]} == set(entry["source_loan_ids"]), "Connected source loan claims differ from the file.")
    return content


def _receipts(workspace_id, namespace):
    party_receipts = {}
    for batch in ImportBatch.objects.filter(workspace_id=workspace_id, source_system="rokkad:"+namespace).exclude(state="CANCELLED").only("public_id", "state", "contract_version", "source_sha256").order_by("created_at").iterator():
        key = (batch.contract_version, batch.source_sha256)
        if key not in party_receipts or party_receipts[key].state != "COMPLETED":
            party_receipts[key] = batch
    financial = {batch.source_sha256: batch for batch in LoanRestoreBatch.objects.filter(workspace_id=workspace_id).exclude(state="CANCELLED").only("public_id", "state", "source_sha256").iterator()}
    return party_receipts, financial


def inspect_exchange(*, workspace_id, actor, directory, expected_sha256=None):
    require_access(workspace_id, actor, "import")
    doc = read_manifest(directory, expected_sha256=expected_sha256)
    parties, financial = _receipts(workspace_id, doc["source_namespace"])
    progress = []
    for number, entry in enumerate(doc["chunks"], 1):
        chunk_bytes(directory, entry)
        batch = parties.get((entry["profile"], entry["sha256"])) if entry["profile"] in PARTY_MODELS else financial.get(entry["sha256"])
        progress.append(dict(chunk=number, state=batch.state if batch else "UNSTAGED", batch=str(batch.public_id) if batch else None))
    return dict(sha256=doc["sha256"], counts=doc["counts"], progress=progress)


@transaction.atomic
def stage_chunk(*, workspace_id, actor, directory, expected_sha256, number):
    require_access(workspace_id, actor, "import")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    doc = read_manifest(directory, expected_sha256=expected_sha256)
    _require(type(number) is int and 1 <= number <= len(doc["chunks"]), "Choose a manifest chunk number.")
    entry = doc["chunks"][number-1]
    # Party dependencies are bounded separately. Independent financial graphs
    # need no all-portfolio receipt scan on every chunk (quadratic at JCL size).
    dependencies = {(prior["profile"], prior["sha256"]) for prior in doc["chunks"][:number-1] if prior["profile"] in PARTY_MODELS}
    completed = set(ImportBatch.objects.filter(workspace_id=workspace_id,
        source_system="rokkad:"+doc["source_namespace"], state="COMPLETED",
        source_sha256__in=[checksum for _,checksum in dependencies])
        .values_list("contract_version", "source_sha256"))
    _require(dependencies <= completed, "Finish the earlier manifest Party chunks before staging this chunk.")
    content = chunk_bytes(directory, entry)
    if entry["profile"] in PARTY_MODELS:
        query = ImportBatch.objects.filter(workspace_id=workspace_id,
            source_system="rokkad:"+doc["source_namespace"], contract_version=entry["profile"],
            source_sha256=entry["sha256"]).exclude(state="CANCELLED")
        batch = query.filter(state="COMPLETED").first() or query.order_by("-created_at").first()
        if batch:
            return batch
        return services.stage_import(workspace_id=workspace_id, actor=actor, content=content,
            filename=entry["path"], source_system=doc["source_namespace"], profile=entry["profile"])
    return loan_restore.stage(workspace_id=workspace_id, actor=actor, content=content)
