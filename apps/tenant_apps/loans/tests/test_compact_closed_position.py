"""Compact storage retains financial/source integrity and standalone portability."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.db import connection, transaction, DatabaseError

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import closed_position as admission
from apps.tenant_apps.loans.services.closed_position_portability import export_closed_position, parse_closed_position_file
from apps.tenant_apps.loans.services.history_contract import digest, dump
from . import test_closed_position_admission as fixtures


class CompactClosedPositionTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.ClosedPositionAdmissionTests.setup_tenant.__func__)
    make_snapshot = fixtures.ClosedPositionAdmissionTests.make_snapshot
    prepare_history = fixtures.ClosedPositionAdmissionTests.prepare_history
    prepare_position = fixtures.ClosedPositionAdmissionTests.prepare_position
    retain_source = fixtures.ClosedPositionAdmissionTests.retain_source
    admit_position = fixtures.ClosedPositionAdmissionTests.admit_position

    @classmethod
    def get_test_schema_name(cls):
        return "compact-closed-position"

    def setUp(self):
        super().setUp()
        self.prepare_position()

    def admit_legacy(self):
        workspace, series, accepted = admission._prepare(document=self.document, **self.mapping)
        accepted["profile"] = admission.ADMISSION_PROFILE
        accepted["position"] = deepcopy(self.document)
        loan, created = admission._write(workspace, series, self.actor, accepted)
        self.assertTrue(created)
        return loan, {}, None

    def restricted(self):
        from contextlib import contextmanager
        @contextmanager
        def role_scope():
            role = connection.ops.quote_name("compact_position_" + uuid4().hex)
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
                cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
                cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
                cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
                cursor.execute(f"SET LOCAL ROLE {role}")
            try:
                yield
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")
                    cursor.execute(f"DROP OWNED BY {role}")
                    cursor.execute(f"DROP ROLE {role}")
        return role_scope()

    def test_full_source_stored_once_and_export_hydrates_without_changing_snapshots(self):
        self.retain_source()
        # Retain a distinct valid larger snapshot, representative of source rows.
        source = deepcopy(self.document["retained_evidence"])
        source["source_records"].append({"original_notes": "preserved source facts " * 4000})
        from apps.tenant_apps.loans.services.archive import accept_evidence
        evidence = accept_evidence(workspace_id=self.tenant.pk, actor=self.actor, document=source,
            expected_sha256=digest(source), confirmed=True)
        self.document["retained_evidence"] = source
        self.mapping["evidence_id"] = evidence.public_id
        loan, _, _ = self.admit_position()
        origin = loan.historical_import
        event = loan.loan_events.get()
        stored = deepcopy(origin.document)
        payload = deepcopy(event.payload)
        self.assertEqual(stored["profile"], admission.COMPACT_ADMISSION_PROFILE)
        self.assertEqual(payload["opening"]["profile"], admission.COMPACT_EVIDENCE_PROFILE)
        self.assertIsNone(stored["position"]["retained_evidence"])
        self.assertEqual(payload["opening"]["review"], stored)
        self.assertLess(len(dump(stored)), 2500)
        full = {**stored, "profile": admission.ADMISSION_PROFILE, "position": self.document}
        self.assertGreater(len(dump(full)) - len(dump(stored)), 80000)
        self.assertEqual(admission.read_position(loan), self.document)
        content, _ = export_closed_position(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk)
        self.assertEqual(parse_closed_position_file(content)[0], self.document)
        origin.refresh_from_db(); event.refresh_from_db(); evidence.refresh_from_db()
        self.assertEqual(origin.document, stored)
        self.assertEqual(event.payload, payload)
        self.assertEqual(evidence.document, source)

    def test_v1_retry_and_batch_review_preserve_original_bytes_and_hashes(self):
        self.retain_source()
        loan, _, _ = self.admit_legacy()
        before = (deepcopy(loan.historical_import.document), loan.historical_import.source_sha256,
            deepcopy(loan.loan_events.get().payload))
        _, token = admission.preview_closed_position(document=self.document, **self.mapping)
        same, created = admission.admit_closed_position(document=self.document, review_token=token,
            confirmed=True, **self.mapping)
        self.assertFalse(created); self.assertEqual(same.pk, loan.pk)
        from apps.tenant_apps.loans.services.closed_position_batch import review_closed_position_batch, apply_closed_position_batch
        candidate = dict(document=self.document, **{k: v for k, v in self.mapping.items() if k not in {"workspace_id", "actor"}})
        manifest, token = review_closed_position_batch(workspace_id=self.tenant.pk, actor=self.actor, candidates=[candidate])
        result = apply_closed_position_batch(workspace_id=self.tenant.pk, actor=self.actor,
            manifest=manifest, review_token=token, confirmed=True)
        self.assertEqual((result["created"], result["already_admitted"]), (0, 1))
        self.assertEqual(manifest["entries"][0]["accepted_sha256"], before[1])
        loan.historical_import.refresh_from_db()
        self.assertEqual((loan.historical_import.document, loan.historical_import.source_sha256,
            loan.loan_events.get().payload), before)
        self.assertEqual(admission.read_position(loan), self.document)

    def test_v1_export_restores_to_fresh_workspace_as_compact_with_exact_media(self):
        with patch.object(self, "admit_position", side_effect=self.admit_legacy):
            fixtures.ClosedPositionAdmissionTests.test_export_reimports_to_fresh_workspace_with_new_local_ids_and_exact_media(self)
        origins = m.HistoricalLoanImport.objects.filter(source_namespace=self.document["source"]["namespace"])
        self.assertEqual(set(origins.values_list("document__profile", flat=True)),
            {admission.ADMISSION_PROFILE, admission.COMPACT_ADMISSION_PROFILE})

    def test_missing_or_corrupt_source_blocks_read_and_export(self):
        evidence = self.retain_source()
        loan, _, _ = self.admit_position()
        original_filter = m.HistoricalLoanEvidence.objects.filter
        corrupted = SimpleNamespace(document={**evidence.document, "source_records": []}, source_sha256=evidence.source_sha256)
        for result in (None, corrupted):
            def source_filter(*args, **kwargs):
                if kwargs.get("pk") == evidence.pk:
                    return SimpleNamespace(first=lambda: result)
                return original_filter(*args, **kwargs)
            with self.subTest(result=result), patch.object(m.HistoricalLoanEvidence.objects, "filter", side_effect=source_filter):
                with self.assertRaisesMessage(ValueError, "Retained source evidence differs"):
                    admission.read_position(loan)
                with self.assertRaisesMessage(ValueError, "Retained source evidence differs"):
                    export_closed_position(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk)

    def test_restricted_database_rejects_source_event_and_origin_mutation_or_delete(self):
        evidence = self.retain_source()
        loan, _, _ = self.admit_position()
        origin = loan.historical_import
        event = loan.loan_events.get()
        with self.restricted():
            for model, pk, changes in (
                (m.HistoricalLoanEvidence, evidence.pk, {"document": {}}),
                (m.HistoricalLoanImport, origin.pk, {"archive_evidence_id": None}),
                (m.HistoricalLoanImport, origin.pk, {"document": {}}),
                (m.PawnLoanEvent, event.pk, {"payload": {}}),
            ):
                with self.subTest(model=model), self.assertRaises(DatabaseError), transaction.atomic():
                    model.objects.filter(pk=pk).update(**changes)
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM loans_historicalloanevidence WHERE id=%s", [evidence.pk])

    def test_restricted_database_refuses_forged_compact_reference_and_profile_pair(self):
        evidence = self.retain_source()
        from apps.tenant_apps.loans.services.archive import accept_evidence
        other = deepcopy(evidence.document)
        other["source"]["loan_id"] = "unrelated-source"
        wrong = accept_evidence(workspace_id=self.tenant.pk, actor=self.actor, document=other,
            expected_sha256=digest(other), confirmed=True)
        before = m.PawnLoan.objects.count()
        with self.restricted():
            for mutation in ("hash", "selected", "missing", "rebind", "copy", "known_fact", "duplicate", "profile"):
                with self.subTest(mutation=mutation), self.assertRaises(DatabaseError), transaction.atomic():
                    workspace, series, accepted = admission._prepare(document=self.document, **self.mapping)
                    archive = accepted["archive"]
                    if mutation == "hash": archive["sha256"] = "f" * 64
                    elif mutation == "selected": archive["snapshots"] = [[wrong.pk, wrong.source_sha256]]
                    elif mutation == "missing": archive["snapshots"].append([999999999, "a" * 64])
                    elif mutation == "rebind": archive.update(id=wrong.pk, sha256=wrong.source_sha256, snapshots=[[wrong.pk, wrong.source_sha256]])
                    elif mutation == "copy": accepted["position"]["retained_evidence"] = self.document["retained_evidence"]
                    elif mutation == "known_fact": accepted["position"]["loan"]["number"] = "P-0020"
                    elif mutation == "duplicate": archive["snapshots"] *= 2
                    # Force an invalid profile pair directly in the event writer.
                    event_profile = admission.EVIDENCE_PROFILE if mutation == "profile" else admission.COMPACT_EVIDENCE_PROFILE
                    # Isolate database enforcement: ordinary number/source
                    # checks already reject several of these before SQL.
                    with patch.object(admission, "read_position", return_value={}), \
                            patch("apps.tenant_apps.loans.services.recorded_numbers.claim_number"), \
                            patch.object(admission, "COMPACT_EVIDENCE_PROFILE", event_profile):
                        admission._write(workspace, series, self.actor, accepted)
        self.assertEqual(m.PawnLoan.objects.count(), before)
        self.seq.refresh_from_db(); self.assertEqual(self.seq.next_number, 1)

    def test_guard_rollback_refuses_posted_compact_positions(self):
        self.admit_position()
        from importlib import import_module
        guard = import_module("apps.tenant_apps.loans.migrations.0068_compact_closed_position_evidence")
        with self.assertRaisesMessage(DatabaseError, "rollback refused"), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(guard.Migration.operations[0].reverse_sql)

    def test_populated_v1_guard_upgrade_preserves_snapshots_and_accepts_v2(self):
        self.retain_source()
        old, _, _ = self.admit_legacy()
        before = (deepcopy(old.historical_import.document), old.historical_import.source_sha256,
            deepcopy(old.loan_events.get().payload))
        from importlib import import_module
        guard = import_module("apps.tenant_apps.loans.migrations.0068_compact_closed_position_evidence")
        with connection.cursor() as cursor:
            cursor.execute(guard.Migration.operations[0].reverse_sql)
            cursor.execute(guard.Migration.operations[0].sql)
        old.historical_import.refresh_from_db()
        self.assertEqual((old.historical_import.document, old.historical_import.source_sha256,
            old.loan_events.get().payload), before)
        self.assertEqual(admission.read_position(old), self.document)
        self.document = deepcopy(self.document)
        self.document["source"]["loan_id"] = "loan-11"
        self.document["loan"]["number"] = "P-0011"
        self.document["retained_evidence"] = None
        self.mapping.pop("evidence_id")
        new, _, _ = self.admit_position()
        self.assertEqual(new.historical_import.document["profile"], admission.COMPACT_ADMISSION_PROFILE)

    def test_compact_source_references_remain_hidden_outside_workspace(self):
        evidence = self.retain_source()
        loan, _, _ = self.admit_position()
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context, workspace_context
        other = Company.objects.create(name="Unrelated", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        with self.restricted(), without_workspace_context():
            self.assertFalse(m.HistoricalLoanEvidence.objects.filter(pk=evidence.pk).exists())
            with workspace_context(other.pk):
                self.assertFalse(m.HistoricalLoanEvidence.objects.filter(pk=evidence.pk).exists())
                self.assertFalse(m.HistoricalLoanImport.objects.filter(loan_id=loan.pk).exists())
                self.assertEqual(m.HistoricalLoanEvidence.objects.filter(pk=evidence.pk).update(source_sha256="a"*64), 0)
                with self.assertRaises(ValueError):
                    admission.read_position(loan)

    def test_unadmitted_old_batch_review_requires_fresh_review(self):
        self.retain_source()
        _, _, accepted = admission._prepare(document=self.document, **self.mapping)
        old = deepcopy(accepted)
        old["profile"] = admission.ADMISSION_PROFILE
        old["position"] = deepcopy(self.document)
        from apps.tenant_apps.loans.services.closed_position_batch import review_closed_position_batch
        candidate = dict(document=self.document, expected_sha256=digest(old),
            **{k: v for k, v in self.mapping.items() if k not in {"workspace_id", "actor"}})
        with self.assertRaisesMessage(ValueError, "earlier reviewed source or mapping changed"):
            review_closed_position_batch(workspace_id=self.tenant.pk, actor=self.actor, candidates=[candidate])
        self.assertFalse(m.PawnLoan.objects.filter(is_imported_closed_position=True).exists())
