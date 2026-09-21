import importlib
import io
import json
import uuid
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import Client, override_settings
from django.urls import reverse

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenancy import testing
from apps.tenant_apps.party.models import PartyRoleType
from apps.tenant_apps.data_portability import bundle_history, bundle_import, bundle_commit, bundles, services
from apps.tenant_apps.data_portability.models import ImportBundle, ImportBatch
from apps.tenant_apps.data_portability.parsers import PortabilityError
from .fixtures import PortabilityFixture
from . import test_bundles, test_bundle_import


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BundleHistoryTests(PortabilityFixture):
    populate = test_bundles.BundleTests.populate

    def setUp(self):
        super().setUp()
        with self.scoped():
            self.populate()
            self.content = bundles.export_bundle(workspace_id=self.a.pk, actor=self.actor).content
        with self.scoped(self.b):
            PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
            self.history = bundle_import.stage_bundle_history(workspace_id=self.b.pk, actor=self.actor, content=self.content)
        self.args = {"workspace_id": self.b.pk, "actor": self.actor}

    def test_history_has_fixed_membership_and_live_progress(self):
        with self.scoped(self.b):
            history = bundle_history.get_history(**self.args, bundle_id=self.history.public_id)
            self.assertEqual(history.progress, "Awaiting review")
            self.assertEqual(len(history.receipt_entries()), 6)
            master = history.master
            services.cancel_import(**self.args, batch_id=master.public_id)
            history = bundle_history.get_history(**self.args, bundle_id=history.public_id)
            self.assertEqual(history.progress, "Partly finished")
            for _, batch in history.profile_batches():
                services.cancel_import(**self.args, batch_id=batch.public_id)
            self.assertEqual(bundle_history.get_history(**self.args, bundle_id=history.public_id).progress, "Cancelled")

    def test_reopen_after_receipt_expiry_needs_fresh_approval(self):
        with self.scoped(self.b):
            with patch("django.core.signing.time.time", return_value=1000):
                old = bundle_history.review_receipt(self.history)
            with self.assertRaises(PortabilityError): bundle_commit.receipt_batches(**self.args, receipt=old)
            history = bundle_history.get_history(**self.args, bundle_id=self.history.public_id)
            receipt = bundle_history.review_receipt(history)
            preview = bundle_commit.preview_bundle(**self.args, receipt=receipt, role_map={"BORROWER": "CUSTOMER"})
            bundle_commit.commit_bundle(**self.args, approval=preview["approval"], acknowledge_warnings=True, expected_bundle_id=history.public_id)
            self.assertEqual(bundle_history.get_history(**self.args, bundle_id=history.public_id).progress, "Completed")
            with patch("django.core.signing.time.time", return_value=99999999999), self.assertRaises(PortabilityError):
                bundle_commit.commit_bundle(**self.args, approval=preview["approval"], acknowledge_warnings=True)

    def test_wrong_history_confirmation_and_changed_signed_membership_fail(self):
        with self.scoped(self.b):
            receipt = bundle_history.review_receipt(self.history)
            preview = bundle_commit.preview_bundle(**self.args, receipt=receipt, role_map={"BORROWER": "CUSTOMER"})
            with self.assertRaises(PermissionDenied):
                bundle_commit.commit_bundle(**self.args, approval=preview["approval"], acknowledge_warnings=True, expected_bundle_id=uuid.uuid4())
            payload = signing.loads(receipt, salt=bundle_commit.RECEIPT_SALT)
            payload["batches"][0][1] = None
            forged = signing.dumps(payload, salt=bundle_commit.RECEIPT_SALT)
            with self.assertRaises(PortabilityError): bundle_commit.receipt_batches(**self.args, receipt=forged)

    def test_workspace_context_membership_and_lifecycle_are_required(self):
        with self.assertRaises(PermissionDenied): bundle_history.get_history(**self.args, bundle_id=self.history.public_id)
        with self.scoped():
            self.assertFalse(ImportBundle.objects.exists())
            with self.assertRaises(PermissionDenied):
                bundle_history.get_history(workspace_id=self.a.pk, actor=self.actor, bundle_id=self.history.public_id)
        with self.scoped(self.b):
            with self.assertRaises(PermissionDenied):
                bundle_history.get_history(workspace_id=self.b.pk, actor=self.other_actor, bundle_id=self.history.public_id)
            Company.all_objects.filter(pk=self.b.pk).update(lifecycle_state="ARCHIVED")
            with self.assertRaises(PermissionDenied): bundle_history.get_history(**self.args, bundle_id=self.history.public_id)

    def test_restricted_sql_cannot_mutate_delete_or_misbind_history(self):
        with self.scoped(self.b):
            for change in ({"source_sha256": "0" * 64}, {"master_id": None}, {"workspace_id": self.a.pk}):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    ImportBundle.objects.filter(pk=self.history.pk).update(**change)
            with self.assertRaises(DatabaseError), transaction.atomic():
                ImportBundle.objects.filter(pk=self.history.pk).delete()
            for change in ({"workspace_id": self.a.pk}, {"source_namespace": uuid.uuid4()},
                           {"master_id": None, "contact_id": self.history.master_id}, {"source_sha256": "bad"}):
                data = {"workspace_id": self.b.pk, "source_namespace": self.history.source_namespace,
                        "source_sha256": self.history.source_sha256, "created_by": self.actor, "master_id": self.history.master_id}
                data.update(change)
                with self.assertRaises(DatabaseError), transaction.atomic():
                    ImportBundle.objects.bulk_create([ImportBundle(**data)])

    def test_forced_rls_without_context(self):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid='data_portability_importbundle'::regclass")
            self.assertEqual(cursor.fetchone(), (True, True))
            cursor.execute(f"SET LOCAL ROLE {self.role_sql}")
            try:
                self.assertFalse(ImportBundle.objects.exists())
                with self.assertRaises(DatabaseError), transaction.atomic():
                    ImportBundle.objects.create(workspace_id=self.b.pk, created_by=self.actor,
                        source_namespace=uuid.uuid4(), source_sha256="0" * 64)
            finally:
                cursor.execute("RESET ROLE")

    def test_history_and_batches_roll_back_together(self):
        with self.scoped(self.b):
            before = ImportBatch.objects.count()
            with patch.object(ImportBundle.objects, "create", side_effect=PortabilityError("History failure")), self.assertRaises(PortabilityError):
                bundle_import.stage_bundle_history(**self.args, content=self.content)
            self.assertEqual(ImportBatch.objects.count(), before)
            self.assertEqual(ImportBundle.objects.count(), 1)

    def test_empty_bundle_and_repeat_upload_have_distinct_history(self):
        with self.scoped(self.b):
            content = test_bundle_import.pack(test_bundle_import.empty_members())
            first = bundle_import.stage_bundle_history(**self.args, content=content)
            second = bundle_import.stage_bundle_history(**self.args, content=content)
            self.assertNotEqual(first.public_id, second.public_id)
            self.assertEqual(first.progress, "Empty")
            self.assertTrue(all(batch is None for _, batch in first.profile_batches()))

    def test_legacy_audit_backfill_is_verified_repeatable_and_restores_context(self):
        with self.scoped(self.b):
            with zipfile.ZipFile(io.BytesIO(self.content)) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                master_bytes = archive.read(manifest["entities"][0]["path"])
            master = services.stage_import(**self.args, content=master_bytes, filename="master.jsonl", source_system=manifest["source_namespace"])
            members = {profile: None for profile in bundles.PROFILES}; members["party-master/1"] = str(master.public_id)
            data = {"source_namespace": manifest["source_namespace"], "sha256": "a" * 64, "batches": members}
            AuditLog.log("DATA_IMPORT", company=self.b, user=self.actor,
                description="Validated and staged Party bundle for separate profile review; no Party data committed.", data=data)
            AuditLog.log("DATA_IMPORT", company=self.b, user=self.actor,
                description="Validated and staged Party bundle for separate profile review; no Party data committed.", data={**data, "sha256": "invalid"})
            migration = importlib.import_module("apps.tenant_apps.data_portability.migrations.0010_importbundle")
            migration.backfill(apps, SimpleNamespace(connection=connection))
            migration.backfill(apps, SimpleNamespace(connection=connection))
            self.assertEqual(ImportBundle.objects.filter(master=master).count(), 1)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.workspace_id')")
                self.assertEqual(cursor.fetchone()[0], str(self.b.pk))

    def test_history_ui_reopens_without_old_receipt_and_is_workspace_bound(self):
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.b))
        client = Client(enforce_csrf_checks=True); client.force_login(self.actor)
        upload = reverse("workspace_portability:upload", kwargs={"workspace_slug": self.b.slug})
        self.assertContains(client.get(upload), "Bundle history")
        url = reverse("workspace_portability:bundle_history", kwargs={"workspace_slug": self.b.slug, "bundle_id": self.history.public_id})
        response = client.get(url)
        self.assertContains(response, "Generate combined preview")
        self.assertContains(response, "saved page can be reopened")
        self.assertIn("no-store", response["Cache-Control"])
        receipt = response.context["receipt"]
        self.assertEqual(client.post(url, {"action": "preview"}).status_code, 403)
        response = client.post(url, {"action": "preview", "receipt": receipt, "role_type_0": "CUSTOMER",
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertContains(response, "Confirm and commit whole bundle")
        approval = response.context["preview"]["approval"]
        response = client.post(url, {"action": "commit", "approval": approval, "warnings": "yes",
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], url)
        self.assertContains(client.get(url), "All profiles in this bundle are completed")
