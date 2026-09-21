import copy
import hashlib
import io
import json
import stat
import zipfile
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, WorkspaceRoleGrant
from apps.tenant_apps.party.models import Party, PartyRoleType
from apps.tenant_apps.data_portability import bundle_import, bundles, contracts, child_contracts, services
from apps.tenant_apps.data_portability.models import ImportBatch, ImportRow
from apps.tenant_apps.data_portability.parsers import PortabilityError
from .fixtures import PortabilityFixture
from . import test_bundles


def pack(members, mutate=None, rehash=False):
    members = dict(members)
    manifest = json.loads(members["manifest.json"])
    if mutate:
        mutate(manifest)
    if rehash:
        for entry in manifest["files"]:
            entry["bytes"] = len(members[entry["path"]])
            entry["sha256"] = hashlib.sha256(members[entry["path"]]).hexdigest()
    members["manifest.json"] = json.dumps(manifest).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return output.getvalue()


def empty_members():
    members, entities = {}, []
    for entry in bundle_import.ENTITIES:
        entities.append({**entry, "count": 0, "coverage": "EMPTY"})
        members[entry["path"]] = b""
        schema = contracts.schema() if entry["profile"] == contracts.PROFILE else child_contracts.schema(entry["profile"])
        members[entry["schema"]] = json.dumps(schema).encode()
    members["README.txt"] = b"Uploaded instructions must never be rendered or executed."
    manifest = {"format": "rokkad-data", "profile": bundles.PROFILE,
        "source_namespace": "37f09600-1e3b-4d98-82db-73644912b8ae", "scope": "PARTIAL",
        "snapshot": {"consistency": "workspace-row-locks", "captured_at": "2026-09-12T10:00:00+00:00"},
        "entities": entities, "import_order": [e["path"] for e in entities],
        "zip_import_supported": False, "exclusions": bundles.EXCLUSIONS,
        "limits": {"records_per_profile": 1000, "bytes_per_profile": 5 * 1024 * 1024},
        "files": [{"path": p, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()} for p, b in members.items()]}
    members["manifest.json"] = json.dumps(manifest).encode()
    return members


class BundleParserTests(SimpleTestCase):
    def test_old_export_capability_and_empty_members_are_accepted(self):
        manifest, members = bundle_import.parse_bundle(pack(empty_members()))
        self.assertEqual(len(members), 14)
        self.assertFalse(manifest["zip_import_supported"])

    def test_manifest_unknown_shape_counts_and_authority_rejected(self):
        mutations = [lambda m: m.update(scope="FULL"), lambda m: m.update(profile="loans/1"),
            lambda m: m.update(destination_workspace=1), lambda m: m.update(source_namespace="../bad"),
            lambda m: m.update(entities={}), lambda m: m.update(files=[]),
            lambda m: m["entities"][0].update(count=True), lambda m: m["entities"][0].update(count=1),
            lambda m: m["entities"][0].update(coverage="INCLUDED"),
            lambda m: m.update(import_order=list(reversed(m["import_order"]))),
            lambda m: m["snapshot"].update(captured_at="not a date"),
            lambda m: m["limits"].update(bytes_per_profile=999999999)]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(PortabilityError):
                bundle_import.parse_bundle(pack(empty_members(), mutate))

    def test_hash_size_and_duplicate_file_index_rejected(self):
        for mutate in [lambda m: m["files"][0].update(sha256="0" * 64),
                       lambda m: m["files"][0].update(bytes=True),
                       lambda m: m["files"].__setitem__(1, m["files"][0])]:
            with self.assertRaises(PortabilityError):
                bundle_import.parse_bundle(pack(empty_members(), mutate))

    def test_schemas_are_pinned_and_uploaded_readme_is_not_trusted(self):
        members = empty_members()
        members[bundle_import.ENTITIES[0]["schema"]] = b'{"$ref":"https://example.com/execute"}'
        with self.assertRaises(PortabilityError):
            bundle_import.parse_bundle(pack(members, rehash=True))

    def test_unknown_missing_traversal_and_case_collision_members_rejected(self):
        for name in ("../escape", "entities/loans.jsonl", "README.TXT", "C:/secret", "entities\\evil"):
            members = empty_members(); members[name] = members.pop("README.txt")
            with self.subTest(name=name), self.assertRaises(PortabilityError):
                bundle_import.parse_bundle(pack(members))
        members = empty_members(); members.pop("README.txt")
        with self.assertRaises(PortabilityError):
            bundle_import.parse_bundle(pack(members))

    def test_symlink_and_unsupported_compression_rejected(self):
        for kind in ("symlink", "compression", "encrypted"):
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w") as archive:
                for name, data in empty_members().items():
                    info = zipfile.ZipInfo(name)
                    if name == "README.txt" and kind == "symlink":
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    if kind == "compression":
                        info.compress_type = zipfile.ZIP_BZIP2
                    archive.writestr(info, data)
            content = output.getvalue()
            if kind == "encrypted":
                content = bytearray(content)
                start = content.index(b"PK\x01\x02")
                content[start + 8] |= 1
                content = bytes(content)
            with self.subTest(kind=kind), self.assertRaises(PortabilityError):
                bundle_import.parse_bundle(content)

    def test_duplicate_json_corruption_trailing_and_size_bounds(self):
        good = pack(empty_members())
        for data in (b"", b"not zip", good[:-4], good + b"extra"):
            with self.assertRaises(PortabilityError):
                bundle_import.parse_bundle(data)
        members = empty_members(); members["manifest.json"] = b'{"format":"x","format":"y"}'
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for name, data in members.items(): archive.writestr(name, data)
        with self.assertRaises(PortabilityError): bundle_import.parse_bundle(output.getvalue())
        with patch.object(bundle_import, "MAX_BUNDLE_BYTES", len(good) - 1), self.assertRaises(PortabilityError):
            bundle_import.parse_bundle(good)
        members = empty_members(); members["README.txt"] = b"a" * (bundle_import.MAX_METADATA_BYTES + 1)
        with self.assertRaises(PortabilityError): bundle_import.parse_bundle(pack(members, rehash=True))


@override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BundleStagingTests(PortabilityFixture):
    populate = test_bundles.BundleTests.populate

    def setUp(self):
        super().setUp()
        with self.scoped():
            self.populate()
            self.content = bundles.export_bundle(workspace_id=self.a.pk, actor=self.actor).content

    def stage_bundle(self, content=None, workspace=None, actor=None):
        return bundle_import.stage_bundle(workspace_id=(workspace or self.b).pk, actor=actor or self.actor,
                                          content=self.content if content is None else content)

    def test_six_previews_no_writes_then_manual_commit_and_replay(self):
        with self.scoped(self.b):
            PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
            for repeat in range(2):
                staged = self.stage_bundle()
                self.assertEqual(len(staged), 6)
                self.assertEqual(Party.objects.count(), 2 if repeat else 0)
                self.assertEqual(ImportBatch.objects.count(), 12 if repeat else 6)
                if not repeat:
                    self.assertEqual(staged[0][1].state, "READY")
                    self.assertTrue(all(b.state == "NEEDS_MAPPING" for _, b in staged[1:]))
                for profile, batch in staged:
                    mapping = {"role_type_map": {"BORROWER": "CUSTOMER"}} if profile == child_contracts.ROLE else {}
                    ready = self.ready(batch, mapping, self.b)
                    self.assertEqual(ready.state, "READY", list(ready.rows.values_list("issues", flat=True)))
                    self.commit(ready, self.b, acknowledge_warnings=True)
            self.assertEqual(Party.objects.count(), 2)

    def test_empty_bundle_creates_no_batches(self):
        with self.scoped(self.b):
            staged = self.stage_bundle(pack(empty_members()))
            self.assertTrue(all(batch is None for _, batch in staged))
            self.assertFalse(ImportBatch.objects.exists())

    def test_bad_member_or_late_staging_failure_rolls_back_every_batch(self):
        with self.scoped(self.b):
            with self.assertRaises(PortabilityError): self.stage_bundle(self.content[:-4])
            original = services.validate_import
            def fail_late(**kwargs):
                if ImportBatch.objects.count() > 1: raise PortabilityError("Late failure")
                return original(**kwargs)
            with patch.object(services, "validate_import", side_effect=fail_late), self.assertRaises(PortabilityError):
                self.stage_bundle()
            self.assertFalse(ImportBatch.objects.exists())
            self.assertFalse(ImportRow.objects.exists())
            self.assertFalse(Party.objects.exists())

    def test_whole_bundle_capacity_is_checked_before_staging(self):
        with self.scoped(self.b):
            for _ in range(15): self.stage(workspace=self.b)
            with self.assertRaisesMessage(PortabilityError, "make room"):
                self.stage_bundle()
            self.assertEqual(ImportBatch.objects.count(), 15)

    def test_context_permissions_and_archived_destination_fail_closed(self):
        with self.assertRaises(PermissionDenied): self.stage_bundle()
        with self.scoped():
            with self.assertRaises(PermissionDenied): self.stage_bundle()
        with self.scoped(self.b):
            with self.assertRaises(PermissionDenied): self.stage_bundle(actor=self.other_actor)
            Company.all_objects.filter(pk=self.b.pk).update(lifecycle_state="ARCHIVED")
            with self.assertRaises(PermissionDenied): self.stage_bundle()
            Company.all_objects.filter(pk=self.b.pk).update(lifecycle_state="ACTIVE")
            membership = Membership.objects.get(company=self.b, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.b.pk, workspace_role__role_id=membership.role_id,
                                               permission__codename="data_import").delete()
            with self.assertRaises(PermissionDenied): self.stage_bundle()
            self.assertFalse(ImportBatch.objects.exists())

    def test_manifest_namespace_never_changes_destination_and_dangling_refs_rejected(self):
        with zipfile.ZipFile(io.BytesIO(self.content)) as archive:
            members = {name: archive.read(name) for name in archive.namelist()}
        namespace = "37f09600-1e3b-4d98-82db-73644912b8ae"
        with self.scoped(self.b):
            # Changing only namespace invalidates child references even with correct member hashes.
            with self.assertRaises(PortabilityError):
                self.stage_bundle(pack(members, lambda m: m.update(source_namespace=namespace)))
            self.assertFalse(ImportBatch.objects.exists())

    def test_csrf_receipt_refresh_and_cross_workspace_receipt(self):
        from types import SimpleNamespace
        from apps.tenancy import testing
        for workspace in (self.a, self.b):
            testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=workspace))
        client = Client(enforce_csrf_checks=True); client.force_login(self.actor)
        url = reverse("workspace_portability:upload", kwargs={"workspace_slug": self.b.slug})
        self.assertContains(client.get(url), "Stage ZIP for review")
        self.assertEqual(client.post(url, {"action": "bundle"}).status_code, 403)
        response = client.post(url, {"action": "bundle", "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            "bundle_file": SimpleUploadedFile("party.zip", self.content)})
        self.assertEqual(response.status_code, 302)
        for _ in range(2):
            page = client.get(response["Location"])
            self.assertContains(page, "Bundle staging results")
            self.assertContains(page, "review preview", count=6)
            self.assertIn("no-store", page["Cache-Control"])
        with self.scoped(self.b): self.assertEqual(ImportBatch.objects.count(), 6)
        other_url = reverse("workspace_portability:upload", kwargs={"workspace_slug": self.a.slug})
        denied = client.get(other_url + "?" + response["Location"].split("?", 1)[1])
        self.assertContains(denied, "invalid or expired")
        self.assertNotContains(denied, "review preview")
