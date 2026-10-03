import hashlib
import json
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from django.db import connection
from django.test import TestCase, override_settings

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataAccount
from apps.tenant_apps.loans.services import khata_recovery as recovery, khata_documents as documents
from .test_khata_corrections import CorrectionFixture
from . import test_khata_opening as opening_tests, test_khata_foundation as foundation


@override_settings(STORAGES=opening_tests.STORAGES)
class KhataRecoveryTests(CorrectionFixture, TestCase):
    def export(self):
        self.content = recovery.export_archive(workspace=self.workspace, actor=self.actor)
        self.sha = hashlib.sha256(self.content).hexdigest()
        return self.content

    def restore(self, **changes):
        args = dict(workspace=self.workspace, actor=self.actor, content=self.content, expected_sha256=self.sha)
        args.update(changes)
        return recovery.restore_archive(**args)

    def empty_test_destination(self):
        # Fictional TestCase only: simulate a recovered DB with khata tables absent.
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        with workspace_context(self.workspace.pk), connection.cursor() as cursor:
            connection.check_constraints()
            for model in recovery._models():
                cursor.execute(f'ALTER TABLE "{model._meta.db_table}" DISABLE TRIGGER USER')
            for model in reversed(recovery._models()):
                cursor.execute(f'DELETE FROM "{model._meta.db_table}" WHERE workspace_id=%s', [self.workspace.pk])
            connection.check_constraints()
            for model in recovery._models():
                cursor.execute(f'ALTER TABLE "{model._meta.db_table}" ENABLE TRIGGER USER')

    def test_exact_restore_preview_rolls_back_then_commit_reconciles_and_reexports(self):
        replacement = self.replacement("100")
        self.exchange([self.first], [replacement])
        import uuid
        issue = documents.issue_document(**self.args(), request_key=uuid.uuid4())
        self.export()
        original = recovery._read(self.content, self.sha)[0]
        self.empty_test_destination()
        result = self.restore()
        self.assertFalse(result["committed"])
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataAccount.objects.exists())
        result = self.restore(commit=True)
        self.assertTrue(result["committed"])
        new_content = recovery.export_archive(workspace=self.workspace, actor=self.actor)
        new = recovery._read(new_content, hashlib.sha256(new_content).hexdigest())[0]
        self.assertEqual(original, new)
        self.assertTrue(documents.document_bytes(**self.args(), issue_id=issue.pk)[1].startswith(b"%PDF"))
        self.payout("1000")  # Restored active evidence still accepts normal servicing.

    def test_existing_evidence_is_never_overwritten(self):
        self.export()
        with self.assertRaisesMessage(ValueError, "already contains"):
            self.restore(commit=True)

    def test_checksum_and_workspace_identity_required(self):
        self.export()
        with self.assertRaisesMessage(ValueError, "checksum"):
            self.restore(expected_sha256="0" * 64)
        import uuid
        other, actor, _ = foundation.fixture(uuid.uuid4().hex[:8])
        with self.assertRaisesMessage(ValueError, "original Workspace"):
            self.restore(workspace=other, actor=actor)

    def test_missing_prerequisite_and_changed_balance_refuse_restore(self):
        self.export()
        self.empty_test_destination()
        manifest, files = recovery._read(self.content, self.sha)
        manifest["prerequisites"][0]["sha256"] = "0" * 64
        self.replace_manifest(manifest, files)
        with self.assertRaisesMessage(ValueError, "identity differs"):
            self.restore(commit=True)
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataAccount.objects.exists())

    def replace_manifest(self, manifest, files):
        stream = BytesIO()
        with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            for name, content in files.items():
                archive.writestr("media/" + name, content)
        self.content = stream.getvalue()
        self.sha = hashlib.sha256(self.content).hexdigest()

    def test_reconciliation_failure_rolls_back_all_rows_and_restores_guards(self):
        self.export()
        self.empty_test_destination()
        manifest, files = recovery._read(self.content, self.sha)
        manifest["reconciliation"][0]["principal"] = "1.00"
        self.replace_manifest(manifest, files)
        with self.assertRaisesMessage(ValueError, "differs from the backup"):
            self.restore(commit=True)
        with workspace_context(self.workspace.pk), connection.cursor() as cursor:
            self.assertFalse(KhataAccount.objects.exists())
            cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid='loans_khataaccount'::regclass AND tgenabled <> 'O'")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_complete_corrected_interest_reduction_settlement_and_photo_round_trip(self):
        self.photo(self.first)
        extra = self.replacement("10")
        with self.later(1):
            receipt = self.pay("100000")
            self.correct(receipt)
            self.pay("100000")
            self.quote()
            revision = self.reduce_with_return([extra])
            self.handover(extra, revision)
            source = self.settle()
            self.handover(self.first, source)
            self.export()
            original = recovery._read(self.content, self.sha)[0]
            self.empty_test_destination()
            self.assertTrue(self.restore(commit=True)["committed"])
            current = recovery.export_archive(workspace=self.workspace, actor=self.actor)
            restored = recovery._read(current, hashlib.sha256(current).hexdigest())[0]
            self.assertEqual(original, restored)
            self.assertEqual(restored["reconciliation"][0]["state"], "CLOSED")

    def test_failed_reconciliation_removes_only_new_media(self):
        photo = self.photo(self.first)
        self.export()
        self.empty_test_destination()
        photo.file.storage.delete(photo.file.name)
        manifest, files = recovery._read(self.content, self.sha)
        manifest["reconciliation"][0]["principal"] = "1.00"
        self.replace_manifest(manifest, files)
        with self.assertRaisesMessage(ValueError, "differs from the backup"):
            self.restore(commit=True)
        self.assertFalse(photo.file.storage.exists(photo.file.name))

    def test_runtime_can_export_but_cannot_restore_or_disable_evidence_guards(self):
        import uuid
        role = "khata_restore_test_" + uuid.uuid4().hex[:12]
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"')
            cursor.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{role}"')
            cursor.execute(f'SET LOCAL ROLE "{role}"')
        try:
            self.export()
            with self.assertRaisesMessage(ValueError, "table-owner"):
                self.restore()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

    def test_corrupt_retained_photo_prevents_export(self):
        photo = self.photo(self.first)
        photo.file.storage.delete(photo.file.name)
        from django.core.files.base import ContentFile
        photo.file.storage.save(photo.file.name, ContentFile(b"broken"))
        with self.assertRaisesMessage(ValueError, "missing or corrupt"):
            self.export()
