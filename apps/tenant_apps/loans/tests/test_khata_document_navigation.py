"""Saved-document browsing and contextual navigation preserve source authority."""
import copy
import uuid
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataDocumentIssue
from apps.tenant_apps.loans.selectors.khata_documents import saved_documents
from apps.tenant_apps.loans.services import khata_documents as documents, khata_labels as labels, khata_accounts
from apps.tenant_apps.loans.web import khata_views, khata_workflows
from . import test_khata_detail_layout as layout, test_khata_foundation as foundation
from .test_khata_corrections import CorrectionFixture
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataDocumentNavigationTests(CorrectionFixture, TestCase):
    request = layout.KhataDetailLayoutTests.request
    detail = layout.KhataDetailLayoutTests.detail

    def issue(self, source=None, **changes):
        return documents.issue_document(**self.args(), request_key=uuid.uuid4(), source_operation_id=source.pk if source else None, **changes)

    def label(self, **changes):
        return labels.issue_labels(**self.args(), request_key=uuid.uuid4(), origin="https://rokkad.example",
            mode="SELECTED", item_ids=[self.first.pk], **changes)

    def test_saved_issues_are_paged_sorted_and_source_only(self):
        issues = [self.issue() for _ in range(27)]
        with workspace_context(self.workspace.pk):
            before = list(self.account.operations.values())
        with patch.object(khata_views, "account_summary", side_effect=AssertionError("No balance replay")):
            first = self.detail(dict(tab="documents"))
            self.assertContains(first, 'data-saved-document=', count=25)
            self.assertContains(first, f'data-saved-document="{issues[-1].pk}"')
            self.assertNotContains(first, f'data-saved-document="{issues[0].pk}"')
            second = self.detail({"tab": "documents", "documents-page": 2})
            self.assertContains(second, 'data-saved-document=', count=2)
            self.assertContains(second, f'data-saved-document="{issues[0].pk}"')
            oldest = self.detail({"documents-sort": "oldest", "documents-kind": "STATEMENT"})
            self.assertContains(oldest, f'data-saved-document="{issues[0].pk}"')
            self.assertContains(oldest, 'documents-sort=oldest')
            self.assertContains(oldest, 'documents-kind=STATEMENT')
        with workspace_context(self.workspace.pk):
            self.assertEqual(before, list(self.account.operations.values()))
            self.assertEqual(KhataDocumentIssue.objects.count(), 27)

    def test_search_type_dates_request_and_item_identity_match_saved_facts(self):
        statement = self.issue()
        label = self.label()
        with workspace_context(self.workspace.pk):
            for q in (str(label.request_key), str(self.first.public_id), "Selected collateral label batch"):
                self.assertEqual(list(saved_documents(self.account, dict(q=q)).values_list("pk", flat=True)), [label.pk])
            self.assertEqual(set(saved_documents(self.account, dict(q=str(self.first.pk))).values_list("pk", flat=True)), {statement.pk, label.pk})
            self.assertEqual(list(saved_documents(self.account, dict(kind="LABEL", from_date=timezone.localdate(), to_date=timezone.localdate())).values_list("pk", flat=True)), [label.pk])
            self.assertFalse(saved_documents(self.account, dict(q="Unrelated missing title")).exists())
        response = self.detail({"documents-q": str(label.request_key), "documents-kind": "LABEL"})
        self.assertContains(response, 'data-saved-document=', count=1)
        self.assertContains(response, label.payload["title"])

    def test_invalid_filters_select_documents_show_errors_and_no_partial_results(self):
        self.issue()
        for params, message in (({"documents-from_date": "2026-10-03", "documents-to_date": "2026-10-02"}, "Through date"),
            ({"documents-kind": "FOREIGN"}, "Select a valid choice"), ({"documents-from_date": "bad"}, "Enter a valid date")):
            response = self.detail(params)
            self.assertContains(response, 'id="khata-panel-documents"')
            self.assertContains(response, message)
            self.assertNotContains(response, 'data-saved-document=')
        with workspace_context(self.workspace.pk):
            self.assertEqual(KhataDocumentIssue.objects.count(), 1)

    def test_correction_badge_and_source_link_preserve_original_pdf_after_filtering(self):
        with self.later(1, 1):
            receipt = self.pay("1000")
            issue = self.issue(receipt)
            original = documents.document_bytes(**self.args(), issue_id=issue.pk)[1]
            correction = self.correct(receipt)
            response = self.detail({"documents-q": "Interest receipt", "documents-kind": "OPERATION"})
            self.assertContains(response, "original source subsequently corrected")
            self.assertContains(response, f"history-operation={correction.pk}")
            self.assertContains(response, reverse("workspace_loans:khata_event", args=(self.workspace.slug, self.account.pk, receipt.pk)))
            self.assertEqual(original, documents.document_bytes(**self.args(), issue_id=issue.pk)[1])

    def test_account_workspace_scope_and_viewer_export_boundary(self):
        issue = self.issue()
        other = khata_accounts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        with workspace_context(self.workspace.pk):
            self.assertFalse(saved_documents(other, {}).exists())
            with self.assertRaises(Http404):
                khata_views.download(self.request(), other.pk, issue.pk)
            viewer = self.staff()
        response = self.detail(dict(tab="documents"), actor=viewer)
        self.assertContains(response, issue.payload["title"])
        self.assertNotContains(response, f'/documents/{issue.pk}/')
        self.assertNotContains(response, '>Issue PDF</button>')
        with workspace_context(self.workspace.pk), self.assertRaises(PermissionDenied):
            khata_views.download(self.request(actor=viewer), self.account.pk, issue.pk)
        foreign_workspace, actor, _ = foundation.fixture(uuid.uuid4().hex[:8])
        request = self.request(dict(tab="documents"), actor=actor)
        request.workspace = foreign_workspace
        with workspace_context(foreign_workspace.pk), self.assertRaises(Http404):
            khata_views.detail(request, self.account.pk)

    def test_contextual_action_and_review_return_links_ignore_external_next(self):
        with workspace_context(self.workspace.pk):
            for action, tab in (("deposit", "collateral"), ("photo", "collateral"), ("exchange", "collateral"),
                ("interest", "interest"), ("proposal", "actions"), ("withdraw", "overview"), ("correct", "history")):
                response = khata_workflows.operate(self.request(dict(next="https://outside.invalid/")), self.account.pk, action)
                self.assertContains(response, f'?tab={tab}')
                self.assertNotContains(response, 'https://outside.invalid/')
        with self.later(1, 1), workspace_context(self.workspace.pk):
            review = khata_workflows.operate(self.request(dict(request_key=uuid.uuid4(), value="1000", payment_reference="Bank test receipt"), "post"), self.account.pk, "interest")
            self.assertContains(review, '?tab=interest')

    def test_confirmed_interest_returns_to_interest_without_duplicate_posting(self):
        import re
        with self.later(1, 1), workspace_context(self.workspace.pk):
            review = khata_workflows.operate(self.request(dict(request_key=uuid.uuid4(), value="1000", payment_reference="Bank test receipt"), "post"), self.account.pk, "interest")
            token = re.search(r'name="review_token" value="([^"]+)"', review.content.decode()).group(1)
            request = dict(review_token=token, next="https://outside.invalid/")
            response = khata_workflows.operate(self.request(request, "post"), self.account.pk, "interest")
            retry = khata_workflows.operate(self.request(request, "post"), self.account.pk, "interest")
            self.assertEqual(response["Location"], reverse("workspace_loans:khata_detail", args=(self.workspace.slug, self.account.pk))+"?tab=interest")
            self.assertEqual(retry["Location"], response["Location"])
            self.assertEqual(self.account.operations.filter(kind="INTEREST").count(), 1)

    def test_mobile_section_chooser_tracks_active_legacy_and_invalid_tabs(self):
        for params, expected in (({"tab": "documents"}, "documents"), ({"section": "collateral"}, "collateral"), ({"tab": "unknown"}, "overview")):
            response = self.detail(params)
            self.assertContains(response, 'id="khata-section-picker"')
            self.assertContains(response, f'value="{expected}" selected')
            self.assertContains(response, 'js/khata-detail.js')


@override_settings(STORAGES=STORAGES)
class KhataDocumentNavigationRLSTests(CorrectionFixture, TestCase):
    def setUp(self):
        super().setUp()
        from django.db import connection
        self.runtime_role = "khata_documents_" + uuid.uuid4().hex
        quoted = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}")

    runtime = foundation.KhataRLSBoundaryTests.runtime

    def test_restricted_saved_document_read_is_scoped_even_for_mismatched_account_object(self):
        with self.runtime(), workspace_context(self.workspace.pk):
            issue = documents.issue_document(**self.args(), request_key=uuid.uuid4())
            mismatched = copy.copy(self.account)
            mismatched.workspace_id = self.workspace.pk + 99999
            self.assertFalse(saved_documents(mismatched, {}).exists())
            self.assertEqual(list(saved_documents(self.account, dict(q=str(issue.request_key))).values_list("pk", flat=True)), [issue.pk])
