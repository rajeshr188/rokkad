"""Bounded Party bundles. All bytes are built while the snapshot locks are held."""
import hashlib
import io
import zipfile

from django.db import OperationalError, transaction
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.party.models import (
    Party, PartyAddress, PartyContactMethod, PartyIdentifier, PartyRelationship,
    PartyRole, PartyRoleType,
)
from . import child_contracts, contracts, services
from .access import require_access
from .parsers import MAX_BYTES, MAX_ROWS, PortabilityError

PROFILE = "party-bundle/1"
PROFILES = (contracts.PROFILE, *child_contracts.PROFILES)
EXCLUSIONS = ["Loans", "Binary files and KYC documents", "Party metadata",
              "Party role-type definitions", "Workspace settings and access grants",
              "Mapping presets", "Other business apps"]
README = """Rokkad partial Party bundle v1

This is private customer data, not a complete Workspace backup.
manifest.json lists coverage, counts, byte sizes and SHA-256 checksums.
All six entity files describe one lock-stabilized database snapshot.
Schemas describe each existing JSONL profile; no business schema is changed.

Upload this ZIP on Import Party data to stage nonempty profiles for separate
review. The staging results also offer combined review and one atomic commit
for wholly unfinished bundles, with explicit role-type mapping. Or extract JSONL
files and import them in manifest import_order, starting
with Party master. After committing master, revalidate child previews. Supply the
manifest source_namespace as the source system. Review each preview and commit;
Party roles require explicit destination role-type mapping. Empty files mean
zero records and should be skipped. Existing import permissions, warnings,
conflict checks and identity-based replay rules still apply. Source namespace
is lineage, never authority to choose the destination Workspace.

Excluded: Loans, files/KYC, Party metadata, role-type definitions, Workspace
settings/access grants, mapping presets and other business apps. Retain the
manifest with the extracted files. Checksums detect changes, not authenticity.
""".encode("utf-8")


def _lock_snapshot(workspace_id):
    # FOR UPDATE on Company conflicts with the FK key-share checks of new
    # Workspace-owned rows, including deferred checks at commit. Lock existing
    # business rows against updates/deletes before reading any export fields.
    # NOWAIT avoids deadlocks with native writers that acquired a Party first.
    Company.all_objects.select_for_update(nowait=True).get(pk=workspace_id)
    for model in (Party, PartyRoleType, PartyContactMethod, PartyAddress,
                  PartyIdentifier, PartyRole, PartyRelationship):
        ids = list(model.objects.filter(workspace_id=workspace_id).order_by("pk")
                   .select_for_update(nowait=True).values_list("pk", flat=True)[:MAX_ROWS + 1])
        if len(ids) > MAX_ROWS:
            raise PortabilityError("The bundle supports at most 1,000 records per Party profile and 1,000 role types; nothing was exported.")


def export_bundle(*, workspace_id, actor):
    require_access(workspace_id, actor, "export")
    try:
        with transaction.atomic():
            _lock_snapshot(workspace_id)
            workspace = require_access(workspace_id, actor, "export")
            captured_at = timezone.now().isoformat()
            members, entities = {}, []
            namespace = None
            for profile in PROFILES:
                result = (services.export_parties(workspace_id=workspace_id, actor=actor)
                          if profile == contracts.PROFILE else services.export_children(
                              workspace_id=workspace_id, actor=actor, profile=profile))
                namespace = result.namespace
                name = profile.split("/")[0]
                path, schema_path = f"entities/{name}.jsonl", f"schema/{name}-v1.schema.json"
                members[path] = result.content
                members[schema_path] = (contracts.dump(contracts.schema() if profile == contracts.PROFILE
                    else child_contracts.schema(profile)) + "\n").encode("utf-8")
                entities.append({"profile": profile, "path": path, "schema": schema_path,
                                 "count": result.count, "coverage": "EMPTY" if not result.count else "INCLUDED"})
            members["README.txt"] = README
            manifest = {
                "format": "rokkad-data", "profile": PROFILE, "source_namespace": namespace,
                "scope": "PARTIAL", "snapshot": {"consistency": "workspace-row-locks", "captured_at": captured_at},
                "entities": entities, "import_order": [e["path"] for e in entities],
                "zip_import_supported": True, "exclusions": EXCLUSIONS,
                "limits": {"records_per_profile": MAX_ROWS, "bytes_per_profile": MAX_BYTES, "role_types": MAX_ROWS},
                "files": [{"path": path, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
                          for path, content in members.items()],
            }
            members["manifest.json"] = (contracts.dump(manifest) + "\n").encode("utf-8")
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path, content in members.items():
                    archive.writestr(path, content)
            content = buffer.getvalue()
            result = services.PartyExport(content, namespace, sum(e["count"] for e in entities),
                                          hashlib.sha256(content).hexdigest())
            AuditLog.log("DATA_EXPORT", company=workspace, user=actor,
                description="Exported partial Party bundle from one locked snapshot.",
                data={"profile": PROFILE, "count": result.count, "sha256": result.sha256})
            return result
    except OperationalError as exc:
        if getattr(exc.__cause__, "pgcode", None) in {"55P03", "40P01"} or getattr(exc.__cause__, "sqlstate", None) in {"55P03", "40P01"}:
            raise PortabilityError("Party data is being edited. Retry the bundle export shortly; nothing was exported.") from exc
        raise
