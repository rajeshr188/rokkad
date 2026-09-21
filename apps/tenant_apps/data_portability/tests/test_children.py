import copy
import json
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import RequestFactory, override_settings
from django.urls import reverse

from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod
from apps.tenant_apps.data_portability import child_contracts as contract, services, views
from apps.tenant_apps.data_portability.contracts import dump
from apps.tenant_apps.data_portability.models import ChildIdentity, ChildSourceIdentity, ImportRow, PartyIdentity
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class ChildPortabilityTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        with self.scoped():
            self.commit(self.ready())

    def record(self, profile=contract.CONTACT, **changes):
        record = {"party_source_system": "paper", "party_external_id": "old-1", "source_is_verified": False}
        if profile == contract.CONTACT:
            record.update(contact_type="EMAIL", label="Home", value="ASHA@EXAMPLE.COM", is_primary=True)
        else:
            record.update(address_type="HOME", line1="12 Market Road", line2=None, area=None, city="Pune",
                          state="Maharashtra", postal_code="001234", country="IN", is_default=True)
        return {**record, **changes}

    def child_ready(self, record=None, *, profile=contract.CONTACT, external="detail-1", records=None):
        records = records or [record or self.record(profile)]
        # CSV-shaped raw strings with explicit reviewed boolean normalization/defaults.
        import csv, io
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Legacy", *records[0]])
        for index, item in enumerate(records):
            writer.writerow([external if index == 0 else external + str(index), *[
                str(v).lower() if type(v) is bool else v for v in item.values()]])
        batch = services.stage_import(workspace_id=self.a.pk, actor=self.actor, content=output.getvalue().encode(),
            filename="details.csv", source_system="details", profile=profile)
        mapping = {"columns": {"Legacy": "source.external_id", **{k: k for k in records[0]}}, "normalization": [
            {"field": k, "rule": "boolean", "version": 1} for k in records[0] if k in {"is_primary", "is_default", "source_is_verified"}]}
        return self.ready(batch, mapping)

    def export(self, profile, workspace=None):
        return services.export_children(workspace_id=(workspace or self.a).pk, actor=self.actor, profile=profile)

    def restore(self, exported, profile, workspace):
        batch = services.stage_import(workspace_id=workspace.pk, actor=self.actor, content=exported.content,
            filename="details.jsonl", source_system=exported.namespace, profile=profile)
        return self.ready(batch, {}, workspace)

    def test_contact_staging_preview_commit_and_noop(self):
        with self.scoped():
            batch = self.child_ready()
            self.assertEqual(batch.state, "READY")
            self.assertFalse(PartyContactMethod.objects.exists())
            self.assertTrue(any(i["code"] == "PARTY_NORMALIZED" for i in batch.rows.get().issues))
            self.commit(batch)
            self.assertEqual(Party.objects.get().primary_email, "asha@example.com")
            self.assertEqual(PartyContactMethod.objects.get().normalized_value, "asha@example.com")
            self.commit(self.child_ready())
            self.assertEqual(PartyContactMethod.objects.count(), 1)
            self.assertEqual(ChildSourceIdentity.objects.count(), 1)
            self.assertEqual(ImportRow.objects.filter(child_identity__isnull=False).count(), 2)

    def test_address_roundtrip_and_contact_roundtrip(self):
        with self.scoped():
            self.commit(self.child_ready())
            self.commit(self.child_ready(profile=contract.ADDRESS))
            master = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            exports = {p: self.export(p) for p in (contract.CONTACT, contract.ADDRESS)}
            self.assertEqual(exports[contract.CONTACT], self.export(contract.CONTACT))
        with self.scoped(self.b):
            missing = self.restore(exports[contract.CONTACT], contract.CONTACT, self.b)
            self.assertEqual(missing.summary["conflicts"], 1)
            self.commit(self.restore(master, "party-master/1", self.b), self.b)
            for profile, exported in exports.items():
                self.commit(self.restore(exported, profile, self.b), self.b)
                self.commit(self.restore(exported, profile, self.b), self.b)
            self.assertEqual(PartyContactMethod.objects.count(), 1)
            self.assertEqual(PartyAddress.objects.get().postal_code, "001234")
            self.assertEqual(Party.objects.get().primary_email, "asha@example.com")
            self.assertEqual(PartyAddress.objects.count(), 1)
            self.assertEqual(ChildIdentity.objects.count(), 2)

    def test_source_changes_and_local_edits_conflict(self):
        with self.scoped():
            self.commit(self.child_ready())
            self.assertEqual(self.child_ready(self.record(value="different@example.com")).summary["conflicts"], 1)
            PartyContactMethod.objects.update(label="Edited locally")
            self.assertEqual(self.child_ready().summary["conflicts"], 1)

    def test_missing_and_other_workspace_parent_fail(self):
        with self.scoped():
            for record in [self.record(party_external_id="missing"), self.record(party_external_id=str(self.b.pk))]:
                batch = self.child_ready(record)
                self.assertEqual(batch.summary["conflicts"], 1)
                with self.assertRaises(PortabilityError):
                    self.commit(batch)
        with self.scoped(self.b):
            self.assertFalse(ChildIdentity.objects.exists())

    def test_primary_and_default_collisions_block_without_demoting(self):
        with self.scoped():
            for profile in (contract.CONTACT, contract.ADDRESS):
                self.commit(self.child_ready(profile=profile))
                record = self.record(profile, **({"value": "another@example.com"} if profile == contract.CONTACT else {"line1": "Another road"}))
                self.assertEqual(self.child_ready(record, profile=profile, external="other").summary["conflicts"], 1)
            self.assertTrue(PartyContactMethod.objects.get().is_primary)
            self.assertTrue(PartyAddress.objects.get().is_default)

    def test_batch_duplicates_and_two_defaults_block_all(self):
        with self.scoped():
            for profile in (contract.CONTACT, contract.ADDRESS):
                first = self.record(profile)
                second = self.record(profile, **({"value": "other@example.com"} if profile == contract.CONTACT else {"line1": "Other street"}))
                batch = self.child_ready(profile=profile, records=[first, second])
                self.assertEqual(batch.summary["rows_with_errors"], 2)
            self.assertFalse(PartyContactMethod.objects.exists())
            self.assertFalse(PartyAddress.objects.exists())

    def test_summary_change_is_previewed_and_requires_acknowledgment(self):
        with self.scoped():
            Party.objects.update(primary_email="old@example.com")
            batch = self.child_ready()
            self.assertEqual(batch.summary["rows_with_warnings"], 1)
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.commit(batch, acknowledge_warnings=True)
            self.assertEqual(Party.objects.get().primary_email, "asha@example.com")

    def review_addresses(self, batch, **changes):
        from apps.tenant_apps.data_portability.address_reviews import review_distinct_addresses
        return review_distinct_addresses(**{**dict(workspace_id=self.a.pk, actor=self.actor,
            batch_id=batch.public_id, external_ids=list(batch.rows.values_list('external_id', flat=True)),
            reason='Owner confirms distinct source addresses.', approval_digest=batch.approval_digest), **changes})

    def test_reviewed_matching_addresses_keep_separate_ids_and_default(self):
        with self.scoped():
            batch = self.child_ready(profile=contract.ADDRESS, records=[self.record(contract.ADDRESS), self.record(contract.ADDRESS, is_default=False)])
            self.assertEqual(batch.summary['conflicts'], 2)
            batch = self.review_addresses(batch)
            self.assertEqual(batch.summary['conflicts'], 0)
            with self.assertRaises(PortabilityError): self.commit(batch)
            self.commit(batch, acknowledge_warnings=True)
            self.commit(batch, acknowledge_warnings=True)
            self.assertEqual(PartyAddress.objects.count(), 2)
            self.assertEqual(PartyAddress.objects.filter(is_default=True).count(), 1)
            self.assertEqual(len(set(batch.rows.values_list('child_identity_id', flat=True))), 2)
            exported = [json.loads(s) for s in self.export(contract.ADDRESS).content.splitlines()]
            self.assertEqual(len({r['id'] for r in exported}), 2)

    def test_address_review_keeps_partial_review_default_and_source_id_conflicts(self):
        with self.scoped():
            record = self.record(contract.ADDRESS, is_default=False)
            batch = self.child_ready(profile=contract.ADDRESS, records=[record, record])
            batch = self.review_addresses(batch, external_ids=['detail-1'])
            self.assertEqual(batch.summary['conflicts'], 2)
            defaults = self.child_ready(profile=contract.ADDRESS, records=[self.record(contract.ADDRESS)] * 2)
            self.assertEqual(self.review_addresses(defaults).summary['conflicts'], 2)
            batch.rows.filter(source_row=batch.rows.last().source_row).update(raw=batch.rows.first().raw)
            batch = services.validate_import(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id, mapping=batch.mapping)
            with self.assertRaises(PortabilityError): self.review_addresses(batch, external_ids=['detail-1'])
            self.assertFalse(PartyAddress.objects.exists())

    def test_address_review_binds_values_destination_and_cannot_be_a_preset(self):
        from apps.tenant_apps.data_portability.presets import save_preset
        with self.scoped():
            batch = self.review_addresses(self.child_ready(profile=contract.ADDRESS, record=self.record(contract.ADDRESS, is_default=False)))
            with self.assertRaises(PortabilityError):
                save_preset(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id, name='Addresses', approval_digest=batch.approval_digest)
            PartyAddress.objects.create(party=Party.objects.get(), **{k:v if k == 'is_default' else v or '' for k,v in self.record(contract.ADDRESS, is_default=False).items() if k in contract.ADDRESS_FIELDS})
            with self.assertRaises(PortabilityError): self.commit(batch, acknowledge_warnings=True)
            mapping = copy.deepcopy(batch.mapping)
            mapping['defaults']['area'] = 'Changed area'
            batch = services.validate_import(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id, mapping=mapping)
            self.assertTrue(any(i['code']=='ADDRESS_REVIEW_CHANGED' for i in batch.rows.get().issues))

    def test_address_review_requires_current_authorized_preview(self):
        with self.scoped():
            batch = self.child_ready(profile=contract.ADDRESS)
            with self.assertRaises(PermissionDenied): self.review_addresses(batch, actor=self.other_actor)
            with self.assertRaises(PortabilityError): self.review_addresses(batch, approval_digest='stale')
            with self.assertRaises(PortabilityError): self.review_addresses(batch, reason='')
        with self.scoped(self.b):
            with self.assertRaises(PermissionDenied): self.review_addresses(batch, workspace_id=self.b.pk)

    def test_address_review_http_action_only_revalidates(self):
        with self.scoped():
            batch = self.child_ready(profile=contract.ADDRESS, records=[self.record(contract.ADDRESS, is_default=False)]*2)
            req = RequestFactory().post('/', {'action':'review_distinct_addresses', 'source_ids':'detail-1\ndetail-11',
                'reason':'Confirmed separate source address records.', 'approval_digest':batch.approval_digest})
            req.user=self.actor;req.workspace=self.a
            self.assertEqual(views.batch_detail(req,batch.public_id).status_code,302)
            batch.refresh_from_db()
            self.assertEqual(batch.summary['conflicts'],0)
            self.assertEqual(len(batch.mapping['address_reviews']),2)
            self.assertFalse(PartyAddress.objects.exists())

    def test_source_verification_is_provenance_only(self):
        with self.scoped():
            batch = self.child_ready(self.record(source_is_verified=True))
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.commit(batch, acknowledge_warnings=True)
            self.assertFalse(PartyContactMethod.objects.get().is_verified)
            self.assertTrue(json.loads(self.export(contract.CONTACT).content)["source_is_verified"])

    def test_invalid_phone_email_website_and_address(self):
        with self.scoped():
            for kind, value in [("PHONE", "bad"), ("EMAIL", "bad"), ("WEBSITE", "bad")]:
                self.assertGreater(self.child_ready(self.record(contact_type=kind, value=value)).summary["rows_with_errors"], 0)
            self.assertGreater(self.child_ready(self.record(contract.ADDRESS, city=""), profile=contract.ADDRESS).summary["rows_with_errors"], 0)

    def test_destination_change_after_preview_blocks_commit(self):
        with self.scoped():
            batch = self.child_ready()
            PartyContactMethod.objects.create(party=Party.objects.get(), contact_type="EMAIL", value="native@example.com", is_primary=True)
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.assertFalse(ChildIdentity.objects.exists())

    def test_failure_rolls_back_children_summary_and_evidence(self):
        with self.scoped():
            batch = self.child_ready()
            with patch("apps.tenant_apps.data_portability.children.ChildSourceIdentity.objects.create", side_effect=RuntimeError("fixture")):
                with self.assertRaises(RuntimeError):
                    self.commit(batch)
            self.assertFalse(PartyContactMethod.objects.exists())
            self.assertFalse(ChildIdentity.objects.exists())
            self.assertFalse(Party.objects.get().primary_email)
            self.assertIsNone(batch.rows.get().committed_at)

    def test_native_delete_leaves_tombstone_and_replay_conflicts(self):
        with self.scoped():
            self.commit(self.child_ready())
            PartyContactMethod.objects.get().delete()
            self.assertIsNone(ChildIdentity.objects.get().contact_id)
            self.assertEqual(self.child_ready().summary["conflicts"], 1)

    def test_sql_ownership_parent_result_and_immutability_guards(self):
        with self.scoped():
            self.commit(self.child_ready())
            identity = ChildIdentity.objects.get()
            other = Party.objects.create(display_name="Other")
            parent = PartyIdentity.objects.create(party=other)
            invalid = [
                ("UPDATE data_portability_childidentity SET parent_id=%s WHERE id=%s", [parent.pk, identity.pk]),
                ("UPDATE data_portability_childidentity SET workspace_id=%s WHERE id=%s", [self.b.pk, identity.pk]),
                ("UPDATE data_portability_childsourceidentity SET external_id='changed'", []),
                ("UPDATE data_portability_importrow SET child_identity_id=NULL WHERE child_identity_id=%s", [identity.pk]),
            ]
            for sql, args in invalid:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(sql, args)
        with self.scoped(self.b):
            self.assertFalse(ChildIdentity.objects.exists())
            self.assertFalse(ChildSourceIdentity.objects.exists())
            with self.assertRaises(DatabaseError), transaction.atomic():
                ChildIdentity.objects.create(workspace_id=self.b.pk, parent_id=identity.parent_id, profile=contract.CONTACT, contact_id=identity.contact_id)

    def test_context_actor_and_edit_permissions_precede_replay(self):
        with self.scoped():
            batch = self.child_ready()
            self.commit(batch)
            with patch("apps.tenant_apps.data_portability.access.PARTY_ACTION_PERMISSIONS", {"view": ["contact.view"], "edit": ["never.granted"]}):
                # Owner policy may grant all registered actions; use revoked actor instead.
                with self.assertRaises(PermissionDenied):
                    services.commit_import(workspace_id=self.a.pk, actor=self.other_actor, batch_id=batch.public_id, approval_digest=batch.approval_digest)
            with self.assertRaises(PermissionDenied):
                services.export_children(workspace_id=self.a.pk, actor=None, profile=contract.CONTACT)
        with self.assertRaises(PermissionDenied):
            self.export(contract.CONTACT)

    def test_native_multiple_phone_primaries_preserve_summary_on_roundtrip(self):
        with self.scoped():
            party = Party.objects.get()
            PartyContactMethod.objects.create(party=party, contact_type="PHONE", value="+919876543210", is_primary=True)
            PartyContactMethod.objects.create(party=party, contact_type="MOBILE", value="+919876543211", is_primary=True)
            party.primary_phone = "+919876543210"
            party.save()
            master = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            exported = self.export(contract.CONTACT)
        with self.scoped(self.b):
            self.commit(self.restore(master, "party-master/1", self.b), self.b)
            self.commit(self.restore(exported, contract.CONTACT, self.b), self.b, acknowledge_warnings=True)
            self.assertEqual(Party.objects.get().primary_phone, "+919876543210")
            self.assertEqual(PartyContactMethod.objects.filter(is_primary=True).count(), 2)

    def test_schema_frozen_and_export_screen_profiles(self):
        for profile in (contract.CONTACT, contract.ADDRESS):
            path = Path(__file__).resolve().parents[4] / "docs/contracts" / (profile.replace("/", "-v") + ".schema.json")
            self.assertEqual(json.loads(path.read_text()), contract.schema(profile))
        with self.scoped():
            request = RequestFactory().get("/", {"schema": "1", "profile": contract.ADDRESS})
            request.user, request.workspace = self.actor, self.a
            self.assertEqual(json.loads(views.export(request).content)["title"], contract.ADDRESS)
            request = RequestFactory().post("/", {"profile": contract.CONTACT})
            request.user, request.workspace = self.actor, self.a
            response = views.export(request)
            self.assertEqual(response["X-Rokkad-Profile"], contract.CONTACT)

    def test_unknown_profile_and_mapping_parent_normalization_rejected(self):
        with self.scoped():
            with self.assertRaises(PortabilityError):
                services.stage_import(workspace_id=self.a.pk, actor=self.actor, content=b"a\nx\n", filename="x.csv", source_system="x", profile="loans/1")
            from apps.tenant_apps.data_portability.mapping import validate_mapping
            with self.assertRaises(PortabilityError):
                validate_mapping({"columns": {"id": "source.external_id"}, "normalization": [{"field": "party_external_id", "rule": "trim", "version": 1}]}, ["id"], "csv", profile=contract.CONTACT)


    def test_edit_grant_required_but_create_grant_not_required(self):
        from apps.orgs.models import Membership, WorkspaceRoleGrant
        with self.scoped():
            membership = Membership.objects.get(company=self.a, user=self.actor)
            grants = WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id)
            grants.filter(permission__codename__in=["contact_create", "data_create"]).delete()
            batch = self.child_ready()
            self.commit(batch)
            grants.filter(permission__codename__in=["contact_edit", "data_edit"]).delete()
            with self.assertRaises(PermissionDenied):
                self.commit(batch)

    def test_moved_child_conflicts_instead_of_rebinding(self):
        with self.scoped():
            self.commit(self.child_ready())
            other = Party.objects.create(display_name="Moved destination", primary_email="asha@example.com")
            PartyContactMethod.objects.update(party=other)
            self.assertEqual(self.child_ready().summary["conflicts"], 1)
            with self.assertRaises(PortabilityError):
                self.export(contract.CONTACT)

    def test_inconsistent_native_summary_export_fails_without_partial_file(self):
        with self.scoped():
            self.commit(self.child_ready())
            Party.objects.update(primary_email="different@example.com")
            with self.assertRaises(PortabilityError):
                self.export(contract.CONTACT)

    def test_cancel_and_foreign_batch_do_not_write_children(self):
        with self.scoped():
            batch = self.child_ready()
            services.cancel_import(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id)
            self.assertEqual(batch.rows.get().raw, {})
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.assertFalse(PartyContactMethod.objects.exists())
        with self.scoped(self.b):
            with self.assertRaises(PermissionDenied):
                services.preview_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id)
