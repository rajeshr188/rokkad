"""Bounded label selection preserves immutable custody identities and exact retries."""
import copy
import hashlib
import uuid
from unittest.mock import patch

import fitz
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataDocumentIssue
from apps.tenant_apps.loans.services import khata_labels as labels, khata_accounts, khata_recovery as recovery
from apps.tenant_apps.loans.documents import khata_labels as renderer
from apps.tenant_apps.loans.web import khata_labels as views
from .test_khata_corrections import CorrectionFixture
from . import test_khata_labels as label_tests
from .test_khata_foundation import draft_args
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataLabelBatchTests(CorrectionFixture, TestCase):
    request = label_tests.KhataLabelTests.request
    content = label_tests.KhataLabelTests.content

    def issue(self, ids, **changes):
        args = dict(self.args(), request_key=uuid.uuid4(), origin="https://rokkad.example", mode="SELECTED", item_ids=ids)
        args.update(changes)
        return labels.issue_labels(**args)

    def test_account_above_100_has_complete_bounded_chunks_in_item_order(self):
        items = [self.first, *(self.deposit(description=f"Batch item {n}") for n in range(101))]
        ids = [item.pk for item in items]
        with workspace_context(self.workspace.pk):
            before = list(self.account.operations.values())
            page1 = views.labels(self.request(), self.account.pk)
            page2 = views.labels(self.request(dict(page=2)), self.account.pk)
            self.assertContains(page1, 'data-label-item', count=100)
            self.assertContains(page2, 'data-label-item', count=2)
            self.assertContains(page2, "Batch 2 of 2")
        issues = [self.issue(ids[:100][::-1]), self.issue(ids[100:])]
        self.assertEqual([row["id"] for issue in issues for row in issue.payload["items"]], ids)
        for issue, group in zip(issues, (items[:100], items[100:])):
            with fitz.open(stream=self.content(issue), filetype="pdf") as pdf:
                self.assertEqual(len(pdf), len(group))
                for page, item in zip(pdf, group):
                    self.assertAlmostEqual(page.rect.width, 100 * 72 / 25.4, places=3)
                    self.assertAlmostEqual(page.rect.height, 60 * 72 / 25.4, places=3)
                    self.assertIn(str(item.public_id), "".join(page.get_text().split()))
                    spans = [s for b in page.get_text("dict")["blocks"] if "lines" in b for l in b["lines"] for s in l["spans"]]
                    self.assertTrue(all(s["size"] >= 6 for s in spans))
        with self.assertRaisesMessage(ValueError, "selected-item batches"):
            labels.issue_labels(**self.args(), request_key=uuid.uuid4(), origin="https://rokkad.example", mode="EACH")
        with workspace_context(self.workspace.pk):
            self.assertEqual(before, list(self.account.operations.values()))

    def test_selected_retry_is_set_stable_and_original_pdf_survives_handover(self):
        incoming = self.replacement()
        exchange = self.exchange([self.first], [incoming])
        ids = [incoming.pk, self.first.pk]
        key = uuid.uuid4()
        issue = self.issue(ids, request_key=key, origin="http://testserver")
        content = self.content(issue)
        self.assertEqual(issue.payload["items"][0]["custody"], "Return pending")
        self.handover(self.first, exchange)
        self.deposit(description="Later item is not added to saved batch")
        self.assertEqual(self.issue(ids[::-1], request_key=key, origin="http://testserver").pk, issue.pk)
        self.assertEqual(self.content(issue), content)
        with self.assertRaisesMessage(ValueError, "different instructions"):
            self.issue([incoming.pk], request_key=key, origin="http://testserver")
        with self.assertRaisesMessage(ValueError, "still be physically held"):
            self.issue(ids)
        with workspace_context(self.workspace.pk):
            response = views.labels(self.request(dict(mode="SELECTED", items=ids, request_key=key), "post"), self.account.pk)
            self.assertEqual(response.status_code, 302)

    def test_empty_duplicate_non_integer_and_above_bound_fail_before_rendering(self):
        for ids in ([], [self.first.pk] * 2, [str(self.first.pk)], [True], [-1], list(range(1, 102))):
            with patch.object(labels, "render_labels", side_effect=AssertionError("Must not render")), self.assertRaises(ValueError):
                self.issue(ids)
        with self.assertRaisesMessage(ValueError, "selected-item layout"):
            self.issue([self.first.pk], mode="EACH")
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataDocumentIssue.objects.exists())

    def test_other_account_and_unknown_item_never_create_partial_batch(self):
        other = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        for account_id, ids in ((other.pk, [self.first.pk]), (self.account.pk, [self.first.pk, 999999999])):
            with self.assertRaisesMessage(ValueError, "belong to this account"):
                self.issue(ids, account_id=account_id)
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataDocumentIssue.objects.exists())

    def test_search_matches_unique_identity_description_and_store_without_issuing(self):
        extra = self.deposit(description="Distinct bangle", storage_reference="Drawer B")
        with workspace_context(self.workspace.pk):
            for query in (str(extra.pk), str(extra.public_id), "Distinct bangle", "Drawer B"):
                response = views.labels(self.request(dict(q=query)), self.account.pk)
                self.assertContains(response, 'data-label-item', count=1)
                self.assertContains(response, f'id="label-item-{extra.pk}"')
            self.assertFalse(KhataDocumentIssue.objects.exists())

    def test_no_script_print_displayed_batch_uses_submitted_membership(self):
        extra = self.deposit()
        later = self.deposit()
        data = dict(mode="ALL", print_page="1", request_key=str(uuid.uuid4()),
            page_items=[str(extra.pk), str(self.first.pk)])
        with workspace_context(self.workspace.pk):
            response = views.labels(self.request(data, "post"), self.account.pk)
            self.assertEqual(response.status_code, 302)
            issue = KhataDocumentIssue.objects.get()
            self.assertEqual(issue.payload["mode"], "SELECTED")
            self.assertEqual([row["id"] for row in issue.payload["items"]], [self.first.pk, extra.pk])
            self.assertNotIn(later.pk, [row["id"] for row in issue.payload["items"]])

    def test_failed_render_saves_no_partial_issue_and_old_request_hash_is_unchanged(self):
        extra = self.deposit()
        with workspace_context(self.workspace.pk):
            payload = labels.label_payload(self.account, origin="https://rokkad.example", mode="SELECTED", item_ids=[self.first.pk])
            first_page = renderer.render_labels(payload)
        with patch.object(renderer, "_page", side_effect=[first_page, ValueError("no text was omitted")]), self.assertRaisesMessage(ValueError, "no text was omitted"):
            self.issue([self.first.pk, extra.pk])
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataDocumentIssue.objects.exists())
        key = uuid.uuid4()
        legacy = labels.issue_labels(**self.args(), request_key=key, origin="https://rokkad.example", mode="ONE", item_id=self.first.pk)
        self.assertEqual(legacy.request_sha256, khata_accounts._hash(dict(kind="KHATA_LABEL", account=self.account.pk,
            actor=self.actor.pk, mode="ONE", item=self.first.pk, origin="https://rokkad.example")))

    def test_selected_batch_native_archive_round_trip_keeps_exact_membership_and_bytes(self):
        extra = self.deposit()
        issue = self.issue([extra.pk, self.first.pk])
        original = self.content(issue)
        payload = copy.deepcopy(issue.payload)
        archive = recovery.export_archive(workspace=self.workspace, actor=self.actor)
        from .test_khata_recovery import KhataRecoveryTests
        KhataRecoveryTests.empty_test_destination(self)
        result = recovery.restore_archive(workspace=self.workspace, actor=self.actor, content=archive,
            expected_sha256=hashlib.sha256(archive).hexdigest(), commit=True)
        self.assertTrue(result["committed"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(KhataDocumentIssue.objects.get(pk=issue.pk).payload, payload)
        self.assertEqual(self.content(issue), original)


@override_settings(STORAGES=STORAGES)
class KhataLabelBatchRLSTests(CorrectionFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.runtime_role = "khata_batch_" + uuid.uuid4().hex
        quoted = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}")

    runtime = label_tests.KhataLabelRLSTests.runtime

    def test_restricted_guard_rejects_unordered_or_all_mode_subset_and_stale_items(self):
        extra = self.deposit()
        self.deposit(description="Excluded third item")
        with self.runtime():
            issue = labels.issue_labels(**self.args(), request_key=uuid.uuid4(), origin="https://rokkad.example",
                mode="SELECTED", item_ids=[self.first.pk, extra.pk])
            with workspace_context(self.workspace.pk):
                for change in ("order", "EACH", "ALL", "unknown"):
                    forged = copy.copy(issue)
                    forged.pk = None
                    forged.request_key = uuid.uuid4()
                    forged.payload = copy.deepcopy(issue.payload)
                    if change == "order": forged.payload["items"].reverse()
                    elif change == "unknown": forged.payload["items"][0]["id"] = 999999999
                    else: forged.payload["mode"] = change
                    forged.artifact.name = f"loans/khata/{self.workspace.pk}/documents/{self.account.pk}/{forged.request_key}.pdf"
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        KhataDocumentIssue.objects.bulk_create([forged])
            replacement = self.replacement()
            exchange = self.exchange([self.first], [replacement])
            self.handover(self.first, exchange)
            with workspace_context(self.workspace.pk):
                forged = copy.copy(issue)
                forged.pk = None
                forged.request_key = uuid.uuid4()
                forged.payload = copy.deepcopy(issue.payload)
                forged.source_sequence = self.account.operations.order_by("-sequence").first().sequence
                forged.payload["source_sequence"] = forged.source_sequence
                forged.artifact.name = f"loans/khata/{self.workspace.pk}/documents/{self.account.pk}/{forged.request_key}.pdf"
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataDocumentIssue.objects.bulk_create([forged])
