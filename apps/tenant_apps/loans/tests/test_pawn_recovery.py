import hashlib
import json
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED
from django.db import connection, transaction, DatabaseError
from django.test import override_settings
from django.urls import reverse
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import pawn_recovery as recovery
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from . import test_recorded_origination as origins, test_recorded_history as histories
from . import test_independent_paper as paper


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PawnRecoveryTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit
    renewal_data = paper.IndependentPaperTests.renewal_data

    @classmethod
    def get_test_schema_name(cls):
        return "pawn-recovery"

    def setUp(self):
        self.prepare_history()

    def export(self):
        self.content = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        self.sha = hashlib.sha256(self.content).hexdigest()
        return recovery._read(self.content, self.sha)[0]

    def restore(self, **changes):
        args = dict(workspace=self.tenant, actor=self.actor, content=self.content, expected_sha256=self.sha)
        args.update(changes)
        return recovery.restore_archive(**args)

    def empty(self):
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        connection.check_constraints()
        with connection.cursor() as cursor:
            for model in recovery._models():
                cursor.execute(f'ALTER TABLE "{model._meta.db_table}" DISABLE TRIGGER USER')
            for model in reversed(recovery._models()):
                cursor.execute(f'DELETE FROM "{model._meta.db_table}" WHERE workspace_id=%s', [self.tenant.pk])
            connection.check_constraints()
            for model in recovery._models():
                cursor.execute(f'ALTER TABLE "{model._meta.db_table}" ENABLE TRIGGER USER')

    def change_manifest(self, change):
        manifest, files = recovery._read(self.content, self.sha)
        change(manifest)
        stream = BytesIO()
        with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            for name, data in files.items():
                archive.writestr("media/" + name, data)
        self.content = stream.getvalue()
        self.sha = hashlib.sha256(self.content).hexdigest()

    def test_recorded_receipts_correction_coverage_and_exact_rows_round_trip(self):
        self.data["events"] = [self.row(amount="2000")]
        loan, _, _ = self.admit()
        from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction, record_contract_correction
        data = dict(date=self.day.isoformat(), principal="12000", rate="3", cash_paid="12000",
            reference="Checked original book", reason="Original principal corrected", request_key=uuid4().hex)
        _, token = preview_contract_correction(loan.pk, actor=self.actor, data=data)
        record_contract_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        original = self.export()
        self.assertEqual(original["reconciliation"][-1]["coverage"]["status"], "CHANGED")
        self.empty()
        self.assertFalse(self.restore()["committed"])
        self.assertFalse(m.PawnLoan.objects.filter(workspace=self.tenant).exists())
        self.assertTrue(self.restore(commit=True)["committed"])
        new = self.export()
        for key in ("tables", "files", "reconciliation", "prerequisites", "schema", "guards_sha256"):
            self.assertEqual(original[key], new[key], key)
        loan.refresh_from_db()
        self.assertEqual(collection_balance(loan, self.today).total_due, 10360)
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.PawnLoanEvent.objects.filter(loan=loan).delete()

    def test_paired_renewal_and_dated_custody_restatement_round_trip(self):
        loan, _, _ = self.admit()
        from apps.tenant_apps.loans.services.recorded_renewal_actions import preview_existing_paper_renewal, record_existing_paper_renewal
        facts = self.renewal_data()
        _, token = preview_existing_paper_renewal(loan_id=loan.pk, actor=self.actor, data=facts)
        successor, _ = record_existing_paper_renewal(loan_id=loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        renewal = successor.origin_renewal
        from datetime import timedelta
        from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction, record_contract_correction
        data = dict(date=(self.day+timedelta(days=3)).isoformat(), principal="12000", rate="2", cash_paid="11750",
            reference="Correct dated agreement", reason="Renewal date transcribed incorrectly", request_key=uuid4().hex,
            predecessor=dict(cash_received="0", cash_paid="1550", interest_offset="200", reference="Checked old settlement", confirmed_custody=True))
        _, token = preview_contract_correction(successor.pk, actor=self.actor, data=data)
        record_contract_correction(successor.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        original = self.export()
        self.empty()
        self.restore(commit=True)
        self.assertEqual(original["tables"], self.export()["tables"])
        restored = m.PawnLoanRenewal.objects.get(pk=renewal.pk)
        self.assertEqual(restored.source_loan_id, loan.pk)
        self.assertEqual(restored.successor_loan.collateral_items.get().renewed_from_id, loan.collateral_items.get().pk)
        self.assertEqual(collection_balance(restored.successor_loan, self.today).total_due, 12000)
        self.assertTrue(m.PawnCollateralCustodyEvent.objects.filter(restatement_of__isnull=False).exists())

    def test_closed_handover_and_preserved_pdf_bytes_round_trip(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="", closure_basis="PAPER_SETTLEMENT")])
        loan, _, _ = self.admit()
        from apps.tenant_apps.loans.services.paper_handover import preview_paper_handover, confirm_paper_handover
        facts = dict(date=self.today.isoformat(), recipient="Borrower", reference="Signed closing page", request_key=uuid4().hex)
        _, token = preview_paper_handover(loan.pk, actor=self.actor, data=facts)
        confirm_paper_handover(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        from apps.tenant_apps.loans.services.document_issuance import issue_recorded_document
        issue, _ = issue_recorded_document(workspace=self.tenant, loan=loan, actor=self.actor)
        with issue.artifact.open("rb") as stream:
            before = stream.read()
        original = self.export()
        self.empty()
        self.restore(commit=True)
        restored = m.LoanDocumentIssue.objects.get(pk=issue.pk)
        with restored.artifact.open("rb") as stream:
            self.assertEqual(before, stream.read())
        self.assertEqual(original["reconciliation"], self.export()["reconciliation"])

    def test_existing_identity_checksum_schema_and_reconciliation_refuse_overwrite(self):
        self.admit()
        self.export()
        with self.assertRaisesMessage(ValueError, "already contains"):
            self.restore(commit=True)
        with self.assertRaisesMessage(ValueError, "checksum"):
            self.restore(expected_sha256="0" * 64)
        self.empty()
        self.change_manifest(lambda doc: doc["reconciliation"][-1].update(principal="1"))
        with self.assertRaisesMessage(ValueError, "differs from the backup"):
            self.restore(commit=True)
        self.assertFalse(m.PawnLoan.objects.filter(workspace=self.tenant).exists())
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_trigger WHERE tgrelid='loans_pawnloanevent'::regclass AND tgenabled <> 'O'")
            self.assertEqual(cursor.fetchone()[0], 0)

    def test_restricted_runtime_exports_but_cannot_restore(self):
        self.admit()
        role = "pawn_recovery_test_" + uuid4().hex[:12]
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{role}"')
            cursor.execute(f'SET LOCAL ROLE "{role}"')
        try:
            self.export()
            with self.assertRaisesMessage(ValueError, "table-owner"):
                self.restore()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

    def test_missing_external_identity_and_foreign_ownership_refuse_restore(self):
        loan, _, _ = self.admit()
        self.export()
        self.empty()
        self.change_manifest(lambda doc: doc["prerequisites"][0].update(sha256="0" * 64))
        with self.assertRaisesMessage(ValueError, "identity differs"):
            self.restore(commit=True)
        self.assertFalse(m.PawnLoan.objects.filter(workspace=self.tenant).exists())

    def test_new_media_is_removed_on_failed_restore_and_old_media_never_overwritten(self):
        loan, _, _ = self.admit()
        from apps.tenant_apps.loans.services.document_issuance import issue_recorded_document
        issue, _ = issue_recorded_document(workspace=self.tenant, loan=loan, actor=self.actor)
        self.export()
        self.empty()
        issue.artifact.storage.delete(issue.artifact.name)
        self.change_manifest(lambda doc: doc["reconciliation"][-1].update(agreed_total="1"))
        with self.assertRaisesMessage(ValueError, "differs from the backup"):
            self.restore(commit=True)
        self.assertFalse(issue.artifact.storage.exists(issue.artifact.name))
        from django.core.files.base import ContentFile
        issue.artifact.storage.save(issue.artifact.name, ContentFile(b"other retained file"))
        with self.assertRaisesMessage(ValueError, "media conflicts"):
            self.restore(commit=True)
        with issue.artifact.storage.open(issue.artifact.name, "rb") as stream:
            self.assertEqual(stream.read(), b"other retained file")

    def test_ordinary_download_is_read_only_and_checksum_filename_matches_bytes(self):
        self.start_active_trial()
        self.admit()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        path = reverse("workspace_loans:pawn_recovery_backup", args=[self.tenant.slug])
        before = m.PawnLoanEvent.objects.count()
        page = client.get(path)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Loans recovery backup")
        import os
        from pathlib import Path
        if os.environ.get("PAPER_QA_CAPTURE"):
            Path(os.environ["PAPER_QA_CAPTURE"], "recovery-backup.html").write_bytes(page.content)
        response = client.post(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        checksum = hashlib.sha256(response.content).hexdigest()
        self.assertEqual(response["X-Rokkad-Archive-SHA256"], checksum)
        self.assertIn(checksum, response["Content-Disposition"])
        self.assertEqual(m.PawnLoanEvent.objects.count(), before)
        recovery._read(response.content, checksum)
