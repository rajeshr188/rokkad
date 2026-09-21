import copy
import json
import uuid
from pathlib import Path
from contextlib import contextmanager
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role, WorkspaceRoleGrant
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party, PartyCodeSequence
from apps.tenant_apps.party.services.party_merge import merge_parties
from apps.tenant_apps.data_portability import services, views
from apps.tenant_apps.data_portability.contracts import dump, schema, semantic, validate_record
from apps.tenant_apps.data_portability.models import ImportBatch, ImportRow, PartyIdentity, SourceIdentity, WorkspaceNamespace
from apps.tenant_apps.data_portability.parsers import MAX_BYTES, PortabilityError, parse_source


MAPPING = {"columns": {"Legacy": "source.external_id", "Party": "name", "Phone": "primary_phone"},
           "defaults": {"kind": "INDIVIDUAL", "status": "ACTIVE", "credit_hold": False},
           "normalization": [{"field": "name", "rule": "trim", "version": 1}]}
CSV = b"Legacy,Party,Phone\nold-1, Asha Devi ,\n"


class ParserTests(SimpleTestCase):
    def test_frozen_schema_matches_released_profile(self):
        root = Path(__file__).resolve().parents[4]
        self.assertEqual(json.loads((root / "docs/contracts/party-master-v1.schema.json").read_text(encoding="utf-8")), schema())

    def test_csv_preserves_source_values_and_physical_row_numbers(self):
        name, kind, headers, rows = parse_source(b'ID,Name\n001,"A\nB"\n002,C\n', r'C:\unsafe\source.csv')
        self.assertEqual(name, "source.csv")
        self.assertEqual(rows, [(2, {"ID": "001", "Name": "A\nB"}), (4, {"ID": "002", "Name": "C"})])

    def test_bad_sources_rejected(self):
        for content, name in [(b"", "a.csv"), (b"x", "a.xlsx"), (b"\xff", "a.csv"),
                              (b"a,a\n1,2", "a.csv"), (b"a,b\n1", "a.csv"),
                              (b'a\n"unterminated', "a.csv"), (b'a\n\x00', "a.csv"),
                              (b'{"a":1,"a":2}', "a.jsonl"), (b'{"a":NaN}', "a.jsonl"),
                              (b"[]", "a.jsonl")]:
            with self.subTest(name=name, content=content), self.assertRaises(PortabilityError):
                parse_source(content, name)

    def test_upload_row_and_cell_limits(self):
        for content in [b"x" * (MAX_BYTES + 1), b"a\n" + b"x\n" * 1001, b"a\n" + b"x" * 4097]:
            with self.assertRaises(PortabilityError):
                parse_source(content, "a.csv")

    def test_jsonl_preserves_boolean_and_null(self):
        rows = parse_source(b'{"name":"A","credit_hold":false,"phone":null}\n', "a.jsonl")[3]
        self.assertIs(rows[0][1]["credit_hold"], False)
        self.assertIsNone(rows[0][1]["phone"])


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PortabilityTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_sql = connection.ops.quote_name("portability_test_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {cls.role_sql} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {cls.role_sql}")
            cursor.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {cls.role_sql}")
            cursor.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {cls.role_sql}")

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(f"DROP OWNED BY {cls.role_sql}")
            cursor.execute(f"DROP ROLE {cls.role_sql}")
        super().tearDownClass()

    def setUp(self):
        suffix = uuid.uuid4().hex
        self.actor = get_user_model().objects.create_user(username="port-owner-" + suffix)
        self.other_actor = get_user_model().objects.create_user(username="port-other-" + suffix)
        self.a = Company.objects.create(name="Port A " + suffix, schema_name="pa" + suffix, owner=self.actor, creator=self.actor)
        self.b = Company.objects.create(name="Port B " + suffix, schema_name="pb" + suffix, owner=self.actor, creator=self.actor)
        role = Role.objects.get_or_create(name="Owner")[0]
        for workspace in (self.a, self.b):
            Membership.objects.get_or_create(company=workspace, user=self.actor, defaults={"role": role})

    @contextmanager
    def scoped(self, workspace=None):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {self.role_sql}")
            try:
                with workspace_context((workspace or self.a).pk):
                    yield
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")

    def stage(self, content=CSV, system="paper", filename="parties.csv", workspace=None):
        return services.stage_import(workspace_id=(workspace or self.a).pk, actor=self.actor,
            content=content, filename=filename, source_system=system)

    def ready(self, batch=None, mapping=None, workspace=None):
        batch = batch or self.stage(workspace=workspace)
        return services.validate_import(workspace_id=(workspace or self.a).pk, actor=self.actor,
            batch_id=batch.public_id, mapping=copy.deepcopy(MAPPING) if mapping is None else mapping)

    def commit(self, batch, workspace=None, **kwargs):
        return services.commit_import(workspace_id=(workspace or self.a).pk, actor=self.actor,
            batch_id=batch.public_id, approval_digest=batch.approval_digest, **kwargs)

    def test_upload_and_preview_have_no_domain_or_sequence_effects(self):
        with self.scoped():
            batch = self.stage()
            self.assertEqual(batch.state, "NEEDS_MAPPING")
            batch = self.ready(batch)
            self.assertEqual(batch.state, "READY")
            self.assertEqual(batch.summary["new_records"], 1)
            self.assertFalse(Party.objects.exists())
            self.assertFalse(PartyCodeSequence.objects.exists())
            row = batch.rows.get()
            self.assertEqual(row.raw["Party"], " Asha Devi ")
            self.assertEqual(row.canonical["name"], "Asha Devi")
            self.assertTrue(any(i["severity"] == "INFO" for i in row.issues))

    def test_commit_provenance_and_repeat_batch_are_idempotent(self):
        with self.scoped():
            batch = self.ready()
            self.commit(batch)
            self.commit(batch)
            party = Party.objects.get()
            self.assertEqual(party.party_code, "P-000001")
            self.assertEqual(party.created_by_id, self.actor.pk)
            row = batch.rows.get()
            self.assertEqual(row.identity.party_id, party.pk)
            self.assertEqual(row.external_id, "old-1")
            self.assertEqual(row.source_row, 2)
            self.assertIsNotNone(row.committed_at)
            second = self.ready()
            self.assertEqual(second.summary["existing_records"], 1)
            self.commit(second)
            self.assertEqual(Party.objects.count(), 1)
            self.assertEqual(PartyCodeSequence.objects.get().next_number, 2)
            self.assertEqual(ImportRow.objects.filter(committed_at__isnull=False).count(), 2)

    def test_changed_source_is_conflict(self):
        with self.scoped():
            self.commit(self.ready())
            batch = self.ready(self.stage(CSV.replace(b"Asha Devi", b"Changed Name")))
            self.assertEqual(batch.summary["conflicts"], 1)
            with self.assertRaises(PortabilityError):
                self.commit(batch)

    def test_local_edit_blocks_source_replay(self):
        with self.scoped():
            self.commit(self.ready())
            Party.objects.update(display_name="Locally corrected")
            batch = self.ready()
            self.assertEqual(batch.rows.get().issues[-1]["code"], "LOCAL_CHANGED")

    def test_matching_name_never_silently_merges(self):
        with self.scoped():
            Party.objects.create(display_name="Asha Devi")
            batch = self.ready()
            self.assertEqual(batch.summary["conflicts"], 1)
            self.assertEqual(Party.objects.count(), 1)

    def test_duplicate_ids_and_rows_in_one_batch_block_all(self):
        with self.scoped():
            for content in [b"Legacy,Party,Phone\nx,A,\nx,B,\n", b"Legacy,Party,Phone\nx,A,\ny,A,\n"]:
                batch = self.ready(self.stage(content))
                self.assertEqual(batch.summary["rows_with_errors"], 2)
            self.assertFalse(Party.objects.exists())

    def test_invalid_fields_have_structured_row_issues(self):
        with self.scoped():
            batch = self.ready(self.stage(b"Legacy,Party,Phone\nx,,invalid\n"))
            self.assertEqual(batch.state, "NEEDS_MAPPING")
            self.assertTrue(all({"code", "field", "message", "severity"} <= set(i) for i in batch.rows.get().issues))

    def test_shared_phone_and_case_variant_names_require_duplicate_review(self):
        with self.scoped():
            for content in [b"Legacy,Party,Phone\nx,Asha,\ny,ASHA,\n",
                            b"Legacy,Party,Phone\nx,Asha,+919876543210\ny,Kavita,+919876543210\n"]:
                batch = self.ready(self.stage(content))
                self.assertEqual(batch.summary["conflicts"], 2)
                self.assertFalse(Party.objects.exists())

    def test_arbitrary_mapping_and_phone_normalization(self):
        with self.scoped():
            batch = self.stage(b"Register key,Full name,Mobile\n001,Kavita,+919876543210\n")
            mapping = copy.deepcopy(MAPPING)
            mapping["columns"] = {"Register key": "source.external_id", "Full name": "name", "Mobile": "primary_phone"}
            self.commit(self.ready(batch, mapping))
            self.assertEqual(Party.objects.get().primary_phone, "+919876543210")
            self.assertEqual(SourceIdentity.objects.get().external_id, "001")

    def test_unmapped_columns_warn_and_require_acknowledgement(self):
        with self.scoped():
            batch = self.ready(self.stage(b"Legacy,Party,Phone,Address\nx,A,,Private address\n"))
            self.assertEqual(batch.summary["rows_with_warnings"], 1)
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.commit(batch, acknowledge_warnings=True)

    def test_mapping_and_canonical_allowlists(self):
        with self.scoped():
            batch = self.stage()
            for mapping in [{"columns": {"Party": "workspace"}}, {"columns": {"Legacy": "source.external_id", "Party": "name"}, "normalization": [{"field": "name", "rule": "eval", "version": 1}]}]:
                with self.assertRaises(PortabilityError):
                    self.ready(batch, mapping)
            record = {"id": str(uuid.uuid4()), "name": "A", "kind": "INDIVIDUAL", "status": "ACTIVE", "credit_hold": False, "workspace": self.b.pk}
            b = self.stage(dump(record).encode(), str(uuid.uuid4()), "a.jsonl")
            b = self.ready(b, {})
            self.assertEqual(b.state, "NEEDS_MAPPING")

    def test_invalid_enums_types_and_metadata_are_rejected(self):
        base = {"name": "A", "kind": "INDIVIDUAL", "status": "ACTIVE", "credit_hold": False}
        with self.scoped():
            for field, value in [("kind", "alien"), ("credit_hold", "false"), ("name", 42), ("extensions", {"secret": "x"}), ("photo_ref", "../x"), ("source_recorded_at", "2020-01-01")]:
                record, issues = validate_record({**base, field: value})
                self.assertTrue(any(i["severity"] == "ERROR" for i in issues), field)

    def test_stale_approval_and_mutated_staging_fail(self):
        with self.scoped():
            batch = self.ready()
            old = batch.approval_digest
            batch = self.ready(batch)
            with self.assertRaises(PortabilityError):
                services.commit_import(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id, approval_digest=old)
            batch.rows.update(raw={"Legacy": "old-1", "Party": "Changed", "Phone": ""})
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.assertFalse(Party.objects.exists())

    def test_destination_conflict_after_preview_blocks_commit(self):
        with self.scoped():
            batch = self.ready()
            Party.objects.create(display_name="Asha Devi")
            with self.assertRaises(PortabilityError):
                self.commit(batch)
            self.assertFalse(SourceIdentity.objects.exists())

    def test_all_rows_and_sequence_rollback_on_commit_failure(self):
        with self.scoped():
            batch = self.ready(self.stage(b"Legacy,Party,Phone\nx,A,\ny,B,\n"))
            original = services.create_party_from_form
            calls = []
            def fail_second(**kwargs):
                calls.append(1)
                if len(calls) == 2:
                    raise RuntimeError("injected")
                return original(**kwargs)
            with patch.object(services, "create_party_from_form", side_effect=fail_second), self.assertRaises(RuntimeError):
                self.commit(batch)
            self.assertFalse(Party.objects.exists())
            self.assertFalse(PartyCodeSequence.objects.exists())
            self.assertFalse(SourceIdentity.objects.exists())
            self.assertFalse(batch.rows.filter(committed_at__isnull=False).exists())
            self.commit(batch)
            self.assertEqual(Party.objects.count(), 2)

    def test_cancel_discards_staged_values_and_denies_commit(self):
        with self.scoped():
            batch = self.ready()
            services.cancel_import(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id)
            self.assertEqual(batch.rows.get().raw, {})
            with self.assertRaises(PortabilityError):
                self.commit(batch)

    def test_completed_batch_and_identity_are_sql_immutable(self):
        with self.scoped():
            batch = self.ready()
            self.commit(batch)
            for write in [lambda: batch.rows.update(canonical={}), lambda: ImportBatch.objects.filter(pk=batch.pk).update(state="READY"),
                          lambda: PartyIdentity.objects.update(public_id=uuid.uuid4()), lambda: SourceIdentity.objects.update(external_id="spoof")]:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    write()

    def test_round_trip_uses_new_local_ids_and_same_domain_facts(self):
        with self.scoped():
            self.commit(self.ready())
            native = Party.objects.create(display_name="Native Person", party_type="ORGANIZATION", credit_hold=True, status="BLOCKED")
            expected = sorted([semantic(p) for p in Party.objects.all()], key=lambda p: p["name"])
            source_ids = set(Party.objects.values_list("pk", flat=True))
            first = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            second = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            self.assertEqual(first.content, second.content)
            self.assertEqual(first.namespace, second.namespace)
            self.assertNotIn(b"workspace_id", first.content)
        with self.scoped(self.b):
            batch = self.ready(self.stage(first.content, first.namespace, "parties.jsonl", self.b), {}, self.b)
            self.assertEqual(batch.state, "READY", batch.summary)
            self.commit(batch, self.b)
            actual = sorted([semantic(p) for p in Party.objects.all()], key=lambda p: p["name"])
            self.assertEqual(actual, expected)
            self.assertTrue(source_ids.isdisjoint(Party.objects.values_list("pk", flat=True)))
            repeat = self.ready(self.stage(first.content, first.namespace, "parties.jsonl", self.b), {}, self.b)
            self.assertEqual(repeat.summary["existing_records"], 2)
            self.commit(repeat, self.b)
            self.assertEqual(Party.objects.count(), 2)

    def test_exported_formula_text_is_lossless_json_not_executable(self):
        with self.scoped():
            Party.objects.create(display_name="=HYPERLINK(\"https://invalid.example\")")
            exported = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            self.assertTrue(json.loads(exported.content)["name"].startswith("=HYPERLINK"))

    def test_same_workspace_export_import_is_noop(self):
        with self.scoped():
            Party.objects.create(display_name="Existing")
            exported = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            batch = self.ready(self.stage(exported.content, exported.namespace, "a.jsonl"), {})
            self.assertEqual(batch.summary["existing_records"], 1)
            self.commit(batch)
            self.assertEqual(Party.objects.count(), 1)

    def test_archived_merge_source_keeps_identity_and_blocks_reimport(self):
        with self.scoped():
            self.commit(self.ready())
            source = Party.objects.get()
            identifier = source.exchange_identity.public_id
            target = Party.objects.create(display_name="Target")
            merge_parties(target=target, source=source, actor=self.actor)
            self.assertEqual(PartyIdentity.objects.get(party=source).public_id, identifier)
            self.assertEqual(self.ready().summary["conflicts"], 1)

    def test_missing_context_denies_every_public_service(self):
        for call in [lambda: self.stage(), lambda: services.export_parties(workspace_id=self.a.pk, actor=self.actor),
                     lambda: services.preview_import(workspace_id=self.a.pk, actor=self.actor, batch_id=uuid.uuid4())]:
            with self.assertRaises(PermissionDenied):
                call()

    def test_other_workspace_batches_and_rows_hidden_by_rls(self):
        with self.scoped(self.b):
            foreign = self.ready(self.stage(workspace=self.b), workspace=self.b)
            self.commit(foreign, self.b)
        with self.scoped():
            self.assertFalse(ImportBatch.objects.filter(pk=foreign.pk).exists())
            self.assertFalse(ImportRow.objects.filter(batch_id=foreign.pk).exists())
            for call in [lambda: services.preview_import(workspace_id=self.a.pk, actor=self.actor, batch_id=foreign.public_id),
                         lambda: services.commit_import(workspace_id=self.a.pk, actor=self.actor, batch_id=foreign.public_id, approval_digest=foreign.approval_digest),
                         lambda: services.export_parties(workspace_id=self.b.pk, actor=self.actor)]:
                with self.assertRaises(PermissionDenied):
                    call()
            self.assertEqual(services.export_parties(workspace_id=self.a.pk, actor=self.actor).count, 0)

    def test_restricted_sql_cannot_spoof_ownership_or_cross_link(self):
        with self.scoped(self.b):
            foreign = self.stage(workspace=self.b)
            foreign_party = Party.objects.create(display_name="Foreign")
        with self.scoped():
            for write in [lambda: ImportRow.objects.create(workspace_id=self.a.pk, batch_id=foreign.pk, source_row=20),
                          lambda: PartyIdentity.objects.create(workspace_id=self.a.pk, party_id=foreign_party.pk),
                          lambda: WorkspaceNamespace.objects.bulk_create([WorkspaceNamespace(workspace_id=self.b.pk)])]:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    write()

    def test_sql_missing_context_hides_data_and_denies_insert(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {self.role_sql}")
            try:
                self.assertFalse(ImportBatch.objects.exists())
                with self.assertRaises(DatabaseError), transaction.atomic():
                    WorkspaceNamespace.objects.create(workspace_id=self.a.pk)
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")

    def test_permission_removal_before_commit_and_replay_is_denied(self):
        with self.scoped():
            batch = self.ready()
            self.commit(batch)
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                                              permission__codename="data_import").delete()
            with self.assertRaises(PermissionDenied):
                self.commit(batch)

    def test_nonmember_actorless_and_inactive_workspace_denied(self):
        with self.scoped():
            for actor in (None, self.other_actor):
                with self.assertRaises(PermissionDenied):
                    services.stage_import(workspace_id=self.a.pk, actor=actor, content=CSV, filename="a.csv", source_system="paper")
            Company.all_objects.filter(pk=self.a.pk).update(lifecycle_state="ARCHIVED")
            with self.assertRaises(PermissionDenied):
                self.stage()
            self.assertEqual(services.export_parties(workspace_id=self.a.pk, actor=self.actor).count, 0)

    def test_new_infrastructure_not_in_legacy_model_picker(self):
        from apps.tenant_apps.utils.importing.forms import _tenant_model_choices
        names = {name for name, label in _tenant_model_choices()}
        self.assertNotIn("ImportBatch", names)
        self.assertNotIn("SourceIdentity", names)

    def test_workspace_routes_and_minimal_ui_flow(self):
        factory = RequestFactory()
        def request(method, data=None):
            req = getattr(factory, method)("/", data=data or {})
            req.workspace, req.user = self.a, self.actor
            return req
        with self.scoped():
            url = reverse("workspace_portability:upload", kwargs={"workspace_slug": self.a.slug})
            self.assertEqual(resolve(url).view_name, "workspace_portability:upload")
            self.assertEqual(views.upload(request("get")).status_code, 200)
            response = views.upload(request("post", {"source_system": "paper", "source_file": SimpleUploadedFile("a.csv", CSV)}))
            self.assertEqual(response.status_code, 302)
            batch = ImportBatch.objects.get()
            self.assertEqual(views.batch_detail(request("get"), batch.public_id).status_code, 200)
            batch = self.ready(batch)
            self.assertContains(views.batch_detail(request("get"), batch.public_id), "Confirm and commit")
            self.commit(batch)
            result = views.export(request("post"))
            self.assertEqual(result.status_code, 200)
            self.assertIn("no-store", result["Cache-Control"])
            self.assertIn("PARTIAL", result["X-Rokkad-Coverage"])
            self.assertEqual(result["X-Content-Type-Options"], "nosniff")

    @override_settings(ALLOWED_HOSTS=["testserver"])
    def test_export_recovery_and_csrf_through_real_middleware(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        Company.all_objects.filter(pk=self.a.pk).update(lifecycle_state="ARCHIVED")
        url = reverse("workspace_portability:export", kwargs={"workspace_slug": self.a.slug})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.post(url).status_code, 403)
        token = client.cookies["csrftoken"].value
        self.assertEqual(client.post(url, {"csrfmiddlewaretoken": token}).status_code, 200)
        denied = client.get(reverse("workspace_portability:upload", kwargs={"workspace_slug": self.a.slug}))
        self.assertNotEqual(denied.status_code, 200)

    def test_foreign_source_identity_and_result_links_denied(self):
        with self.scoped(self.b):
            self.commit(self.ready(self.stage(workspace=self.b), workspace=self.b), self.b)
            foreign = PartyIdentity.objects.get()
        with self.scoped():
            batch = self.ready()
            for write in [lambda: SourceIdentity.objects.create(workspace_id=self.a.pk, source_system="x", external_id="x",
                           identity_id=foreign.pk, accepted_digest="x", local_digest="x"),
                          lambda: batch.rows.update(identity_id=foreign.pk, committed_at=timezone.now())]:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    write()
