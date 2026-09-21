import csv
import io
import json
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, override_settings

from apps.orgs.models import Membership, WorkspaceRoleGrant
from apps.tenant_apps.party.models import Party, PartyRole, PartyRoleType
from apps.tenant_apps.data_portability import child_contracts as contract, services, views
from apps.tenant_apps.data_portability.models import ChildIdentity, ChildSourceIdentity
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RolePortabilityTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        with self.scoped():
            self.commit(self.ready())
            self.kind = PartyRoleType.objects.create(key="BORROWER", label="Borrower")

    def record(self, **changes):
        return {"party_source_system": "paper", "party_external_id": "old-1", "role_type_key": "customer",
                "status": "ACTIVE", "segment": "RETAIL", "effective_from": "2020-01-01", "effective_to": None, **changes}

    def role_ready(self, *, records=None, role_map=None, external="r1"):
        records = records or [self.record()]
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Legacy", *records[0]])
        for index, record in enumerate(records):
            writer.writerow([external + str(index), *record.values()])
        batch = services.stage_import(workspace_id=self.a.pk, actor=self.actor, profile=contract.ROLE,
            source_system="roles", filename="roles.csv", content=output.getvalue().encode())
        return self.ready(batch, {"columns": {"Legacy": "source.external_id", **{k: k for k in records[0]}},
            "role_type_map": {"customer": "BORROWER"} if role_map is None else role_map})

    def restore(self, exported, profile, workspace, role_map=None):
        batch = services.stage_import(workspace_id=workspace.pk, actor=self.actor, profile=profile,
            content=exported.content, source_system=exported.namespace, filename="roles.jsonl")
        return self.ready(batch, {"role_type_map": role_map or {}} if profile == contract.ROLE else {}, workspace)

    def test_explicit_mapping_preview_commit_and_replay(self):
        with self.scoped():
            missing = self.role_ready(role_map={})
            self.assertEqual(missing.summary["rows_with_errors"], 1)
            self.assertFalse(PartyRole.objects.exists())
            batch = self.role_ready()
            self.assertEqual(batch.rows.get().canonical["_role_type"]["key"], "BORROWER")
            self.commit(batch)
            self.commit(self.role_ready())
            self.assertEqual(PartyRole.objects.count(), 1)
            self.assertEqual(PartyRole.objects.get().role_type_id, self.kind.pk)
            self.assertEqual(PartyRoleType.objects.count(), 1)
            self.assertEqual(Membership.objects.filter(company=self.a).count(), 1)

    def test_roundtrip_with_different_destination_role_key(self):
        with self.scoped():
            self.commit(self.role_ready())
            master = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            exported = services.export_children(workspace_id=self.a.pk, actor=self.actor, profile=contract.ROLE)
            self.assertEqual(exported, services.export_children(workspace_id=self.a.pk, actor=self.actor, profile=contract.ROLE))
            self.commit(self.restore(exported, contract.ROLE, self.a, {"BORROWER": "BORROWER"}))
        with self.scoped(self.b):
            target = PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
            self.commit(self.restore(master, "party-master/1", self.b), self.b)
            self.assertEqual(self.restore(exported, contract.ROLE, self.b).summary["rows_with_errors"], 1)
            self.commit(self.restore(exported, contract.ROLE, self.b, {"BORROWER": "CUSTOMER"}), self.b)
            self.commit(self.restore(exported, contract.ROLE, self.b, {"BORROWER": "CUSTOMER"}), self.b)
            obj = PartyRole.objects.get()
            self.assertEqual(obj.role_type_id, target.pk)
            self.assertEqual(str(obj.effective_from), "2020-01-01")

    def test_inactive_and_foreign_type_mapping_fail(self):
        with self.scoped(self.b):
            PartyRoleType.objects.create(key="FOREIGN", label="Foreign")
        with self.scoped():
            self.assertEqual(self.role_ready(role_map={"customer": "FOREIGN"}).summary["rows_with_errors"], 1)
            PartyRoleType.objects.filter(pk=self.kind.pk).update(is_active=False)
            self.assertEqual(self.role_ready().summary["rows_with_errors"], 1)

    def test_definition_change_invalidates_approval(self):
        with self.scoped():
            batch = self.role_ready()
            PartyRoleType.objects.filter(pk=self.kind.pk).update(label="Changed after preview")
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.assertFalse(PartyRole.objects.exists())

    def test_active_duplicates_and_identical_history_conflict(self):
        with self.scoped():
            batch = self.role_ready(records=[self.record(), self.record(segment="WHOLESALE")])
            self.assertEqual(batch.summary["rows_with_errors"], 2)
            self.commit(self.role_ready())
            self.assertEqual(self.role_ready(external="other").summary["conflicts"], 1)
            ended = self.record(status="ENDED", effective_to="2021-01-01")
            self.commit(self.role_ready(records=[ended], external="ended"))
            self.assertEqual(self.role_ready(records=[ended], external="duplicate").summary["conflicts"], 1)

    def test_distinct_history_rows_import_without_creating_active_role(self):
        with self.scoped():
            self.commit(self.role_ready(records=[self.record(status="ENDED", effective_to="2021-01-01"),
                self.record(status="INACTIVE", effective_from="2022-01-01")]))
            self.assertEqual(PartyRole.objects.count(), 2)
            self.assertFalse(PartyRole.objects.filter(status="ACTIVE").exists())

    def test_bad_status_dates_missing_parent_and_metadata_fail(self):
        with self.scoped():
            for changes in [{"status": "INVALID"}, {"effective_from": "01/01/2020"}, {"segment": "x" * 65}, {"party_external_id": "missing"}]:
                self.assertEqual(self.role_ready(records=[self.record(**changes)]).summary["rows_with_errors"], 1)
            record, issues = contract.validate_child({**self.record(), "metadata": {"x": 1}}, contract.ROLE, role_map={"customer": "BORROWER"})
            self.assertTrue(any(i["code"] == "UNKNOWN_FIELD" for i in issues))

    def test_source_local_and_mapping_changes_conflict(self):
        with self.scoped():
            self.commit(self.role_ready())
            self.assertEqual(self.role_ready(records=[self.record(segment="changed")]).summary["conflicts"], 1)
            PartyRoleType.objects.create(key="OTHER", label="Other")
            self.assertEqual(self.role_ready(role_map={"customer": "OTHER"}).summary["conflicts"], 1)
            PartyRole.objects.update(status="ENDED")
            self.assertEqual(self.role_ready().summary["conflicts"], 1)

    def test_rollback_and_native_deletion_tombstone(self):
        with self.scoped():
            batch = self.role_ready()
            with patch("apps.tenant_apps.data_portability.children.ChildSourceIdentity.objects.create", side_effect=RuntimeError("fixture")):
                with self.assertRaises(RuntimeError):
                    self.commit(batch)
            self.assertFalse(PartyRole.objects.exists())
            self.assertFalse(ChildIdentity.objects.exists())
            self.commit(batch)
            PartyRole.objects.get().delete()
            self.assertIsNone(ChildIdentity.objects.get().role_id)
            self.assertEqual(self.role_ready().summary["conflicts"], 1)

    def test_replay_permissions_and_foreign_workspace(self):
        with self.scoped():
            batch = self.role_ready()
            self.commit(batch)
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                permission__codename__in=["contact_edit", "data_edit"]).delete()
            with self.assertRaises(PermissionDenied):
                self.commit(batch)
        with self.scoped(self.b):
            self.assertFalse(ChildIdentity.objects.exists())
            self.assertFalse(ChildSourceIdentity.objects.exists())
            with self.assertRaises(PermissionDenied):
                services.preview_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id)

    def test_sql_guards_and_metadata_export(self):
        with self.scoped():
            self.commit(self.role_ready())
            identity = ChildIdentity.objects.get()
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.filter(pk=identity.pk).update(role=None)
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS portability_child_tombstone_guard IMMEDIATE")
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.filter(pk=identity.pk).update(profile=contract.CONTACT)
            PartyRole.objects.update(metadata={"source": "unsupported"})
            with self.assertRaises(PortabilityError):
                services.export_children(workspace_id=self.a.pk, actor=self.actor, profile=contract.ROLE)

    def test_frozen_schema_and_jsonl_mapping_ui(self):
        schema_path = Path(__file__).resolve().parents[4] / "docs/contracts/party-role-v1.schema.json"
        self.assertEqual(json.loads(schema_path.read_text()), contract.schema(contract.ROLE))
        with self.scoped():
            self.commit(self.role_ready())
            exported = services.export_children(workspace_id=self.a.pk, actor=self.actor, profile=contract.ROLE)
            batch = services.stage_import(workspace_id=self.a.pk, actor=self.actor, profile=contract.ROLE,
                content=exported.content, filename="roles.jsonl", source_system=exported.namespace)
            request = RequestFactory().get("/")
            request.workspace, request.user = self.a, self.actor
            response = views.batch_detail(request, batch.public_id)
            self.assertContains(response, "Source role BORROWER")
            request = RequestFactory().post("/", {"action": "validate", "role_type_0": "BORROWER"})
            request.workspace, request.user = self.a, self.actor
            self.assertEqual(views.batch_detail(request, batch.public_id).status_code, 302)
            batch.refresh_from_db()
            self.assertEqual(batch.state, "READY")
