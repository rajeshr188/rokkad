"""Validate the released Party ZIP envelope before atomic, review-only staging."""
import hashlib
import io
import stat
import struct
import uuid
import zipfile
import zlib

from django.db import transaction
from django.utils.dateparse import parse_datetime

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from . import bundles, child_contracts, contracts, services
from .access import require_access
from .models import ImportBatch, ImportBundle
from .parsers import MAX_BYTES, MAX_ROWS, PortabilityError, decode_json, parse_source

MAX_BUNDLE_BYTES = 31 * 1024 * 1024
MAX_METADATA_BYTES = 128 * 1024
ENTITIES = [{"profile": profile, "path": f"entities/{profile.split('/')[0]}.jsonl",
             "schema": f"schema/{profile.split('/')[0]}-v1.schema.json"} for profile in bundles.PROFILES]
MEMBERS = {"manifest.json", "README.txt", *(e["path"] for e in ENTITIES), *(e["schema"] for e in ENTITIES)}


def _require(condition):
    if not condition:
        raise PortabilityError("The ZIP does not match the supported Party bundle contract. Nothing was staged.")


def _object(value, keys):
    _require(isinstance(value, dict) and set(value) == set(keys))


def _uuid(value):
    _require(isinstance(value, str))
    try:
        _require(str(uuid.UUID(value)) == value)
    except (ValueError, AttributeError) as exc:
        raise PortabilityError("Invalid bundle identity. Nothing was staged.") from exc
    return value


def _read_members(content):
    _require(isinstance(content, bytes) and 22 <= len(content) <= MAX_BUNDLE_BYTES)
    # Our exporter emits an ordinary, single-disk ZIP with no comment. Bound the
    # directory before ZipFile allocates entries; ZIP64 and appended data fail.
    end = struct.unpack("<4s4H2LH", content[-22:])
    _require(end[0] == b"PK\x05\x06" and end[1:5] == (0, 0, 14, 14) and end[7] == 0)
    _require(end[5] <= 16384 and end[6] + end[5] == len(content) - 22)
    _require(content.startswith(b"PK\x03\x04"))
    members = {}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = archive.infolist()
        _require(len(infos) == 14 and {i.filename for i in infos} == MEMBERS)
        _require(sum(i.file_size for i in infos) <= MAX_BUNDLE_BYTES)
        for info in infos:
            limit = MAX_BYTES if info.filename.startswith("entities/") else MAX_METADATA_BYTES
            mode = stat.S_IFMT(info.external_attr >> 16)
            _require(info.orig_filename == info.filename and not info.is_dir() and mode in (0, stat.S_IFREG))
            _require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))
            _require(0 <= info.file_size <= limit)
            with archive.open(info) as source:
                data = source.read(limit + 1)
            _require(len(data) == info.file_size and len(data) <= limit)
            members[info.filename] = data
    return members


def parse_bundle(content):
    try:
        members = _read_members(content)
        manifest = decode_json(members["manifest.json"].decode("utf-8"))
        _object(manifest, ("format", "profile", "source_namespace", "scope", "snapshot", "entities",
                           "import_order", "zip_import_supported", "exclusions", "limits", "files"))
        _require(manifest["format"] == "rokkad-data" and manifest["profile"] == bundles.PROFILE and manifest["scope"] == "PARTIAL")
        namespace = _uuid(manifest["source_namespace"])
        _require(type(manifest["zip_import_supported"]) is bool)  # Older exports correctly described the old app capability.
        _require(manifest["exclusions"] == bundles.EXCLUSIONS)
        snapshot = manifest["snapshot"]
        _object(snapshot, ("consistency", "captured_at"))
        _require(snapshot["consistency"] == "workspace-row-locks" and isinstance(snapshot["captured_at"], str))
        captured = parse_datetime(snapshot["captured_at"])
        _require(captured is not None and captured.utcoffset() is not None)
        limits = manifest["limits"]
        _require(isinstance(limits, dict) and set(limits) in ({"records_per_profile", "bytes_per_profile"}, {"records_per_profile", "bytes_per_profile", "role_types"}))
        _require(all(type(v) is int for v in limits.values()) and limits["records_per_profile"] == MAX_ROWS and limits["bytes_per_profile"] == MAX_BYTES)
        _require(limits.get("role_types", MAX_ROWS) == MAX_ROWS)
        _require(manifest["import_order"] == [e["path"] for e in ENTITIES])
        files = manifest["files"]
        _require(isinstance(files, list) and len(files) == 13)
        indexed = set()
        for entry in files:
            _object(entry, ("path", "bytes", "sha256"))
            path = entry["path"]
            _require(isinstance(path, str) and path in MEMBERS - {"manifest.json"} and path not in indexed)
            indexed.add(path)
            _require(type(entry["bytes"]) is int and entry["bytes"] == len(members[path]))
            _require(entry["sha256"] == hashlib.sha256(members[path]).hexdigest())
        _require(isinstance(manifest["entities"], list) and len(manifest["entities"]) == 6)
        rows_by_profile = {}
        for expected, entity in zip(ENTITIES, manifest["entities"]):
            _object(entity, ("profile", "path", "schema", "count", "coverage"))
            _require(all(entity[k] == v for k, v in expected.items()))
            _require(type(entity["count"]) is int and 0 <= entity["count"] <= MAX_ROWS)
            _require(entity["coverage"] == ("INCLUDED" if entity["count"] else "EMPTY"))
            profile = entity["profile"]
            schema = contracts.schema() if profile == contracts.PROFILE else child_contracts.schema(profile)
            _require(decode_json(members[entity["schema"]].decode("utf-8")) == schema)
            data = members[entity["path"]]
            rows = parse_source(data, entity["path"])[3] if data else []
            _require(len(rows) == entity["count"])
            ids = [_uuid(row.get("id")) for _, row in rows]
            _require(len(set(ids)) == len(ids))
            rows_by_profile[profile] = rows
        masters = {row["id"] for _, row in rows_by_profile[contracts.PROFILE]}
        for profile in child_contracts.PROFILES:
            for _, row in rows_by_profile[profile]:
                _require(row.get("party_source_system") == "rokkad:" + namespace and row.get("party_external_id") in masters)
                if profile == child_contracts.RELATIONSHIP:
                    _require(row.get("to_party_source_system") == "rokkad:" + namespace and row.get("to_party_external_id") in masters)
        members["README.txt"].decode("utf-8")  # Never execute or render uploaded instructions/schema.
        return manifest, members
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, UnicodeError, EOFError,
            OSError, RuntimeError, ValueError, TypeError, OverflowError, struct.error) as exc:
        if isinstance(exc, PortabilityError):
            raise
        raise PortabilityError("Malformed or unsupported Party ZIP bundle. Nothing was staged.") from exc


def stage_bundle_history(*, workspace_id, actor, content):
    require_access(workspace_id, actor, "import")
    manifest, members = parse_bundle(content)
    with transaction.atomic():
        Company.all_objects.select_for_update().get(pk=workspace_id)
        workspace = require_access(workspace_id, actor, "import")
        count = sum(e["count"] > 0 for e in manifest["entities"])
        unfinished = ImportBatch.objects.filter(workspace_id=workspace_id, state__in=["NEEDS_MAPPING", "READY"]).count()
        if unfinished + count > 20:
            raise PortabilityError("Cancel unfinished batches to make room for this bundle (20 unfinished batches maximum). Nothing was staged.")
        results = []
        for entity in manifest["entities"]:
            batch = None
            if entity["count"]:
                batch = services.stage_import(workspace_id=workspace_id, actor=actor,
                    content=members[entity["path"]], filename=entity["path"],
                    source_system=manifest["source_namespace"], profile=entity["profile"])
                batch = services.validate_import(workspace_id=workspace_id, actor=actor, batch_id=batch.public_id, mapping={})
            results.append((entity["profile"], batch))
        AuditLog.log("DATA_IMPORT", company=workspace, user=actor,
            description="Validated and staged Party bundle for separate profile review; no Party data committed.",
            data={"profile": bundles.PROFILE, "sha256": hashlib.sha256(content).hexdigest(),
                  "source_namespace": manifest["source_namespace"],
                  "batches": {profile: str(batch.public_id) if batch else None for profile, batch in results}})
        return ImportBundle.objects.create(workspace_id=workspace_id, created_by=actor,
            source_namespace=manifest["source_namespace"], source_sha256=hashlib.sha256(content).hexdigest(),
            **{field: batch for field, (_, batch) in zip(ImportBundle.PROFILE_FIELDS, results)})


def stage_bundle(*, workspace_id, actor, content):
    """Preserve the existing service's ordered profile/batch result."""
    return stage_bundle_history(workspace_id=workspace_id, actor=actor, content=content).profile_batches()
