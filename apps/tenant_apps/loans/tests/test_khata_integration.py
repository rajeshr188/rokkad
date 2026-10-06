"""Combined portfolio, custody, document provenance and private boundary checks."""
import copy
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import fitz
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataDocumentIssue, PawnLoan, PawnLoanEvent
from apps.tenant_apps.loans.selectors.khata_summary import portfolio_summary, summary_accounts, account_summary, collateral_cover
from apps.tenant_apps.loans.selectors.party_loans import get_party_loan_history_summary
from apps.tenant_apps.loans.selectors.business_overview import get_business_overview
from apps.tenant_apps.loans.services import khata_documents as documents, khata_accounts as drafts
from apps.tenant_apps.loans.web import khata_views
from .test_khata_corrections import CorrectionFixture
from . import test_khata_custody_settlement as custody, test_dashboard_batch as pawn_fixtures
from .test_khata_foundation import fixture

STORAGES = custody.revision_tests.collection.opening_tests.STORAGES


@override_settings(STORAGES=STORAGES)
class KhataIntegrationTests(CorrectionFixture, TestCase):
    def issue(self, source=None, **changes):
        values = dict(self.args(), request_key=uuid.uuid4(), source_operation_id=source.pk if source else None)
        values.update(changes)
        return documents.issue_document(**values)

    def read(self, issue, **changes):
        return documents.document_bytes(**dict(self.args(), issue_id=issue.pk, **changes))[1]

    def summary(self):
        with workspace_context(self.workspace.pk):
            return portfolio_summary(workspace=self.workspace)

    def test_limit_is_not_debt_and_due_is_distinct_from_accrual(self):
        result = self.summary()
        self.assertEqual(result["principal"], Decimal("100000"))
        self.assertEqual(result["interest"], Decimal("100000"))
        self.assertEqual(result["due_interest"], 0)
        self.assertEqual(result["limit"], Decimal("10000000"))
        self.assertEqual(result["unused"], Decimal("9900000"))
        with self.later(1, 1):
            receipt = self.pay("25000")
            result = self.summary()
            self.assertEqual(result["due_interest"], Decimal("75000"))
            self.assertEqual(result["overdue_interest"], Decimal("75000"))
            self.correct(receipt)
            self.assertEqual(self.summary()["due_interest"], Decimal("100000"))

    def test_mixed_borrower_counted_once_pawn_totals_preserved_and_routes_distinct(self):
        with workspace_context(self.workspace.pk):
            helper = SimpleNamespace(actor=self.actor)
            loan = pawn_fixtures.DashboardBatchTests.loan(helper, self.workspace)
            loan.borrower = self.borrower
            loan.save(update_fields=["borrower"])
            PawnLoanEvent.objects.create(workspace=self.workspace, loan=loan, event_kind="DISBURSAL",
                effective_date=timezone.localdate(), payload={"values": {"principal": "1234"}},
                payload_fingerprint=uuid.uuid4().hex, idempotency_key=uuid.uuid4().hex)
            overview = get_business_overview(workspace=self.workspace)
            self.assertEqual(overview["active_borrowers"], 1)
            self.assertEqual(overview["active_loans"], 2)
            self.assertEqual(overview["principal_outstanding"], Decimal("101234"))
            self.assertEqual(overview["interest_outstanding"], 0)
            summary = get_party_loan_history_summary(self.borrower, page_size=1)
            self.assertEqual(summary["counts"]["active_outstanding"], Decimal("201234"))
            self.assertEqual(summary["counts"]["active_loans"], 2)
            all_rows = get_party_loan_history_summary(self.borrower, limit=None)["active_loans"]
            khata = next(r for r in all_rows if r.loan_type == "Khata")
            self.assertIn("/khata/", khata.detail_url)
            self.assertFalse(khata.repayment_url)
            self.assertEqual(PawnLoan.objects.count(), 1)

    def test_pagination_does_not_truncate_totals_or_draft_limit_become_debt(self):
        from .test_khata_foundation import draft_args
        drafts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        with workspace_context(self.workspace.pk):
            result = get_party_loan_history_summary(self.borrower, page_size=1, active_page=2, sort="oldest")
            self.assertEqual(result["counts"]["active_loans"], 2)
            self.assertEqual(result["counts"]["active_outstanding"], Decimal("200000"))
            self.assertEqual(len(result["active_loans"]), 1)
        self.assertEqual(self.summary()["active_count"], 1)

    def test_settlement_removes_debt_keeps_pending_custody_then_closes(self):
        settlement = self.settle()
        result = self.summary()
        self.assertEqual(result["active_count"], 0)
        self.assertEqual(result["principal"], 0)
        self.assertEqual(result["interest"], 0)
        self.assertEqual(result["pending_returns"], 1)
        with workspace_context(self.workspace.pk):
            summary = get_party_loan_history_summary(self.borrower)
            self.assertEqual(summary["counts"]["active_outstanding"], 0)
            self.assertEqual(summary["counts"]["khata_pending_returns"], 1)
        self.handover(self.first, settlement)
        self.assertEqual(self.summary()["pending_returns"], 0)

    def test_known_shortfall_and_correction_reservations_do_not_hide_items(self):
        replacement = self.replacement("1")
        exchange = self.exchange([self.first], [replacement])
        self.assertEqual(self.summary()["pending_returns"], 1)
        correction = self.correct(exchange)
        with workspace_context(self.workspace.pk):
            row = account_summary(summary_accounts(workspace=self.workspace).get(pk=self.account.pk))
            self.assertEqual(row["held_count"], 2)
            self.assertEqual(row["pending_returns"], 1)
        self.handover(replacement, correction)
        self.assertEqual(self.summary()["pending_returns"], 0)

    def test_unavailable_evidence_never_returns_partial_money_total(self):
        with workspace_context(self.workspace.pk), patch(
            "apps.tenant_apps.loans.selectors.khata_summary.account_position", return_value=None):
            result = get_business_overview(workspace=self.workspace)
            self.assertIsNone(result["principal_outstanding"])
            self.assertIsNone(result["khata"]["interest"])
            self.assertEqual(result["unavailable_balance_count"], 1)

    def test_mixed_party_unavailable_pawn_evidence_uses_raw_state_not_display_label(self):
        with workspace_context(self.workspace.pk):
            loan = pawn_fixtures.DashboardBatchTests.loan(SimpleNamespace(), self.workspace)
            loan.borrower = self.borrower
            loan.save(update_fields=["borrower"])
            with patch.object(PawnLoan, "get_state_display", return_value="Translated active label"), patch(
                "apps.tenant_apps.loans.selectors.party_history.get_pawn_loan_balance", side_effect=ValueError("Missing opening evidence")):
                summary = get_party_loan_history_summary(self.borrower)
            self.assertIsNone(summary["counts"]["active_outstanding"])
            self.assertEqual(summary["counts"]["unavailable_balances"], 1)

    def test_statement_and_voucher_persist_verified_exact_bytes(self):
        issue = self.issue()
        content = self.read(issue)
        self.assertTrue(content.startswith(b"%PDF"))
        text = "".join(p.get_text() for p in fitz.open(stream=content, filetype="pdf"))
        self.assertIn("Dated khata statement", text)
        self.assertIn("1,00,000", text)
        self.assertIn("1,00,00,000", text)
        self.assertIsNone(issue.payload["license"])
        self.assertEqual(self.issue(request_key=issue.request_key).pk, issue.pk)
        self.revise(limit="15000000")
        self.assertEqual(self.read(issue), content)
        with workspace_context(self.workspace.pk):
            withdrawal = self.account.operations.filter(kind="WITHDRAW").first()
        voucher = self.issue(withdrawal)
        self.assertEqual(voucher.payload["agreement"]["agreed_limit"], "10000000.00")
        self.assertEqual(voucher.payload["unused"], "9900000.00")

    def test_original_receipt_survives_correction_new_document_links_compensation(self):
        with self.later(1):
            receipt = self.pay("100000")
            original = self.issue(receipt)
            content = self.read(original)
            correction = self.correct(receipt)
            self.assertEqual(self.read(original), content)
            self.assertEqual(self.issue(correction).payload["source"]["correction_of_id"], receipt.pk)
            later_copy = self.issue(receipt)
            self.assertEqual(later_copy.payload["correction_notice"], correction.pk)
            self.assertEqual(later_copy.payload["source"]["amount"], "100000.00")

    def test_cancelled_exchange_delayed_document_uses_original_source_custody(self):
        replacement = self.replacement("100")
        exchange = self.exchange([self.first], [replacement])
        self.correct(exchange)
        issue = self.issue(exchange)
        original_item = next(i for i in issue.payload["collateral"] if i["id"] == self.first.pk)
        self.assertEqual(original_item["custody"], "Return pending")
        self.assertTrue(issue.payload["correction_notice"])

    def test_integrity_failure_and_render_failure_never_regenerate_original(self):
        issue = self.issue()
        issue.artifact.storage.delete(issue.artifact.name)
        issue.artifact.storage.save(issue.artifact.name, ContentFile(b"tampered"))
        with self.assertRaisesMessage(ValueError, "integrity"):
            self.read(issue)
        with workspace_context(self.workspace.pk):
            count = KhataDocumentIssue.objects.count()
        with patch.object(documents, "render_document", side_effect=ValueError("Layout failure")):
            with self.assertRaisesMessage(ValueError, "Layout failure"):
                self.issue()
        with workspace_context(self.workspace.pk):
            self.assertEqual(KhataDocumentIssue.objects.count(), count)

    def test_cross_account_source_retry_conflict_and_viewer_export_permissions(self):
        from .test_khata_foundation import draft_args
        other = drafts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        with workspace_context(self.workspace.pk):
            source = self.account.operations.filter(kind="WITHDRAW").first()
        with self.assertRaisesMessage(ValueError, "this khata"):
            documents.issue_document(workspace=self.workspace, actor=self.actor, account_id=other.pk,
                request_key=uuid.uuid4(), source_operation_id=source.pk)
        issue = self.issue()
        with self.assertRaisesMessage(ValueError, "different instructions"):
            self.issue(source, request_key=issue.request_key)
        viewer = self.staff()
        with self.assertRaises(PermissionDenied):
            self.issue(actor=viewer)
        with self.assertRaises(PermissionDenied):
            self.read(issue, actor=viewer)

    def request(self, path="/", data=None, method="get", actor=None):
        request = getattr(RequestFactory(), method)(path, data or {})
        request.user = actor or self.actor
        request.workspace = self.workspace
        return request

    def test_read_pages_private_get_does_not_issue_and_post_redirects_to_pdf(self):
        with workspace_context(self.workspace.pk):
            response = khata_views.index(self.request(data={"association": "independent", "sort": "oldest"}))
            self.assertContains(response, self.account.account_number)
            response = khata_views.detail(self.request(), self.account.pk)
            self.assertContains(response, "Accrued unpaid interest")
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(KhataDocumentIssue.objects.count(), 0)
            response = khata_views.detail(self.request(data={"request_key": uuid.uuid4(), "source": "statement"}, method="post"), self.account.pk)
            self.assertEqual(response.status_code, 302)
            issue = KhataDocumentIssue.objects.get()
            response = khata_views.download(self.request(), self.account.pk, issue.pk)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertIn("private", response["Cache-Control"])
            self.assertIn("no-store", response["Cache-Control"])

    def test_unset_and_foreign_context_rejected_before_summary_reads(self):
        other_workspace, _, _ = fixture(uuid.uuid4().hex[:8])
        with self.assertRaisesMessage(ValueError, "matching Workspace"):
            portfolio_summary(workspace=self.workspace)
        with workspace_context(other_workspace.pk), self.assertRaisesMessage(ValueError, "matching Workspace"):
            portfolio_summary(workspace=self.workspace)

    def test_associated_and_independent_accounts_included_once_with_lender_identity(self):
        from datetime import timedelta
        from .test_khata_foundation import draft_args
        from apps.tenant_apps.loans.models import LoanLicense
        from apps.tenant_apps.loans.services import khata_opening as opening
        with workspace_context(self.workspace.pk):
            license = LoanLicense.objects.create(workspace=self.workspace, name="Fictional associated licence",
                license_number="KHATA-TEST", issued_on=timezone.localdate()-timedelta(days=1),
                expires_on=timezone.localdate()+timedelta(days=365))
        series = drafts.create_series(workspace=self.workspace, actor=self.actor, code="KHA",
            name="Associated khata", prefix="KHA", license_id=license.pk)
        account = drafts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, series))
        args = dict(workspace=self.workspace, actor=self.actor, account_id=account.pk)
        opening.record_deposit(**args, request_key=uuid.uuid4(), business_date=timezone.localdate(),
            description="Associated collateral", metal="GOLD", quantity=1, gross_weight="100", net_weight="100",
            purity="100", storage_reference="Bag 2", received_from="Borrower")
        approval = opening.preview_opening(**args)
        opening.approve_opening(**args, request_key=uuid.uuid4(), business_date=timezone.localdate(), review_hash=approval["review_hash"])
        draw = opening.preview_withdrawal(**args, value="50000")
        op = opening.record_withdrawal(**args, request_key=uuid.uuid4(), business_date=timezone.localdate(),
            value="50000", review_hash=draw["review_hash"], payment_reference="Cash paid")
        result = self.summary()
        self.assertEqual(result["active_count"], 2)
        self.assertEqual(result["principal"], Decimal("150000"))
        self.assertEqual(len(result["borrower_ids"]), 1)
        issue = documents.issue_document(**args, request_key=uuid.uuid4(), source_operation_id=op.pk)
        self.assertEqual(issue.payload["license"]["id"], license.pk)
        self.assertEqual(issue.payload["license"]["number"], "KHATA-TEST")
        self.assertEqual(issue.payload["agreement"]["lender_name"], "Fictional lender")

    def test_summary_reads_are_batched_and_dashboard_does_not_retain_account_graphs(self):
        from .test_khata_foundation import draft_args
        from django.test.utils import CaptureQueriesContext
        with workspace_context(self.workspace.pk):
            with CaptureQueriesContext(connection) as first:
                result = portfolio_summary(workspace=self.workspace, include_rows=False)
            self.assertEqual(result["rows"], [])
            for _ in range(4):
                drafts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
            with CaptureQueriesContext(connection) as second:
                portfolio_summary(workspace=self.workspace, include_rows=False)
            self.assertEqual(len(first), len(second))

    def test_borrower_portal_receipts_and_statement_do_not_reduce_outstanding_twice(self):
        from apps.tenant_apps.party.models import PartyPortalAccess
        from apps.tenant_apps.party.portal_access import PortalIdentity
        from apps.tenant_apps.party.portal_selectors import get_portal_loans_summary, get_portal_statements_summary, get_portal_payments_summary
        with self.later(1):
            receipt = self.pay("25000")
            with workspace_context(self.workspace.pk):
                grant = PartyPortalAccess.objects.create(party=self.borrower, user=self.actor, status="ACTIVE")
                identity = PortalIdentity(user=self.actor, workspace=self.workspace, party=self.borrower, access_grant=grant)
                loans = get_portal_loans_summary(identity, limit=1)
                payments = get_portal_payments_summary(identity, limit=1)
                statement = get_portal_statements_summary(identity)
                self.assertEqual(loans.outstanding_amount, Decimal("175000"))
                self.assertEqual(payments.total_amount, Decimal("25000"))
                self.assertEqual(statement.closing_balance, loans.outstanding_amount)
            self.correct(receipt)
            with workspace_context(self.workspace.pk):
                self.assertEqual(get_portal_payments_summary(identity).total_amount, 0)
                self.assertEqual(get_portal_statements_summary(identity).closing_balance, Decimal("200000"))

    def test_actual_return_and_settlement_vouchers_preserve_full_recipient_evidence(self):
        settlement = self.settle()
        receipt = self.issue(settlement)
        self.assertEqual(receipt.payload["principal"], "0")
        self.assertEqual(receipt.payload["source"]["interest_amount"], "100000.00")
        return_op = self.handover(self.first, settlement, recipient="Borrower with a complete recorded recipient name",
            reference="Signed custody receipt")
        issue = self.issue(return_op)
        self.assertEqual(issue.payload["source"]["parent_id"], settlement.pk)
        self.assertEqual(issue.payload["collateral"][0]["custody"], "Returned")

    def test_private_download_requires_export_and_foreign_routes_do_not_reveal_artifacts(self):
        from django.http import Http404
        issue = self.issue()
        viewer = self.staff()
        with workspace_context(self.workspace.pk), self.assertRaises(PermissionDenied):
            khata_views.download(self.request(actor=viewer), self.account.pk, issue.pk)
        with workspace_context(self.workspace.pk), self.assertRaises(Http404):
            khata_views.download(self.request(), self.account.pk+100000, issue.pk)
        exporter = self.staff("data_export")
        self.assertEqual(self.read(issue, actor=exporter), self.read(issue))
        with self.assertRaises(PermissionDenied):
            self.issue(actor=exporter)

    def test_cover_excludes_pending_outgoing_and_missing_prices_do_not_hide_debt(self):
        replacement = self.replacement("1")
        self.exchange([self.first], [replacement])
        with workspace_context(self.workspace.pk):
            account = summary_accounts(workspace=self.workspace).get(pk=self.account.pk)
            summary = account_summary(account)
            cover = collateral_cover(account, summary)
            self.assertEqual(cover["value"], Decimal("10000"))
            self.assertEqual(cover["capacity"], 0)
            self.assertTrue(cover["undercovered"])
        # Quotes remain eligible through the configured seven-day lending window.
        with self.later(0, 8), workspace_context(self.workspace.pk):
            account = summary_accounts(workspace=self.workspace).get(pk=self.account.pk)
            summary = account_summary(account)
            cover = collateral_cover(account, summary)
            self.assertIsNone(cover["value"])
            self.assertEqual(summary["principal"], Decimal("100000"))

    def test_annual_settlement_document_collects_accrued_not_yet_due_interest(self):
        # The annual calculator/settlement cases are covered by the servicing
        # suite; use a fresh annual account to exercise the document boundary.
        from .test_khata_foundation import draft_args
        from apps.tenant_apps.loans.services import khata_opening as opening, khata_settlement as settlement
        values = draft_args(self.workspace, self.actor, self.borrower, self.series)
        values["frequency"] = "ANNUAL"
        account = drafts.create_draft(**values)
        args = dict(workspace=self.workspace, actor=self.actor, account_id=account.pk)
        opening.record_deposit(**args, request_key=uuid.uuid4(), business_date=timezone.localdate(),
            description="Annual collateral", metal="GOLD", quantity=1, gross_weight="100", net_weight="100",
            purity="100", storage_reference="Annual bag", received_from="Borrower")
        review = opening.preview_opening(**args)
        opening.approve_opening(**args, request_key=uuid.uuid4(), business_date=timezone.localdate(), review_hash=review["review_hash"])
        review = opening.preview_withdrawal(**args, value="100000")
        opening.record_withdrawal(**args, request_key=uuid.uuid4(), business_date=timezone.localdate(), value="100000",
            review_hash=review["review_hash"], payment_reference="Cash paid")
        with self.later(4):
            review = settlement.preview_settlement(**args)
            op = settlement.record_settlement(**args, request_key=uuid.uuid4(), business_date=timezone.localdate(),
                review_hash=review["review_hash"], payment_reference="Early annual settlement")
            issue = documents.issue_document(**args, request_key=uuid.uuid4(), source_operation_id=op.pk)
            self.assertEqual(issue.payload["source"]["interest_amount"], "400000.00")
            self.assertEqual(issue.payload["agreement"]["frequency"], "ANNUAL")

    def test_long_pdf_flows_all_addresses_items_and_final_history_entry(self):
        from apps.tenant_apps.loans.documents.khata import render_document
        with workspace_context(self.workspace.pk):
            account = summary_accounts(workspace=self.workspace).get(pk=self.account.pk)
            payload = documents.document_payload(account)
        payload["borrower"]["address"] = "Long address with every part preserved " * 50 + "ADDRESS-END"
        original = payload["collateral"][0]
        payload["collateral"] = [dict(original, id=i, description="Complete collateral description " * 15 + f"ITEM-END-{i}") for i in range(50)]
        payload["history"][-1]["kind"] = "FINAL-HISTORY-END"
        content = render_document(payload, issue_reference="fictional-long-layout-check")
        with fitz.open(stream=content, filetype="pdf") as pdf:
            self.assertGreater(len(pdf), 5)
            text = "".join(page.get_text() for page in pdf)
            self.assertIn("ADDRESS-END", text)
            self.assertIn("ITEM-END-49", text)
            self.assertIn("FINAL-HISTORY-END", text)
            self.assertIn(f"Page {len(pdf)} of {len(pdf)}", text)


@override_settings(STORAGES=STORAGES)
class KhataDocumentRLSTests(CorrectionFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.issue = documents.issue_document(**self.args(), request_key=uuid.uuid4())
        self.other_workspace, _, _ = fixture(uuid.uuid4().hex[:8])
        self.runtime_role = "khata_docs_" + uuid.uuid4().hex
        quoted = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}")

    def runtime(self):
        from .test_khata_foundation import KhataRLSBoundaryTests
        return KhataRLSBoundaryTests.runtime(self)

    def test_restricted_role_forced_rls_and_immutable_evidence(self):
        with self.runtime():
            self.assertEqual(KhataDocumentIssue.objects.count(), 0)
            with workspace_context(self.other_workspace.pk):
                self.assertFalse(KhataDocumentIssue.objects.filter(pk=self.issue.pk).exists())
            with workspace_context(self.workspace.pk):
                self.assertEqual(KhataDocumentIssue.objects.count(), 1)
                for mutate in (lambda: KhataDocumentIssue.objects.update(payload={}),
                               lambda: KhataDocumentIssue.objects.all().delete()):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        mutate()
                forged = copy.copy(self.issue)
                forged.pk = None
                forged.request_key = uuid.uuid4()
                forged.payload = copy.deepcopy(self.issue.payload)
                forged.payload["account_id"] = -1
                forged.artifact.name = f"loans/khata/{self.workspace.pk}/documents/{self.account.pk}/{forged.request_key}.pdf"
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataDocumentIssue.objects.bulk_create([forged])
