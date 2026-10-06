import copy
import hashlib
import io
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import timedelta

from botocore.exceptions import ClientError
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from apps.orgs import test_platform_console as console_tests
from apps.orgs.models import StorageInventoryObject
from apps.orgs.services.storage_inventory import reconcile_storage
from apps.orgs.services.storage_cleanup import (
    CleanupJournal, R2CleanupStore, approval_digest, backup_key, cleanup_guard,
    execute_cleanup, plan_cleanup, prepare_cleanup, restore_cleanup, valid_key,
)
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party


class MemoryStore:
    """Deterministic private object store with injectable uncertain outcomes."""
    scope = "fixture/media/application/cleanup-test/"
    prefix = "media/application/cleanup-test/"

    def __init__(self):
        self.objects = {}
        self.deleted = []
        self.after_delete = None
        self.before_delete = None
        self.after_put = None

    def source_key(self, relative):
        return self.prefix + valid_key(relative)

    def seed(self, key, body=b"synthetic picture", *, old=False, metadata=None):
        self.objects[key] = (body, {"bytes": len(body), "etag": hashlib.md5(body).hexdigest(),
            "modified": (timezone.now()-timedelta(days=10) if old else timezone.now()).isoformat(),
            "metadata": metadata or {"ContentType": "image/jpeg", "Metadata": {}}})

    def head(self, key):
        return copy.deepcopy(self.objects[key][1]) if key in self.objects else None

    def read(self, key, head):
        assert head == self.head(key)
        return self.objects[key][0]

    def put_new(self, key, body, metadata):
        if key in self.objects:
            raise RuntimeError("PreconditionFailed")
        self.seed(key, body, metadata=metadata)
        if self.after_put:
            self.after_put(key)

    def delete(self, key):
        if self.before_delete:
            self.before_delete(key)
        del self.objects[key]
        self.deleted.append(key)
        if self.after_delete:
            self.after_delete(key)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class CleanupTests(TestCase):
    make_workspace = console_tests.PlatformConsoleTests.make_workspace

    @classmethod
    def setUpClass(cls):
        # Committed before TestCase's wrapping transactions so a second connection
        # can use this restricted role without waiting on fixture ACL changes.
        cls.writer_role = connection.ops.quote_name("cleanup_writer_" + uuid.uuid4().hex)
        with connection.cursor() as c:
            c.execute(f"CREATE ROLE {cls.writer_role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            c.execute(f"GRANT USAGE ON SCHEMA public TO {cls.writer_role}")
            c.execute(f'GRANT SELECT, UPDATE ON "party_party" TO {cls.writer_role}')
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        with connection.cursor() as c:
            c.execute(f"DROP OWNED BY {cls.writer_role}")
            c.execute(f"DROP ROLE {cls.writer_role}")

    def setUp(self):
        console_tests.PlatformConsoleTests.setUp(self)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal = CleanupJournal(self.temp.name)
        self.store = MemoryStore()
        self.store.seed(self.store.source_key("synthetic-a.jpg"), old=True)
        self.store.seed(self.store.source_key("synthetic-b.jpg"), old=True)
        rows = [{"key": key[len(self.store.prefix):], "size": head["bytes"],
                 "modified": timezone.datetime.fromisoformat(head["modified"])}
                for key, (_, head) in self.store.objects.items()]
        self.run = reconcile_storage(actor=self.admin,
            inventory=SimpleNamespace(scope=self.store.scope, objects=lambda: iter(rows)))
        self.ids = list(StorageInventoryObject.objects.filter(run=self.run).values_list("pk", flat=True))

    def make_plan(self, **kw):
        args = dict(actor=self.admin, inventory_id=self.run.pk, object_ids=self.ids,
                    reason="Synthetic fixtures; reviewed retention", journal=self.journal, store=self.store)
        args.update(kw)
        return plan_cleanup(**args)

    def prepare(self):
        self.make_plan()
        return prepare_cleanup(actor=self.admin, journal=self.journal, store=self.store)

    def execute(self, **kw):
        args = dict(actor=self.admin, journal=self.journal, store=self.store,
                    approve_digest=approval_digest(self.journal.read()), writers_stopped=self.store.scope)
        args.update(kw)
        return execute_cleanup(**args)

    def restore(self):
        return restore_cleanup(actor=self.admin, journal=self.journal, store=self.store,
            approve_digest=approval_digest(self.journal.read()), writers_stopped=self.store.scope)

    def test_full_journey_preserves_bytes_metadata_and_recovery(self):
        originals = copy.deepcopy(self.store.objects)
        prepared = self.prepare()
        token = approval_digest(prepared)
        self.assertEqual(len(self.store.deleted), 0)
        self.assertEqual([i["state"] for i in self.execute()["items"]], ["deleted", "deleted"])
        self.assertEqual([i["state"] for i in self.restore()["items"]], ["restored", "restored"])
        for key, (body, head) in originals.items():
            self.assertEqual(self.store.objects[key][0], body)
            self.assertEqual(self.store.head(key)["metadata"], head["metadata"])
        self.assertEqual(approval_digest(self.journal.read()), token)
        self.assertIsNotNone(self.store.head(backup_key(prepared, 0)))
        with self.assertRaises(ValidationError):
            self.execute()

    def test_unauthorized_and_workspace_scoped_operators_cannot_plan(self):
        for actor in (None, self.owner):
            with self.assertRaises(PermissionDenied):
                self.make_plan(actor=actor)
        with workspace_context(self.workspace.pk), self.assertRaises(PermissionDenied):
            self.make_plan()
        self.admin.is_active = False
        with self.assertRaises(PermissionDenied):
            self.make_plan()
        self.assertFalse(self.journal.path.exists())

    def test_owner_database_role_rejected(self):
        with connection.cursor() as c:
            c.execute("SELECT current_user")
            role = c.fetchone()[0]
            c.execute("SET LOCAL ROLE NONE")
        try:
            with self.assertRaises(ValidationError):
                self.make_plan()
        finally:
            with connection.cursor() as c:
                c.execute("SET LOCAL ROLE " + connection.ops.quote_name(role))

    def test_new_reference_in_other_archived_workspace_blocks_execution(self):
        self.prepare()
        other = self.make_workspace("cleanup-archived", "ARCHIVED")
        with workspace_context(other.pk):
            Party.objects.create(workspace=other, display_name="Synthetic", profile_photo="synthetic-a.jpg")
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(self.store.deleted)

    def test_historical_only_reference_blocks_execution(self):
        from apps.tenant_apps.data_portability.models import LegacyMediaReceipt
        self.prepare()
        with workspace_context(self.workspace.pk):
            LegacyMediaReceipt.objects.create(workspace=self.workspace, source_system="fixture", source_id="cleanup",
                evidence_sha256="f"*64, source_evidence={"status": "EXACT_SOURCE_FILE_PRESERVED"},
                target={"kind": "party", "profile_name": "synthetic-a.jpg"}, imported_by=self.admin)
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(self.store.deleted)

    def test_reference_coverage_change_blocks_cleanup(self):
        self.prepare()
        with patch.dict("apps.orgs.services.storage_references.FILE_FIELDS", {("party.party", "unknown"): "unknown"}):
            with self.assertRaises(ValidationError):
                self.execute()
        self.assertFalse(self.store.deleted)

    def test_wrong_digest_or_missing_writer_freeze_blocks(self):
        self.prepare()
        for kwargs in ({"approve_digest": "wrong"}, {"writers_stopped": ""}, {"writers_stopped": "another-prefix"}):
            with self.assertRaises(ValidationError):
                self.execute(**kwargs)
        self.assertFalse(self.store.deleted)

    def test_changed_second_source_blocks_entire_batch(self):
        self.prepare()
        self.store.seed(self.store.source_key("synthetic-b.jpg"), b"changed")
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(self.store.deleted)

    def test_corrupt_recovery_blocks_entire_batch(self):
        data = self.prepare()
        self.store.seed(backup_key(data, 1), b"corrupted recovery")
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(self.store.deleted)

    def test_missing_manifest_blocks_execution(self):
        data = self.prepare()
        del self.store.objects[f"recovery/media-cleanup/{data['plan']['id']}/manifest.txt"]
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(self.store.deleted)

    def test_unknown_delete_outcome_can_resume_without_redeleting_missing_key(self):
        self.prepare()
        def crash(key):
            raise RuntimeError("lost provider response")
        self.store.after_delete = crash
        with self.assertRaises(RuntimeError):
            self.execute()
        self.assertEqual(self.journal.read()["items"][0]["state"], "deleting")
        self.store.after_delete = None
        self.execute()
        self.execute()  # replay checks absence and never repeats the provider delete
        self.assertEqual(len(self.store.deleted), 2)

    def test_failed_delete_before_mutation_can_resume(self):
        self.prepare()
        self.store.before_delete = Mock(side_effect=RuntimeError("network down"))
        with self.assertRaises(RuntimeError):
            self.execute()
        self.assertFalse(self.store.deleted)
        self.store.before_delete = None
        self.execute()
        self.assertEqual(len(self.store.deleted), 2)

    def test_backup_upload_unknown_outcome_can_resume(self):
        self.make_plan()
        self.store.after_put = Mock(side_effect=RuntimeError("lost upload response"))
        with self.assertRaises(RuntimeError):
            prepare_cleanup(actor=self.admin, journal=self.journal, store=self.store)
        self.store.after_put = None
        data = prepare_cleanup(actor=self.admin, journal=self.journal, store=self.store)
        self.assertEqual([i["state"] for i in data["items"]], ["prepared", "prepared"])

    def test_checkpoint_failure_prevents_first_delete(self):
        self.prepare()
        with patch.object(self.journal, "write", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.execute()
        self.assertFalse(self.store.deleted)

    def test_replacement_after_delete_is_never_deleted_or_overwritten(self):
        self.prepare()
        self.execute()
        key = self.store.source_key("synthetic-a.jpg")
        self.store.seed(key, b"new upload")
        with self.assertRaises(ValidationError):
            self.execute()
        with self.assertRaises(ValidationError):
            self.restore()
        self.assertEqual(self.store.objects[key][0], b"new upload")

    def test_partial_cleanup_can_restore_and_never_resume_delete(self):
        self.prepare()
        self.store.after_delete = Mock(side_effect=RuntimeError("interrupted"))
        with self.assertRaises(RuntimeError):
            self.execute()
        self.store.after_delete = None
        self.restore()
        self.assertEqual(len(self.store.deleted), 1)
        with self.assertRaises(ValidationError):
            self.execute()

    def test_restore_unknown_outcome_reconciles_owned_write(self):
        self.prepare()
        self.execute()
        self.store.after_put = Mock(side_effect=RuntimeError("lost restore response"))
        with self.assertRaises(RuntimeError):
            self.restore()
        self.assertEqual(self.journal.read()["items"][0]["state"], "restoring")
        self.store.after_put = None
        self.restore()
        self.restore()
        self.assertEqual([i["state"] for i in self.journal.read()["items"]], ["restored", "restored"])

    def test_signed_plan_rejects_tampering_and_cross_deployment(self):
        self.prepare()
        self.store.scope = "different/media/application/cleanup-test/"
        with self.assertRaises(ValidationError):
            self.execute()
        self.store.scope = MemoryStore.scope
        self.journal.path.write_text(self.journal.path.read_text() + "tampered")
        with self.assertRaises(signing.BadSignature):
            self.execute()
        self.assertFalse(self.store.deleted)

    def test_stale_inventory_recent_state_and_duplicate_selection_fail(self):
        self.run.completed_at = timezone.now()-timedelta(days=2)
        self.run.save(update_fields=["completed_at"])
        with self.assertRaises(ValidationError):
            self.make_plan()
        self.run.completed_at = timezone.now()
        self.run.save(update_fields=["completed_at"])
        with self.assertRaises(ValidationError):
            self.make_plan(object_ids=[self.ids[0], self.ids[0]])
        StorageInventoryObject.objects.filter(pk=self.ids[0]).update(state="unreferenced_recent")
        with self.assertRaises(ValidationError):
            self.make_plan()

    def test_missing_source_without_intent_fails_closed(self):
        self.prepare()
        del self.store.objects[self.store.source_key("synthetic-a.jpg")]
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(self.store.deleted)

    def test_count_byte_and_reason_bounds_fail_before_backups(self):
        for args in ({"object_ids": []}, {"object_ids": list(range(51))}, {"reason": ""}):
            with self.assertRaises(ValidationError):
                self.make_plan(**args)
        with patch("apps.orgs.services.storage_cleanup.MAX_BATCH_BYTES", 1):
            with self.assertRaises(ValidationError):
                self.make_plan()
        self.assertFalse(self.journal.path.exists())

    def test_summary_audit_failure_does_not_erase_deletion_receipts(self):
        self.prepare()
        with patch("apps.orgs.services.storage_cleanup.record_summary", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.execute()
        self.assertEqual([i["state"] for i in self.journal.read()["items"]], ["deleted", "deleted"])
        self.execute()
        self.assertEqual(len(self.store.deleted), 2)

    def test_restoration_failure_still_prevents_delete_replay(self):
        self.prepare()
        # Restore is deliberately a one-way decision even if its first read fails.
        with patch("apps.orgs.services.storage_cleanup.verify_backup", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                self.restore()
        with self.assertRaises(ValidationError):
            self.execute()

    def test_global_avatar_reference_is_retained(self):
        from django.apps import apps
        self.prepare()
        profile = apps.get_model("accounts.UserProfile").objects.get(user=self.owner)
        profile.profile_picture = "synthetic-b.jpg"
        profile.save(update_fields=["profile_picture"])
        with self.assertRaises(ValidationError):
            self.execute()
        self.assertFalse(self.store.deleted)

    def test_database_locks_block_concurrent_reference_writer(self):
        import psycopg2
        cfg = connection.settings_dict
        other = psycopg2.connect(dbname=cfg["NAME"], user=cfg["USER"], password=cfg["PASSWORD"], host=cfg["HOST"], port=cfg["PORT"])
        self.addCleanup(other.close)
        other.autocommit = True
        with other.cursor() as c:
            c.execute(f"SET ROLE {self.writer_role}")
            c.execute("SET lock_timeout='100ms'")
        with cleanup_guard(self.admin, references_locked=True):
            with other.cursor() as c:
                with self.assertRaises(psycopg2.errors.LockNotAvailable):
                    c.execute('UPDATE "party_party" SET profile_photo=profile_photo WHERE false')
                c.execute("SELECT pg_try_advisory_lock(721504015)")
                self.assertFalse(c.fetchone()[0])


class StoreBoundaryTests(SimpleTestCase):
    def test_adapter_uses_conditional_read_and_create_only_put(self):
        client = Mock()
        storage = SimpleNamespace(location="media/application/cleanup-test", bucket_name="fixture",
            connection=SimpleNamespace(meta=SimpleNamespace(client=client)))
        store = R2CleanupStore(storage)
        client.get_object.return_value = {"ContentLength": 3, "Body": io.BytesIO(b"abc")}
        self.assertEqual(store.read("exact", {"bytes": 3, "etag": "etag"}), b"abc")
        client.get_object.assert_called_once_with(Bucket="fixture", Key="exact", IfMatch="etag")
        store.put_new("exact", b"abc", {"ContentType": "text/plain"})
        self.assertEqual(client.put_object.call_args.kwargs["IfNoneMatch"], "*")

    def test_denied_head_is_not_treated_as_missing(self):
        client = Mock()
        store = R2CleanupStore(SimpleNamespace(location="media/application/test", bucket_name="fixture",
            connection=SimpleNamespace(meta=SimpleNamespace(client=client))))
        client.head_object.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "HeadObject")
        with self.assertRaises(ClientError):
            store.head("key")
        client.head_object.side_effect = ClientError({"Error": {"Code": "404"}}, "HeadObject")
        self.assertIsNone(store.head("key"))

    def test_expiry_metadata_survives_serialization_and_restoration(self):
        client = Mock()
        store = R2CleanupStore(SimpleNamespace(location="media/application/test", bucket_name="fixture",
            connection=SimpleNamespace(meta=SimpleNamespace(client=client))))
        now = timezone.now()
        client.head_object.return_value = {"ContentLength": 3, "ETag": "etag", "LastModified": now, "Expires": now}
        head = store.head("key")
        self.assertEqual(head["metadata"]["Expires"], now.isoformat())
        store.put_new("key", b"abc", head["metadata"])
        self.assertEqual(client.put_object.call_args.kwargs["Expires"], now)

    def test_unsafe_keys_and_bucket_root_fail_closed(self):
        for key in ("../x", "/absolute", "a//b", "a\\b", "a/./b", "line\nfeed"):
            with self.assertRaises(ValidationError):
                valid_key(key)
        with self.assertRaises(ValidationError):
            R2CleanupStore(SimpleNamespace(location="recovery/archive", bucket_name="fixture"))

    def test_command_redacts_provider_error_details(self):
        with patch("apps.orgs.management.commands.cleanup_storage.get_user_model", side_effect=RuntimeError("secret provider URL")):
            with self.assertRaises(CommandError) as error:
                call_command("cleanup_storage", "inspect", actor_id=1, directory="irrelevant", stdout=io.StringIO())
        self.assertNotIn("secret provider URL", str(error.exception))
