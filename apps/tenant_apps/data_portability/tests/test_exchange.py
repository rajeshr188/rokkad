"""Synthetic cohorts at audited population sizes, never live customer copies."""
from copy import deepcopy
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from django.core.exceptions import PermissionDenied
from django.core.management import call_command, CommandError
from django.test import override_settings

from apps.tenant_apps.data_portability import exchange, services, loan_restore, children
from apps.tenant_apps.data_portability.contracts import dump
from apps.tenant_apps.data_portability.models import ImportBatch, PartyIdentity, WorkspaceNamespace
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.party.models import Party, PartyContactMethod
from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services.closed_position import preview_closed_position, admit_closed_position
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from .fixtures import PortabilityFixture


def rewrite_manifest(directory, edit):
    path = Path(directory) / "manifest.json"
    doc = json.loads(path.read_bytes())
    edit(doc)
    doc["sha256"] = exchange.sha(dump({k:v for k,v in doc.items() if k != "sha256"}).encode())
    path.write_text(dump(doc), encoding="utf-8")
    return doc


class ExchangeTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def export(self, **values):
        return exchange.write_exchange(workspace_id=self.a.pk, actor=self.actor,
            directory=self.directory, include_loans=False, **values)

    def stage_chunk(self, doc, number):
        return exchange.stage_chunk(workspace_id=self.b.pk, actor=self.actor,
            directory=self.directory, expected_sha256=doc["sha256"], number=number)

    def test_audited_customer_population_sizes_have_complete_bounded_stable_chunks(self):
        with self.scoped(self.b):
            Party.objects.bulk_create([Party(workspace_id=self.b.pk, display_name=f"Synthetic Lakshmi {i}", party_code=f"L{i}") for i in range(2104)])
        with self.scoped():
            Party.objects.bulk_create([Party(workspace_id=self.a.pk, display_name=f"Synthetic JCL {i}", party_code=f"J{i}") for i in range(5887)])
            parents = list(Party.objects.order_by("pk").values_list("pk", flat=True)[:1001])
            PartyContactMethod.objects.bulk_create([PartyContactMethod(workspace_id=self.a.pk, party_id=pk,
                contact_type="EMAIL", value=f"synthetic{i}@example.com", normalized_value=f"synthetic{i}@example.com") for i,pk in enumerate(parents)])
            doc = self.export()
            self.assertEqual(doc["counts"]["party-master/1"], 5887)
            self.assertEqual([c["count"] for c in doc["chunks"] if c["profile"] == "party-master/1"], [1000]*5+[887])
            self.assertEqual([c["count"] for c in doc["chunks"] if c["profile"] == "party-contact/1"], [1000,1])
            ids, bytes_first = set(), []
            for entry in doc["chunks"]:
                content = exchange.chunk_bytes(self.directory, entry)
                self.assertNotIn(b"Synthetic Lakshmi", content)
                records = [json.loads(line) for line in content.splitlines()]
                if entry["profile"] == "party-master/1":
                    self.assertFalse(ids.intersection(r["id"] for r in records))
                    ids.update(r["id"] for r in records)
                bytes_first.append(content)
            self.assertEqual(len(ids), 5887)
            with TemporaryDirectory() as target:
                repeated = exchange.write_exchange(workspace_id=self.a.pk, actor=self.actor, directory=target, include_loans=False)
                self.assertEqual([exchange.chunk_bytes(target, c) for c in repeated["chunks"]], bytes_first)
        with TemporaryDirectory() as target, self.scoped(self.b):
            lakshmi = exchange.write_exchange(workspace_id=self.b.pk, actor=self.actor, directory=target, include_loans=False)
            self.assertEqual([c["count"] for c in lakshmi["chunks"]], [1000,1000,104])

    def test_interrupted_stage_reuses_receipt_and_enforces_dependency_order(self):
        with self.scoped(), patch.object(exchange, "MAX_ROWS", 2):
            Party.objects.bulk_create([Party(workspace_id=self.a.pk, display_name=f"Chunk borrower {i}", party_code=f"B{i}") for i in range(3)])
            doc = self.export()
        with self.scoped(self.b):
            with self.assertRaisesMessage(PortabilityError, "earlier manifest"):
                self.stage_chunk(doc, 2)
            first = self.stage_chunk(doc, 1)
            self.assertEqual(self.stage_chunk(doc, 1).pk, first.pk)
            self.assertFalse(Party.objects.exists())
            first = services.validate_import(workspace_id=self.b.pk, actor=self.actor, batch_id=first.public_id, mapping={})
            services.commit_import(workspace_id=self.b.pk, actor=self.actor, batch_id=first.public_id, approval_digest=first.approval_digest, acknowledge_warnings=True)
            self.assertEqual(self.stage_chunk(doc, 1).state, "COMPLETED")
            second = self.stage_chunk(doc, 2)
            second = services.validate_import(workspace_id=self.b.pk, actor=self.actor, batch_id=second.public_id, mapping={})
            services.commit_import(workspace_id=self.b.pk, actor=self.actor, batch_id=second.public_id, approval_digest=second.approval_digest, acknowledge_warnings=True)
            self.assertEqual(Party.objects.count(), 3)
            self.assertEqual(ImportBatch.objects.count(), 2)
            progress = exchange.inspect_exchange(workspace_id=self.b.pk, actor=self.actor, directory=self.directory)
            self.assertEqual([row["state"] for row in progress["progress"]], ["COMPLETED"]*2)
        # Source edits do not change already materialized exchange bytes.
        with self.scoped():
            Party.objects.update(display_name="Changed after snapshot")
        with self.scoped(self.b):
            self.assertEqual(self.stage_chunk(doc, 2).state, "COMPLETED")

    def test_child_groups_keep_primary_summary_order_across_chunks(self):
        with self.scoped(), patch.object(exchange, "MAX_ROWS", 2):
            first = Party.objects.create(display_name="First")
            second = Party.objects.create(display_name="Second", primary_phone="+919222222222")
            PartyContactMethod.objects.create(party=first, contact_type="EMAIL", value="first@example.com")
            PartyContactMethod.objects.create(party=second, contact_type="PHONE", value="+919111111111", is_primary=True)
            PartyContactMethod.objects.create(party=second, contact_type="MOBILE", value="+919222222222", is_primary=True)
            doc = self.export()
            self.assertEqual([c["count"] for c in doc["chunks"] if c["profile"] == "party-contact/1"], [1,2])
        with self.scoped(self.b):
            for number in range(1, len(doc["chunks"])+1):
                batch = self.stage_chunk(doc, number)
                batch = services.validate_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id, mapping={})
                self.assertEqual(batch.state, "READY", batch.summary)
                services.commit_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id, approval_digest=batch.approval_digest, acknowledge_warnings=True)
            self.assertEqual(Party.objects.get(display_name="Second").primary_phone, "+919222222222")

    def test_missing_corrupt_manifest_and_path_escape_fail_before_staging(self):
        with self.scoped():
            Party.objects.create(display_name="Integrity")
            doc = self.export()
        with self.scoped(self.b):
            with self.assertRaises(PortabilityError):
                exchange.stage_chunk(workspace_id=self.b.pk, actor=self.actor, directory=self.directory, expected_sha256="0"*64, number=1)
            path = self.directory / doc["chunks"][0]["path"]
            original = path.read_bytes()
            path.write_bytes(b"changed")
            with self.assertRaisesMessage(PortabilityError, "changed or truncated"):
                self.stage_chunk(doc, 1)
            path.write_bytes(original)
            rewrite_manifest(self.directory, lambda d: d["chunks"][0].update(path="../secret.jsonl"))
            with self.assertRaises(PortabilityError):
                exchange.read_manifest(self.directory)
            self.assertFalse(ImportBatch.objects.exists())

    def test_overflow_and_late_profile_error_roll_back_identity_allocation(self):
        with self.scoped():
            Party.objects.create(display_name="Bounded")
            with patch.object(exchange, "MAX_TOTAL_BYTES", 1), self.assertRaises(PortabilityError):
                self.export()
            self.assertFalse(WorkspaceNamespace.objects.exists())
            self.assertFalse(PartyIdentity.objects.exists())
            self.assertFalse((self.directory / "manifest.json").exists())

    def test_byte_overflow_splits_files_instead_of_truncating_or_raising_row_limit(self):
        with self.scoped():
            for i in range(3):
                Party.objects.create(display_name=f"Large row {i} " + "x"*200, legal_name="Legal " + "x"*200)
            limit = len(services.export_parties(workspace_id=self.a.pk, actor=self.actor).content)-1
            with patch.object(services, "MAX_BYTES", limit):
                doc = self.export()
            self.assertGreater(len(doc["chunks"]), 1)
            self.assertEqual(sum(entry["count"] for entry in doc["chunks"]), 3)
            self.assertTrue(all(entry["bytes"] <= limit for entry in doc["chunks"]))

    def test_context_permission_and_fresh_snapshot_requirements(self):
        with self.assertRaises(PermissionDenied):
            self.export()
        with self.scoped():
            with self.assertRaises(PermissionDenied):
                exchange.write_exchange(workspace_id=self.a.pk, actor=self.other_actor, directory=self.directory, include_loans=False)
            with self.assertRaisesMessage(PortabilityError, "REPEATABLE READ"):
                self.export(_consistent_snapshot=True)
            with self.assertRaises(CommandError):
                call_command("portability_exchange", "export", workspace_id=self.a.pk, actor_id=self.actor.pk,
                    directory=str(self.directory / "new"), party_only=True)

    def test_only_unique_completed_native_aliases_resolve_borrowers(self):
        with self.scoped():
            Party.objects.create(display_name="Alias one")
            Party.objects.create(display_name="Alias two")
            result = services.export_parties(workspace_id=self.a.pk, actor=self.actor)
            records = [json.loads(line) for line in result.content.splitlines()]
        reference = dict(party_source_system="source-book", party_external_id="customer-7")
        with self.scoped(self.b):
            for index, record in enumerate(records):
                record["source_refs"] = [dict(system="source-book", external_id="customer-7")]
                batch = services.stage_import(workspace_id=self.b.pk, actor=self.actor, content=(dump(record)+"\n").encode(),
                    filename="master.jsonl", source_system=result.namespace)
                batch = services.validate_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id, mapping={})
                if index == 0:
                    self.assertIsNone(children.parent_for(reference, self.b.pk))
                services.commit_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id, approval_digest=batch.approval_digest, acknowledge_warnings=True)
                if index == 0:
                    self.assertIsNotNone(children.parent_for(reference, self.b.pk))
                else:
                    self.assertIsNone(children.parent_for(reference, self.b.pk))
        with self.scoped():
            self.assertIsNone(children.parent_for(reference, self.a.pk))


@override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},
    "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class FinancialExchangeTests(OpeningImportFixture):
    def setUp(self):
        super().setUp()
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.storage = override_settings(MEDIA_ROOT=self.directory / "media")
        self.storage.enable()
        self.addCleanup(self.storage.disable)

    def test_more_than_twenty_closed_positions_and_counter_claims_roundtrip_in_chunks(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021,2,2)):
            document = dict(profile="loan-closed-position/1",
                source=dict(namespace=self.review["source"]["namespace"], system="paper", loan_id=""),
                loan=dict(number="", borrower_reference=dict(system=self.review["mapping"]["borrower_source_system"], id="old-1"),
                    original_date=None, closed_on=None, original_principal=None, monthly_rate=None, tenure_months=None),
                position=dict(state="CLOSED", as_of="2021-02-02", currency="INR", principal="0", interest="0", fees="0",
                    custody="RETURNED_TO_BORROWER", basis="OWNER_CLOSED_POSITION", evidence_reference="Synthetic verified position"), earlier_history="UNAVAILABLE", retained_evidence=None)
            args = dict(workspace_id=self.a.pk, actor=self.actor, borrower_id=self.source_party.identity.party_id, series_id=self.series.pk)
            for i in range(1,26):
                document["source"]["loan_id"] = f"closed-{i}"
                document["loan"]["number"] = f"H-{i:05d}"
                _, token = preview_closed_position(document=document, **args)
                admit_closed_position(document=document, review_token=token, confirmed=True, **args)
            target = self.directory / "exchange"
            target.mkdir()
            doc = exchange.write_exchange(workspace_id=self.a.pk, actor=self.actor, directory=target)
            self.assertEqual(doc["counts"]["loans"], 25)
            self.assertEqual(len(doc["chunks"]), 26)
            self.sequence.refresh_from_db()
            self.assertEqual(self.sequence.next_number, 26)
        with self.scoped(self.b), patch("django.utils.timezone.localdate", return_value=date(2021,2,2)):
            from apps.tenant_apps.loans.services.license_series import create_license
            licence = create_license(workspace=self.b, actor=self.actor, name="Restore", license_number="OLD-L",
                issued_on=date(2020,1,1), expires_on=date(2022,1,1))
            series = loans.LoanSeries.objects.create(license=licence, name="Restore", code="H")
            counter = loans.LoanNumberSequence.objects.create(series=series, document_kind="PAWN_LOAN", prefix="H-", width=5, maximum_number=10000)
            for number in range(1,27):
                batch = exchange.stage_chunk(workspace_id=self.b.pk, actor=self.actor, directory=target, expected_sha256=doc["sha256"], number=number)
                if isinstance(batch, ImportBatch):
                    batch = services.validate_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id, mapping={})
                    services.commit_import(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id, approval_digest=batch.approval_digest, acknowledge_warnings=True)
                    # Financial graphs are independent: all Party dependencies
                    # suffice, without scanning every prior financial receipt.
                    ahead = exchange.stage_chunk(workspace_id=self.b.pk, actor=self.actor, directory=target,
                        expected_sha256=doc["sha256"], number=26)
                    self.assertEqual(ahead.state, "STAGED")
                else:
                    borrower = Party.objects.get()
                    approval = loan_restore.preview(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id,
                        values={"position":dict(borrower_id=borrower.pk, series_id=series.pk)})
                    loan_restore.commit(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id, approval=approval, confirmed=True)
            self.assertEqual(loans.PawnLoan.objects.filter(state="CLOSED").count(), 25)
            self.assertEqual(loans.PawnLoanEvent.objects.count(), 25)
            counter.refresh_from_db()
            self.assertEqual(counter.next_number, 26)
            final = exchange.stage_chunk(workspace_id=self.b.pk, actor=self.actor, directory=target, expected_sha256=doc["sha256"], number=26)
            self.assertEqual(final.state, "COMPLETED")
            self.assertEqual(loans.PawnLoan.objects.count(), 25)

    def test_supported_servicing_graph_and_missing_media_cannot_be_silently_skipped(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021,2,2)):
            origin = self.write()
            target = self.directory / "exchange"
            target.mkdir()
            doc = exchange.write_exchange(workspace_id=self.a.pk, actor=self.actor, directory=target)
            entry = doc["chunks"][-1]
            self.assertEqual(entry["source_loan_ids"], [origin.loan_id])
            self.assertEqual(entry["profile"], "loan-servicing-bundle/1")
            exchange.chunk_bytes(target, entry)
            with TemporaryDirectory() as failed:
                with patch.object(exchange.servicing_bundle, "export_servicing_bundle", side_effect=ValueError("Retained source file missing")):
                    with self.assertRaises(ValueError):
                        exchange.write_exchange(workspace_id=self.a.pk, actor=self.actor, directory=failed)
                    self.assertFalse((Path(failed) / "manifest.json").exists())
