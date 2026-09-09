from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans.services.document_issuance import (
    issue_configurable_document,
)


class ConfigurableDocumentIssuanceTests(SimpleTestCase):
    def setUp(self):
        access = patch("apps.tenant_apps.loans.services.document_issuance.require_loan_action")
        access.start()
        self.addCleanup(access.stop)
        self.workspace = SimpleNamespace(pk=1)
        self.loan = SimpleNamespace(
            workspace_id=1, workspace=self.workspace,
            license=SimpleNamespace(pk=2), series=SimpleNamespace(pk=3)
        )
        self.payload = SimpleNamespace(
            document_type="loan_ticket", schema_version=3, file_name="ticket.pdf"
        )

    @patch(
        "apps.tenant_apps.loans.services.document_issuance."
        "LoanDocumentLayoutService.audit_fixed_recovery"
    )
    def test_fixed_recovery_is_audited_and_requests_fallback(self, audit):
        result = self._issue(fixed_recovery=True)

        self.assertTrue(result.use_fixed_renderer)
        self.assertIsNone(result.issue)
        audit.assert_called_once()

    @patch(
        "apps.tenant_apps.loans.services.document_issuance."
        "LoanDocumentLayoutService.find_official_issue"
    )
    def test_existing_official_issue_is_reused_before_resolution(self, find):
        issue = object()
        find.return_value = issue

        result = self._issue()

        self.assertIs(result.issue, issue)
        self.assertFalse(result.use_fixed_renderer)

    @patch(
        "apps.tenant_apps.loans.services.document_issuance."
        "LoanDocumentLayoutService.resolve",
        return_value=None,
    )
    @patch(
        "apps.tenant_apps.loans.services.document_issuance."
        "LoanDocumentLayoutService.find_official_issue",
        return_value=None,
    )
    def test_missing_assignment_persists_an_official_fixed_issue(self, _find, _resolve):
        module = "apps.tenant_apps.loans.services.document_issuance."
        with patch(module + "PawnLoanDocumentService.render_payload") as render, patch(
            module + "LoanDocumentLayoutService.issue"
        ) as issue:
            render.return_value = SimpleNamespace(pdf=b"%PDF-fixed")
            result = self._issue()

        self.assertFalse(result.use_fixed_renderer)
        self.assertIs(result.issue, issue.return_value)
        self.assertEqual(issue.call_args.kwargs["render_result"].pdf, b"%PDF-fixed")
        self.assertEqual(issue.call_args.kwargs["render_result"].renderer_version, "fixed-pawn-v1")

    def _issue(self, **changes):
        values = {
            "workspace": self.workspace,
            "payload": self.payload,
            "loan": self.loan,
            "source_type": "PawnLoan",
            "source_id": 4,
            "source_fingerprint": "fingerprint",
        }
        values.update(changes)
        return issue_configurable_document(**values)
