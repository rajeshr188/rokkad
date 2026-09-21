import copy
import csv
import io
import uuid
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, override_settings

from apps.orgs.models import Membership, WorkspaceRoleGrant
from apps.tenant_apps.party.models import Party, PartyRoleType
from apps.tenant_apps.data_portability import child_contracts, presets, services, views
from apps.tenant_apps.data_portability.models import ImportBatch, MappingPresetVersion
from apps.tenant_apps.data_portability.parsers import PortabilityError
from .fixtures import PortabilityFixture
from .test_portability import CSV, MAPPING


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MappingPresetTests(PortabilityFixture):
    def raw_insert(self, workspace_id):
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO data_portability_mappingpresetversion
                (workspace_id,public_id,name,version,profile,source_system,headers,mapping,created_by_id,created_at)
                VALUES (%s,%s,'Forged',1,'party-master/1','paper','[]','{}',%s,NOW())""",
                [workspace_id, uuid.uuid4(), self.actor.pk])

    def save(self, batch, name="Register", **kwargs):
        return presets.save_preset(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id,
            name=name, approval_digest=kwargs.get("approval_digest", batch.approval_digest))

    def apply(self, batch, preset, workspace=None):
        return services.validate_import(workspace_id=(workspace or self.a).pk, actor=self.actor,
            batch_id=batch.public_id, preset_id=preset.public_id)

    def test_save_apply_preview_commit_export_and_replay(self):
        with self.scoped():
            original = self.ready()
            preset = self.save(original)
            self.assertEqual(preset.version, 1)
            self.assertFalse(Party.objects.exists())
            batch = self.apply(self.stage(), preset)
            self.assertEqual(batch.state, "READY")
            self.assertEqual(batch.mapping_preset_id, preset.pk)
            self.assertEqual(batch.mapping, original.mapping)
            self.commit(batch)
            self.commit(self.apply(self.stage(), preset))
            self.assertEqual(Party.objects.count(), 1)
            self.assertEqual(self.save(batch).pk, preset.pk)
            self.assertEqual(services.export_parties(workspace_id=self.a.pk, actor=self.actor).count, 1)

    def test_new_versions_preserve_existing_approval_and_old_version(self):
        with self.scoped():
            first = self.save(self.ready())
            old_batch = self.apply(self.stage(), first)
            old_approval = old_batch.approval_digest
            mapping = copy.deepcopy(MAPPING)
            mapping["defaults"]["risk_label"] = "LOW"
            second = self.save(self.ready(mapping=mapping))
            self.assertEqual(second.version, 2)
            first.refresh_from_db()
            self.assertNotIn("risk_label", first.mapping["defaults"])
            old_batch.refresh_from_db()
            self.assertEqual(old_batch.approval_digest, old_approval)
            self.assertEqual(old_batch.mapping_preset_id, first.pk)
            self.commit(old_batch)

    def test_reapply_invalidates_old_approval_and_manual_mapping_clears_link(self):
        with self.scoped():
            preset = self.save(self.ready())
            original = self.ready()
            batch = self.apply(original, preset)
            self.assertNotEqual(original.approval_digest, batch.approval_digest)
            with self.assertRaises(PortabilityError):
                self.commit(original)
            batch = self.ready(batch)
            self.assertIsNone(batch.mapping_preset_id)
            self.commit(batch)

    def test_header_reordering_allowed_but_changed_headers_system_profile_rejected(self):
        with self.scoped():
            preset = self.save(self.ready())
            reordered = self.stage(b"Phone,Party,Legacy\n,Asha Devi,old-1\n")
            self.assertEqual(self.apply(reordered, preset).state, "READY")
            batches = [self.stage(b"Legacy,Party,Telephone\nold-1,Asha Devi,\n"),
                       self.stage(system="different"),
                       services.stage_import(workspace_id=self.a.pk, actor=self.actor, content=CSV,
                           source_system="paper", filename="roles.csv", profile=child_contracts.ROLE)]
            for batch in batches:
                with self.assertRaises(PortabilityError):
                    self.apply(batch, preset)
                self.assertEqual(presets.available_presets(workspace_id=self.a.pk, actor=self.actor, batch=batch), [])

    def test_only_reviewed_csv_can_be_saved_and_jsonl_cannot_apply(self):
        with self.scoped():
            with self.assertRaises(PortabilityError):
                self.save(self.stage())
            ready = self.ready()
            with self.assertRaises(PortabilityError):
                self.save(ready, approval_digest="stale")
            preset = self.save(ready)
            self.commit(ready)
            exported = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            batch = services.stage_import(workspace_id=self.a.pk, actor=self.actor, content=exported.content,
                source_system=exported.namespace, filename="parties.jsonl")
            batch = self.ready(batch, {})
            with self.assertRaises(PortabilityError):
                self.save(batch)
            with self.assertRaises(PortabilityError):
                self.apply(batch, preset)
            with self.assertRaises(PortabilityError):
                self.apply(ready, preset)

    def test_cross_workspace_and_missing_context_denied(self):
        with self.scoped():
            preset = self.save(self.ready())
        with self.assertRaises(PermissionDenied):
            presets.save_preset(workspace_id=self.a.pk, actor=self.actor, batch_id="bad", name="X", approval_digest="")
        with self.scoped(self.b):
            self.assertFalse(MappingPresetVersion.objects.exists())
            batch = self.stage(workspace=self.b)
            with self.assertRaises(PortabilityError):
                self.apply(batch, preset, self.b)
            with self.assertRaises(PermissionDenied):
                presets.save_preset(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id, name="X", approval_digest="")
            with self.assertRaises(DatabaseError), transaction.atomic():
                self.raw_insert(self.a.pk)

    def test_sql_without_workspace_cannot_read_or_insert_presets(self):
        with self.scoped():
            self.save(self.ready())
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {self.role_sql}")
                cursor.execute("SELECT COUNT(*) FROM data_portability_mappingpresetversion")
                self.assertEqual(cursor.fetchone()[0], 0)
            try:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    self.raw_insert(self.a.pk)
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")

    def test_permissions_checked_even_on_identical_save_and_apply(self):
        with self.scoped():
            batch = self.ready()
            preset = self.save(batch)
            member = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=member.role_id,
                permission__codename="data_import").delete()
            for callback in (lambda: self.save(batch), lambda: self.apply(batch, preset),
                    lambda: presets.available_presets(workspace_id=self.a.pk, actor=self.actor, batch=batch)):
                with self.assertRaises(PermissionDenied):
                    callback()

    def test_sql_immutability_mapping_and_foreign_link_guards(self):
        with self.scoped(self.b):
            foreign_batch = self.ready(workspace=self.b)
            foreign = presets.save_preset(workspace_id=self.b.pk, actor=self.actor,
                batch_id=foreign_batch.public_id, name="Register", approval_digest=foreign_batch.approval_digest)
        with self.scoped():
            preset = self.save(self.ready())
            for callback in (lambda: MappingPresetVersion.objects.filter(pk=preset.pk).update(mapping={}),
                    lambda: MappingPresetVersion.objects.filter(pk=preset.pk).delete(),
                    lambda: MappingPresetVersion.objects.filter(pk=preset.pk).update(workspace=self.b)):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    callback()
            batch = self.ready()
            with self.assertRaises(DatabaseError), transaction.atomic():
                ImportBatch.objects.filter(pk=batch.pk).update(mapping_preset=foreign)
            batch = self.apply(batch, preset)
            with self.assertRaises(DatabaseError), transaction.atomic():
                ImportBatch.objects.filter(pk=batch.pk).update(mapping={})
            self.commit(batch)
            with self.assertRaises(DatabaseError), transaction.atomic():
                ImportBatch.objects.filter(pk=batch.pk).update(mapping_preset=None)

    def test_version_name_family_and_limit(self):
        with self.scoped():
            batch = self.ready()
            for name in ("", " leading", "x\ny", "x" * 81):
                with self.assertRaises(PortabilityError):
                    self.save(batch, name)
            preset = self.save(batch)
            with patch.object(presets, "MAX_VERSIONS", 1):
                self.assertEqual(self.save(batch).pk, preset.pk)
                with self.assertRaises(PortabilityError):
                    self.save(batch, "Another")
            different = self.ready(self.stage(system="another"))
            with self.assertRaises(PortabilityError):
                self.save(different)

    def test_save_rollback_and_tampered_preview_fail(self):
        with self.scoped():
            batch = self.ready()
            with patch("apps.tenant_apps.data_portability.presets.AuditLog.log", side_effect=RuntimeError("fixture")):
                with self.assertRaises(RuntimeError):
                    self.save(batch)
            self.assertFalse(MappingPresetVersion.objects.exists())
            batch.rows.update(raw={"Legacy": "changed"})
            with self.assertRaises(PortabilityError):
                self.save(batch)

    def test_all_child_profiles_and_stale_role_mapping_are_revalidated(self):
        from . import test_children, test_roles, test_relationships
        with self.scoped():
            self.commit(self.ready())
            self.commit(self.ready(self.stage(b"Legacy,Party,Phone\nold-2,Bina Shah,\n")))
            kind = PartyRoleType.objects.create(key="BORROWER", label="Borrower")
            records = {
                child_contracts.CONTACT: test_children.ChildPortabilityTests.record(self, child_contracts.CONTACT),
                child_contracts.ADDRESS: test_children.ChildPortabilityTests.record(self, child_contracts.ADDRESS),
                child_contracts.IDENTIFIER: {"party_source_system": "paper", "party_external_id": "old-1",
                    "identifier_type": "PASSPORT", "value": "AB001234", "source_is_verified": False},
                child_contracts.ROLE: test_roles.RolePortabilityTests.record(self),
                child_contracts.RELATIONSHIP: test_relationships.RelationshipPortabilityTests.record(self),
            }
            for profile, record in records.items():
                output = io.StringIO(newline="")
                writer = csv.writer(output)
                writer.writerow(["Legacy", *record])
                writer.writerow(["child-1", *[str(v).lower() if type(v) is bool else v for v in record.values()]])
                args = dict(workspace_id=self.a.pk, actor=self.actor, source_system="details", filename="children.csv",
                    profile=profile, content=output.getvalue().encode())
                batch = services.stage_import(**args)
                mapping = {"columns": {"Legacy": "source.external_id", **{k: k for k in record}}, "normalization": [
                    {"field": k, "rule": "boolean", "version": 1} for k, v in record.items() if type(v) is bool]}
                if profile == child_contracts.ROLE:
                    mapping["role_type_map"] = {"customer": "BORROWER"}
                batch = self.ready(batch, mapping)
                self.assertEqual(batch.state, "READY", list(batch.rows.values_list("issues", flat=True)))
                preset = self.save(batch, profile)
                applied = self.apply(services.stage_import(**args), preset)
                self.assertEqual(applied.state, "READY")
                if profile == child_contracts.ROLE:
                    PartyRoleType.objects.filter(pk=kind.pk).update(is_active=False)
                    with self.assertRaises(PortabilityError):
                        self.commit(applied)
                    self.assertEqual(self.apply(applied, preset).state, "NEEDS_MAPPING")
                else:
                    self.commit(applied)

    def test_web_save_apply_and_revalidate_current_mapping(self):
        with self.scoped():
            batch = self.ready()
            def request(batch, data=None):
                req = RequestFactory().post("/", data) if data else RequestFactory().get("/")
                req.workspace, req.user = self.a, self.actor
                return views.batch_detail(req, batch.public_id)
            self.assertContains(request(batch), "Save this reviewed mapping as a preset")
            self.assertEqual(request(batch, {"action": "save_preset", "preset_name": "Register",
                "approval_digest": batch.approval_digest}).status_code, 302)
            preset = MappingPresetVersion.objects.get()
            saved_request = RequestFactory().get("/", {"saved_preset": str(preset.public_id)})
            saved_request.workspace, saved_request.user = self.a, self.actor
            self.assertContains(views.batch_detail(saved_request, batch.public_id), "Saved mapping preset Register, version 1.")
            target = self.stage()
            self.assertContains(request(target), "Register")
            self.assertEqual(request(target, {"action": "apply_preset", "preset_id": str(preset.public_id)}).status_code, 302)
            target.refresh_from_db()
            self.assertEqual(target.mapping_preset_id, preset.pk)
            self.assertEqual(request(target, {"action": "revalidate_mapping"}).status_code, 302)
            self.assertContains(request(target, {"action": "apply_preset", "preset_id": "invalid"}), "preset version is unavailable")

    def test_cancelled_batch_retains_preset_and_rejects_further_actions(self):
        with self.scoped():
            preset = self.save(self.ready())
            batch = self.apply(self.stage(), preset)
            services.cancel_import(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id)
            batch.refresh_from_db()
            self.assertEqual(batch.mapping_preset_id, preset.pk)
            self.assertEqual(batch.rows.get().raw, {})
            with self.assertRaises(PortabilityError):
                self.apply(batch, preset)
            with self.assertRaises(PortabilityError):
                self.save(batch)
