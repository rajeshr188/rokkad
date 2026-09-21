import csv
import io
import json
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, override_settings

from apps.orgs.models import Membership, WorkspaceRoleGrant
from apps.tenant_apps.party.models import Party, PartyRelationship
from apps.tenant_apps.data_portability import child_contracts as contract, services, views
from apps.tenant_apps.data_portability.forms import MappingForm
from apps.tenant_apps.data_portability.mapping import validate_mapping
from apps.tenant_apps.data_portability.models import ChildIdentity, ChildSourceIdentity, PartyIdentity
from apps.tenant_apps.data_portability.parsers import PortabilityError
from .fixtures import PortabilityFixture
from . import test_children


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RelationshipPortabilityTests(PortabilityFixture):
    export = test_children.ChildPortabilityTests.export
    restore = test_children.ChildPortabilityTests.restore

    def setUp(self):
        super().setUp()
        with self.scoped():
            self.commit(self.ready())
            self.commit(self.ready(self.stage(b"Legacy,Party,Phone\nold-2,Bina Shah,\n")))

    def record(self, **changes):
        return {"party_source_system": "paper", "party_external_id": "old-1",
                "to_party_source_system": "paper", "to_party_external_id": "old-2",
                "relationship_type": "FAMILY", "notes": "Sister", "is_active": True, **changes}

    def relationship_ready(self, *, records=None, external="r1"):
        records = records or [self.record()]
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Legacy", *records[0]])
        for index, record in enumerate(records):
            writer.writerow([external + str(index), *[str(v).lower() if type(v) is bool else v for v in record.values()]])
        batch = services.stage_import(workspace_id=self.a.pk, actor=self.actor, profile=contract.RELATIONSHIP,
            source_system="relationships", filename="relationships.csv", content=output.getvalue().encode())
        return self.ready(batch, {"columns": {"Legacy": "source.external_id", **{k: k for k in records[0]}},
            "normalization": [{"field": "is_active", "rule": "boolean", "version": 1}]})

    def test_preview_commit_and_replay(self):
        with self.scoped():
            batch = self.relationship_ready()
            self.assertEqual(batch.state, "READY", list(batch.rows.values_list("issues", flat=True)))
            self.assertFalse(PartyRelationship.objects.exists())
            self.commit(batch)
            self.commit(self.relationship_ready())
            obj = PartyRelationship.objects.get()
            self.assertEqual(obj.from_party.display_name, "Asha Devi")
            self.assertEqual(obj.to_party.display_name, "Bina Shah")
            self.assertEqual(ChildIdentity.objects.get().related_parent.party_id, obj.to_party_id)
            self.assertEqual(ChildSourceIdentity.objects.count(), 1)

    def test_roundtrip_preserves_both_endpoints_and_direction(self):
        with self.scoped():
            self.commit(self.relationship_ready(records=[self.record(), self.record(party_external_id="old-2",
                to_party_external_id="old-1", notes=None, is_active=False)]))
            master = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            exported = self.export(contract.RELATIONSHIP)
            self.assertEqual(exported, self.export(contract.RELATIONSHIP))
            self.commit(self.restore(exported, contract.RELATIONSHIP, self.a))
        with self.scoped(self.b):
            self.assertEqual(self.restore(exported, contract.RELATIONSHIP, self.b).summary["rows_with_errors"], 2)
            self.commit(self.restore(master, "party-master/1", self.b), self.b)
            self.commit(self.restore(exported, contract.RELATIONSHIP, self.b), self.b)
            self.commit(self.restore(exported, contract.RELATIONSHIP, self.b), self.b)
            self.assertEqual(set(PartyRelationship.objects.values_list("from_party__display_name", "to_party__display_name", "notes", "is_active")),
                {("Asha Devi", "Bina Shah", "Sister", True), ("Bina Shah", "Asha Devi", "", False)})

    def test_self_missing_foreign_and_database_id_references_fail(self):
        with self.scoped(self.b):
            foreign = Party.objects.create(display_name="Foreign")
            identity = PartyIdentity.objects.create(party=foreign)
            namespace = services.export_parties(workspace_id=self.b.pk, actor=self.actor).namespace
        with self.scoped():
            for changes in ({"to_party_external_id": "old-1"}, {"to_party_external_id": "missing"},
                    {"party_external_id": "missing"}, {"to_party_external_id": str(foreign.pk)},
                    {"to_party_source_system": "rokkad:" + namespace, "to_party_external_id": str(identity.public_id)}):
                batch = self.relationship_ready(records=[self.record(**changes)])
                self.assertEqual(batch.summary["rows_with_errors"], 1)
                with self.assertRaises(PortabilityError):
                    self.commit(batch)
            self.assertFalse(PartyRelationship.objects.exists())

    def test_duplicate_direction_type_conflicts_even_if_inactive(self):
        with self.scoped():
            self.assertEqual(self.relationship_ready(records=[self.record(), self.record(is_active=False)]).summary["conflicts"], 2)
            self.commit(self.relationship_ready())
            self.assertEqual(self.relationship_ready(records=[self.record(is_active=False)], external="other").summary["conflicts"], 1)
            self.commit(self.relationship_ready(records=[self.record(relationship_type="OTHER")], external="different-type"))
            self.assertEqual(PartyRelationship.objects.count(), 2)

    def test_changed_source_local_and_second_endpoint_fail(self):
        with self.scoped():
            self.commit(self.relationship_ready())
            self.assertEqual(self.relationship_ready(records=[self.record(notes="Changed")]).summary["conflicts"], 1)
            replay = self.relationship_ready()
            PartyRelationship.objects.update(notes="Edited locally")
            with self.assertRaises(PortabilityError):
                self.commit(replay)
            self.assertEqual(self.relationship_ready().summary["conflicts"], 1)
            third = Party.objects.create(display_name="Third")
            PartyRelationship.objects.update(to_party=third)
            self.assertEqual(self.relationship_ready().summary["conflicts"], 1)
            with self.assertRaises(PortabilityError):
                self.export(contract.RELATIONSHIP)

    def test_new_duplicate_after_preview_invalidates_approval(self):
        with self.scoped():
            batch = self.relationship_ready()
            ids = batch.rows.get().canonical["_parties"]
            PartyRelationship.objects.create(from_party_id=ids["from"], to_party_id=ids["to"], relationship_type="FAMILY")
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.assertEqual(PartyRelationship.objects.count(), 1)
            self.assertFalse(ChildIdentity.objects.exists())

    def test_rollback_delete_tombstone_and_no_rebinding(self):
        with self.scoped():
            batch = self.relationship_ready()
            with patch("apps.tenant_apps.data_portability.children.ChildSourceIdentity.objects.create", side_effect=RuntimeError("fixture")):
                with self.assertRaises(RuntimeError):
                    self.commit(batch)
            self.assertFalse(PartyRelationship.objects.exists())
            self.assertFalse(ChildIdentity.objects.exists())
            self.commit(batch)
            obj = PartyRelationship.objects.get()
            origin, target = obj.from_party, obj.to_party
            obj.delete()
            identity = ChildIdentity.objects.get()
            self.assertIsNone(identity.relationship_id)
            self.assertIsNotNone(identity.related_parent_id)
            self.assertEqual(self.relationship_ready().summary["conflicts"], 1)
            replacement = PartyRelationship.objects.create(from_party=origin, to_party=target, relationship_type="FAMILY")
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.filter(pk=identity.pk).update(relationship=replacement)

    def test_sql_guards_for_both_endpoints_and_live_detach(self):
        with self.scoped(self.b):
            foreign = PartyIdentity.objects.create(party=Party.objects.create(display_name="Foreign"))
        with self.scoped():
            self.commit(self.relationship_ready())
            identity = ChildIdentity.objects.get()
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.filter(pk=identity.pk).update(relationship=None)
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS portability_child_tombstone_guard IMMEDIATE")
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.filter(pk=identity.pk).update(related_parent=identity.parent)
            obj = PartyRelationship.objects.create(from_party=identity.relationship.to_party,
                to_party=identity.relationship.from_party, relationship_type="OTHER")
            for target in (foreign, identity.related_parent, None):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    ChildIdentity.objects.create(parent=identity.related_parent, related_parent=target,
                        relationship=obj, profile=contract.RELATIONSHIP)
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.create(parent=identity.related_parent, related_parent=identity.parent,
                    relationship=obj, profile=contract.CONTACT)
        with self.scoped(self.b):
            self.assertFalse(ChildIdentity.objects.exists())
            self.assertFalse(ChildSourceIdentity.objects.exists())

    def test_replay_requires_edit_and_other_workspace_cannot_preview(self):
        with self.scoped():
            batch = self.relationship_ready()
            self.commit(batch)
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                permission__codename__in=["contact_edit", "data_edit"]).delete()
            with self.assertRaises(PermissionDenied):
                self.commit(batch)
        with self.scoped(self.b):
            with self.assertRaises(PermissionDenied):
                services.preview_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id)

    def test_csv_mapping_ui_and_exact_reference_rules(self):
        with self.scoped():
            batch = self.relationship_ready()
            data = {"action": "validate", "trim": "on", "uppercase": "on",
                **{f"column_{i}": "source.external_id" if h == "Legacy" else h for i, h in enumerate(batch.headers)}}
            form = MappingForm(data, headers=batch.headers, profile=contract.RELATIONSHIP)
            self.assertTrue(form.is_valid(), form.errors)
            mapping = form.mapping()
            self.assertNotIn("source_is_verified", form.fields)
            self.assertFalse(any(r["field"] in contract.parent_fields(contract.RELATIONSHIP) for r in mapping["normalization"]))
            request = RequestFactory().post("/", data)
            request.workspace, request.user = self.a, self.actor
            self.assertEqual(views.batch_detail(request, batch.public_id).status_code, 302)
            batch.refresh_from_db()
            self.assertEqual(batch.state, "READY", list(batch.rows.values_list("issues", flat=True)))
            mapping["normalization"].append({"field": "to_party_external_id", "rule": "trim", "version": 1})
            with self.assertRaises(PortabilityError):
                validate_mapping(mapping, batch.headers, "csv", contract.RELATIONSHIP)

    def test_schema_jsonl_validation_and_unknown_fields(self):
        schema_path = Path(__file__).resolve().parents[4] / "docs/contracts/party-relationship-v1.schema.json"
        self.assertEqual(json.loads(schema_path.read_text(encoding="utf-8")), contract.schema(contract.RELATIONSHIP))
        with self.scoped():
            self.commit(self.relationship_ready())
            exported = self.export(contract.RELATIONSHIP)
            record = json.loads(exported.content)
            self.assertNotIn("_parties", record)
            self.assertNotIn("source_is_verified", record)
            for changes in ({"is_active": "true"}, {"relationship_type": "INVALID"}, {"_parties": {"to": 123}},
                            {"to_party_external_id": " old-2"}, {"notes": []}):
                _, errors = contract.validate_child({**record, **changes}, contract.RELATIONSHIP, canonical_source=True)
                self.assertTrue(any(i["severity"] == "ERROR" for i in errors))

    def test_first_export_binds_second_endpoint_against_moves(self):
        with self.scoped():
            parties = list(Party.objects.order_by("pk"))
            obj = PartyRelationship.objects.create(from_party=parties[0], to_party=parties[1], relationship_type="OTHER")
            self.export(contract.RELATIONSHIP)
            third = Party.objects.create(display_name="Third")
            PartyRelationship.objects.filter(pk=obj.pk).update(to_party=third)
            with self.assertRaises(PortabilityError):
                self.export(contract.RELATIONSHIP)
