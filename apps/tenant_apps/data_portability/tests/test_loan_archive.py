import copy
import json
import uuid
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import SimpleTestCase

from apps.orgs.models import Membership, WorkspaceRoleGrant
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.archive import accept_evidence, export_evidence, get_evidence
from apps.tenant_apps.loans.services.archive_contract import ArchiveError, encode, parse, review_document, MAX_BYTES, PROFILE
from apps.tenant_apps.loans.services.history_contract import dump, digest
from apps.tenant_apps.loans.services.portability_validation import PortabilityValidationError
from apps.tenant_apps.data_portability import loan_archive
from apps.tenant_apps.data_portability.models import LoanArchiveBatch
from apps.tenant_apps.party.models import Party
from .fixtures import PortabilityFixture


def document():
    return {"profile": PROFILE,
        "source": {"namespace": "491cf2e4-99eb-499c-b555-68f3a8d5caaa", "system": "paper-register-a",
                   "loan_id": "L123", "snapshot_reference": "book-1990-page-12-scan-1",
                   "evidence_reference": "Synthetic source book page; settlement slips unavailable"},
        "facts": {"status": "CLOSED", "loan_number": "L123", "raw_status": "released",
                  "borrower_reference": {"system": "paper-register-a", "id": "missing-customer"},
                  "borrower_name": "Synthetic former borrower", "opened_on": "1990-01-01", "closed_on": None,
                  "original_principal": "1000.00", "reported_balance": None, "collateral": None, "payments": None},
        "source_records": [{"loan": "L123", "status": "released", "old_margin_note": "Weight and receipt book unavailable"}]}


class ArchiveContractTests(SimpleTestCase):
    def test_unknown_old_closed_claim_is_preserved_without_operational_admission(self):
        value = document()
        self.assertEqual(parse(encode(value)), value)
        report = review_document(value)
        self.assertTrue(report["historical_retention_ready"])
        self.assertFalse(report["operational_admission"])
        self.assertIn("UNKNOWN_PAYMENTS", {i["code"] for i in report["findings"]})
        self.assertIn("UNRESOLVED_BORROWER", {i["code"] for i in report["findings"]})

    def test_contradictory_claims_are_visible_and_not_repaired(self):
        value = document()
        value["facts"].update(closed_on="1989-01-01", reported_balance="400",
                             payments=[{"id": "p1", "date": None, "amount": "1"}] * 2)
        before = copy.deepcopy(value)
        self.assertTrue({"DATE_ORDER", "CLOSED_WITH_BALANCE", "DUPLICATE_PAYMENT_CLAIM"} <= {i["code"] for i in review_document(value)["findings"]})
        self.assertEqual(value, before)
        self.assertEqual(parse(encode(value)), before)

    def test_zero_empty_and_unknown_remain_distinct(self):
        value = document()
        value["facts"].update(reported_balance="0", collateral=[], payments=[])
        result = parse(encode(value))
        self.assertEqual(result["facts"]["reported_balance"], "0")
        self.assertEqual(result["facts"]["payments"], [])
        self.assertNotIn("UNKNOWN_PAYMENTS", {i["code"] for i in review_document(value)["findings"]})

    def test_active_malformed_unknown_fields_and_oversized_documents_fail(self):
        for mutate in (lambda d: d["facts"].update(status="ACTIVE"), lambda d: d.update(extra=True),
                       lambda d: d["facts"].update(original_principal=1000),
                       lambda d: d.update(source_records=["bad"]), lambda d: d["source"].update(namespace=str(uuid.UUID(int=0))),
                       lambda d: d["source_records"][0].update(value=1.5), lambda d: d["source_records"][0].update(value="\x00")):
            value = document(); mutate(value)
            with self.assertRaises(PortabilityValidationError):
                parse(dump(value).encode())
        for content in (b'{"profile":1,"profile":2}', b'NaN', b'not json', b' ' * (MAX_BYTES + 1)):
            with self.assertRaises(PortabilityValidationError):
                parse(content)


class LoanArchiveTests(PortabilityFixture):
    def args(self, workspace=None):
        return dict(workspace_id=(workspace or self.a).pk, actor=self.actor)

    def staged(self, value=None, workspace=None):
        return loan_archive.stage(**self.args(workspace), content=encode(value or document()))

    def accept(self, batch, workspace=None):
        _, token = loan_archive.preview(**self.args(workspace), batch_id=batch.public_id)
        return loan_archive.commit(**self.args(workspace), batch_id=batch.public_id, approval=token, confirmed=True)

    def assert_no_operational_rows(self):
        for model in (m.PawnLoan, m.PawnLoanEvent, m.PawnLoanRelease, m.PawnCollateralItem,
                      m.PawnCollateralCustodyEvent, m.RepaymentObligation, m.HistoricalLoanImport, Party):
            self.assertFalse(model.objects.exists(), model.__name__)

    def test_l123_without_payments_creates_only_immutable_evidence_and_retry_reuses_it(self):
        with self.scoped():
            batch = self.staged()
            report, token = loan_archive.preview(**self.args(), batch_id=batch.public_id)
            self.assertFalse(m.HistoricalLoanEvidence.objects.exists())
            self.assert_no_operational_rows()
            self.assertFalse(report["operational_admission"])
            result = self.accept(batch)
            replay = loan_archive.commit(**self.args(), batch_id=batch.public_id, approval=token, confirmed=True)
            duplicate = self.accept(self.staged())
            self.assertEqual((result.pk, result.pk), (replay.pk, duplicate.pk))
            self.assertEqual(result.document, document())
            self.assert_no_operational_rows()

    def test_changed_snapshot_is_an_additional_record_not_an_overwrite(self):
        with self.scoped():
            first = self.accept(self.staged())
            value = document()
            value["source"]["snapshot_reference"] = "scan-2"
            value["facts"].update(closed_on="1980-01-01", reported_balance="200")
            second = self.accept(self.staged(value))
            first.refresh_from_db()
            self.assertEqual(first.document, document())
            self.assertNotEqual(first.pk, second.pk)
            self.assertIn("DATE_ORDER", {i["code"] for i in second.review["findings"]})
            self.assert_no_operational_rows()

    def test_export_and_accept_in_another_workspace_preserve_source_document(self):
        with self.scoped():
            result = self.accept(self.staged())
            content = export_evidence(**self.args(), evidence_id=result.public_id)
        with self.scoped(self.b):
            restored = self.accept(self.staged(parse(content), self.b), self.b)
            self.assertEqual(export_evidence(**self.args(self.b), evidence_id=restored.public_id), content)
            self.assertEqual(restored.document, result.document)
            self.assertNotEqual(restored.pk, result.pk)
            self.assert_no_operational_rows()

    def test_cancel_clears_only_staging_and_cannot_erase_accepted_evidence(self):
        with self.scoped():
            accepted_batch = self.staged()
            result = self.accept(accepted_batch)
            staged = self.staged()
            loan_archive.cancel(**self.args(), batch_id=staged.public_id, confirmed=True)
            staged.refresh_from_db()
            self.assertEqual(staged.document, {})
            self.assertEqual(staged.state, "CANCELLED")
            with self.assertRaises(ArchiveError):
                loan_archive.cancel(**self.args(), batch_id=accepted_batch.public_id, confirmed=True)
            result.refresh_from_db()
            self.assertEqual(result.document, document())

    def test_confirmation_expiry_wrong_batch_and_revoked_grants_block_replay(self):
        with self.scoped():
            batch = self.staged()
            _, token = loan_archive.preview(**self.args(), batch_id=batch.public_id)
            with self.assertRaises(ArchiveError):
                loan_archive.commit(**self.args(), batch_id=batch.public_id, approval=token)
            other = self.staged()
            with self.assertRaises(PermissionDenied):
                loan_archive.commit(**self.args(), batch_id=other.public_id, approval=token, confirmed=True)
            with patch("django.core.signing.TimestampSigner.unsign", side_effect=signing.SignatureExpired), self.assertRaises(ArchiveError):
                loan_archive.commit(**self.args(), batch_id=batch.public_id, approval=token, confirmed=True)
            stale = signing.loads(token, salt=loan_archive.SALT)
            stale["review_sha256"] = "0" * 64
            with self.assertRaises(ArchiveError):
                loan_archive.commit(**self.args(), batch_id=batch.public_id,
                    approval=signing.dumps(stale, salt=loan_archive.SALT), confirmed=True)
            self.accept(batch)
            membership = Membership.objects.get(company=self.a, user=self.actor)
            for code in ("data_import", "workspace_settings", "data_view"):
                with transaction.atomic():
                    deleted, _ = WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id, permission__codename=code).delete()
                    self.assertGreater(deleted, 0)
                    with self.assertRaises(PermissionDenied):
                        loan_archive.commit(**self.args(), batch_id=batch.public_id, approval=token, confirmed=True)
                    transaction.set_rollback(True)

    def test_reader_with_export_grant_does_not_need_import_or_setup_grants(self):
        with self.scoped():
            result = self.accept(self.staged())
            membership = Membership.objects.get(company=self.a, user=self.actor)
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id,
                permission__codename__in=["data_import", "workspace_settings"]).delete()
            self.assertEqual(parse(export_evidence(**self.args(), evidence_id=result.public_id)), document())
            with self.assertRaises(PermissionDenied):
                self.staged()
            WorkspaceRoleGrant.objects.filter(workspace_id=self.a.pk, workspace_role__role_id=membership.role_id, permission__codename="data_export").delete()
            with self.assertRaises(PermissionDenied):
                export_evidence(**self.args(), evidence_id=result.public_id)

    def test_failure_after_acceptance_rolls_back_evidence_and_batch(self):
        with self.scoped():
            batch = self.staged()
            _, token = loan_archive.preview(**self.args(), batch_id=batch.public_id)
            with patch.object(LoanArchiveBatch, "save", side_effect=RuntimeError("late failure")), self.assertRaises(RuntimeError):
                loan_archive.commit(**self.args(), batch_id=batch.public_id, approval=token, confirmed=True)
            self.assertFalse(m.HistoricalLoanEvidence.objects.exists())
            batch.refresh_from_db()
            self.assertEqual(batch.state, "STAGED")

    def test_restricted_sql_cannot_mutate_delete_or_misbind_source(self):
        with self.scoped():
            batch = self.staged()
            result = self.accept(batch)
            for model, pk in ((m.HistoricalLoanEvidence, result.pk), (LoanArchiveBatch, batch.pk)):
                table = model._meta.db_table
                for sql in (f'UPDATE "{table}" SET document=\'{{}}\'::jsonb WHERE id=%s', f'DELETE FROM "{table}" WHERE id=%s'):
                    with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                        cursor.execute(sql, [pk])
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.HistoricalLoanEvidence.objects.create(workspace_id=self.a.pk, source_namespace=uuid.uuid4(),
                    source_system="wrong", source_id="wrong", source_sha256=digest(document()),
                    document=document(), review=review_document(document()), accepted_by=self.actor)
            fresh = self.staged()
            wrong = document(); wrong["source"]["loan_id"] = "L999"
            wrong_result = self.accept(self.staged(wrong))
            with self.assertRaises(DatabaseError), transaction.atomic():
                LoanArchiveBatch.objects.filter(pk=fresh.pk).update(state="COMPLETED", result=wrong_result)

    def test_cross_workspace_reads_writes_and_result_references_are_denied(self):
        with self.scoped():
            result = self.accept(self.staged())
        with self.scoped(self.b):
            self.assertFalse(m.HistoricalLoanEvidence.objects.filter(pk=result.pk).exists())
            with self.assertRaises(PermissionDenied):
                get_evidence(**self.args(self.b), evidence_id=result.public_id)
            with self.assertRaises(PermissionDenied):
                get_evidence(**self.args(), evidence_id=result.public_id)
            cross = document(); cross["source"]["loan_id"] = "cross"
            with self.assertRaisesRegex(DatabaseError, "row-level security"), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute('INSERT INTO loans_historicalloanevidence (public_id,workspace_id,source_namespace,source_system,source_id,source_sha256,document,review,accepted_by_id,accepted_at) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,now())',
                    [str(uuid.uuid4()), self.a.pk, str(result.source_namespace), result.source_system, "cross", digest(cross), dump(cross), dump(review_document(cross)), self.actor.pk])
            fresh = self.staged(workspace=self.b)
            with self.assertRaises(DatabaseError), transaction.atomic():
                LoanArchiveBatch.objects.filter(pk=fresh.pk).update(state="COMPLETED", result_id=result.pk)

    def test_nonmember_missing_context_and_inactive_workspace_are_denied(self):
        with self.assertRaises(PermissionDenied):
            loan_archive.stage(**self.args(), content=encode(document()))
        with self.scoped():
            with self.assertRaises(PermissionDenied):
                loan_archive.stage(workspace_id=self.a.pk, actor=self.other_actor, content=encode(document()))
            self.a.lifecycle_state = "ARCHIVED"
            self.a.save(update_fields=["lifecycle_state"])
            with self.assertRaises(PermissionDenied):
                self.staged()

    def test_http_upload_review_accept_browse_export_and_csrf(self):
        from types import SimpleNamespace
        from django.test import Client, override_settings
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.tenancy import testing
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        with override_settings(ALLOWED_HOSTS=["testserver"], STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
            client = Client(enforce_csrf_checks=True); client.force_login(self.actor)
            url = reverse("workspace_portability:archive_upload", kwargs={"workspace_slug": self.a.slug})
            page = client.get(url); self.assertContains(page, "Upload historical evidence")
            self.assertIn("no-store", page["Cache-Control"])
            self.assertEqual(client.post(url, {}).status_code, 403)
            csrf = {"csrfmiddlewaretoken": client.cookies["csrftoken"].value}
            value = document(); value["source_records"][0]["note"] = "<script>alert(1)</script>"
            response = client.post(url, {**csrf, "source": SimpleUploadedFile("old.json", encode(value))})
            self.assertEqual(response.status_code, 302)
            review_url = response.url
            review = client.get(review_url)
            self.assertContains(review, "Payments is unknown")
            self.assertNotContains(review, "<script>alert(1)</script>")
            self.assertContains(review, "&lt;script&gt;")
            token = review.context["approval"]
            self.assertContains(client.post(review_url, {**csrf, "action": "accept", "approval": token}), "Confirm retention")
            accepted = client.post(review_url, {**csrf, "action": "accept", "approval": token, "confirmed": "yes"})
            self.assertEqual(accepted.status_code, 302)
            page = client.get(accepted.url); self.assertContains(page, "Accepted historical evidence")
            with self.scoped():
                result = m.HistoricalLoanEvidence.objects.get()
                self.assert_no_operational_rows()
            export_url = reverse("workspace_portability:archive_export", kwargs={"workspace_slug": self.a.slug, "evidence_id": result.public_id})
            self.assertEqual(client.get(export_url).status_code, 405)
            self.assertEqual(parse(client.post(export_url, csrf).content), value)
            listing = reverse("workspace_portability:archive_list", kwargs={"workspace_slug": self.a.slug})
            self.assertContains(client.get(listing, {"q": "L123"}), "L123")
