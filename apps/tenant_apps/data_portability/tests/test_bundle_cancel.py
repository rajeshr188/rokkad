from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import Client, override_settings
from django.urls import reverse

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenancy import testing
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.data_portability import bundle_history, bundle_commit, services
from apps.tenant_apps.data_portability.models import ImportBatch, ImportRow
from apps.tenant_apps.data_portability.parsers import PortabilityError
from .fixtures import PortabilityFixture
from . import test_bundle_history


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BundleCancelTests(PortabilityFixture):
    populate = test_bundle_history.BundleHistoryTests.populate

    def setUp(self):
        # Reuse fixture setup without inheriting its tests.
        super().setUp()
        from apps.tenant_apps.data_portability import bundles, bundle_import
        with self.scoped():
            self.populate()
            content = bundles.export_bundle(workspace_id=self.a.pk, actor=self.actor).content
        with self.scoped(self.b):
            self.history = bundle_import.stage_bundle_history(workspace_id=self.b.pk, actor=self.actor, content=content)
        self.args = {"workspace_id": self.b.pk, "actor": self.actor}

    def cancel(self, **kwargs):
        return bundle_history.cancel_unfinished(**self.args, bundle_id=self.history.public_id, **kwargs)

    def test_clears_staged_values_retains_metadata_and_replay_is_noop(self):
        with self.scoped(self.b):
            membership = self.history.receipt_entries()
            metadata = list(ImportBatch.objects.order_by("pk").values_list("mapping", "source_sha256"))
            self.assertEqual(self.cancel(confirmed=True), 6)
            self.assertEqual(ImportBatch.objects.filter(state="CANCELLED", approval_digest="").count(), 6)
            self.assertFalse(ImportBatch.objects.filter(state__in=["READY", "NEEDS_MAPPING"]).exists())
            self.assertTrue(all(r.raw == {} and r.canonical == {} and r.issues == [] for r in ImportRow.objects.all()))
            self.assertEqual(list(ImportBatch.objects.order_by("pk").values_list("mapping", "source_sha256")), metadata)
            history = bundle_history.get_history(**self.args, bundle_id=self.history.public_id)
            self.assertEqual(history.receipt_entries(), membership)
            self.assertEqual(history.progress, "Cancelled")
            audits = AuditLog.objects.count()
            self.assertEqual(self.cancel(confirmed=True), 0)
            self.assertEqual(AuditLog.objects.count(), audits)

    def test_preserves_completed_evidence_and_skips_cancelled_profiles(self):
        with self.scoped(self.b):
            master = self.history.master
            services.commit_import(**self.args, batch_id=master.public_id, approval_digest=master.approval_digest, acknowledge_warnings=True)
            before = list(master.rows.order_by("pk").values())
            services.cancel_import(**self.args, batch_id=self.history.contact.public_id)
            self.assertEqual(self.cancel(confirmed=True), 4)
            master.refresh_from_db()
            self.assertEqual(master.state, "COMPLETED")
            self.assertEqual(list(master.rows.order_by("pk").values()), before)
            self.assertEqual(Party.objects.count(), 2)

    def test_confirmation_and_current_authorization_required_even_on_replay(self):
        with self.assertRaises(PermissionDenied): self.cancel(confirmed=True)
        with self.scoped():
            with self.assertRaises(PermissionDenied):
                bundle_history.cancel_unfinished(workspace_id=self.a.pk, actor=self.actor, bundle_id=self.history.public_id, confirmed=True)
        with self.scoped(self.b):
            with self.assertRaises(PortabilityError): self.cancel()
            with self.assertRaises(PermissionDenied):
                bundle_history.cancel_unfinished(workspace_id=self.b.pk, actor=self.other_actor, bundle_id=self.history.public_id, confirmed=True)
            self.assertEqual(self.cancel(confirmed=True), 6)
            Company.all_objects.filter(pk=self.b.pk).update(lifecycle_state="ARCHIVED")
            with self.assertRaises(PermissionDenied): self.cancel(confirmed=True)

    def test_late_failure_rolls_back_rows_states_and_audit(self):
        with self.scoped(self.b):
            batches = list(ImportBatch.objects.order_by("pk").values())
            rows = list(ImportRow.objects.order_by("pk").values())
            audits = AuditLog.objects.count()
            original = services.cancel_import
            calls = []
            def fail(**kwargs):
                result = original(**kwargs)
                calls.append(result.pk)
                if len(calls) == 6: raise PortabilityError("Last cancellation failed")
                return result
            with patch.object(services, "cancel_import", side_effect=fail), self.assertRaises(PortabilityError):
                self.cancel(confirmed=True)
            self.assertEqual(list(ImportBatch.objects.order_by("pk").values()), batches)
            self.assertEqual(list(ImportRow.objects.order_by("pk").values()), rows)
            self.assertEqual(AuditLog.objects.count(), audits)

    def test_cancellation_invalidates_combined_approval(self):
        from apps.tenant_apps.party.models import PartyRoleType
        with self.scoped(self.b):
            PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
            preview = bundle_commit.preview_bundle(**self.args, receipt=bundle_history.review_receipt(self.history), role_map={"BORROWER": "CUSTOMER"})
            self.assertTrue(preview["ready"])
            self.cancel(confirmed=True)
            with self.assertRaises(PortabilityError):
                bundle_commit.commit_bundle(**self.args, approval=preview["approval"], acknowledge_warnings=True)
            self.assertFalse(Party.objects.exists())

    def test_confirmation_ui_csrf_and_finished_button_removal(self):
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.b))
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        url = reverse("workspace_portability:bundle_history", kwargs={"workspace_slug": self.b.slug, "bundle_id": self.history.public_id})
        self.assertContains(client.get(url), "Cancel all unfinished profiles")
        self.assertEqual(client.post(url, {"action": "cancel_unfinished", "confirm_cancel": "yes"}).status_code, 403)
        data = {"action": "cancel_unfinished", "csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        self.assertContains(client.post(url, data), "Confirm cancellation")
        response = client.post(url, {**data, "confirm_cancel": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], url)
        self.assertNotContains(client.get(url), "Cancel all unfinished profiles")

    def test_revoked_import_permission_denies_noop_replay(self):
        from apps.orgs.models import Membership, WorkspaceRoleGrant
        with self.scoped(self.b):
            self.cancel(confirmed=True)
            membership = Membership.objects.get(company=self.b, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.b.pk, workspace_role__role_id=membership.role_id,
                permission__codename="data_import").delete()
            with self.assertRaises(PermissionDenied): self.cancel(confirmed=True)
