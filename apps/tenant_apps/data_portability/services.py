"""Public services require explicit, already-established Workspace context."""
import hashlib
import uuid
import re
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.creation import create_party_from_form
from . import children, child_contracts
from .access import require_access
from .contracts import (PROFILE, digest, dump, export_record, issue, party_form,
                        semantic, source_digest, validate_record)
from .mapping import map_row, validate_mapping
from .models import ImportBatch, ImportRow, PartyIdentity, SourceIdentity, WorkspaceNamespace
from .normalization import normalize
from .parsers import MAX_BYTES, MAX_ROWS, PortabilityError, parse_source

LEGACY_SOURCE_SYSTEM = re.compile(r"legacy:[0-9a-f]{32}:[a-z][a-z0-9_]{0,62}\Z")


def _batch(workspace_id, batch_id, *, lock=False):
    qs = ImportBatch.objects.filter(workspace_id=workspace_id)
    if lock:
        qs = qs.select_for_update()
    try:
        batch = qs.get(public_id=batch_id)
    except (ImportBatch.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("Import batch is unavailable.") from exc
    if batch.contract_version not in (PROFILE, *child_contracts.PROFILES):
        raise PortabilityError("Unsupported import contract version.")
    return batch


@transaction.atomic
def stage_import(*, workspace_id, actor, content, filename, source_system, profile=PROFILE):
    workspace = require_access(workspace_id, actor, "import")
    if profile not in (PROFILE, *child_contracts.PROFILES):
        raise PortabilityError("Unsupported import profile.")
    if not isinstance(source_system, str) or not source_system.strip() or len(source_system) > 120:
        raise PortabilityError("Supply a stable source system name (at most 120 characters).")
    if source_system != source_system.strip() or any(ord(c) < 32 for c in source_system):
        raise PortabilityError("Source system names cannot contain surrounding whitespace or control characters.")
    name, source_type, headers, raw_rows = parse_source(content, filename)
    if source_type == "jsonl":
        if source_system.startswith("legacy:"):
            if not LEGACY_SOURCE_SYSTEM.fullmatch(source_system):
                raise PortabilityError("Legacy JSONL requires legacy:<installation-uuid-without-hyphens>:<schema>.")
        else:
            try:
                source_system = "rokkad:" + str(uuid.UUID(source_system.removeprefix("rokkad:")))
            except ValueError as exc:
                raise PortabilityError("For JSONL, supply a native Workspace namespace UUID or exact legacy source system.") from exc
    elif source_system.startswith("rokkad:"):
        raise PortabilityError("The rokkad namespace is reserved for canonical JSONL.")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    if ImportBatch.objects.filter(workspace_id=workspace_id, state__in=["NEEDS_MAPPING", "READY"]).count() >= 20:
        raise PortabilityError("Cancel unfinished batches before uploading more (limit 20).")
    batch = ImportBatch.objects.create(workspace_id=workspace_id, source_name=name,
        source_type=source_type, source_system=source_system,
        source_sha256=hashlib.sha256(content).hexdigest(), source_bytes=len(content),
        headers=headers, created_by=actor, contract_version=profile)
    ImportRow.objects.bulk_create([ImportRow(workspace_id=workspace_id, batch=batch,
        source_row=number, raw=raw) for number, raw in raw_rows])
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor,
                 description="Staged Party source; no Party records created.",
                 data={"batch": str(batch.public_id), "rows": len(raw_rows)})
    return batch


def _resolve(record, external, batch, name_review=None):
    source = SourceIdentity.objects.select_related("identity__party").filter(
        workspace_id=batch.workspace_id, source_system=batch.source_system, external_id=external).first()
    if source:
        if source.accepted_digest != source_digest(record):
            return "CONFLICT", [issue("SOURCE_CHANGED", "", "This source identity has different previously imported values.")]
        if source.local_digest != digest(semantic(source.identity.party)):
            return "CONFLICT", [issue("LOCAL_CHANGED", "", "The destination Party changed after import; review it before proceeding.")]
        return "EXISTING", []
    # Canonical export of this same Workspace can be recognized without an import alias.
    namespace = WorkspaceNamespace.objects.filter(workspace_id=batch.workspace_id).first()
    if namespace and batch.source_system == "rokkad:" + str(namespace.public_id):
        identity = PartyIdentity.objects.select_related("party").filter(
            workspace_id=batch.workspace_id, public_id=external).first()
        if identity and semantic(identity.party) == {k: record[k] for k in semantic(identity.party)}:
            return "EXISTING", []
        return "CONFLICT", [issue("LOCAL_ID_CONFLICT", "id", "This local export identity is missing or changed.")]
    if name_review is not None:
        matches = set(Party.objects.filter(workspace_id=batch.workspace_id,
            display_name__iexact=record["name"]).values_list("pk", flat=True))
        if matches != set(name_review["party_ids"]):
            return "CONFLICT", [issue("NAME_REVIEW_CHANGED", "name", "Customers with this name changed since review. Review their identities again.")]
    query = Q(pk__in=[]) if name_review is not None else Q(display_name__iexact=record["name"])
    for key, field in (("primary_phone", "primary_phone"), ("primary_email", "primary_email"),
                       ("tax_pan", "tax_pan"), ("gstin", "gstin")):
        if record.get(key):
            query |= Q(**{field + "__iexact": record[key]})
    if Party.objects.filter(workspace_id=batch.workspace_id).filter(query).exists():
        return "CONFLICT", [issue("POSSIBLE_DUPLICATE", "", "A Party has matching identity details. Resolve the ambiguity outside this import.")]
    return "NEW", []


def _evaluate(batch, rows, mapping):
    evaluated, external_seen, detail_seen = [], {}, {}
    reviewed_rows = set()
    for row in rows:
        record, external, issues = map_row(row.raw, mapping, batch.source_type)
        record, changes = normalize(record, mapping["normalization"])
        issues += changes
        record, errors = (validate_record(record, canonical_source=batch.source_type == "jsonl")
            if batch.contract_version == PROFILE else child_contracts.validate_child(record, batch.contract_version, canonical_source=batch.source_type == "jsonl", role_map=mapping.get("role_type_map")))
        issues += errors
        if batch.source_type == "jsonl" and not any(i["severity"] == "ERROR" for i in issues):
            external = str(uuid.UUID(external))
        if not isinstance(external, str) or not external.strip() or len(external) > 255 or external != external.strip():
            issues.append(issue("INVALID_SOURCE_ID", "source.external_id", "A nonempty stable source ID without surrounding whitespace is required."))
            external = ""
        disposition = "ERROR"
        name_review = mapping.get("name_reviews", {}).get(external)
        if name_review is not None:
            if name_review["record_sha256"] != source_digest(record):
                issues.append(issue("NAME_REVIEW_CHANGED", "name", "The reviewed customer values changed; review their identity again."))
                name_review = None
            else:
                reviewed_rows.add(row.source_row)
                issues.append(issue("DISTINCT_NAME_REVIEWED", "name",
                    "Keep this reviewed source customer separate despite matching names. " + name_review["reason"], "WARNING"))
        if not any(i["severity"] == "ERROR" for i in issues):
            disposition, conflicts = (_resolve(record, external, batch, name_review) if batch.contract_version == PROFILE
                else children.resolve(record, external, batch))
            issues += conflicts
        row.canonical, row.external_id, row.issues, row.disposition = record, external, issues, disposition
        candidate_keys = [(external, external_seen)]
        if batch.contract_version != PROFILE and not any(i["severity"] == "ERROR" for i in issues):
            candidate_keys.extend((key, detail_seen) for key in children.duplicate_keys(record, batch))
        for field in (("name", "primary_phone", "primary_email", "tax_pan", "gstin") if batch.contract_version == PROFILE else ()):
            value = record.get(field)
            if isinstance(value, str) and value:
                candidate_keys.append(((field, value.casefold()), detail_seen))
        for key, index in candidate_keys:
            if key and key in index:
                if (isinstance(key, tuple) and key[0] == "name"
                        and row.source_row in reviewed_rows and index[key].source_row in reviewed_rows):
                    continue
                for duplicate in (row, index[key]):
                    duplicate.disposition = "CONFLICT"
                    duplicate.issues.append(issue("DUPLICATE_ROW", "source.external_id", "Duplicate source identity or identity details within this batch."))
            elif key:
                index[key] = row
        evaluated.append(row)
    summary = {"rows_found": len(rows), "rows_valid": 0, "rows_with_warnings": 0,
               "rows_with_errors": 0, "new_records": 0, "existing_records": 0, "conflicts": 0}
    for row in evaluated:
        error = any(i["severity"] == "ERROR" for i in row.issues)
        summary["rows_with_errors"] += int(error)
        summary["rows_valid"] += int(not error)
        summary["rows_with_warnings"] += int(any(i["severity"] == "WARNING" for i in row.issues))
        summary["new_records"] += int(row.disposition == "NEW")
        summary["existing_records"] += int(row.disposition == "EXISTING")
        summary["conflicts"] += int(row.disposition == "CONFLICT")
    return evaluated, summary


def _approval(batch, rows):
    payload = {"profile": batch.contract_version, "source": batch.source_sha256,
                   "source_system": batch.source_system, "mapping": batch.mapping,
                   "revision": batch.revision, "rows": [
                       [r.source_row, r.raw, r.external_id, r.canonical, r.issues, r.disposition] for r in rows]}
    if batch.mapping_preset_id is not None:
        payload["mapping_preset_id"] = batch.mapping_preset_id
    return digest(payload)


@transaction.atomic
def validate_import(*, workspace_id, actor, batch_id, mapping=None, preset_id=None):
    require_access(workspace_id, actor, "import")
    batch = _batch(workspace_id, batch_id, lock=True)
    if batch.state not in {"NEEDS_MAPPING", "READY"}:
        raise PortabilityError("Only an unfinished batch can be validated.")
    batch.mapping_preset = None
    if preset_id is not None:
        from .presets import preset_for_batch
        from copy import deepcopy
        if mapping is not None:
            raise PortabilityError("Choose a preset version or an explicit mapping, not both.")
        batch.mapping_preset = preset_for_batch(preset_id, batch)
        mapping = deepcopy(batch.mapping_preset.mapping)
    batch.mapping = validate_mapping(mapping, batch.headers, batch.source_type, profile=batch.contract_version)
    rows, batch.summary = _evaluate(batch, list(batch.rows.order_by("source_row")), batch.mapping)
    for row in rows:
        row.save(update_fields=["canonical", "issues", "external_id", "disposition"])
    batch.revision += 1
    batch.state = "NEEDS_MAPPING" if batch.summary["rows_with_errors"] else "READY"
    batch.approval_digest = _approval(batch, rows)
    batch.save(update_fields=["mapping", "mapping_preset", "summary", "revision", "state", "approval_digest"])
    if batch.mapping_preset_id:
        AuditLog.log("DATA_IMPORT", company=Company.all_objects.get(pk=workspace_id), user=actor, description="Applied a CSV mapping preset for fresh preview.",
            data={"batch": str(batch.public_id), "preset": str(batch.mapping_preset.public_id), "version": batch.mapping_preset.version,
                  "revision": batch.revision})
    return batch


def preview_import(*, workspace_id, actor, batch_id):
    require_access(workspace_id, actor, "import")
    batch = _batch(workspace_id, batch_id)
    return batch, list(batch.rows.order_by("source_row"))


@transaction.atomic
def commit_import(*, workspace_id, actor, batch_id, approval_digest, acknowledge_warnings=False):
    workspace = require_access(workspace_id, actor, "import")
    # Bounded Workspace serialization covers competing source imports/identity allocation.
    Company.all_objects.select_for_update().get(pk=workspace_id)
    workspace = require_access(workspace_id, actor, "import")
    batch = _batch(workspace_id, batch_id, lock=True)
    require_access(workspace_id, actor, "commit" if batch.contract_version == PROFILE else "child_commit")
    if not approval_digest or approval_digest != batch.approval_digest:
        raise PortabilityError("The preview changed. Validate and review it again.")
    if batch.state == "COMPLETED":
        return batch
    if batch.state != "READY" or batch.summary.get("rows_with_errors", 1):
        raise PortabilityError("Only a validated, error-free batch can be committed.")
    if batch.summary["rows_with_warnings"] and acknowledge_warnings is not True:
        raise PortabilityError("Acknowledge the preview warnings before committing.")
    rows = list(batch.rows.select_for_update().order_by("source_row"))
    if _approval(batch, rows) != approval_digest:
        raise PortabilityError("The staged input changed. Validate again.")
    if batch.contract_version != PROFILE:
        require_access(workspace_id, actor, "child_commit")
        children.lock_destinations(batch, rows)
    # Lock existing Parties used by source replays before rechecking local edits.
    identities = SourceIdentity.objects.filter(workspace_id=workspace_id,
        source_system=batch.source_system, external_id__in=[r.external_id for r in rows])
    list(Party.objects.select_for_update().filter(
        workspace_id=workspace_id, exchange_identity__sources__in=identities).order_by("pk"))
    rows, summary = _evaluate(batch, rows, batch.mapping)
    if summary["rows_with_errors"] or _approval(batch, rows) != approval_digest:
        raise PortabilityError("Destination data changed since preview. Validate and review again.")
    now = timezone.now()
    for row in rows:
        if batch.contract_version != PROFILE:
            children.commit_row(batch, row, now)
            continue
        source = SourceIdentity.objects.select_related("identity").filter(
            workspace_id=workspace_id, source_system=batch.source_system, external_id=row.external_id).first()
        if source:
            identity = source.identity
        elif row.disposition == "EXISTING":
            identity = PartyIdentity.objects.get(workspace_id=workspace_id, public_id=row.external_id)
        else:
            party = create_party_from_form(form=party_form(row.canonical), workspace_id=workspace_id, actor=actor)
            identity = PartyIdentity.objects.create(workspace_id=workspace_id, party=party)
        if not source:
            SourceIdentity.objects.create(workspace_id=workspace_id, source_system=batch.source_system,
                external_id=row.external_id, identity=identity, accepted_digest=source_digest(row.canonical),
                local_digest=digest(semantic(identity.party)))
        row.identity, row.committed_at = identity, now
        row.save(update_fields=["identity", "committed_at"])
    batch.state, batch.committed_at, batch.committed_by = "COMPLETED", now, actor
    batch.save(update_fields=["state", "committed_at", "committed_by"])
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor, description="Committed staged Party import.",
                 data={"batch": str(batch.public_id), "profile": batch.contract_version, "summary": summary, "approval": approval_digest})
    return batch


@transaction.atomic
def cancel_import(*, workspace_id, actor, batch_id):
    require_access(workspace_id, actor, "import")
    batch = _batch(workspace_id, batch_id, lock=True)
    if batch.state == "COMPLETED":
        raise PortabilityError("Completed imports cannot be cancelled or erased.")
    if batch.state == "CANCELLED":
        return batch
    batch.rows.update(raw={}, canonical={}, issues=[])
    batch.state, batch.approval_digest = "CANCELLED", ""
    batch.save(update_fields=["state", "approval_digest"])
    return batch


@dataclass(frozen=True)
class PartyExport:
    content: bytes
    namespace: str
    count: int
    sha256: str


@transaction.atomic
def export_parties(*, workspace_id, actor):
    workspace = require_access(workspace_id, actor, "export")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    workspace = require_access(workspace_id, actor, "export")
    # One materialized Party query is the master-field snapshot. No lazy reads after response.
    parties = list(Party.objects.filter(workspace_id=workspace_id).order_by("pk")[:MAX_ROWS + 1])
    if len(parties) > MAX_ROWS:
        raise PortabilityError("This bounded Party export supports at most 1,000 Parties; no partial truncation was exported.")
    namespace, _ = WorkspaceNamespace.objects.get_or_create(workspace_id=workspace_id)
    identities = {i.party_id: i for i in PartyIdentity.objects.filter(workspace_id=workspace_id)}
    records = []
    for party in parties:
        identity = identities.get(party.pk)
        if identity is None:
            identity = PartyIdentity.objects.create(workspace_id=workspace_id, party=party)
        sources = list(identity.sources.order_by("source_system", "external_id"))
        if len(sources) > 10:
            raise PortabilityError("A Party has more than ten source aliases; this profile cannot export it losslessly.")
        provenance = identity.import_rows.filter(committed_at__isnull=False, batch__contract_version=PROFILE).order_by("committed_at", "pk").first()
        records.append(export_record(party, identity, sources, provenance))
    content = ("".join(dump(r) + "\n" for r in sorted(records, key=lambda r: r["id"]))).encode("utf-8")
    if len(content) > MAX_BYTES:
        raise PortabilityError("The export exceeds the 5 MiB import boundary; no truncated file was exported.")
    if content:
        parse_source(content, "parties.jsonl")
    result = PartyExport(content, str(namespace.public_id), len(records), hashlib.sha256(content).hexdigest())
    AuditLog.log("DATA_EXPORT", company=workspace, user=actor, description="Exported partial Party master JSONL.",
                 data={"profile": PROFILE, "count": result.count, "sha256": result.sha256})
    return result


@transaction.atomic
def export_children(*, workspace_id, actor, profile):
    from apps.tenant_apps.party.models import PartyContactMethod, PartyAddress, PartyIdentifier, PartyRole, PartyRoleType, PartyRelationship
    from .models import ChildIdentity
    workspace = require_access(workspace_id, actor, "export")
    if profile not in child_contracts.PROFILES:
        raise PortabilityError("Unsupported child profile.")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    require_access(workspace_id, actor, "export")
    model = {child_contracts.CONTACT: PartyContactMethod, child_contracts.ADDRESS: PartyAddress, child_contracts.IDENTIFIER: PartyIdentifier, child_contracts.ROLE: PartyRole, child_contracts.RELATIONSHIP: PartyRelationship}[profile]
    # Use the same parent-before-child lock order as native Party writes.
    parent_field = "from_party" if profile == child_contracts.RELATIONSHIP else "party"
    candidates = list(model.objects.filter(workspace_id=workspace_id).order_by("pk").values_list("pk", parent_field + "_id")[:MAX_ROWS + 1])
    party_ids = [p for _, p in candidates]
    if profile == child_contracts.RELATIONSHIP:
        party_ids += list(model.objects.filter(workspace_id=workspace_id, pk__in=[pk for pk, _ in candidates]).values_list("to_party_id", flat=True))
    list(Party.objects.select_for_update().filter(workspace_id=workspace_id, pk__in=party_ids).order_by("pk"))
    if profile == child_contracts.ROLE:
        role_ids = model.objects.filter(workspace_id=workspace_id, pk__in=[pk for pk, _ in candidates]).values_list("role_type_id", flat=True)
        list(PartyRoleType.objects.select_for_update().filter(workspace_id=workspace_id, pk__in=role_ids).order_by("pk"))
    objects = list(model.objects.select_related(parent_field).select_for_update(of=("self",)).filter(workspace_id=workspace_id, pk__in=[pk for pk, _ in candidates]).order_by("pk")[:MAX_ROWS + 1])
    if len(objects) > MAX_ROWS:
        raise PortabilityError("Child exports support at most 1,000 records; nothing was truncated.")
    if profile == child_contracts.CONTACT:
        primary_values = {}
        for obj in objects:
            field = children.summary_field({"contact_type": obj.contact_type})
            if obj.is_primary and field:
                values, selected = primary_values.setdefault((obj.party_id, field), (set(), getattr(obj.party, field)))
                values.add(obj.value)
        if any(selected not in values for values, selected in primary_values.values()):
            raise PortabilityError("A Party summary differs from all its primary contacts. Resolve this before a lossless child export.")
    namespace, _ = WorkspaceNamespace.objects.get_or_create(workspace_id=workspace_id)
    records = []
    summary_matches = set()
    for obj in objects:
        parent, _ = PartyIdentity.objects.get_or_create(workspace_id=workspace_id, party_id=children.child_party_id(obj))
        relation = {{child_contracts.CONTACT: "contact", child_contracts.ADDRESS: "address", child_contracts.IDENTIFIER: "identifier", child_contracts.ROLE: "role", child_contracts.RELATIONSHIP: "relationship"}[profile]: obj}
        defaults = {"parent": parent, "profile": profile}
        if profile == child_contracts.RELATIONSHIP:
            if not Party.objects.filter(workspace_id=workspace_id, pk=obj.to_party_id).exists():
                raise PortabilityError("Both relationship Parties must belong to this Workspace.")
            related, _ = PartyIdentity.objects.get_or_create(workspace_id=workspace_id, party_id=obj.to_party_id)
            defaults["related_parent"] = related
        identity, _ = ChildIdentity.objects.get_or_create(workspace_id=workspace_id, **relation, defaults=defaults)
        if profile == child_contracts.RELATIONSHIP and identity.related_parent_id != related.pk:
            raise PortabilityError("A portable relationship destination moved. Resolve its identity before export.")
        if identity.parent_id != parent.pk:
            raise PortabilityError("A portable child moved to another Party. Resolve its identity before export.")
        sources = list(identity.sources.order_by("source_system", "external_id"))
        refs = [{"system": s.source_system, "external_id": s.external_id} for s in sources]
        provenance = identity.import_rows.filter(committed_at__isnull=False).order_by("committed_at", "pk").first()
        recorded = None
        verified = getattr(obj, "is_verified", False)
        if provenance:
            recorded = provenance.canonical.get("source_recorded_at") or provenance.canonical.get("recorded_at")
            verified = verified or provenance.canonical.get("source_is_verified", False)
            for ref in provenance.canonical.get("source_refs", []):
                if ref not in refs:
                    refs.append(ref)
        if len(refs) > 10:
            raise PortabilityError("A child has more than ten source references; export would lose provenance.")
        record = {**child_contracts.semantic(profile, obj), "id": str(identity.public_id),
            "party_source_system": "rokkad:" + str(namespace.public_id), "party_external_id": str(parent.public_id),
            "source_is_verified": verified, "source_recorded_at": recorded,
            "recorded_at": obj.created_at.isoformat(), "source_refs": refs}
        if profile == child_contracts.RELATIONSHIP:
            record.pop("source_is_verified")
            record.update(to_party_source_system="rokkad:" + str(namespace.public_id), to_party_external_id=str(related.public_id))
        if profile == child_contracts.ROLE:
            record.pop("source_is_verified")
            if obj.metadata:
                raise PortabilityError("Role metadata is outside this profile; export cannot omit it silently.")
        if profile == child_contracts.IDENTIFIER:
            if obj.metadata:
                raise PortabilityError("Identifier metadata is outside this profile; no incomplete identifier export was produced.")
            record["source_verified_at"] = (obj.verified_at.isoformat() if obj.verified_at else
                provenance.canonical.get("source_verified_at") if provenance else None)
        records.append(record)
        if profile == child_contracts.CONTACT and obj.is_primary:
            summary = children.summary_field(record)
            if summary and getattr(obj.party, summary) == obj.value:
                summary_matches.add(record["id"])
    content = "".join(dump(r) + "\n" for r in sorted(records, key=lambda r: (r["id"] in summary_matches, r["id"]))).encode("utf-8")
    if len(content) > MAX_BYTES:
        raise PortabilityError("The child export exceeds 5 MiB; nothing was truncated.")
    if content:
        parse_source(content, "children.jsonl")
    result = PartyExport(content, str(namespace.public_id), len(records), hashlib.sha256(content).hexdigest())
    AuditLog.log("DATA_EXPORT", company=workspace, user=actor, description="Exported partial Party child JSONL.",
        data={"profile": profile, "count": result.count, "sha256": result.sha256})
    return result
