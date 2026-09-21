import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, override_settings

from apps.orgs.models import Membership, WorkspaceRoleGrant
from apps.tenant_apps.party.models import Party, PartyIdentifier
from apps.tenant_apps.data_portability import child_contracts as contract, services, views
from apps.tenant_apps.data_portability.models import ChildIdentity, ChildSourceIdentity, PartyIdentity
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
from apps.tenant_apps.data_portability.tests import test_children


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class IdentifierPortabilityTests(PortabilityFixture):
    child_ready = test_children.ChildPortabilityTests.child_ready
    export = test_children.ChildPortabilityTests.export
    restore = test_children.ChildPortabilityTests.restore

    def setUp(self):
        super().setUp()
        with self.scoped():
            self.commit(self.ready())

    def record(self, profile=contract.IDENTIFIER, **changes):
        return {"party_source_system": "paper", "party_external_id": "old-1", "source_is_verified": False,
                "identifier_type": "PASSPORT", "value": " ab001234 ", "masked_value": "****1234",
                "expires_on": "2030-12-31", **changes}

    def identifier_ready(self, **changes):
        return self.child_ready(self.record(**changes), profile=contract.IDENTIFIER)

    def test_stage_normalize_commit_and_unchanged_replay(self):
        with self.scoped():
            batch = self.identifier_ready()
            self.assertFalse(PartyIdentifier.objects.exists())
            self.assertEqual(batch.rows.get().raw["value"], " ab001234 ")
            self.assertEqual(batch.rows.get().canonical["value"], "AB001234")
            self.commit(batch)
            self.commit(self.identifier_ready())
            obj = PartyIdentifier.objects.get()
            self.assertEqual(obj.value, "AB001234")
            self.assertEqual(obj.masked_value, "****1234")
            self.assertEqual(obj.expires_on, date(2030, 12, 31))
            self.assertEqual(ChildIdentity.objects.get().identifier_id, obj.pk)
            self.assertFalse(Party.objects.get().tax_pan)
            self.assertFalse(Party.objects.get().gstin)

    def test_clean_workspace_roundtrip_and_same_workspace_noop(self):
        with self.scoped():
            self.commit(self.identifier_ready())
            master = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            exported = self.export(contract.IDENTIFIER)
            self.assertEqual(exported, self.export(contract.IDENTIFIER))
            self.commit(self.restore(exported, contract.IDENTIFIER, self.a))
            self.assertEqual(PartyIdentifier.objects.count(), 1)
        with self.scoped(self.b):
            missing = self.restore(exported, contract.IDENTIFIER, self.b)
            self.assertEqual(missing.summary["conflicts"], 1)
            self.commit(self.restore(master, "party-master/1", self.b), self.b)
            self.commit(self.restore(exported, contract.IDENTIFIER, self.b), self.b)
            self.commit(self.restore(exported, contract.IDENTIFIER, self.b), self.b)
            obj = PartyIdentifier.objects.get()
            self.assertEqual(obj.value, "AB001234")
            self.assertEqual(obj.expires_on, date(2030, 12, 31))
            self.assertEqual(ChildIdentity.objects.count(), 1)

    def test_type_collision_and_duplicate_batch_never_overwrite(self):
        with self.scoped():
            batch = self.child_ready(profile=contract.IDENTIFIER, records=[self.record(), self.record(value="OTHER")])
            self.assertEqual(batch.summary["rows_with_errors"], 2)
            self.commit(self.identifier_ready())
            collision = self.child_ready(self.record(value="OTHER"), profile=contract.IDENTIFIER, external="new-id")
            self.assertEqual(collision.summary["conflicts"], 1)
            self.assertEqual(PartyIdentifier.objects.get().value, "AB001234")

    def test_invalid_types_values_dates_and_files_block(self):
        with self.scoped():
            for changes in [{"identifier_type": "UNKNOWN"}, {"value": ""}, {"value": "x" * 129},
                            {"expires_on": "31/12/2030"}, {"expires_on": "2030-02-30"},
                            {"source_verified_at": "2030-01-01T12:00:00"}]:
                self.assertGreater(self.identifier_ready(**changes).summary["rows_with_errors"], 0)
            for key in ("document", "file_ref", "metadata", "value_hash", "verified_at", "is_verified"):
                _, issues = contract.validate_child({**self.record(), key: "untrusted"}, contract.IDENTIFIER)
                self.assertTrue(any(i["code"] == "UNKNOWN_FIELD" for i in issues))

    def test_source_verification_timestamp_retained_without_local_verification(self):
        with self.scoped():
            batch = self.identifier_ready(source_is_verified=True, source_verified_at="2024-01-02T10:00:00+00:00")
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.commit(batch, acknowledge_warnings=True)
            obj = PartyIdentifier.objects.get()
            self.assertFalse(obj.is_verified)
            self.assertIsNone(obj.verified_at)
            exported = json.loads(self.export(contract.IDENTIFIER).content)
            self.assertTrue(exported["source_is_verified"])
            self.assertEqual(exported["source_verified_at"], "2024-01-02T10:00:00+00:00")

    def test_changed_source_local_edit_and_deleted_identifier_conflict(self):
        with self.scoped():
            self.commit(self.identifier_ready())
            self.assertEqual(self.identifier_ready(value="DIFFERENT").summary["conflicts"], 1)
            PartyIdentifier.objects.update(masked_value="changed")
            self.assertEqual(self.identifier_ready().summary["conflicts"], 1)
            PartyIdentifier.objects.get().delete()
            self.assertIsNone(ChildIdentity.objects.get().identifier_id)
            self.assertEqual(self.identifier_ready().summary["conflicts"], 1)

    def test_atomic_failure_and_stale_destination_do_not_leave_results(self):
        with self.scoped():
            batch = self.identifier_ready()
            with patch("apps.tenant_apps.data_portability.children.ChildSourceIdentity.objects.create", side_effect=RuntimeError("fixture")):
                with self.assertRaises(RuntimeError):
                    self.commit(batch)
            self.assertFalse(PartyIdentifier.objects.exists())
            self.assertFalse(ChildIdentity.objects.exists())
            PartyIdentifier.objects.create(party=Party.objects.get(), identifier_type="PASSPORT", value="NATIVE")
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.assertIsNone(batch.rows.get().committed_at)

    def test_sql_profile_parent_workspace_and_tombstone_guards(self):
        with self.scoped():
            self.commit(self.identifier_ready())
            identity = ChildIdentity.objects.get()
            other = Party.objects.create(display_name="Other")
            parent = PartyIdentity.objects.create(party=other)
            for sql, args in [
                ("UPDATE data_portability_childidentity SET parent_id=%s WHERE id=%s", [parent.pk, identity.pk]),
                ("UPDATE data_portability_childidentity SET profile='party-address/1' WHERE id=%s", [identity.pk]),
                ("UPDATE data_portability_childidentity SET workspace_id=%s WHERE id=%s", [self.b.pk, identity.pk]),
            ]:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(sql, args)
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.filter(pk=identity.pk).update(identifier=None)
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS portability_child_tombstone_guard IMMEDIATE")
        with self.scoped(self.b):
            self.assertFalse(ChildIdentity.objects.exists())
            self.assertFalse(ChildSourceIdentity.objects.exists())
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.create(parent_id=identity.parent_id, profile=contract.IDENTIFIER, identifier_id=identity.identifier_id)

    def test_authorization_before_replay_and_missing_context_denied(self):
        with self.scoped():
            batch = self.identifier_ready()
            self.commit(batch)
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                permission__codename__in=["contact_edit", "data_edit"]).delete()
            with self.assertRaises(PermissionDenied):
                self.commit(batch)
            with self.assertRaises(PermissionDenied):
                services.export_children(workspace_id=self.a.pk, actor=self.other_actor, profile=contract.IDENTIFIER)
        with self.assertRaises(PermissionDenied):
            self.export(contract.IDENTIFIER)

    def test_metadata_export_fails_instead_of_silently_losing_data(self):
        with self.scoped():
            PartyIdentifier.objects.create(party=Party.objects.get(), identifier_type="PAN", value="ABCDE1234F", metadata={"legacy": "fact"})
            with self.assertRaises(PortabilityError):
                self.export(contract.IDENTIFIER)
            self.assertFalse(ChildIdentity.objects.exists())

    def test_frozen_schema_and_profile_http_response(self):
        path = Path(__file__).resolve().parents[4] / "docs/contracts/party-identifier-v1.schema.json"
        self.assertEqual(json.loads(path.read_text()), contract.schema(contract.IDENTIFIER))
        with self.scoped():
            self.commit(self.identifier_ready())
            request = RequestFactory().post("/", {"profile": contract.IDENTIFIER})
            request.workspace, request.user = self.a, self.actor
            response = views.export(request)
            self.assertEqual(response["X-Rokkad-Profile"], contract.IDENTIFIER)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(json.loads(response.content)["value"], "AB001234")
