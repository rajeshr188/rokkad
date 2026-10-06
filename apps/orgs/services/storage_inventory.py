"""Read-only object-store reconciliation; no upload, download or deletion methods."""
import hashlib
import re
from collections import defaultdict
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import connection, transaction
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, StorageInventoryRun, StorageInventoryObject, WorkspaceStorageUsage
from apps.orgs.services.platform_console import require_console_access
from apps.orgs.services.storage_references import collect_references, validate_coverage
from apps.tenancy.context import workspace_context


class R2Inventory:
    def __init__(self, storage=None):
        self.storage = storage or default_storage
        self.prefix = (getattr(self.storage, "location", "") or "").strip("/")
        # Never scan a bucket root, another deployment or preservation/backup prefixes.
        if not re.fullmatch(r"media/application/(?:production/)?[A-Za-z0-9_-]+", self.prefix):
            raise ValidationError("Inventory requires an explicit application media prefix.")
        self.scope = self.storage.bucket_name + "/" + self.prefix + "/"

    def objects(self):
        prefix = self.prefix + "/"
        client = self.storage.connection.meta.client
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.storage.bucket_name, Prefix=prefix):
            for value in page.get("Contents", []):
                key = value["Key"]
                if not key.startswith(prefix):
                    raise ValidationError("Storage returned an object outside the selected scope.")
                yield {"key": key[len(prefix):], "size": value["Size"], "modified": value["LastModified"]}


def _counter():
    return {"objects": 0, "bytes": 0}


def classify(objects, references, workspace_ids, *, started_at):
    """Disjoint physical totals; shared bytes are never billed or assigned arbitrarily."""
    physical = defaultdict(_counter)
    usage = {pk: {"owned": _counter(), "shared": _counter(), "missing": _counter()} for pk in workspace_ids}
    categories = {pk: defaultdict(_counter) for pk in workspace_ids}
    rows, seen = [], set()
    for obj in objects:
        key = obj["key"]
        if key in seen or len(seen) >= 250000 or len(key) > 1024 or obj["size"] < 0:
            raise ValidationError("Object listing is duplicate, invalid or exceeds the reviewed bound.")
        seen.add(key)
        refs = references.get(key, set())
        owners = {pk for pk, _ in refs if pk is not None}
        labels = {label for _, label in refs}
        # Retention evidence is another reference to the same media, not another
        # media type. Keep it in refs for ownership and deletion protection.
        display_labels = labels - {"historical_evidence"} or labels
        category = next(iter(display_labels)) if len(display_labels) == 1 else "multiple_uses" if display_labels else "unassigned"
        shared = len(owners) > 1 or (owners and any(pk is None for pk, _ in refs))
        modified = obj["modified"]
        if refs:
            state = "shared" if shared else "owned" if owners else "platform"
        else:
            state = "unreferenced_recent" if modified is None or modified >= started_at-timedelta(days=7) else "unreferenced_review"
        physical[state]["objects"] += 1
        physical[state]["bytes"] += obj["size"]
        for pk in owners:
            if pk not in usage:
                raise ValidationError("Workspace inventory changed during reconciliation; retry.")
            bucket = usage[pk]["shared" if shared else "owned"]
            bucket["objects"] += 1
            bucket["bytes"] += obj["size"]
            if not shared:
                categories[pk][category]["objects"] += 1
                categories[pk][category]["bytes"] += obj["size"]
        rows.append(dict(key=key, key_digest=hashlib.sha256(key.encode()).hexdigest(), byte_size=obj["size"],
            modified_at=modified, state=state, category=category, workspace_count=len(owners)))
    for key, refs in references.items():
        if key not in seen:
            physical["missing"]["objects"] += 1
            owners = {pk for pk, _ in refs if pk is not None}
            for pk in owners:
                if pk in usage:
                    usage[pk]["missing"]["objects"] += 1
            rows.append(dict(key=key, key_digest=hashlib.sha256(key.encode()).hexdigest(), state="missing",
                             category="referenced_missing", workspace_count=len(owners)))
    return dict(physical), usage, categories, rows


def reconcile_storage(*, actor, inventory=None):
    require_console_access(actor)
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        if cursor.fetchone() != (False, False):
            raise ValidationError("Storage reconciliation must run under the restricted runtime role.")
    coverage = validate_coverage()
    inventory = inventory or R2Inventory()
    run = StorageInventoryRun.objects.create(actor=actor, scope=inventory.scope)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_xact_lock(721504015)")
                if not cursor.fetchone()[0]:
                    raise ValidationError("Another storage reconciliation is running.")
            ids = list(Company.all_objects.order_by("pk").values_list("pk", flat=True))
            references = collect_references(ids)
            objects = []
            for value in inventory.objects():
                objects.append(value)
                if len(objects) > 250000:
                    raise ValidationError("Object inventory exceeded its reviewed bound.")
            # Union protects references removed/added during listing. This is evidence,
            # not a deletion authorization or an atomic storage/database snapshot.
            for key, refs in collect_references(ids).items():
                references[key].update(refs)
            if ids != list(Company.all_objects.order_by("pk").values_list("pk", flat=True)):
                raise ValidationError("Workspace inventory changed during reconciliation; retry.")
            totals, usage, categories, rows = classify(objects, references, ids, started_at=run.started_at)
            StorageInventoryObject.objects.bulk_create([StorageInventoryObject(run=run, **row) for row in rows], batch_size=1000)
            for pk in ids:
                with workspace_context(pk):
                    WorkspaceStorageUsage.objects.create(workspace_id=pk, run=run, totals=usage[pk],
                        categories=[{"category": key, **counts} for key, counts in sorted(categories[pk].items())])
            run.state = StorageInventoryRun.State.COMPLETE
            run.completed_at = timezone.now()
            run.totals = totals
            run.coverage = {"file_fields": coverage, "historical_sources": ["issued-ticket media", "legacy admission receipts"],
                            "workspace_count": len(ids), "reference_passes": 2, "review_age_days": 7}
            run.save(update_fields=["state", "completed_at", "totals", "coverage"])
            AuditLog.log("STORAGE_INVENTORY", user=actor, description="Read-only storage reconciliation completed",
                         data={"run_id": run.pk, "workspace_count": len(ids)}, success=True)
    except Exception as exc:
        StorageInventoryRun.objects.filter(pk=run.pk).update(state="failed", completed_at=timezone.now(),
            failure_code=type(exc).__name__[:80])
        raise
    return run
