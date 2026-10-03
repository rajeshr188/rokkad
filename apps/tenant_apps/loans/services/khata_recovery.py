"""Native, exact-identity khata disaster recovery; never a paper-account importer.

Restore is an offline table-owner operation into an empty khata Workspace in a
matching restored database. Runtime code cannot disable evidence triggers. The
independently retained ZIP checksum is mandatory; this is a trusted backup, not
an admission path for edited or third-party financial records.
"""
import hashlib
import json
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from django.apps import apps
from django.core.files.base import ContentFile
from django.db import connection
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataAccount
from apps.tenant_apps.loans.selectors.khata import account_position, interest_schedule, held_items, eligible_items
from .action_access import require_workspace_action

FORMAT = "khata-native-recovery/1"
MODEL_NAMES = ("KhataSeries", "KhataSeriesStatusChange", "KhataPolicyRevision", "KhataAccount", "KhataAgreementRevision",
    "KhataOperation", "KhataCollateralItem", "KhataCollateralValuation", "KhataCollateralSelection",
    "KhataInterestPeriod", "KhataInterestSegment", "KhataInterestAllocation", "KhataCollateralPhoto", "KhataDocumentIssue")
MAX_BYTES = 256 * 1024 * 1024
MAX_ROWS = 50000


class _PreviewRollback(Exception):
    def __init__(self, result):
        self.result = result


def _models():
    return tuple(apps.get_model("loans", name) for name in MODEL_NAMES)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _row(obj, fields=None):
    fields = fields or obj._meta.concrete_fields
    return {f.attname: None if getattr(obj, f.attname) is None else
        f.value_from_object(obj) if f.get_internal_type() == "JSONField" else f.value_to_string(obj) for f in fields}


def _schema():
    return {m._meta.label: [[f.attname, f.get_internal_type(), f.max_length,
        getattr(f, "max_digits", None), getattr(f, "decimal_places", None)] for f in m._meta.concrete_fields] for m in _models()}


def _guards():
    """Refuse same-field schemas whose financial guard definitions have changed."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid), pg_get_functiondef(t.tgfoid) "
            "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE t.tgrelid = ANY(%s::regclass[]) "
            "AND NOT t.tgisinternal ORDER BY c.relname, t.tgname", [[m._meta.db_table for m in _models()]])
        return _digest(_json(cursor.fetchall()))


def _identity(workspace):
    return dict(id=workspace.pk, slug=workspace.slug, schema_name=workspace.schema_name)


def _reference(obj):
    # Authentication secrets and mutable login details are never backup content.
    if obj._meta.app_label == "auth" or obj._meta.label == apps.get_model("loans", "KhataAccount")._meta.get_field("created_by").related_model._meta.label:
        fields = [obj._meta.pk, obj._meta.get_field(obj.USERNAME_FIELD), obj._meta.get_field("date_joined")]
        data = _row(obj, fields)
    elif isinstance(obj, Company):
        data = _identity(obj)
    else:
        data = _row(obj)
    return dict(model=obj._meta.label, id=obj.pk, sha256=_digest(_json(data)))


def _parent_account(obj):
    if obj._meta.label not in _schema():
        return None
    if isinstance(obj, KhataAccount):
        return obj.pk
    if hasattr(obj, "account_id"):
        return obj.account_id
    if hasattr(obj, "period_id"):
        return obj.period.account_id
    if hasattr(obj, "item_id"):
        return obj.item.account_id
    return None


def _position(workspace, as_of):
    rows = []
    for account in KhataAccount.objects.filter(workspace=workspace).order_by("pk"):
        position = account_position(account)
        schedule = interest_schedule(account, as_of) if position else []
        rows.append(dict(id=account.pk, state=account.state,
            principal=str(position.principal) if position else "0",
            unused=str(position.unused) if position else "0",
            interest=str(sum((p["outstanding"] for p in schedule), start=Decimal(0))),
            due_interest=str(sum((p["outstanding"] for p in schedule if p["due_on"] <= as_of), start=Decimal(0))),
            held=sorted(held_items(account).values_list("pk", flat=True)),
            eligible=sorted(eligible_items(account).values_list("pk", flat=True)),
            schedule=[{k: str(p[k]) for k in ("index", "start_on", "end_on", "due_on", "charge", "paid", "outstanding")} for p in schedule]))
    return rows


def _lock(workspace):
    Company.objects.select_for_update().get(pk=workspace.pk)
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE " + ", ".join(connection.ops.quote_name(m._meta.db_table) for m in _models()) + " IN SHARE ROW EXCLUSIVE MODE")


def export_archive(*, workspace, actor):
    """Capture all khata rows and original file bytes under a stable write lock."""
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.export")
        _lock(workspace)
        tables, references, files = {}, {}, {}
        count = 0
        file_bytes = 0
        for model in _models():
            rows = []
            for obj in model.objects.filter(workspace=workspace).order_by("pk").iterator():
                count += 1
                if count > MAX_ROWS:
                    raise ValueError("Khata archive exceeds the bounded row count; use full database/media recovery.")
                rows.append(_row(obj))
                for field in model._meta.concrete_fields:
                    if field.is_relation and field.related_model not in _models() and getattr(obj, field.attname) is not None:
                        related = getattr(obj, field.name)
                        if hasattr(related, "workspace_id") and related.workspace_id != workspace.pk:
                            raise ValueError("Khata prerequisite belongs to another Workspace.")
                        references[(related._meta.label, related.pk)] = _reference(related)
                    if field.get_internal_type() == "FileField":
                        value = getattr(obj, field.name)
                        with value.open("rb") as stream:
                            content = stream.read(MAX_BYTES + 1)
                        digest_field = "artifact_sha256" if field.name == "artifact" else "sha256"
                        if len(content) != obj.byte_size or _digest(content) != getattr(obj, digest_field):
                            raise ValueError("Retained khata file is missing or corrupt.")
                        if value.name not in files:
                            file_bytes += len(content)
                            if file_bytes > MAX_BYTES:
                                raise ValueError("Khata media exceeds the bounded archive size.")
                        files[value.name] = content
            tables[model._meta.label] = rows
        manifest = dict(format=FORMAT, workspace=_identity(workspace), exported_at=timezone.now().isoformat(),
            as_of=timezone.localdate().isoformat(), schema=_schema(), guards_sha256=_guards(), tables=tables,
            prerequisites=sorted(references.values(), key=lambda r: (r["model"], r["id"])),
            reconciliation=_position(workspace, timezone.localdate()),
            files={name: dict(size=len(content), sha256=_digest(content)) for name, content in files.items()})
        raw = _json(manifest)
        if len(raw) + sum(map(len, files.values())) > MAX_BYTES:
            raise ValueError("Khata archive exceeds the bounded byte size; use full database/media recovery.")
        buffer = BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", raw)
            for name, content in files.items():
                archive.writestr("media/" + name, content)
        return buffer.getvalue()


def _read(content, expected_sha256):
    if not expected_sha256 or _digest(content) != expected_sha256.lower():
        raise ValueError("Archive SHA-256 does not match the independently retained backup checksum.")
    if len(content) > MAX_BYTES:
        raise ValueError("Archive is too large.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or sum(i.file_size for i in archive.infolist()) > MAX_BYTES:
                raise ValueError("Duplicate ZIP members or excessive expanded archive size.")
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name:
                    raise ValueError("Unsafe archive member path.")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest["format"] != FORMAT or manifest["schema"] != _schema() or manifest["guards_sha256"] != _guards():
                raise ValueError("Unsupported recovery format or changed model schema.")
            if set(manifest["tables"]) != set(_schema()) or sum(map(len, manifest["tables"].values())) > MAX_ROWS:
                raise ValueError("Incorrect recovery table inventory or excessive rows.")
            if set(names) != {"manifest.json", *("media/" + name for name in manifest["files"])}:
                raise ValueError("Archive file inventory differs from its manifest.")
            files = {}
            for name, evidence in manifest["files"].items():
                data = archive.read("media/" + name)
                if len(data) != evidence["size"] or _digest(data) != evidence["sha256"]:
                    raise ValueError("Archive media bytes differ from their manifest.")
                files[name] = data
            return manifest, files
    except (BadZipFile, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid native khata archive.") from exc


def _owner_only():
    with connection.cursor() as cursor:
        cursor.execute("SELECT c.relname, pg_has_role(current_user, c.relowner, 'USAGE') FROM pg_class c WHERE c.oid = ANY(%s::regclass[])",
            [[m._meta.db_table for m in _models()]])
        result = cursor.fetchall()
        if len(result) != len(MODEL_NAMES) or not all(owns for _, owns in result):
            raise ValueError("Khata restore requires the offline table-owner connection, never the runtime role.")
        cursor.execute("SELECT tgname, tgenabled FROM pg_trigger WHERE tgrelid = ANY(%s::regclass[]) AND NOT tgisinternal",
            [[m._meta.db_table for m in _models()]])
        if any(enabled != "O" for _, enabled in cursor.fetchall()):
            raise ValueError("Khata evidence triggers must all be enabled before recovery.")


def restore_archive(*, workspace, actor, content, expected_sha256, commit=False):
    """Preview by performing and rolling back an exact restore and reconciliation.

    The destination must contain no khata rows. All prerequisite identities must
    already match from full database recovery. No merge, key remapping, historical
    cash replay or ordinary-loan numbering mutation is supported.
    """
    manifest, files = _read(content, expected_sha256)
    if manifest["workspace"] != _identity(workspace):
        raise ValueError("Restore requires the original Workspace identity in a recovered database.")
    created = []
    try:
        with workspace_context(workspace.pk):
            require_workspace_action(workspace, actor, "workspace.transfer", "data.export")
            _owner_only()
            _lock(workspace)
            for model in _models():
                if model.objects.filter(workspace=workspace).exists():
                    raise ValueError("Destination already contains khata evidence; restore never overwrites or merges it.")
            for evidence in manifest["prerequisites"]:
                model = apps.get_model(evidence["model"])
                obj = model._base_manager.filter(pk=evidence["id"]).first()
                if obj is None or _reference(obj) != evidence:
                    raise ValueError("A required Workspace, borrower, actor, licence or rate identity differs from the backup.")
            # PostgreSQL enforces owner-only ALTER TABLE. FK/CHECK/UNIQUE and forced
            # RLS stay enabled. Restore preserves final projections, not fake events.
            with connection.cursor() as cursor:
                for model in _models():
                    cursor.execute(f"ALTER TABLE {connection.ops.quote_name(model._meta.db_table)} DISABLE TRIGGER USER")
                for model in _models():
                    fields = model._meta.concrete_fields
                    expected_fields = {f.attname for f in fields}
                    columns = ", ".join(connection.ops.quote_name(f.column) for f in fields)
                    for row in manifest["tables"][model._meta.label]:
                        if set(row) != expected_fields or int(row["workspace_id"]) != workspace.pk:
                            raise ValueError("Recovery row inventory or Workspace ownership mismatch.")
                        values = [f.get_db_prep_save(f.target_field.to_python(row[f.attname]) if f.is_relation else f.to_python(row[f.attname]), connection=connection) for f in fields]
                        cursor.execute(f"INSERT INTO {connection.ops.quote_name(model._meta.db_table)} ({columns}) VALUES ({', '.join(['%s'] * len(fields))})", values)
                connection.check_constraints()
                # Validate all typed references while rows are visible under RLS.
                for model in _models():
                    for obj in model.objects.filter(workspace=workspace).iterator():
                        parent_accounts = {_parent_account(obj)} - {None}
                        for field in model._meta.concrete_fields:
                            if field.is_relation and getattr(obj, field.attname) is not None:
                                related = getattr(obj, field.name)
                                if hasattr(related, "workspace_id") and related.workspace_id != workspace.pk:
                                    raise ValueError("Recovery reference crosses Workspace ownership.")
                                parent_accounts.add(_parent_account(related))
                        if len(parent_accounts - {None}) > 1:
                            raise ValueError("Recovery reference crosses khata accounts.")
                        for field in model._meta.concrete_fields:
                            if field.get_internal_type() != "FileField":
                                continue
                            file = getattr(obj, field.name)
                            if not file.name.startswith(f"loans/khata/{workspace.pk}/") or file.name not in files:
                                raise ValueError("Recovery file is outside this Workspace or absent from the archive.")
                            data = files[file.name]
                            hash_field = "artifact_sha256" if field.name == "artifact" else "sha256"
                            if len(data) != obj.byte_size or _digest(data) != getattr(obj, hash_field):
                                raise ValueError("Recovery file differs from its typed source evidence.")
                            if field.name == "artifact" and _digest(_json(obj.payload)) != obj.payload_sha256:
                                # Existing documents use ASCII-escaped canonical JSON.
                                from .khata_accounts import _hash
                                if _hash(obj.payload) != obj.payload_sha256:
                                    raise ValueError("Recovery document payload differs from retained evidence.")
                            if file.storage.exists(file.name):
                                with file.storage.open(file.name, "rb") as stream:
                                    original = stream.read(len(data) + 1)
                                if original != data:
                                    raise ValueError("Existing destination media conflicts with the backup.")
                            elif commit:
                                saved = file.storage.save(file.name, ContentFile(data))
                                created.append((file.storage, saved))
                                if saved != file.name:
                                    raise ValueError("Destination media was concurrently created; exact restore refused.")
                if _position(workspace, date.fromisoformat(manifest["as_of"])) != manifest["reconciliation"]:
                    raise ValueError("Restored principal, entitlement, interest or custody differs from the backup.")
                for model in _models():
                    cursor.execute(f"ALTER TABLE {connection.ops.quote_name(model._meta.db_table)} ENABLE TRIGGER USER")
                    if commit:
                        # Explicit restored PKs must not collide with future IDs;
                        # sequence values never move backwards, including rollback.
                        table = model._meta.db_table
                        cursor.execute("SELECT pg_get_serial_sequence(%s, 'id')", [table])
                        sequence = cursor.fetchone()[0]
                        cursor.execute(f"SELECT max(id) FROM {connection.ops.quote_name(table)}")
                        maximum = cursor.fetchone()[0] or 1
                        cursor.execute("SELECT pg_sequence_last_value(%s::regclass)", [sequence])
                        current = cursor.fetchone()[0] or 1
                        cursor.execute("SELECT setval(%s::regclass, %s, true)", [sequence, max(maximum, current)])
            result = dict(format=FORMAT, workspace=workspace.pk, committed=commit,
                rows={name: len(rows) for name, rows in manifest["tables"].items()},
                media=len(files), reconciliation=manifest["reconciliation"], sha256=_digest(content))
            if not commit:
                raise _PreviewRollback(result)
            return result
    except _PreviewRollback as preview:
        return preview.result
    except BaseException:
        for storage, name in reversed(created):
            storage.delete(name)
        raise
