from collections import defaultdict
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs import test_platform_console as console_tests
from apps.orgs.models import StorageInventoryRun, StorageInventoryObject, WorkspaceStorageUsage
from apps.orgs.services.storage_inventory import R2Inventory, classify, reconcile_storage
from apps.orgs.services.storage_references import collect_references, validate_coverage
from apps.tenancy.context import workspace_context
from apps.tenancy.registry import rls_protected_models
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.data_portability.models import LegacyMediaReceipt


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class StorageInventoryTests(TestCase):
    setUp = console_tests.PlatformConsoleTests.setUp
    make_workspace = console_tests.PlatformConsoleTests.make_workspace
    subscription = console_tests.PlatformConsoleTests.subscription

    def inventory(self, entries=None):
        return SimpleNamespace(scope="fixture/media/application/test/", objects=lambda: iter(entries or []))

    def obj(self, key, size=100, age=30):
        return {"key": key, "size": size, "modified": timezone.now()-timedelta(days=age)}

    def party(self, key="photos/private-customer.jpg", workspace=None):
        workspace = workspace or self.workspace
        with workspace_context(workspace.pk):
            return Party.objects.create(workspace=workspace, display_name="Private customer", profile_photo=key)

    def test_registry_has_every_file_field_and_rls_model(self):
        self.assertEqual(len(validate_coverage()), 16)
        self.assertIn(WorkspaceStorageUsage, rls_protected_models())
        with patch.dict("apps.orgs.services.storage_references.FILE_FIELDS", {("party.party", "new_photo"): "unknown"}):
            with self.assertRaises(ValidationError):
                validate_coverage()

    def test_physical_totals_deduplicate_and_leave_shared_unassigned(self):
        now = timezone.now()
        references = {"one": {(1,"customer_photos"),(1,"historical_evidence")},
            "shared": {(1,"customer_photos"),(2,"customer_photos")},
            "avatar": {(None,"platform_avatars")}, "missing": {(1,"customer_photos")}}
        totals, usage, categories, rows = classify([self.obj("one"), self.obj("shared",200), self.obj("avatar",50),
            self.obj("old",70),self.obj("new",30,1)], references,[1,2],started_at=now)
        self.assertEqual(sum(c["bytes"] for c in totals.values()),450)
        self.assertEqual(usage[1]["owned"], {"objects":1,"bytes":100})
        self.assertEqual(usage[1]["shared"], {"objects":1,"bytes":200})
        self.assertEqual(usage[2]["owned"]["bytes"],0)
        self.assertEqual(categories[1]["customer_photos"]["bytes"],100)
        self.assertEqual(totals["unreferenced_review"]["bytes"],70)
        self.assertEqual(totals["unreferenced_recent"]["bytes"],30)
        self.assertEqual(usage[1]["missing"]["objects"],1)
        self.assertEqual(next(r for r in rows if r["key"]=="old")["workspace_count"],0)

    def test_history_does_not_hide_media_type_or_duplicate_physical_bytes(self):
        references = {
            "collateral": {(1, "collateral_photos"), (1, "historical_evidence")},
            "borrower": {(1, "customer_photos"), (1, "historical_evidence")},
            "history-only": {(1, "historical_evidence")},
            "two-types": {(1, "customer_photos"), (1, "collateral_photos"), (1, "historical_evidence")},
        }
        original = {key: set(refs) for key, refs in references.items()}
        totals, usage, categories, rows = classify([self.obj(key) for key in references], references, [1], started_at=timezone.now())
        self.assertEqual({row["key"]: row["category"] for row in rows}, {
            "collateral": "collateral_photos", "borrower": "customer_photos",
            "history-only": "historical_evidence", "two-types": "multiple_uses",
        })
        self.assertEqual(totals["owned"], {"objects": 4, "bytes": 400})
        self.assertEqual(usage[1]["owned"], totals["owned"])
        self.assertEqual(sum(c["bytes"] for c in categories[1].values()), 400)
        self.assertEqual(references, original)

    def test_historical_reference_in_another_workspace_keeps_file_shared(self):
        references = {"shared-photo": {(1, "collateral_photos"), (2, "historical_evidence")}}
        totals, usage, categories, rows = classify([self.obj("shared-photo")], references, [1, 2], started_at=timezone.now())
        self.assertEqual(totals["shared"], {"objects": 1, "bytes": 100})
        self.assertEqual(rows[0]["category"], "collateral_photos")
        for workspace_id in (1, 2):
            self.assertEqual(usage[workspace_id]["shared"]["objects"], 1)
            self.assertEqual(usage[workspace_id]["owned"]["objects"], 0)
            self.assertFalse(categories[workspace_id])

    def test_receipt_retains_deleted_mutable_reference_and_archived_workspace(self):
        self.party()
        archived = self.make_workspace("archived-storage", "ARCHIVED")
        self.party("archive-photo", archived)
        with workspace_context(self.workspace.pk):
            LegacyMediaReceipt.objects.create(workspace=self.workspace, source_system="fixture", source_id="1",
                evidence_sha256="f"*64, source_evidence={"status":"EXACT_SOURCE_FILE_PRESERVED"},
                target={"kind":"party", "profile_name":"retained-only"}, imported_by=self.admin)
        refs = collect_references([self.workspace.pk,archived.pk])
        self.assertIn((self.workspace.pk,"historical_evidence"),refs["retained-only"])
        self.assertIn((archived.pk,"customer_photos"),refs["archive-photo"])

    def test_completed_scan_and_repeat_preserve_dated_totals(self):
        self.party()
        inventory = self.inventory([self.obj("photos/private-customer.jpg"),self.obj("unused")])
        first=reconcile_storage(actor=self.admin,inventory=inventory)
        second=reconcile_storage(actor=self.admin,inventory=inventory)
        self.assertEqual(first.totals,second.totals)
        self.assertEqual(first.totals["owned"]["bytes"],100)
        self.assertEqual(StorageInventoryObject.objects.filter(run=first).count(),2)
        self.assertEqual(WorkspaceStorageUsage.objects.count(),0)
        with workspace_context(self.workspace.pk):
            self.assertEqual(WorkspaceStorageUsage.objects.count(),2)
            self.assertEqual(WorkspaceStorageUsage.objects.first().totals["owned"]["bytes"],100)

    def test_reference_arriving_during_listing_is_protected(self):
        refs=defaultdict(set)
        later=defaultdict(set,{"arrived":{(self.workspace.pk,"customer_photos")}})
        with patch("apps.orgs.services.storage_inventory.collect_references",side_effect=[refs,later]):
            run=reconcile_storage(actor=self.admin,inventory=self.inventory([self.obj("arrived")]))
        self.assertEqual(run.totals["owned"]["objects"],1)
        self.assertNotIn("unreferenced_review",run.totals)

    def test_issued_ticket_snapshot_protects_prior_photo(self):
        from apps.tenant_apps.loans.models import LoanDocumentIssue
        with workspace_context(self.workspace.pk):
            LoanDocumentIssue.objects.create(workspace=self.workspace, document_type="loan_ticket",
                source_type="fixture", source_id="1", source_fingerprint="f"*64,
                payload_schema_version=1, payload_hash="a"*64, pdf_hash="b"*64,
                artifact="issued.pdf", source_snapshot={"schema_version":2, "workspace_id":self.workspace.pk,
                    "media":{"borrower.photo":{"file_name":"previous-photo"}}}, issued_by=self.admin)
        references=collect_references([self.workspace.pk])
        self.assertIn((self.workspace.pk,"historical_evidence"),references["previous-photo"])
        self.assertIn((self.workspace.pk,"issued_documents"),references["issued.pdf"])

    def test_partial_failure_never_publishes_usage_or_replaces_good_run(self):
        good=reconcile_storage(actor=self.admin,inventory=self.inventory())
        def broken():
            yield self.obj("first")
            raise RuntimeError("Do not display provider details")
        with self.assertRaises(RuntimeError):
            reconcile_storage(actor=self.admin,inventory=SimpleNamespace(scope="fixture",objects=broken))
        failed=StorageInventoryRun.objects.first()
        self.assertEqual(failed.state,"failed")
        self.assertEqual(failed.failure_code,"RuntimeError")
        self.assertFalse(StorageInventoryObject.objects.filter(run=failed).exists())
        self.assertEqual(StorageInventoryRun.objects.filter(state="complete").first(),good)

    def test_duplicate_listing_and_audit_failure_fail_closed(self):
        with self.assertRaises(ValidationError):
            reconcile_storage(actor=self.admin,inventory=self.inventory([self.obj("same"),self.obj("same")]))
        with patch("apps.orgs.services.storage_inventory.AuditLog.log",side_effect=RuntimeError("audit")):
            with self.assertRaises(RuntimeError):
                reconcile_storage(actor=self.admin,inventory=self.inventory([self.obj("one")]))
        self.assertFalse(StorageInventoryObject.objects.exists())
        with workspace_context(self.workspace.pk):
            self.assertFalse(WorkspaceStorageUsage.objects.exists())

    def test_rls_direct_read_and_cross_workspace_write_denied(self):
        second=self.make_workspace("second-storage")
        run=reconcile_storage(actor=self.admin,inventory=self.inventory())
        self.assertEqual(WorkspaceStorageUsage.objects.count(),0)
        with workspace_context(self.workspace.pk):
            self.assertEqual(set(WorkspaceStorageUsage.objects.values_list("workspace_id",flat=True)),{self.workspace.pk})
            with self.assertRaises(DatabaseError),transaction.atomic():
                WorkspaceStorageUsage.objects.filter(workspace=self.workspace).update(workspace=second)
        with connection.cursor() as cursor:
            cursor.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid='orgs_workspacestorageusage'::regclass")
            self.assertEqual(cursor.fetchone(),(True,True))

    def test_operator_authorization_and_tenant_context(self):
        for actor in (None,self.owner):
            with self.assertNumQueries(0),self.assertRaises(PermissionDenied):
                reconcile_storage(actor=actor,inventory=self.inventory())
        self.admin.is_active=False
        with self.assertRaises(PermissionDenied):
            reconcile_storage(actor=self.admin,inventory=self.inventory())
        self.admin.is_active=True
        with workspace_context(self.workspace.pk),self.assertRaises(PermissionDenied):
            reconcile_storage(actor=self.admin,inventory=self.inventory())

    def test_workspace_settings_permission_and_target_are_required(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Membership, Role
        from apps.orgs.web.storage import workspace_storage
        viewer=get_user_model().objects.create_user(username="storage-viewer")
        Membership.objects.create(user=viewer,company=self.workspace,role=Role.objects.get_or_create(name="Viewer")[0])
        request=RequestFactory().get("/")
        request.user=viewer;request.workspace=self.workspace
        with workspace_context(self.workspace.pk),self.assertRaises(PermissionDenied):
            workspace_storage(request,workspace_slug=self.workspace.slug)
        request.user=self.admin
        other=self.make_workspace("mismatched-storage")
        with workspace_context(self.workspace.pk),self.assertRaises(PermissionDenied):
            workspace_storage(request,workspace_slug=other.slug)

    def test_superuser_database_connection_cannot_collect_business_references(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            role=cursor.fetchone()[0]
            cursor.execute("SET LOCAL ROLE NONE")
        try:
            with self.assertRaises(ValidationError):
                reconcile_storage(actor=self.admin,inventory=self.inventory())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE " + connection.ops.quote_name(role))

    def test_http_permissions_no_paths_no_remote_calls_and_empty_states(self):
        url=reverse("platform_storage")
        self.assertEqual(self.client.get(url).status_code,302)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(url),"No completed storage inventory")
        self.assertEqual(self.client.post(url).status_code,405)
        self.party()
        reconcile_storage(actor=self.admin,inventory=self.inventory([self.obj("photos/private-customer.jpg")]))
        with patch("apps.orgs.services.storage_inventory.R2Inventory",side_effect=AssertionError("HTTP must not scan")):
            response=self.client.get(url+"?state=owned")
            self.assertEqual(response.status_code,200)
            self.assertNotContains(response,"private-customer")
            self.assertIn("no-store",response["Cache-Control"])
            self.client.force_login(self.owner)
            self.subscription(5)
            response=self.client.get(reverse("workspace_storage",kwargs={"workspace_slug":self.workspace.slug}))
            self.assertContains(response,"100\u00a0bytes")
            self.assertNotContains(response,"private-customer")
            other=self.make_workspace("other-storage")
            # Owner is a member of both, but the summary still comes only from the URL Workspace.
            self.subscription(5,other)
            response=self.client.get(reverse("workspace_storage",kwargs={"workspace_slug":other.slug}))
            self.assertContains(response,"No completed storage measurement")

    def test_r2_adapter_is_prefix_scoped_and_metadata_only(self):
        storage=Mock(location="media/application/production/fixture",bucket_name="private-bucket")
        client=storage.connection.meta.client
        client.get_paginator.return_value.paginate.return_value=[{"Contents":[{
            "Key":"media/application/production/fixture/photo", "Size":123, "LastModified":timezone.now()}]}]
        result=list(R2Inventory(storage).objects())
        self.assertEqual(result[0]["key"],"photo")
        client.get_paginator.assert_called_once_with("list_objects_v2")
        client.get_paginator.return_value.paginate.assert_called_once_with(Bucket="private-bucket",Prefix="media/application/production/fixture/")
        client.get_object.assert_not_called()
        client.delete_object.assert_not_called()
        for prefix in ("", "media/legacy", "media/application", "media/application/../legacy"):
            storage.location=prefix
            with self.assertRaises(ValidationError):R2Inventory(storage)
