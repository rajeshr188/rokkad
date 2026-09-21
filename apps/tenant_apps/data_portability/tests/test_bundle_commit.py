from unittest.mock import patch
from types import SimpleNamespace

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.test import Client, override_settings
from django.urls import reverse

from apps.tenancy import testing
from apps.orgs.models import Membership, WorkspaceRoleGrant
from apps.orgs.audit import AuditLog
from apps.tenant_apps.party.models import (Party, PartyRoleType, PartyRelationship, PartyCodeSequence)
from apps.tenant_apps.data_portability import bundle_commit, bundle_import, bundles, services
from apps.tenant_apps.data_portability.models import ImportBatch, PartyIdentity
from apps.tenant_apps.data_portability.parsers import PortabilityError
from .fixtures import PortabilityFixture
from . import test_bundles


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BundleCommitTests(PortabilityFixture):
    populate = test_bundles.BundleTests.populate

    def setUp(self):
        super().setUp()
        with self.scoped():
            self.populate()
            content = bundles.export_bundle(workspace_id=self.a.pk, actor=self.actor).content
        with self.scoped(self.b):
            self.kind = PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
            staged = bundle_import.stage_bundle(workspace_id=self.b.pk, actor=self.actor, content=content)
            self.receipt = signing.dumps({"workspace": self.b.pk,
                "batches": [(profile, str(batch.public_id) if batch else None) for profile, batch in staged]}, salt=bundle_commit.RECEIPT_SALT)
        self.args = {"workspace_id": self.b.pk, "actor": self.actor}

    def preview(self, **kwargs):
        return bundle_commit.preview_bundle(**self.args, receipt=self.receipt,
            role_map=kwargs.get("role_map", {"BORROWER": "CUSTOMER"}))

    def commit_bundle(self, approval, **kwargs):
        return bundle_commit.commit_bundle(**self.args, approval=approval, acknowledge_warnings=kwargs.get("acknowledge_warnings", True))

    def test_preview_rolls_back_every_effect_then_all_profiles_commit_once(self):
        with self.scoped(self.b):
            before = list(ImportBatch.objects.order_by("pk").values())
            audits = AuditLog.objects.count()
            preview = self.preview()
            self.assertTrue(preview["ready"], preview)
            self.assertEqual(len(preview["profiles"]), 6)
            self.assertFalse(Party.objects.exists())
            self.assertFalse(PartyIdentity.objects.exists())
            self.assertFalse(PartyCodeSequence.objects.filter(workspace_id=self.b.pk).exists())
            self.assertEqual(list(ImportBatch.objects.order_by("pk").values()), before)
            self.assertEqual(AuditLog.objects.count(), audits)
            result = self.commit_bundle(preview["approval"])
            self.assertEqual(len(result), 6)
            self.assertTrue(all(batch.state == "COMPLETED" for batch in result))
            self.assertEqual(len({b.summary["bundle_approval"] for b in result}), 1)
            self.assertEqual(Party.objects.count(), 2)
            self.assertEqual(PartyRelationship.objects.count(), 1)
            after_audits = AuditLog.objects.count()
            self.commit_bundle(preview["approval"])
            self.assertEqual(Party.objects.count(), 2)
            self.assertEqual(AuditLog.objects.count(), after_audits)

    def test_missing_role_mapping_returns_errors_and_no_approval_or_parents(self):
        with self.scoped(self.b):
            preview = self.preview(role_map={})
            self.assertFalse(preview["ready"])
            self.assertEqual(preview["approval"], "")
            self.assertGreater(preview["profiles"][-1]["summary"]["rows_with_errors"], 0)
            self.assertFalse(Party.objects.exists())
            self.assertFalse(ImportBatch.objects.filter(state="COMPLETED").exists())

    def test_late_failure_rolls_back_all_six_commits(self):
        with self.scoped(self.b):
            preview = self.preview()
            before = list(ImportBatch.objects.order_by("pk").values())
            original = services.commit_import
            def fail(**kwargs):
                result = original(**kwargs)
                if result.contract_version == "party-relationship/1":
                    raise PortabilityError("Last profile failed")
                return result
            with patch.object(services, "commit_import", side_effect=fail), self.assertRaises(PortabilityError):
                self.commit_bundle(preview["approval"])
            self.assertFalse(Party.objects.exists())
            self.assertFalse(PartyIdentity.objects.exists())
            self.assertEqual(list(ImportBatch.objects.order_by("pk").values()), before)

    def test_changed_role_definition_invalidates_entire_commit(self):
        with self.scoped(self.b):
            preview = self.preview()
            PartyRoleType.objects.filter(pk=self.kind.pk).update(label="Changed definition")
            with self.assertRaisesMessage(PortabilityError, "Destination data changed"):
                self.commit_bundle(preview["approval"])
            self.assertFalse(Party.objects.exists())
            self.assertFalse(ImportBatch.objects.filter(state="COMPLETED").exists())

    def test_destination_conflict_appearing_after_review_keeps_only_existing_party(self):
        with self.scoped(self.b):
            preview = self.preview()
            Party.objects.create(display_name="Asha Devi")
            with self.assertRaises(PortabilityError): self.commit_bundle(preview["approval"])
            self.assertEqual(Party.objects.count(), 1)
            self.assertFalse(ImportBatch.objects.filter(state="COMPLETED").exists())

    def test_individual_revalidation_or_commit_invalidates_combined_approval(self):
        with self.scoped(self.b):
            preview = self.preview()
            master = ImportBatch.objects.get(contract_version="party-master/1")
            services.validate_import(**self.args, batch_id=master.public_id, mapping={})
            with self.assertRaises(PortabilityError): self.commit_bundle(preview["approval"])
            preview = self.preview()
            master.refresh_from_db()
            services.commit_import(**self.args, batch_id=master.public_id, approval_digest=master.approval_digest, acknowledge_warnings=True)
            with self.assertRaises(PortabilityError): self.commit_bundle(preview["approval"])
            with self.assertRaises(PortabilityError): self.preview()
            self.assertEqual(ImportBatch.objects.filter(state="COMPLETED").count(), 1)

    def test_authorization_acknowledgement_expiry_and_replay(self):
        with self.assertRaises(PermissionDenied): self.preview()
        with self.scoped(self.b):
            preview = self.preview()
            with self.assertRaises(PortabilityError): self.commit_bundle(preview["approval"], acknowledge_warnings=False)
            with self.assertRaises(PortabilityError): self.commit_bundle(preview["approval"] + "invalid")
            with patch("django.core.signing.time.time", return_value=99999999999), self.assertRaises(PortabilityError):
                self.commit_bundle(preview["approval"])
            self.commit_bundle(preview["approval"])
            membership = Membership.objects.get(company=self.b, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.b.pk, workspace_role__role_id=membership.role_id,
                permission__codename__in=["contact_edit", "data_edit"]).delete()
            with self.assertRaises(PermissionDenied): self.commit_bundle(preview["approval"])

    def test_foreign_receipt_and_operator_approval_are_denied(self):
        with self.scoped():
            with self.assertRaises(PermissionDenied):
                bundle_commit.receipt_batches(workspace_id=self.a.pk, actor=self.actor, receipt=self.receipt)
        with self.scoped(self.b):
            preview = self.preview()
            role = Membership.objects.get(company=self.b, user=self.actor).role
            Membership.objects.create(company=self.b, user=self.other_actor, role=role)
            with self.assertRaises(PermissionDenied):
                bundle_commit.commit_bundle(workspace_id=self.b.pk, actor=self.other_actor, approval=preview["approval"], acknowledge_warnings=True)

    def test_preview_discards_on_commit_callbacks(self):
        called = []
        original = services.commit_import
        def callback(**kwargs):
            transaction.on_commit(lambda: called.append(True))
            return original(**kwargs)
        with self.scoped(self.b), self.captureOnCommitCallbacks(execute=True):
            with patch.object(services, "commit_import", side_effect=callback):
                self.assertTrue(self.preview()["ready"])
        self.assertEqual(called, [])

    def test_combined_ui_preview_confirmation_and_csrf(self):
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.b))
        client = Client(enforce_csrf_checks=True); client.force_login(self.actor)
        url = reverse("workspace_portability:bundle", kwargs={"workspace_slug": self.b.slug})
        page = client.get(url, {"receipt": self.receipt})
        self.assertContains(page, "Generate combined preview")
        self.assertEqual(client.post(url, {"receipt": self.receipt, "action": "preview"}).status_code, 403)
        data = {"receipt": self.receipt, "action": "preview", "role_type_0": "CUSTOMER",
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        response = client.post(url, data)
        self.assertContains(response, "Confirm and commit whole bundle")
        approval = response.context["preview"]["approval"]
        with self.scoped(self.b): self.assertFalse(Party.objects.exists())
        response = client.post(url, {**data, "action": "commit", "approval": approval, "warnings": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get(response["Location"]), "All profiles in this bundle are completed")


    def test_changed_raw_input_invalidates_approval(self):
        with self.scoped(self.b):
            preview = self.preview()
            batch = ImportBatch.objects.get(contract_version="party-master/1")
            row = batch.rows.order_by("source_row").first()
            row.raw["name"] = "Changed after review"
            row.save(update_fields=["raw"])
            with self.assertRaises(PortabilityError): self.commit_bundle(preview["approval"])
            self.assertFalse(Party.objects.exists())

    def test_completed_bundle_marker_is_immutable_under_restricted_sql(self):
        with self.scoped(self.b):
            result = self.commit_bundle(self.preview()["approval"])
            with self.assertRaises(DatabaseError), transaction.atomic():
                ImportBatch.objects.filter(pk=result[0].pk).update(summary={"bundle_approval": "forged"})
