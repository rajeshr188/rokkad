"""Production admission boundaries, using only isolated PostgreSQL and local files."""
import copy
import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID, uuid5

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, override_settings

from apps.tenant_apps.data_portability import legacy_media_target as guard
from apps.tenant_apps.data_portability.management.commands import linode_media as command
from apps.tenant_apps.data_portability.models import LegacyMediaReceipt, PartyIdentity, SourceIdentity
from apps.tenant_apps.party.models import Party, PartyDocument
from .fixtures import PortabilityFixture
from .test_legacy_media import LocalCopies, NAMESPACE, evidence


def manifest():
    return {
        "profile": guard.PROFILE,
        "database": {"name": "production", "host": "127.0.0.1", "port": 5432,
                     "user": "runtime", "server_address": "127.0.0.1", "server_port": 5432},
        "storage": {"endpoint": "https://" + "a" * 32 + ".r2.cloudflarestorage.com",
                    "bucket": "test", "location": "media/application/production/test"},
        "source": {"namespace": NAMESPACE, "archive_sha256": "a" * 64},
        "workspaces": {"jcl": {"id": 1, "slug": "jcl"}},
    }


def configured_storage(target):
    value = target["storage"]
    return SimpleNamespace(endpoint_url=value["endpoint"], bucket_name=value["bucket"],
        location=value["location"], default_acl=None, custom_domain=None,
        querystring_auth=True, use_ssl=True, verify=None, file_overwrite=False, object_parameters={})


def write_json(path, value):
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def write_rows(path, rows):
    raw = b"".join((json.dumps(row) + "\n").encode() for row in rows)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


class TargetManifestTests(SimpleTestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))

    def test_exact_manifest_and_checksum(self):
        target = manifest()
        path = self.root / "target.json"
        sha = write_json(path, target)
        self.assertEqual(guard.load_target(path, sha), target)
        with self.assertRaises(CommandError):
            guard.load_target(path, "0" * 64)

    def test_rejects_unsafe_or_ambiguous_manifest_values(self):
        changes = [
            ("profile", None, "unknown"), ("database", "name", "rokkad_baseline_rehearsal_test"),
            ("database", "server_address", "hostname"), ("database", "port", True),
            ("storage", "endpoint", "http://" + "a" * 32 + ".r2.cloudflarestorage.com"),
            ("storage", "location", "media/legacy/source"),
            ("storage", "location", "media/application/production/../source"),
            ("source", "namespace", "bad"), ("source", "archive_sha256", "x" * 64),
            ("workspaces", "jcl", {"id": True, "slug": "jcl"}),
            ("workspaces", "jcl", {"id": 1, "slug": ""}),
        ]
        for section, key, value in changes:
            with self.subTest(section=section, key=key, value=value):
                target = manifest()
                if key is None:
                    target[section] = value
                else:
                    target[section][key] = value
                path = self.root / "target.json"
                with self.assertRaises(CommandError):
                    guard.load_target(path, write_json(path, target))
        for raw in (b'{"profile":1,"profile":2}', b"x" * 65537):
            path.write_bytes(raw)
            with self.assertRaises(CommandError):
                guard.load_target(path, hashlib.sha256(raw).hexdigest())

    def test_workspace_mapping_is_strict(self):
        for raw in ('{}', '[]', '{"public":1}', '{"jcl":true}', '{"jcl":1,"jcl":2}',
                    '{"jcl":1,"jsk":1}', '{"jcl":"1"}'):
            with self.subTest(raw=raw), self.assertRaises(CommandError):
                guard.workspace_mapping(raw)

    def test_exact_connection_server_and_storage(self):
        target = manifest()
        db = Mock(settings_dict={"NAME": "production", "USER": "runtime", "HOST": "127.0.0.1", "PORT": "5432"})
        cursor = Mock()
        db.cursor.return_value = SimpleCursor(cursor)
        cursor.fetchone.return_value = ("production", "runtime", "127.0.0.1", 5432)
        kwargs = dict(connection=db, database="production", workspaces={"jcl": 1}, storage=configured_storage(target))
        guard.check_target(target, **kwargs)
        for identity in (("other", "runtime", "127.0.0.1", 5432), ("production", "owner", "127.0.0.1", 5432),
                         ("production", "runtime", "127.0.0.2", 5432), ("production", "runtime", "127.0.0.1", 5433)):
            cursor.fetchone.return_value = identity
            with self.subTest(identity=identity), self.assertRaises(CommandError):
                guard.check_target(target, **kwargs)
        cursor.fetchone.return_value = ("production", "runtime", "127.0.0.1", 5432)
        for key in ("NAME", "USER", "HOST", "PORT"):
            saved = db.settings_dict[key]
            db.settings_dict[key] = "different"
            with self.subTest(key=key), self.assertRaises(CommandError):
                guard.check_target(target, **kwargs)
            db.settings_dict[key] = saved
        with self.assertRaises(CommandError):
            guard.check_target(target, **{**kwargs, "workspaces": {"jcl": 2}})

    def test_storage_privacy_tls_and_destination(self):
        target = manifest()
        for key, value in (("endpoint_url", "https://other"), ("bucket_name", "other"), ("location", "other"),
                           ("default_acl", "public-read"), ("custom_domain", "public.example"),
                           ("querystring_auth", False), ("use_ssl", False), ("verify", False),
                           ("file_overwrite", True), ("object_parameters", {"ACL": "public-read"})):
            storage = configured_storage(target)
            setattr(storage, key, value)
            with self.subTest(key=key), self.assertRaises(CommandError):
                guard.check_storage(target, storage)

    def test_unbound_production_refused_before_database_access(self):
        db = Mock(settings_dict={"NAME": "production"})
        with patch.object(command, "connection", db), self.assertRaises(CommandError):
            command.Command().handle(database="production")
        db.cursor.assert_not_called()


class SimpleCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *args):
        return False


class ProductionMediaCommandTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(override_settings(SETTINGS_MODULE="django_project.settings.prod_r2", MEDIA_ROOT=str(self.root), STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}))
        with self.scoped():
            self.party = Party.objects.create(display_name="Media target customer", party_code="TARGET")
            identity = PartyIdentity.objects.create(party=self.party)
            SourceIdentity.objects.create(identity=identity, source_system=f"legacy:{UUID(NAMESPACE).hex}:jcl",
                external_id=str(uuid5(uuid5(UUID(NAMESPACE), "jcl"), "contact_customer:1")),
                accepted_digest="a" * 64, local_digest="b" * 64)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port()")
                name, user, address, port = cursor.fetchone()
        self.target = manifest()
        self.target["database"] = dict(name=name, user=user, host=connection.settings_dict["HOST"],
            port=int(connection.settings_dict.get("PORT") or 5432), server_address=address, server_port=port)
        self.target["workspaces"] = {"jcl": {"id": self.a.pk, "slug": self.a.slug}}
        self.target_path = self.root / "target.json"
        target_sha = write_json(self.target_path, self.target)
        proxy = SimpleNamespace(settings_dict={**connection.settings_dict, "USER": user}, cursor=connection.cursor)
        self.enterContext(patch.object(command, "connection", proxy))
        self.s3 = configured_storage(self.target)
        self.enterContext(patch.object(command, "default_storage", self.s3))
        copies = LocalCopies(self.root)
        self.adapter = SimpleNamespace(storage=self.s3, verify=copies.verify,
            prepare=Mock(side_effect=lambda names, original: copies.prepare(names)))
        self.factory = self.enterContext(patch.object(command, "R2MediaCopies", return_value=self.adapter))
        value = evidence()
        refs, customers = self.root / "refs.jsonl", self.root / "customers.jsonl"
        self.options = dict(database=name, actor=self.actor.pk, workspaces=json.dumps({"jcl": self.a.pk}),
            target_manifest=str(self.target_path), target_sha256=target_sha, output=str(self.root / "output"),
            references=str(refs), references_sha256=write_rows(refs, [{k: value[k] for k in ("source", "status", "verified_source_file")}]),
            customers=str(customers), customers_sha256=write_rows(customers, [value["customer_source"]]),
            namespace=NAMESPACE, archive_sha256="a" * 64, confirmed=True, workers=1)

    def run_command(self, action, **changes):
        with self.scoped():
            call_command("linode_media", action, **{**self.options, **changes}, stdout=StringIO())

    def plan(self):
        self.run_command("plan")
        path = self.root / "output" / "plan.jsonl"
        self.options.update(plan=str(path), plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return [json.loads(line) for line in path.read_bytes().splitlines()]

    def replace_plan(self, rows):
        self.options["plan_sha256"] = write_rows(Path(self.options["plan"]), rows)

    def assert_no_copy(self):
        self.factory.assert_not_called()
        self.adapter.prepare.assert_not_called()
        with self.scoped():
            self.assertFalse(LegacyMediaReceipt.objects.exists())
            self.assertFalse(PartyDocument.objects.exists())

    def test_plan_apply_retry_and_removal_under_restricted_role(self):
        rows = self.plan()
        self.assertEqual(rows[0], {"profile": guard.PLAN_PROFILE, "target_sha256": self.options["target_sha256"]})
        self.assert_no_copy()
        self.run_command("apply")
        with self.scoped():
            self.assertEqual(LegacyMediaReceipt.objects.count(), 1)
            self.assertEqual(PartyDocument.objects.count(), 1)
            self.party.refresh_from_db()
            self.assertTrue(self.party.profile_photo)
            self.party.profile_photo.delete()
        self.run_command("apply")
        self.adapter.prepare.assert_called_once()
        with self.scoped():
            self.party.refresh_from_db()
            self.assertFalse(self.party.profile_photo)
            self.assertEqual(LegacyMediaReceipt.objects.count(), 1)
        summary = json.loads((self.root / "output" / "summary.json").read_text())
        self.assertEqual(summary["state"], "PRODUCTION_MEDIA_ATTACHED")
        self.assertFalse(summary["production_ready"])
        self.assertEqual(summary["counts"], {"already_attached": 1})

    def test_unbound_changed_header_and_duplicate_plans_refused(self):
        rows = self.plan()
        for changed in (rows[1:], [], [{"profile": guard.PLAN_PROFILE, "target_sha256": "0" * 64}] + rows[1:], rows + rows[1:]):
            with self.subTest(changed=changed):
                self.replace_plan(changed)
                with self.assertRaises(CommandError):
                    self.run_command("apply")
                self.assert_no_copy()

    def test_bad_final_row_blocks_all_copying(self):
        rows = self.plan()
        for field, value in (("database", "other"), ("workspace_id", self.b.pk), ("target_id", self.party.pk + 100),
                             ("names", {"document": "unexpected.jpg"})):
            changed = copy.deepcopy(rows)
            changed[-1][field] = value
            self.replace_plan(changed)
            with self.subTest(field=field), self.assertRaises(CommandError):
                self.run_command("apply")
            self.assert_no_copy()
        # A valid first row must not be copied before a later source mismatch is found.
        changed = copy.deepcopy(rows)
        later = copy.deepcopy(rows[-1])
        later["evidence"]["archive_sha256"] = "b" * 64
        changed.append(later)
        self.replace_plan(changed)
        with self.assertRaises(CommandError):
            self.run_command("apply")
        self.assert_no_copy()

    def test_changed_source_bucket_namespace_and_storage_refused(self):
        rows = self.plan()
        for key, value in (("namespace", "6ca968d6-2647-4dbb-8e39-24f0c1a12ed7"), ("archive_sha256", "b" * 64),
                           ("verified_source_file", {**rows[-1]["evidence"]["verified_source_file"], "bucket": "other"})):
            changed = copy.deepcopy(rows)
            changed[-1]["evidence"][key] = value
            self.replace_plan(changed)
            with self.subTest(key=key), self.assertRaises(CommandError):
                self.run_command("apply")
            self.assert_no_copy()
        self.replace_plan(rows)
        self.s3.location += "-changed"
        with self.assertRaises(CommandError):
            self.run_command("apply")
        self.assert_no_copy()

    def test_changed_manifest_requires_new_plan_even_when_mapping_is_valid(self):
        self.plan()
        self.target["storage"]["location"] += "-new"
        self.s3.location = self.target["storage"]["location"]
        self.options["target_sha256"] = write_json(self.target_path, self.target)
        with self.assertRaises(CommandError):
            self.run_command("apply")
        self.assert_no_copy()

    def test_workspace_slug_owner_and_settings_checked(self):
        self.plan()
        self.target["workspaces"]["jcl"]["slug"] = "wrong"
        self.options["target_sha256"] = write_json(self.target_path, self.target)
        with self.assertRaises(CommandError):
            self.run_command("apply")
        self.assert_no_copy()
        self.target["workspaces"]["jcl"]["slug"] = self.a.slug
        self.options["target_sha256"] = write_json(self.target_path, self.target)
        with override_settings(SETTINGS_MODULE="django_project.settings.test"), self.assertRaises(CommandError):
            self.run_command("apply")
        self.assert_no_copy()
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            self.run_command("apply", actor=self.other_actor.pk)
        self.assert_no_copy()

    def test_empty_plan_still_binds_target_without_storage_client(self):
        self.options["references_sha256"] = write_rows(Path(self.options["references"]), [])
        rows = self.plan()
        self.assertEqual(len(rows), 1)
        self.run_command("apply")
        self.assert_no_copy()

    def test_privileged_role_refused_before_copy(self):
        self.plan()
        # Match the configured and connected identity so the independent role guard is exercised.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user")
            user = cursor.fetchone()[0]
        self.target["database"]["user"] = user
        self.options["target_sha256"] = write_json(self.target_path, self.target)
        proxy = SimpleNamespace(settings_dict={**connection.settings_dict, "USER": user}, cursor=connection.cursor)
        with patch.object(command, "connection", proxy), self.assertRaisesMessage(CommandError, "restricted runtime role"):
            call_command("linode_media", "apply", **self.options, stdout=StringIO())
        self.assert_no_copy()

    def test_rehearsal_keeps_original_plan_format_and_rejects_production_header(self):
        production_rows = self.plan()
        rehearsal = "rokkad_baseline_rehearsal_guard_test"
        proxy = SimpleNamespace(settings_dict={**connection.settings_dict, "NAME": rehearsal}, cursor=connection.cursor)
        self.options.update(database=rehearsal, target_manifest=None, target_sha256=None)
        with patch.object(command, "connection", proxy):
            rows = self.plan()
            self.assertEqual(len(rows), 1)
            self.assertNotIn("profile", rows[0])
            self.replace_plan(production_rows)
            with self.assertRaisesMessage(CommandError, "Production plans"):
                self.run_command("apply")
            self.assert_no_copy()
            self.replace_plan(rows)
            self.run_command("apply")
            self.adapter.prepare.assert_called_once()
