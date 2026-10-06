"""Bounded, offline operator cleanup. Private checkpoints survive DB rollback.

No scheduled purge: external writers must be stopped for execute/restore. Database
table locks additionally protect every registered current/historical reference.
"""
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
import uuid

from botocore.exceptions import ClientError
from django.apps import apps
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import connection, transaction
from django.utils import timezone
from storages.utils import clean_name

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, StorageInventoryRun, StorageInventoryObject
from apps.orgs.services.platform_console import require_console_access
from apps.orgs.services.storage_inventory import R2Inventory
from apps.orgs.services.storage_references import FILE_FIELDS, collect_references, validate_coverage

MAX_OBJECTS = 50
MAX_OBJECT_BYTES = 20 * 1024**2
MAX_BATCH_BYTES = 64 * 1024**2
SALT = "orgs.reviewed-storage-cleanup.v1"
METADATA = ("ContentType", "ContentDisposition", "ContentEncoding", "ContentLanguage", "CacheControl", "Expires", "Metadata")


def fail(message):
    raise ValidationError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def valid_key(key):
    if (not isinstance(key, str) or not key or len(key) > 1024 or key.startswith("/")
            or "\\" in key or any(part in ("", ".", "..") for part in key.split("/"))
            or any(ord(c) < 32 for c in key)):
        fail("Ambiguous object key; manual review required.")
    return key


def private_directory(path):
    """CLI evidence must be outside source/media trees on a private POSIX volume."""
    path = Path(path).absolute()
    if os.name != "posix":
        fail("Run this operator command on the private Linux server volume.")
    if any(p.is_symlink() for p in (path, *path.parents)):
        fail("Recovery directory cannot traverse symlinks.")
    forbidden = [Path(settings.BASE_DIR).resolve()]
    if getattr(settings, "MEDIA_ROOT", ""):
        forbidden.append(Path(settings.MEDIA_ROOT).resolve())
    if not path.is_dir() or any(path.resolve().is_relative_to(p) for p in forbidden):
        fail("Use an existing private directory outside the application/media trees.")
    stat = path.stat()
    if stat.st_uid != os.geteuid() or stat.st_mode & 0o077:
        fail("Recovery directory must be owned by this operator process and mode 0700.")
    return path


class CleanupJournal:
    """One signed, atomic checkpoint containing immutable plan and durable events."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / "state.json"

    def read(self):
        if self.path.is_symlink() or self.path.stat().st_size > 2 * 1024**2:
            fail("Invalid cleanup checkpoint.")
        return signing.loads(self.path.read_text(encoding="utf-8"), salt=SALT)

    def write(self, data):
        if self.directory.is_symlink() or self.path.is_symlink():
            fail("Invalid cleanup checkpoint path.")
        token = signing.dumps(data, salt=SALT)
        temp = self.directory / ("checkpoint-" + uuid.uuid4().hex)
        try:
            with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as output:
                output.write(token)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temp, self.path)
            if os.name == "posix":
                fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temp.unlink(missing_ok=True)

    def event(self, data, actor, action, item=None):
        data["events"].append({"at": timezone.now().isoformat(), "actor_id": actor.pk,
                               "action": action, "item": item})
        if len(data["events"]) > 2000:
            fail("Cleanup event bound exceeded; preserve evidence for manual recovery.")
        self.write(data)


class R2CleanupStore:
    def __init__(self, storage=None):
        self.storage = storage or default_storage
        inventory = R2Inventory(self.storage)
        self.prefix = inventory.prefix + "/"
        self.scope = inventory.scope
        self.bucket = self.storage.bucket_name
        self.client = self.storage.connection.meta.client

    def source_key(self, relative):
        return self.prefix + valid_key(relative)

    def head(self, key):
        try:
            value = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        metadata = {k: value[k] for k in METADATA if k in value}
        if "Expires" in metadata:
            metadata["Expires"] = metadata["Expires"].isoformat()
        return {"bytes": value["ContentLength"], "etag": value["ETag"],
                "modified": value["LastModified"].isoformat(),
                "metadata": metadata}

    def read(self, key, head):
        value = self.client.get_object(Bucket=self.bucket, Key=key, IfMatch=head["etag"])
        with value["Body"] as stream:
            if value["ContentLength"] != head["bytes"] or not 0 <= head["bytes"] <= MAX_OBJECT_BYTES:
                fail("Object size changed or exceeds the cleanup limit.")
            body = stream.read(MAX_OBJECT_BYTES + 1)
        if len(body) != head["bytes"]:
            fail("Incomplete or oversized recovery read.")
        return body

    def put_new(self, key, body, metadata):
        metadata = dict(metadata)
        if "Expires" in metadata:
            metadata["Expires"] = datetime.fromisoformat(metadata["Expires"])
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, IfNoneMatch="*", **metadata)

    def delete(self, key):
        # No unsupported conditional-delete assumption. Offline writers + DB locks
        # are required, with a fresh HEAD immediately before this exact-key delete.
        self.client.delete_object(Bucket=self.bucket, Key=key)


def deployment(store):
    cfg = connection.settings_dict
    return {"scope": store.scope, "database": cfg["NAME"], "host": cfg["HOST"], "port": str(cfg["PORT"])}


@contextmanager
def cleanup_guard(actor, *, references_locked=False):
    require_console_access(actor)
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
            if cursor.fetchone() != (False, False):
                fail("Cleanup requires the restricted runtime database role.")
            cursor.execute("SELECT pg_try_advisory_xact_lock(721504015)")
            if not cursor.fetchone()[0]:
                fail("Another storage operation is running.")
            validate_coverage()
            if references_locked:
                labels = {label for label, _ in FILE_FIELDS} | {"data_portability.legacymediareceipt"}
                tables = sorted({apps.get_model(label)._meta.db_table for label in labels})
                quoted = ", ".join(connection.ops.quote_name(table) for table in tables)
                cursor.execute(f"LOCK TABLE {quoted} IN SHARE MODE NOWAIT")
        yield


def references(store):
    ids = list(Company.all_objects.order_by("pk").values_list("pk", flat=True))
    refs = collect_references(ids)
    if ids != list(Company.all_objects.order_by("pk").values_list("pk", flat=True)):
        fail("Workspace set changed; repeat review.")
    # Fail closed on aliases so normalization cannot conceal an existing reference.
    for key in refs:
        valid_key(key)
        if clean_name(key) != key:
            fail("A media reference needs normalization review.")
    return refs


def load_bound(journal, store):
    data = journal.read()
    if data["plan"]["deployment"] != deployment(store):
        fail("Cleanup plan belongs to a different deployment.")
    return data


def check_references(data, store):
    refs = references(store)
    if any(item["key"] in refs for item in data["plan"]["objects"]):
        fail("A selected object is now referenced; nothing further may be deleted.")


def approval_digest(data):
    return digest({"plan": data["plan"], "recovery": [item.get("sha256") for item in data["items"]]})


def backup_key(data, index):
    return f"recovery/media-cleanup/{data['plan']['id']}/{index:03d}"


def verify_backup(data, index, store):
    head = store.head(backup_key(data, index))
    if not head or head["bytes"] != data["plan"]["objects"][index]["head"]["bytes"]:
        fail("Recovery object missing or size changed.")
    body = store.read(backup_key(data, index), head)
    if hashlib.sha256(body).hexdigest() != data["items"][index]["sha256"]:
        fail("Recovery checksum does not match; preserve source.")
    return body


def verify_manifest(data, store):
    key = f"recovery/media-cleanup/{data['plan']['id']}/manifest.txt"
    head = store.head(key)
    if not head or store.read(key, head) != data.get("recovery_manifest", "").encode():
        fail("Independent recovery manifest is missing or changed.")


def record_summary(actor, data, action):
    AuditLog.log("STORAGE_CLEANUP", user=actor, description=f"Reviewed media cleanup: {action}",
                 data={"plan_id": data["plan"]["id"], "action": action, "objects": len(data["items"]),
                       "digest": approval_digest(data)}, success=True)


def plan_cleanup(*, actor, inventory_id, object_ids, reason, journal, store=None):
    store = store or R2CleanupStore()
    with cleanup_guard(actor):
        if journal.path.exists():
            fail("A cleanup plan already exists at this path.")
        if not reason.strip() or len(reason) > 1000 or not 1 <= len(object_ids) <= MAX_OBJECTS or len(set(object_ids)) != len(object_ids):
            fail("Choose 1–50 distinct candidates and give a retention-review reason.")
        run = StorageInventoryRun.objects.get(pk=inventory_id, state="complete", scope=store.scope)
        if not run.completed_at or run.completed_at < timezone.now() - timedelta(hours=24):
            fail("Use a completed inventory from the last 24 hours.")
        rows = list(StorageInventoryObject.objects.filter(run=run, pk__in=object_ids).order_by("pk"))
        if len(rows) != len(object_ids):
            fail("Candidate selection does not match this inventory.")
        objects = []
        for row in rows:
            if row.state != "unreferenced_review" or row.workspace_count or not row.modified_at or row.modified_at >= timezone.now()-timedelta(days=7):
                fail("Only old, unreferenced review candidates can be selected.")
            head = store.head(store.source_key(row.key))
            if (not head or head["bytes"] != row.byte_size or head["modified"] != row.modified_at.isoformat()
                    or head["bytes"] > MAX_OBJECT_BYTES):
                fail("Candidate metadata changed or size exceeds the reviewed limit.")
            objects.append({"inventory_object_id": row.pk, "key": row.key, "head": head})
        if sum(row["head"]["bytes"] for row in objects) > MAX_BATCH_BYTES:
            fail("Cleanup batch exceeds 64 MiB.")
        data = {"plan": {"version": 1, "id": uuid.uuid4().hex, "actor_id": actor.pk,
                         "deployment": deployment(store), "inventory_id": run.pk, "reason": reason.strip(),
                         "created_at": timezone.now().isoformat(), "recovery_expiry": None, "objects": objects},
                "items": [{"state": "planned"} for _ in objects], "events": []}
        check_references(data, store)
        journal.event(data, actor, "planned")
        record_summary(actor, data, "planned")
        return data


def prepare_cleanup(*, actor, journal, store=None):
    store = store or R2CleanupStore()
    with cleanup_guard(actor):
        data = load_bound(journal, store)
        if any(item["state"] not in ("planned", "prepared") for item in data["items"]):
            fail("This plan has already entered execution; use execute or restore.")
        check_references(data, store)
        for index, obj in enumerate(data["plan"]["objects"]):
            source = store.source_key(obj["key"])
            if store.head(source) != obj["head"]:
                fail("Source changed since review; prepare a new plan.")
            body = store.read(source, obj["head"])
            sha = hashlib.sha256(body).hexdigest()
            if data["items"][index].get("sha256", sha) != sha:
                fail("Source content changed.")
            data["items"][index]["sha256"] = sha
            journal.event(data, actor, "backup_intent", index)
            if store.head(backup_key(data, index)) is None:
                store.put_new(backup_key(data, index), body, {"ContentType": "application/octet-stream",
                              "CacheControl": "private, no-store", "Metadata": {"sha256": sha}})
            verify_backup(data, index, store)
            data["items"][index]["state"] = "prepared"
            journal.event(data, actor, "backup_verified", index)
        if "recovery_manifest" not in data:
            data["recovery_manifest"] = signing.dumps({"plan": data["plan"], "items": data["items"]}, salt=SALT)
            journal.event(data, actor, "manifest_intent")
        key = f"recovery/media-cleanup/{data['plan']['id']}/manifest.txt"
        body = data["recovery_manifest"].encode()
        if store.head(key) is None:
            store.put_new(key, body, {"ContentType": "text/plain", "CacheControl": "private, no-store"})
        if store.read(key, store.head(key)) != body:
            fail("Recovery manifest does not match.")
        journal.event(data, actor, "prepared")
        record_summary(actor, data, "prepared")
        return data


def execute_cleanup(*, actor, journal, approve_digest, writers_stopped, store=None):
    store = store or R2CleanupStore()
    if writers_stopped != store.scope:
        fail("Stop every writer and explicitly acknowledge the exact bucket/prefix.")
    with cleanup_guard(actor, references_locked=True):
        data = load_bound(journal, store)
        if approve_digest != approval_digest(data) or "recovery_manifest" not in data:
            fail("Approval must match the prepared recovery manifest digest.")
        if data.get("restoration_started") or any(item["state"] not in ("prepared", "deleting", "deleted") for item in data["items"]):
            fail("Plan is not ready or has entered restoration; do not replay deletion.")
        verify_manifest(data, store)
        check_references(data, store)
        for index, obj in enumerate(data["plan"]["objects"]):
            verify_backup(data, index, store)
            current = store.head(store.source_key(obj["key"]))
            state = data["items"][index]["state"]
            if state == "deleted":
                if current is not None:
                    fail("A deleted key is occupied again; never delete its replacement.")
            elif current is None and state != "deleting":
                fail("Source disappeared without recorded deletion intent.")
            elif current is not None and current != obj["head"]:
                fail("Source metadata changed; preserve it.")
        journal.event(data, actor, "execution_approved")
        for index, obj in enumerate(data["plan"]["objects"]):
            item = data["items"][index]
            if item["state"] == "deleted":
                continue
            key = store.source_key(obj["key"])
            current = store.head(key)
            if current is not None and current != obj["head"]:
                fail("Source changed immediately before deletion.")
            if current is None and item["state"] != "deleting":
                fail("Source disappeared before deletion intent.")
            item["state"] = "deleting"
            journal.event(data, actor, "delete_intent", index)
            if current is not None:
                store.delete(key)
            if store.head(key) is not None:
                fail("Deletion is not confirmed; retain recovery and retry this plan.")
            item["state"] = "deleted"
            journal.event(data, actor, "deleted", index)
        record_summary(actor, data, "deleted")
        return data


def restore_cleanup(*, actor, journal, approve_digest, writers_stopped, store=None):
    store = store or R2CleanupStore()
    if writers_stopped != store.scope:
        fail("Stop every writer and acknowledge the exact recovery destination scope.")
    with cleanup_guard(actor, references_locked=True):
        data = load_bound(journal, store)
        if approve_digest != approval_digest(data):
            fail("Restoration approval must match the prepared manifest digest.")
        verify_manifest(data, store)
        if not all(item["state"] in ("prepared", "deleting", "deleted", "restoring", "restored") for item in data["items"]):
            fail("Recovery has not been prepared.")
        # Persist a one-way restoration boundary even for an interrupted partial run.
        data["restoration_started"] = True
        journal.event(data, actor, "restore_approved")
        for index, obj in enumerate(data["plan"]["objects"]):
            item = data["items"][index]
            body = verify_backup(data, index, store)
            key = store.source_key(obj["key"])
            current = store.head(key)
            if current is not None:
                # Only reconcile our own prior restore or the untouched original.
                if item["state"] in ("restoring", "restored"):
                    if hashlib.sha256(store.read(key, current)).hexdigest() != item["sha256"] or current["metadata"] != obj["head"]["metadata"]:
                        fail("Restore destination is occupied by different content or metadata.")
                elif item["state"] not in ("prepared", "deleting") or current != obj["head"]:
                    fail("Restore destination is occupied; never overwrite it.")
            else:
                if item["state"] == "prepared":
                    fail("An unexecuted source is missing; investigate before restoring.")
                item["state"] = "restoring"
                journal.event(data, actor, "restore_intent", index)
                store.put_new(key, body, obj["head"]["metadata"])
                current = store.head(key)
                if not current or hashlib.sha256(store.read(key, current)).hexdigest() != item["sha256"]:
                    fail("Restored content could not be verified.")
            item["state"] = "restored"
            journal.event(data, actor, "restored", index)
        record_summary(actor, data, "restored")
        return data
