import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import current_workspace_id, workspace_context
from apps.tenant_apps.party.models import Party, PartyCodeSequence
from apps.tenant_apps.data_portability.models import PartyIdentity
from apps.tenant_apps.data_portability.services import stage_import, validate_import, commit_import, export_parties
from apps.tenant_apps.data_portability.tests.test_portability import CSV, MAPPING


class PortabilityConcurrencyTests(TransactionTestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex
        self.actor = get_user_model().objects.create_user(username="port-concurrent-" + suffix)
        self.workspace = Company.objects.create(name="Concurrent " + suffix, schema_name="pc" + suffix,
                                                owner=self.actor, creator=self.actor)
        Membership.objects.get_or_create(company=self.workspace, user=self.actor,
                                          defaults={"role": Role.objects.get_or_create(name="Owner")[0]})
        self.role = connection.ops.quote_name("port_concurrent_" + suffix)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {self.role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {self.role}")
            cursor.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {self.role}")
            cursor.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {self.role}")

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {self.role}")
            cursor.execute(f"DROP ROLE {self.role}")

    def parallel(self, callback):
        barrier = Barrier(2)
        def run():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                barrier.wait(timeout=30)
                with workspace_context(self.workspace.pk):
                    result = callback()
                self.assertIsNone(current_workspace_id())
                return result
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            return [future.result(timeout=60) for future in futures]

    def test_concurrent_commit_of_same_approval_creates_once(self):
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            batch = stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
            batch = validate_import(**args, batch_id=batch.public_id, mapping=MAPPING)
        result = self.parallel(lambda: commit_import(**args, batch_id=batch.public_id, approval_digest=batch.approval_digest).state)
        self.assertEqual(result, ["COMPLETED", "COMPLETED"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(Party.objects.filter(workspace=self.workspace).count(), 1)
            self.assertEqual(PartyCodeSequence.objects.get(workspace=self.workspace).next_number, 2)

    def test_concurrent_first_exports_allocate_same_stable_identity(self):
        with workspace_context(self.workspace.pk):
            Party.objects.create(display_name="Export race")
        result = self.parallel(lambda: export_parties(workspace_id=self.workspace.pk, actor=self.actor))
        self.assertEqual(result[0], result[1])
        with workspace_context(self.workspace.pk):
            self.assertEqual(PartyIdentity.objects.filter(workspace=self.workspace).count(), 1)


    def test_concurrent_child_commit_creates_once(self):
        from apps.tenant_apps.data_portability.models import ChildIdentity
        from apps.tenant_apps.party.models import PartyContactMethod
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            master = stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
            master = validate_import(**args, batch_id=master.public_id, mapping=MAPPING)
            commit_import(**args, batch_id=master.public_id, approval_digest=master.approval_digest)
            batch = stage_import(**args, profile="party-contact/1", filename="contacts.csv", source_system="contacts",
                content=b"Key,Party,Type,Value\nc-1,old-1,EMAIL,asha@example.com\n")
            batch = validate_import(**args, batch_id=batch.public_id, mapping={"columns": {
                "Key": "source.external_id", "Party": "party_external_id", "Type": "contact_type", "Value": "value"},
                "defaults": {"party_source_system": "paper", "source_is_verified": False, "is_primary": True}})
        result = self.parallel(lambda: commit_import(**args, batch_id=batch.public_id, approval_digest=batch.approval_digest).state)
        self.assertEqual(result, ["COMPLETED", "COMPLETED"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(PartyContactMethod.objects.filter(workspace=self.workspace).count(), 1)
            self.assertEqual(ChildIdentity.objects.filter(workspace=self.workspace).count(), 1)

    def test_concurrent_first_child_exports_share_ids(self):
        from apps.tenant_apps.data_portability.services import export_children
        from apps.tenant_apps.data_portability.models import ChildIdentity
        from apps.tenant_apps.party.models import PartyAddress
        with workspace_context(self.workspace.pk):
            party = Party.objects.create(display_name="Address export")
            PartyAddress.objects.create(party=party, address_type="HOME", line1="12 Road", city="Pune")
        result = self.parallel(lambda: export_children(workspace_id=self.workspace.pk, actor=self.actor, profile="party-address/1"))
        self.assertEqual(result[0], result[1])
        with workspace_context(self.workspace.pk):
            self.assertEqual(ChildIdentity.objects.filter(workspace=self.workspace).count(), 1)


    def test_concurrent_identifier_commit_creates_once(self):
        from apps.tenant_apps.party.models import PartyIdentifier
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            master = stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
            master = validate_import(**args, batch_id=master.public_id, mapping=MAPPING)
            commit_import(**args, batch_id=master.public_id, approval_digest=master.approval_digest)
            batch = stage_import(**args, profile="party-identifier/1", filename="identifiers.csv", source_system="identifiers",
                content=b"Key,Party,Type,Value\ni-1,old-1,PASSPORT,AB001234\n")
            batch = validate_import(**args, batch_id=batch.public_id, mapping={"columns": {
                "Key": "source.external_id", "Party": "party_external_id", "Type": "identifier_type", "Value": "value"},
                "defaults": {"party_source_system": "paper", "source_is_verified": False}})
        result = self.parallel(lambda: commit_import(**args, batch_id=batch.public_id, approval_digest=batch.approval_digest).state)
        self.assertEqual(result, ["COMPLETED", "COMPLETED"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(PartyIdentifier.objects.filter(workspace=self.workspace).count(), 1)


    def test_concurrent_role_commit_creates_once(self):
        from apps.tenant_apps.party.models import PartyRole, PartyRoleType
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            PartyRoleType.objects.create(key="BORROWER", label="Borrower")
            master = stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
            master = validate_import(**args, batch_id=master.public_id, mapping=MAPPING)
            commit_import(**args, batch_id=master.public_id, approval_digest=master.approval_digest)
            batch = stage_import(**args, profile="party-role/1", filename="roles.csv", source_system="roles",
                content=b"Key,Party,Role,Status\nr-1,old-1,customer,ACTIVE\n")
            batch = validate_import(**args, batch_id=batch.public_id, mapping={"columns": {
                "Key": "source.external_id", "Party": "party_external_id", "Role": "role_type_key", "Status": "status"},
                "defaults": {"party_source_system": "paper"}, "role_type_map": {"customer": "BORROWER"}})
        result = self.parallel(lambda: commit_import(**args, batch_id=batch.public_id, approval_digest=batch.approval_digest).state)
        self.assertEqual(result, ["COMPLETED", "COMPLETED"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(PartyRole.objects.filter(workspace=self.workspace).count(), 1)


    def test_role_commit_locks_destination_rows_even_when_type_ids_differ(self):
        from django.db import DatabaseError
        from apps.tenant_apps.party.models import PartyRole, PartyRoleType
        from apps.tenant_apps.data_portability import children
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            PartyRoleType.objects.create(pk=987654, key="BORROWER", label="Borrower")
            master = stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
            master = validate_import(**args, batch_id=master.public_id, mapping=MAPPING)
            commit_import(**args, batch_id=master.public_id, approval_digest=master.approval_digest)
            content = b"Key,Party,Role,Status\nr-1,old-1,customer,ACTIVE\n"
            mapping = {"columns": {"Key": "source.external_id", "Party": "party_external_id", "Role": "role_type_key", "Status": "status"},
                "defaults": {"party_source_system": "paper"}, "role_type_map": {"customer": "BORROWER"}}
            batch = stage_import(**args, profile="party-role/1", filename="roles.csv", source_system="roles", content=content)
            batch = validate_import(**args, batch_id=batch.public_id, mapping=mapping)
            commit_import(**args, batch_id=batch.public_id, approval_digest=batch.approval_digest)
            role_pk = PartyRole.objects.get(workspace=self.workspace).pk
            replay = stage_import(**args, profile="party-role/1", filename="roles.csv", source_system="roles", content=content)
            replay = validate_import(**args, batch_id=replay.public_id, mapping=mapping)
        def try_native_lock():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                with workspace_context(self.workspace.pk):
                    PartyRole.objects.select_for_update(nowait=True).get(pk=role_pk)
                return False
            except DatabaseError as exc:
                return getattr(exc.__cause__, "pgcode", None) == "55P03"
            finally:
                connections.close_all()
        with workspace_context(self.workspace.pk):
            children.lock_destinations(replay, list(replay.rows.all()))
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertTrue(pool.submit(try_native_lock).result(timeout=30))


    def relationship_batch(self, args):
        content = b"Legacy,Party,Phone\nold-1,Asha Devi,\nold-2,Bina Shah,\n"
        master = stage_import(**args, content=content, filename="a.csv", source_system="paper")
        master = validate_import(**args, batch_id=master.public_id, mapping=MAPPING)
        commit_import(**args, batch_id=master.public_id, approval_digest=master.approval_digest)
        batch = stage_import(**args, profile="party-relationship/1", filename="relationships.csv", source_system="relationships",
            content=b"Key,From,To,Type\nr-1,old-1,old-2,FAMILY\n")
        return validate_import(**args, batch_id=batch.public_id, mapping={"columns": {
            "Key": "source.external_id", "From": "party_external_id", "To": "to_party_external_id", "Type": "relationship_type"},
            "defaults": {"party_source_system": "paper", "to_party_source_system": "paper", "is_active": True}})

    def test_concurrent_relationship_commit_creates_once(self):
        from apps.tenant_apps.party.models import PartyRelationship
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            batch = self.relationship_batch(args)
        result = self.parallel(lambda: commit_import(**args, batch_id=batch.public_id, approval_digest=batch.approval_digest).state)
        self.assertEqual(result, ["COMPLETED", "COMPLETED"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(PartyRelationship.objects.filter(workspace=self.workspace).count(), 1)

    def test_concurrent_first_relationship_exports_share_both_identities(self):
        from apps.tenant_apps.data_portability.services import export_children
        from apps.tenant_apps.data_portability.models import ChildIdentity
        from apps.tenant_apps.party.models import PartyRelationship
        with workspace_context(self.workspace.pk):
            first = Party.objects.create(display_name="From")
            second = Party.objects.create(display_name="To")
            PartyRelationship.objects.create(from_party=first, to_party=second, relationship_type="FAMILY")
        result = self.parallel(lambda: export_children(workspace_id=self.workspace.pk, actor=self.actor, profile="party-relationship/1"))
        self.assertEqual(result[0], result[1])
        with workspace_context(self.workspace.pk):
            identity = ChildIdentity.objects.get(workspace=self.workspace)
            self.assertEqual(identity.parent.party_id, first.pk)
            self.assertEqual(identity.related_parent.party_id, second.pk)

    def test_relationship_commit_locks_both_parties_and_relationship(self):
        from django.db import DatabaseError
        from apps.tenant_apps.party.models import PartyRelationship
        from apps.tenant_apps.data_portability import children
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            batch = self.relationship_batch(args)
            commit_import(**args, batch_id=batch.public_id, approval_digest=batch.approval_digest)
            obj = PartyRelationship.objects.get(workspace=self.workspace)
        def try_native_lock(model, pk):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                with workspace_context(self.workspace.pk):
                    model.objects.select_for_update(nowait=True).get(pk=pk)
                return False
            except DatabaseError as exc:
                return getattr(exc.__cause__, "pgcode", None) == "55P03"
            finally:
                connections.close_all()
        with workspace_context(self.workspace.pk):
            children.lock_destinations(batch, list(batch.rows.all()))
            with ThreadPoolExecutor(max_workers=1) as pool:
                for model, pk in ((Party, obj.from_party_id), (Party, obj.to_party_id), (PartyRelationship, obj.pk)):
                    self.assertTrue(pool.submit(try_native_lock, model, pk).result(timeout=30))


    def test_concurrent_preset_saves_reuse_identical_version(self):
        from apps.tenant_apps.data_portability.presets import save_preset
        from apps.tenant_apps.data_portability.models import MappingPresetVersion
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            batch = stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
            batch = validate_import(**args, batch_id=batch.public_id, mapping=MAPPING)
        result = self.parallel(lambda: save_preset(**args, batch_id=batch.public_id, name="Register", approval_digest=batch.approval_digest).pk)
        self.assertEqual(result[0], result[1])
        with workspace_context(self.workspace.pk):
            self.assertEqual(MappingPresetVersion.objects.filter(workspace=self.workspace).count(), 1)

    def test_concurrent_changed_preset_saves_append_distinct_versions(self):
        import copy
        from apps.tenant_apps.data_portability.presets import save_preset
        from apps.tenant_apps.data_portability.models import MappingPresetVersion
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        batches = []
        with workspace_context(self.workspace.pk):
            for value in ("LOW", "HIGH"):
                mapping = copy.deepcopy(MAPPING)
                mapping["defaults"]["risk_label"] = value
                batch = stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
                batches.append(validate_import(**args, batch_id=batch.public_id, mapping=mapping))
        barrier = Barrier(2)
        def save(batch):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                barrier.wait(timeout=30)
                with workspace_context(self.workspace.pk):
                    return save_preset(**args, batch_id=batch.public_id, name="Register", approval_digest=batch.approval_digest).version
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(save, batch) for batch in batches]
            self.assertEqual(sorted(f.result(timeout=60) for f in futures), [1, 2])
        with workspace_context(self.workspace.pk):
            versions = MappingPresetVersion.objects.filter(workspace=self.workspace)
            self.assertEqual({p.mapping["defaults"]["risk_label"] for p in versions}, {"LOW", "HIGH"})


    def test_concurrent_xlsx_preset_commit_creates_once(self):
        from apps.tenant_apps.data_portability.presets import save_preset
        from apps.tenant_apps.data_portability.tests.test_xlsx import workbook_bytes
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            original = stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
            original = validate_import(**args, batch_id=original.public_id, mapping=MAPPING)
            preset = save_preset(**args, batch_id=original.public_id, name="Register", approval_digest=original.approval_digest)
            batch = stage_import(**args, content=workbook_bytes(), filename="a.xlsx", source_system="paper")
            batch = validate_import(**args, batch_id=batch.public_id, preset_id=preset.public_id)
        result = self.parallel(lambda: commit_import(**args, batch_id=batch.public_id, approval_digest=batch.approval_digest).state)
        self.assertEqual(result, ["COMPLETED", "COMPLETED"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(Party.objects.filter(workspace=self.workspace).count(), 1)


    def test_bundle_snapshot_blocks_writes_and_phantoms_without_blocking_other_workspaces(self):
        from unittest.mock import patch
        from django.db import OperationalError, transaction
        from apps.tenant_apps.data_portability import bundles
        from apps.tenant_apps.party.models import PartyAddress
        other = Company.objects.create(name="Other snapshot", schema_name="other" + uuid.uuid4().hex,
                                       owner=self.actor, creator=self.actor)
        with workspace_context(self.workspace.pk):
            party = Party.objects.create(display_name="Snapshot")
            address = PartyAddress.objects.create(party=party, address_type="HOME", line1="Before")
        with workspace_context(other.pk):
            outsider = Party.objects.create(display_name="Unrelated")

        def attempt(kind):
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                target = other.pk if kind == "other" else self.workspace.pk
                with workspace_context(target):
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '300ms'")
                    if kind == "update":
                        PartyAddress.objects.filter(pk=address.pk).update(line1="After")
                    elif kind == "update_parent":
                        Party.objects.filter(pk=party.pk).update(display_name="Changed parent")
                    elif kind == "delete":
                        PartyAddress.objects.filter(pk=address.pk).delete()
                    elif kind == "insert":
                        # Direct ORM insert, bypassing all application service locks.
                        PartyAddress.objects.create(party_id=party.pk, address_type="WORK", line1="New")
                        connection.check_constraints()
                    elif kind == "parent":
                        Party.objects.create(display_name="New parent")
                        connection.check_constraints()
                    else:
                        Party.objects.filter(pk=outsider.pk).update(display_name="Still independent")
                return "committed"
            except OperationalError as exc:
                return getattr(exc.__cause__, "pgcode", None) or getattr(exc.__cause__, "sqlstate", None)
            finally:
                connections.close_all()

        original = bundles.services.export_parties
        def during_export(**kwargs):
            with ThreadPoolExecutor(max_workers=1) as pool:
                for kind in ("update", "update_parent", "delete", "insert", "parent", "other"):
                    result = pool.submit(attempt, kind).result(timeout=15)
                    self.assertEqual(result, "committed" if kind == "other" else "55P03", kind)
            return original(**kwargs)
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {self.role}")
        try:
            with workspace_context(self.workspace.pk), patch.object(bundles.services, "export_parties", side_effect=during_export):
                result = bundles.export_bundle(workspace_id=self.workspace.pk, actor=self.actor)
                self.assertEqual(result.count, 2)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
        with workspace_context(self.workspace.pk):
            self.assertEqual(PartyAddress.objects.get().line1, "Before")

    def test_bundle_busy_row_is_retryable_and_does_not_leave_partial_identities(self):
        from threading import Event
        from apps.tenant_apps.data_portability import bundles
        from apps.tenant_apps.data_portability.parsers import PortabilityError
        with workspace_context(self.workspace.pk):
            party = Party.objects.create(display_name="Busy")
        locked, release = Event(), Event()
        def hold():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                with workspace_context(self.workspace.pk):
                    Party.objects.select_for_update().get(pk=party.pk)
                    locked.set()
                    if not release.wait(20):
                        raise AssertionError("Export failed to release writer")
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            writer = pool.submit(hold)
            try:
                self.assertTrue(locked.wait(10))
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                with workspace_context(self.workspace.pk):
                    with self.assertRaisesMessage(PortabilityError, "Retry"):
                        bundles.export_bundle(workspace_id=self.workspace.pk, actor=self.actor)
                    self.assertFalse(PartyIdentity.objects.exists())
            finally:
                release.set()
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")
            writer.result(timeout=10)


    def test_concurrent_bundle_staging_respects_whole_bundle_capacity(self):
        from apps.tenant_apps.data_portability import bundle_import, bundles
        from apps.tenant_apps.data_portability.models import ImportBatch
        from apps.tenant_apps.data_portability.parsers import PortabilityError
        from apps.tenant_apps.party.models import PartyAddress
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            party = Party.objects.create(display_name="Bundle capacity")
            PartyAddress.objects.create(party=party, address_type="HOME", line1="12 Road")
            content = bundles.export_bundle(**args).content
            for _ in range(17):
                stage_import(**args, content=CSV, filename="a.csv", source_system="paper")
        def stage():
            try:
                return len([b for _, b in bundle_import.stage_bundle(**args, content=content) if b])
            except PortabilityError:
                return "full"
        results = self.parallel(stage)
        self.assertCountEqual(results, [2, "full"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(ImportBatch.objects.filter(workspace_id=self.workspace.pk).count(), 19)
            self.assertEqual(Party.objects.filter(workspace_id=self.workspace.pk).count(), 1)


    def test_concurrent_combined_bundle_commit_creates_once(self):
        from django.core import signing
        from apps.tenant_apps.data_portability import bundle_commit, bundle_import, bundles
        from apps.tenant_apps.data_portability.models import ImportBatch
        from apps.tenant_apps.party.models import PartyAddress
        source = Company.objects.create(name="Bundle source", schema_name="bs" + uuid.uuid4().hex,
                                        owner=self.actor, creator=self.actor)
        Membership.objects.get_or_create(company=source, user=self.actor,
            defaults={"role": Role.objects.get_or_create(name="Owner")[0]})
        with workspace_context(source.pk):
            party = Party.objects.create(display_name="Atomic bundle")
            PartyAddress.objects.create(party=party, address_type="HOME", line1="12 Road", city="Pune")
            content = bundles.export_bundle(workspace_id=source.pk, actor=self.actor).content
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            staged = bundle_import.stage_bundle(**args, content=content)
            receipt = signing.dumps({"workspace": self.workspace.pk,
                "batches": [(profile, str(batch.public_id) if batch else None) for profile, batch in staged]}, salt=bundle_commit.RECEIPT_SALT)
            preview = bundle_commit.preview_bundle(**args, receipt=receipt, role_map={})
            self.assertTrue(preview["ready"], preview)
            approval = preview["approval"]
        result = self.parallel(lambda: [b.state for b in bundle_commit.commit_bundle(**args,
            approval=approval, acknowledge_warnings=True)])
        self.assertEqual(result, [["COMPLETED", "COMPLETED"], ["COMPLETED", "COMPLETED"]])
        with workspace_context(self.workspace.pk):
            self.assertEqual(Party.objects.filter(workspace_id=self.workspace.pk).count(), 1)
            self.assertEqual(PartyAddress.objects.filter(workspace_id=self.workspace.pk).count(), 1)
            self.assertEqual(ImportBatch.objects.filter(workspace_id=self.workspace.pk, state="COMPLETED").count(), 2)


    def test_bundle_cancellation_serializes_with_combined_commit(self):
        from threading import Lock
        from apps.tenant_apps.data_portability import bundle_history, bundle_commit, bundle_import, bundles
        from apps.tenant_apps.data_portability.models import ImportBatch
        from apps.tenant_apps.data_portability.parsers import PortabilityError
        from apps.tenant_apps.party.models import PartyAddress
        source = Company.objects.create(name="Cancel source", schema_name="cs" + uuid.uuid4().hex,
                                        owner=self.actor, creator=self.actor)
        Membership.objects.get_or_create(company=source, user=self.actor,
            defaults={"role": Role.objects.get_or_create(name="Owner")[0]})
        with workspace_context(source.pk):
            party = Party.objects.create(display_name="Cancellation race")
            PartyAddress.objects.create(party=party, address_type="HOME", line1="12 Road", city="Pune")
            content = bundles.export_bundle(workspace_id=source.pk, actor=self.actor).content
        args = {"workspace_id": self.workspace.pk, "actor": self.actor}
        with workspace_context(self.workspace.pk):
            history = bundle_import.stage_bundle_history(**args, content=content)
            preview = bundle_commit.preview_bundle(**args, receipt=bundle_history.review_receipt(history), role_map={})
            self.assertTrue(preview["ready"], preview)
        calls, lock = [], Lock()
        def run():
            with lock:
                is_cancel = not calls
                calls.append(True)
            if is_cancel:
                return bundle_history.cancel_unfinished(**args, bundle_id=history.public_id, confirmed=True)
            try:
                bundle_commit.commit_bundle(**args, approval=preview["approval"], acknowledge_warnings=True)
                return "committed"
            except PortabilityError:
                return "cancelled"
        result = self.parallel(run)
        with workspace_context(self.workspace.pk):
            states = list(ImportBatch.objects.filter(workspace_id=self.workspace.pk).values_list("state", flat=True))
            if "committed" in result:
                self.assertCountEqual(result, [0, "committed"])
                self.assertEqual(states, ["COMPLETED", "COMPLETED"])
                self.assertEqual(Party.objects.filter(workspace_id=self.workspace.pk).count(), 1)
            else:
                self.assertCountEqual(result, [2, "cancelled"])
                self.assertEqual(states, ["CANCELLED", "CANCELLED"])
                self.assertFalse(Party.objects.filter(workspace_id=self.workspace.pk).exists())

    def test_concurrent_complete_loan_history_commit_creates_one_aggregate(self):
        from datetime import date
        from apps.tenant_apps.data_portability import loan_history
        from apps.tenant_apps.data_portability.tests.test_loan_history import document
        from apps.tenant_apps.loans.services.history_contract import encode
        from apps.tenant_apps.loans.services.license_series import create_license
        from apps.tenant_apps.loans.models import LoanSeries,LoanProduct,LoanProductVersion,PawnLoan,HistoricalLoanImport
        args={"workspace_id":self.workspace.pk,"actor":self.actor}
        with workspace_context(self.workspace.pk):
            party=stage_import(**args,content=CSV,filename="party.csv",source_system="paper")
            party=validate_import(**args,batch_id=party.public_id,mapping=MAPPING)
            commit_import(**args,batch_id=party.public_id,approval_digest=party.approval_digest)
            license=create_license(workspace=self.workspace,actor=self.actor,name="Historical",license_number="OLD-L",issued_on=date(2020,1,1),expires_on=date(2022,1,1))
            series=LoanSeries.objects.create(license=license,name="Historical",code="H")
            product=LoanProduct.objects.create(workspace=self.workspace,code="H",name="Historical")
            version=LoanProductVersion.objects.create(product=product,version=1,status="RETIRED",repayment_structure="FLEXIBLE_PARTIAL_PAYMENT",amortisation_method="NONE",payment_frequency="FLEXIBLE",extra_payment_rule="REDUCE_PRINCIPAL",maximum_tenor_months=12,operational_grace_days=3,calculation_contract_version="TEST-V1")
            batch=loan_history.stage(**args,content=encode(document(True)))
            token=loan_history.preview(**args,batch_id=batch.public_id,values=dict(revision_id=license.revisions.get().pk,series_id=series.pk,product_version_id=version.pk))
        result=self.parallel(lambda:loan_history.commit(**args,batch_id=batch.public_id,approval=token,confirmed=True).pk)
        self.assertEqual(result[0],result[1])
        with workspace_context(self.workspace.pk):
            self.assertEqual(PawnLoan.objects.count(),1)
            self.assertEqual(HistoricalLoanImport.objects.count(),1)
