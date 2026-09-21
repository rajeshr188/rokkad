import hashlib
import io
import json
import zipfile
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import Client, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, WorkspaceRoleGrant
from apps.tenant_apps.party.models import (Party, PartyAddress, PartyContactMethod,
    PartyIdentifier, PartyRole, PartyRoleType, PartyRelationship)
from apps.tenant_apps.data_portability import bundles, services
from apps.tenant_apps.data_portability.models import PartyIdentity, WorkspaceNamespace
from apps.tenant_apps.data_portability.parsers import PortabilityError
from .fixtures import PortabilityFixture


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BundleTests(PortabilityFixture):
    def export(self):
        return bundles.export_bundle(workspace_id=self.a.pk, actor=self.actor)

    def populate(self):
        first = Party.objects.create(display_name="Asha Devi")
        second = Party.objects.create(display_name="Bina Shah")
        PartyContactMethod.objects.create(party=first, contact_type="EMAIL", value="asha@example.com")
        PartyAddress.objects.create(party=first, address_type="HOME", line1="12 Road", city="Pune")
        PartyIdentifier.objects.create(party=first, identifier_type="PASSPORT", value="AB001234")
        role_type = PartyRoleType.objects.create(key="BORROWER", label="Borrower")
        PartyRole.objects.create(party=first, role_type=role_type, status="ACTIVE", effective_from="2020-01-01")
        PartyRelationship.objects.create(from_party=first, to_party=second, relationship_type="FAMILY")

    def unpack(self, result):
        with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        return json.loads(members["manifest.json"]), members

    def test_manifest_integrity_all_profiles_and_stable_entity_bytes(self):
        with self.scoped(self.b):
            Party.objects.create(display_name="Foreign secret")
        with self.scoped():
            self.populate()
            result = self.export()
            manifest, members = self.unpack(result)
            again, repeated = self.unpack(self.export())
        self.assertEqual(result.sha256, hashlib.sha256(result.content).hexdigest())
        self.assertEqual(manifest["profile"], "party-bundle/1")
        self.assertEqual(manifest["scope"], "PARTIAL")
        self.assertEqual(manifest["source_namespace"], result.namespace)
        self.assertTrue(manifest["zip_import_supported"])
        self.assertEqual([e["profile"] for e in manifest["entities"]], list(bundles.PROFILES))
        self.assertEqual([e["count"] for e in manifest["entities"]], [2, 1, 1, 1, 1, 1])
        self.assertEqual(result.count, 7)
        self.assertEqual(set(members), {f["path"] for f in manifest["files"]} | {"manifest.json"})
        for entry in manifest["files"]:
            data = members[entry["path"]]
            self.assertEqual(entry["bytes"], len(data))
            self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(data, repeated[entry["path"]])
            self.assertNotIn(b"Foreign secret", data)

    def test_all_extracted_profiles_roundtrip_and_replay(self):
        with self.scoped():
            self.populate()
            manifest, members = self.unpack(self.export())
        with self.scoped(self.b):
            PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
            for repeat in range(2):
                for entity in manifest["entities"]:
                    batch = services.stage_import(workspace_id=self.b.pk, actor=self.actor,
                        content=members[entity["path"]], filename=entity["path"],
                        source_system=manifest["source_namespace"], profile=entity["profile"])
                    mapping = {"role_type_map": {"BORROWER": "CUSTOMER"}} if entity["profile"] == "party-role/1" else {}
                    batch = self.ready(batch, mapping, self.b)
                    self.assertEqual(batch.state, "READY", list(batch.rows.values_list("issues", flat=True)))
                    self.commit(batch, self.b, acknowledge_warnings=True)
            for model, count in [(Party, 2), (PartyContactMethod, 1), (PartyAddress, 1),
                                 (PartyIdentifier, 1), (PartyRole, 1), (PartyRelationship, 1)]:
                self.assertEqual(model.objects.count(), count)

    def test_empty_workspace_has_six_explicit_empty_files(self):
        with self.scoped():
            manifest, members = self.unpack(self.export())
        for entry in manifest["entities"]:
            self.assertEqual(entry["coverage"], "EMPTY")
            self.assertEqual(entry["count"], 0)
            self.assertEqual(members[entry["path"]], b"")

    def test_failed_later_profile_rolls_back_export_identities(self):
        with self.scoped():
            party = Party.objects.create(display_name="Blocked")
            PartyIdentifier.objects.create(party=party, identifier_type="PASSPORT", value="AB001234", metadata={"private": "value"})
            with self.assertRaises(PortabilityError):
                self.export()
            self.assertFalse(WorkspaceNamespace.objects.exists())
            self.assertFalse(PartyIdentity.objects.exists())

    def test_bounds_fail_without_truncation(self):
        with self.scoped():
            self.populate()
            with patch.object(bundles, "MAX_ROWS", 1), self.assertRaises(PortabilityError):
                self.export()
            self.assertFalse(WorkspaceNamespace.objects.exists())
            with patch("apps.tenant_apps.data_portability.services.MAX_BYTES", 1), self.assertRaises(PortabilityError):
                self.export()
            self.assertFalse(PartyIdentity.objects.exists())

    def test_context_membership_and_export_permission_required(self):
        with self.assertRaises(PermissionDenied):
            self.export()
        with self.scoped():
            with self.assertRaises(PermissionDenied):
                bundles.export_bundle(workspace_id=self.b.pk, actor=self.actor)
            with self.assertRaises(PermissionDenied):
                bundles.export_bundle(workspace_id=self.a.pk, actor=self.other_actor)
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                permission__codename__in=["contact_export", "data_export"]).delete()
            with self.assertRaises(PermissionDenied):
                self.export()

    def test_recovery_download_headers_and_csrf_through_middleware(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        Company.all_objects.filter(pk=self.a.pk).update(lifecycle_state="ARCHIVED")
        url = reverse("workspace_portability:export", kwargs={"workspace_slug": self.a.slug})
        page = client.get(url)
        self.assertContains(page, "Download Party ZIP bundle")
        self.assertEqual(client.post(url, {"action": "bundle"}).status_code, 403)
        result = client.post(url, {"action": "bundle", "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Content-Type"], "application/zip")
        self.assertEqual(result["X-Rokkad-Profile"], bundles.PROFILE)
        self.assertIn("PARTIAL", result["X-Rokkad-Coverage"])
        self.assertIn("no-store", result["Cache-Control"])
        self.assertEqual(result["X-Content-Type-Options"], "nosniff")
        self.assertTrue(result["Content-Disposition"].endswith('.zip"'))
