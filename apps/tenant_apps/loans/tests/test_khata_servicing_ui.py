"""Searchable servicing keeps exact custody sources and signed command checks."""
import json
import re
import uuid

from django.core.exceptions import PermissionDenied
from django.core import signing
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.web import khata_items, khata_workflows
from .test_khata_collateral_ui import image_upload
from .test_khata_corrections import CorrectionFixture
from .test_khata_opening import STORAGES, draft_args
from apps.tenant_apps.loans.services import khata_accounts


@override_settings(STORAGES=STORAGES)
class KhataServicingUITests(CorrectionFixture, TestCase):
    def request(self, data=None, method="get", actor=None):
        request = getattr(RequestFactory(), method)("/", data or {})
        request.user = actor or self.actor
        request.workspace = self.workspace
        return request

    def action(self, action, data=None, method="get", actor=None):
        with workspace_context(self.workspace.pk):
            return khata_workflows.operate(self.request(data, method, actor), self.account.pk, action)

    def browse(self, **params):
        with workspace_context(self.workspace.pk):
            return khata_items.browse(self.request(params), self.account.pk)

    def test_pending_rows_link_exact_source_and_preselect_without_moving(self):
        replacement = self.replacement()
        source = self.exchange([self.first], [replacement])
        self.photo(self.first)
        rows = json.loads(self.browse(mode="pending", format="json").content)["items"]
        self.assertEqual([r["id"] for r in rows], [self.first.pk])
        self.assertEqual(rows[0]["parent"], source.pk)
        self.assertTrue(rows[0]["thumbnail"])
        response = self.browse(mode="pending")
        self.assertContains(response, f'/actions/handover/?item={self.first.pk}')
        self.assertContains(response, f'history-operation={source.pk}')
        response = self.action("handover", dict(item=self.first.pk, parent=99999999))
        self.assertContains(response, f'<option value="{self.first.pk}" selected>')
        self.assertContains(response, f'<option value="{source.pk}" selected>')
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.account.operations.filter(kind="HANDOVER").exists())

    def test_signed_handover_rechecks_and_retry_preserves_single_source(self):
        source = self.exchange([self.first], [self.replacement()])
        data = dict(request_key=uuid.uuid4(), item=self.first.pk, parent=source.pk,
            recipient="Borrower", reference="Signed physical receipt")
        response = self.action("handover", data, "post")
        token = re.search(rb'name="review_token" value="([^"]+)"', response.content).group(1).decode()
        for _ in range(2):
            response = self.action("handover", dict(review_token=token), "post")
            self.assertEqual(response.status_code, 302)
            self.assertIn("?mode=pending", response["Location"])
        self.assertEqual(json.loads(self.browse(mode="pending", format="json").content)["count"], 0)
        response = self.action("handover", dict(data, request_key=uuid.uuid4()), "post")
        self.assertContains(response, "Select a valid choice")
        with workspace_context(self.workspace.pk):
            self.assertEqual(self.account.operations.filter(kind="HANDOVER").count(), 1)

    def test_wrong_parent_and_foreign_get_selection_never_bypass_review(self):
        source = self.exchange([self.first], [self.replacement()])
        other = self.deposit()
        other_source = self.exchange([other], [self.replacement()])
        response = self.action("handover", dict(request_key=uuid.uuid4(), item=self.first.pk,
            parent=other_source.pk, recipient="Borrower", reference="Wrong source"), "post")
        self.assertNotContains(response, 'name="review_token"')
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.account.operations.filter(kind="HANDOVER").exists())
        other_account = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        original = self.account
        self.account = other_account
        foreign = self.deposit()
        self.account = original
        self.assertNotContains(self.action("photo", dict(item=foreign.pk)), f'<option value="{foreign.pk}"')
        self.assertEqual(json.loads(self.browse(mode="held", q=str(foreign.pk), format="json").content)["count"], 0)

    def test_photo_picker_includes_pending_but_refuses_returned_item(self):
        source = self.exchange([self.first], [self.replacement()])
        response = self.action("photo", dict(item=self.first.pk))
        self.assertContains(response, 'id="khata-servicing-data"')
        self.assertContains(response, f'<option value="{self.first.pk}" selected>')
        response = self.action("photo", dict(request_key=uuid.uuid4(), item=self.first.pk, upload=image_upload()), "post")
        self.assertEqual(response.status_code, 302)
        self.handover(self.first, source)
        response = self.action("photo", dict(request_key=uuid.uuid4(), item=self.first.pk, upload=image_upload()), "post")
        self.assertContains(response, "Select a valid choice")

    def test_reduction_picker_excludes_reserved_and_hard_cover_still_blocks(self):
        replacement = self.replacement("100")
        self.exchange([self.first], [replacement])
        self.proposal("60000")
        response = self.action("approve-change")
        self.assertContains(response, 'data-servicing-fallback')
        self.assertNotContains(response, f'<option value="{self.first.pk}"')
        response = self.action("approve-change", dict(request_key=uuid.uuid4(), principal_repayment="40000",
            outgoing=[replacement.pk], agreement_reference="Consent"), "post")
        self.assertNotContains(response, 'name="review_token"')
        self.assertContains(response, "agreed LTV")

    def test_reduction_multiple_selection_survives_signed_review_and_edit(self):
        one, two = self.replacement("10"), self.replacement("10")
        self.proposal("60000")
        response = self.action("approve-change", dict(request_key=uuid.uuid4(), principal_repayment="40000",
            outgoing=[one.pk, two.pk], agreement_reference="Signed consent"), "post")
        token = re.search(rb'name="review_token" value="([^"]+)"', response.content).group(1).decode()
        saved = signing.loads(token, salt=khata_workflows.SALT)
        self.assertEqual(set(saved["data"]["outgoing"]), {str(one.pk), str(two.pk)})
        response = self.action("approve-change", dict(review_token=token, edit="1"), "post")
        for item in (one, two):
            self.assertContains(response, f'<option value="{item.pk}" selected>')
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.account.operations.filter(kind="TERMS_OK").exists())

    def test_viewer_reads_pending_without_write_links_and_modes_are_validated(self):
        source = self.exchange([self.first], [self.replacement()])
        with workspace_context(self.workspace.pk):
            viewer = self.staff()
            response = khata_items.browse(self.request(dict(mode="pending"), actor=viewer), self.account.pk)
            self.assertContains(response, f'Operation {source.pk}')
            self.assertNotContains(response, ">Hand over Item")
            self.assertNotContains(response, ">Attach photo</a>")
        with self.assertRaises(PermissionDenied):
            self.action("handover", actor=viewer)
        with self.assertRaises(Http404):
            self.browse(mode="invalid")
        self.assertEqual(self.browse(mode="pending", format="json", from_date="bad").status_code, 400)
