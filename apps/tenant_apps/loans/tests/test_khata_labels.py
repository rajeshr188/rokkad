import copy
import hashlib
import uuid
from unittest.mock import patch

import fitz
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.http import Http404
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataDocumentIssue
from apps.tenant_apps.loans.services import khata_labels as labels, khata_documents as documents, khata_recovery as recovery
from apps.tenant_apps.loans.services.khata_readiness import assess_readiness
from apps.tenant_apps.loans.web import khata_labels as views, khata_views
from .test_khata_corrections import CorrectionFixture
from . import test_khata_foundation as foundation, test_khata_opening as opening_tests


@override_settings(STORAGES=opening_tests.STORAGES)
class KhataLabelTests(CorrectionFixture, TestCase):
    def issue(self, **changes):
        args = dict(self.args(), request_key=uuid.uuid4(), origin="https://rokkad.example", mode="ONE", item_id=self.first.pk)
        args.update(changes)
        return labels.issue_labels(**args)

    def request(self, data=None, method="get", actor=None):
        request = getattr(RequestFactory(), method)("/", data or {})
        request.workspace = self.workspace
        request.user = actor or self.actor
        return request

    def content(self, issue):
        return documents.document_bytes(**self.args(), issue_id=issue.pk)[1]

    def test_individual_pdf_size_full_identity_and_no_financial_custody_changes(self):
        with workspace_context(self.workspace.pk):
            original_ops = list(self.account.operations.values())
        issue = self.issue()
        content = self.content(issue)
        self.assertEqual(issue.kind, "LABEL")
        with fitz.open(stream=content, filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 1)
            self.assertAlmostEqual(pdf[0].rect.width, 100 * 72 / 25.4, places=3)
            self.assertAlmostEqual(pdf[0].rect.height, 60 * 72 / 25.4, places=3)
            text = pdf[0].get_text()
            for value in (self.account.account_number, self.first.description, str(self.first.public_id), "100.000", "Held"):
                self.assertIn("".join(value.split()), "".join(text.split()))
        with workspace_context(self.workspace.pk):
            self.assertEqual(original_ops, list(self.account.operations.values()))
        self.assertIn(str(self.first.public_id), issue.payload["items"][0]["scan_path"])

    def test_all_held_combined_and_each_item_pages(self):
        extra = self.replacement("20", description="Gold chain", storage_reference="B2")
        combined = self.issue(mode="ALL", item_id=None)
        individual = self.issue(mode="EACH", item_id=None)
        self.assertEqual({row["id"] for row in combined.payload["items"]}, {self.first.pk, extra.pk})
        with fitz.open(stream=self.content(combined), filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 1)
            self.assertIn("120.000", pdf[0].get_text())
        with fitz.open(stream=self.content(individual), filetype="pdf") as pdf:
            self.assertEqual(len(pdf), 2)
            for page in pdf:
                self.assertAlmostEqual(page.rect.width, 100 * 72 / 25.4, places=3)

    def test_pending_return_is_visible_new_label_after_return_refused_exact_reprint_preserved(self):
        old = self.issue()
        original = self.content(old)
        replacement = self.replacement("100")
        exchange = self.exchange([self.first], [replacement])
        pending = self.issue()
        self.assertEqual(pending.payload["items"][0]["custody"], "Return pending")
        self.handover(self.first, exchange)
        with self.assertRaisesMessage(ValueError, "matching held collateral"):
            self.issue()
        self.assertEqual(original, self.content(old))

    def test_idempotent_retry_uses_saved_bytes_after_custody_changes(self):
        key = uuid.uuid4()
        issue = self.issue(request_key=key)
        self.deposit(description="Later collateral")
        self.assertEqual(self.issue(request_key=key).pk, issue.pk)
        with self.assertRaisesMessage(ValueError, "different instructions"):
            self.issue(request_key=key, mode="ALL", item_id=None)

    def test_oversized_combined_label_refuses_without_saving_partial_pdf(self):
        for index in range(5):
            self.replacement("20", description=("Long collateral description " * 15) + str(index))
        with self.assertRaisesMessage(ValueError, "no text was omitted"):
            self.issue(mode="ALL", item_id=None)
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataDocumentIssue.objects.exists())
        with self.assertRaisesMessage(ValueError, "valid application origin"):
            self.issue(origin="https://user:password@elsewhere.example/path")

    def test_scan_authentication_scope_and_collateral_tab(self):
        with workspace_context(self.workspace.pk):
            response = views.item_scan(self.request(), self.first.public_id)
            self.assertIn(f"?section=collateral&item={self.first.public_id}#collateral-item-", response["Location"])
            self.assertIn("no-store", response["Cache-Control"])
            response = views.account_scan(self.request(), self.account.public_id)
            self.assertIn(str(self.account.pk), response["Location"])
            response = khata_views.detail(self.request(dict(section="collateral")), self.account.pk)
            self.assertContains(response, 'id="khata-panel-collateral"')
            self.assertContains(response, f'id="collateral-item-{self.first.public_id}"')
            with self.assertRaises(Http404):
                views.item_scan(self.request(), uuid.uuid4())
        workspace, actor, _ = foundation.fixture(uuid.uuid4().hex[:8])
        request = self.request(actor=actor)
        request.workspace = workspace
        with workspace_context(workspace.pk), self.assertRaises(Http404):
            views.item_scan(request, self.first.public_id)
        anonymous = self.request()
        from django.contrib.auth.models import AnonymousUser
        anonymous.user = AnonymousUser()
        self.assertEqual(views.item_scan(anonymous, self.first.public_id).status_code, 302)

    def test_label_get_is_read_only_post_private_and_permission_checked(self):
        with workspace_context(self.workspace.pk):
            self.assertEqual(views.labels(self.request(), self.account.pk).status_code, 200)
            self.assertFalse(KhataDocumentIssue.objects.exists())
            response = views.labels(self.request(dict(mode="ONE", item=self.first.pk, request_key=uuid.uuid4()), "post"), self.account.pk)
            self.assertEqual(response.status_code, 302)
            issue = KhataDocumentIssue.objects.get()
            response = khata_views.download(self.request(), self.account.pk, issue.pk)
            self.assertIn("private", response["Cache-Control"])
        viewer = self.staff()
        with workspace_context(self.workspace.pk), self.assertRaises(PermissionDenied):
            views.labels(self.request(actor=viewer), self.account.pk)

    def test_label_archive_exact_recovery_and_source_guard_fingerprint(self):
        issue = self.issue()
        content = recovery.export_archive(workspace=self.workspace, actor=self.actor)
        manifest, files = recovery._read(content, hashlib.sha256(content).hexdigest())
        self.assertEqual(manifest["tables"]["loans.KhataDocumentIssue"][0]["kind"], "LABEL")
        self.assertEqual(files[issue.artifact.name], self.content(issue))
        from .test_khata_recovery import KhataRecoveryTests
        KhataRecoveryTests.empty_test_destination(self)
        result = recovery.restore_archive(workspace=self.workspace, actor=self.actor, content=content,
            expected_sha256=hashlib.sha256(content).hexdigest(), commit=True)
        self.assertTrue(result["committed"])
        self.assertEqual(files[issue.artifact.name], self.content(issue))

    def test_labels_available_for_received_draft_collateral_without_claiming_approved_terms(self):
        from apps.tenant_apps.loans.services.khata_accounts import create_draft
        self.account = create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.first = self.deposit()
        issue = self.issue()
        self.assertNotIn("agreement", issue.payload)
        self.assertNotIn("principal", issue.payload)
        self.assertEqual(issue.payload["source_sequence"], 1)
        self.assertEqual(self.account.state, "DRAFT")

    def test_readiness_is_read_only_and_owner_connection_does_not_pass_runtime_gate(self):
        with workspace_context(self.workspace.pk):
            before = list(self.account.operations.values())
            report = assess_readiness(workspace=self.workspace, actor=self.actor)
            checks = {row["code"]: row["passed"] for row in report["checks"]}
            self.assertFalse(checks["RUNTIME_ROLE"])
            self.assertTrue(checks["NATIVE_EVIDENCE"])
            self.assertFalse(report["pilot_authorized"])
            self.assertEqual(before, list(self.account.operations.values()))
            self.assertFalse(KhataDocumentIssue.objects.exists())
            self.assertContains(views.readiness(self.request()), "does not activate a pilot")

    def test_readiness_refuses_missing_label_guard_even_when_other_guards_remain(self):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER khata_label_guard ON loans_khatadocumentissue")
            report = assess_readiness(workspace=self.workspace, actor=self.actor)
            self.assertFalse(next(row["passed"] for row in report["checks"] if row["code"] == "GUARDS"))
            transaction.set_rollback(True)


@override_settings(STORAGES=opening_tests.STORAGES)
class KhataLabelRLSTests(CorrectionFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.runtime_role = "khata_label_" + uuid.uuid4().hex
        quoted = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}")

    runtime = foundation.KhataRLSBoundaryTests.runtime

    def test_runtime_label_guards_scope_identity_and_immutability(self):
        with self.runtime():
            issue = labels.issue_labels(**self.args(), request_key=uuid.uuid4(), origin="https://rokkad.example", mode="ONE", item_id=self.first.pk)
            with workspace_context(self.workspace.pk):
                for change in ("identity", "description", "scan", "custody", "duplicate"):
                    forged = copy.copy(issue)
                    forged.pk = None
                    forged.request_key = uuid.uuid4()
                    forged.payload = copy.deepcopy(issue.payload)
                    row = forged.payload["items"][0]
                    if change == "identity": row["public_id"] = str(uuid.uuid4())
                    if change == "description": row["description"] = "Incorrect identity"
                    if change == "scan": row["scan_path"] = "/loans/other/"
                    if change == "custody": row["custody"] = "Returned"
                    if change == "duplicate": forged.payload["items"].append(copy.deepcopy(row))
                    forged.artifact.name = f"loans/khata/{self.workspace.pk}/documents/{self.account.pk}/{forged.request_key}.pdf"
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        KhataDocumentIssue.objects.bulk_create([forged])
                for mutate in (lambda: KhataDocumentIssue.objects.update(payload={}), lambda: KhataDocumentIssue.objects.all().delete()):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        mutate()
                report = assess_readiness(workspace=self.workspace, actor=self.actor)
                self.assertTrue(report["software_ready"], report)
                self.assertFalse(report["pilot_authorized"])
