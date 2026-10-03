"""Khata tab navigation preserves private source links and workflow access."""
import uuid

from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataDocumentIssue
from apps.tenant_apps.loans.web import khata_views, khata_workflows
from .test_khata_corrections import CorrectionFixture
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataDetailLayoutTests(CorrectionFixture, TestCase):
    def request(self, data=None, method="get", actor=None):
        request = getattr(RequestFactory(), method)("/", data or {})
        request.user = actor or self.actor
        request.workspace = self.workspace
        return request

    def detail(self, data=None, method="get", actor=None):
        with workspace_context(self.workspace.pk):
            return khata_views.detail(self.request(data, method, actor), self.account.pk)

    def test_one_active_panel_default_fallback_and_legacy_source_navigation(self):
        before = self.balance()
        default = self.detail()
        self.assertContains(default, 'id="khata-panel-overview"')
        self.assertContains(default, 'id="position-heading"')
        self.assertNotContains(default, 'id="source-history"')
        self.assertNotContains(default, 'id="documents-heading"')
        history = self.detail(dict(tab="history"))
        self.assertContains(history, 'id="khata-panel-history"')
        self.assertContains(history, 'id="source-history"')
        self.assertNotContains(history, 'id="position-heading"')
        self.assertContains(self.detail(dict(tab="unknown")), 'id="khata-panel-overview"')
        collateral = self.detail(dict(section="collateral"))
        self.assertContains(collateral, 'id="khata-panel-collateral"')
        self.assertContains(collateral, f'id="collateral-item-{self.first.public_id}"')
        source = self.detail({"history-operation": self.first.received_operation_id})
        self.assertContains(source, 'id="khata-panel-history"')
        self.assertContains(source, f'id="operation-{self.first.received_operation_id}"')
        self.assertEqual(self.balance(), before)

    def test_document_validation_and_issuance_errors_select_documents(self):
        response = self.detail(dict(source="invalid"), "post")
        self.assertContains(response, 'id="khata-panel-documents"')
        self.assertContains(response, "This field is required")
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataDocumentIssue.objects.exists())
        response = self.detail(dict(request_key=uuid.uuid4(), source="statement"), "post")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/documents/", response["Location"])

    def test_action_groups_reuse_authorized_links_and_viewer_has_no_write_controls(self):
        with workspace_context(self.workspace.pk):
            request = self.request(dict(tab="actions"))
            response = khata_views.detail(request, self.account.pk)
            self.account.refresh_from_db()
            from apps.tenant_apps.loans.selectors.khata_summary import summary_accounts, account_summary
            from apps.tenant_apps.loans.selectors.khata_workflow import workflow_state
            account = summary_accounts(workspace=self.workspace, balances_only=True).get(pk=self.account.pk)
            guidance = workflow_state(account, summary=account_summary(account), actor=self.actor)
            expected = khata_workflows.action_links(request, account, guidance)
            for name, _ in expected:
                url = reverse("workspace_loans:khata_action", args=(self.workspace.slug, self.account.pk, name))
                self.assertContains(response, f'href="{url}"', count=1)
            viewer = self.staff()
        response = self.detail(dict(tab="actions"), actor=viewer)
        self.assertContains(response, "No servicing actions are available")
        self.assertNotContains(response, "/actions/withdraw/")
        self.assertNotContains(response, "/actions/deposit/")
        response = self.detail(dict(tab="documents"), actor=viewer)
        self.assertContains(response, 'id="khata-panel-documents"')
        self.assertNotContains(response, ">Issue PDF</button>")
