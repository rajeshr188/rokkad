"""Real PostgreSQL connections competing for the first precision ticket issue."""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.documents import DocumentLayoutValidator, starter_layout
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnLoan, PawnLoanApprovalSnapshot, LoanDocumentIssue
from apps.tenant_apps.loans.services.document_issuance import _issue_precision_ticket
from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
from apps.tenant_apps.loans.services.ticket_documents import prepare_ticket_document
from .factories import ensure_test_product_version


class TicketEvidenceConcurrencyTests(TransactionTestCase):
    def test_two_first_prints_capture_once_and_return_the_same_artifact(self):
        actor = get_user_model().objects.create_user(username=uuid.uuid4().hex)
        workspace = Company.objects.create(name="Concurrent ticket test", schema_name=uuid.uuid4().hex, owner=actor, creator=actor)
        role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.create(company=workspace, user=actor, role=role)
        with workspace_context(workspace.pk):
            license = LoanLicense.objects.create(workspace=workspace, name="Test", license_number="TEST", issued_on=date(2020, 1, 1), expires_on=date(2030, 1, 1))
            series = LoanSeries.objects.create(license=license, name="Test", code="A")
            party = Party.objects.create(display_name="Synthetic customer")
            loan = PawnLoan.objects.create(workspace=workspace, license=license, series=series, borrower=party,
                product_version=ensure_test_product_version(workspace), loan_number="TEST-1", principal_amount=1000, monthly_interest_rate=1)
            source = {"loan_number": "TEST-1", "loan_date": "2026-09-22", "principal_amount": "1000", "monthly_interest_rate": "1", "tenure_months": 3, "borrower_id": party.pk, "collateral": []}
            approval = PawnLoanApprovalSnapshot.objects.create(loan=loan, version=1, payload=source, fingerprint="concurrent-approval", approved_by=actor)
            loan.state = "APPROVED"
            loan.save()
            definition = starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict()
            revision = LoanDocumentLayoutService.create_layout(workspace=workspace, document_type="loan_ticket", name="Concurrent", definition=definition, actor=actor)
            revision = LoanDocumentLayoutService.publish(revision=revision, actor=actor)
        ready = Barrier(2)

        def issue():
            try:
                with workspace_context(workspace.pk):
                    ready.wait(timeout=10)
                    result = _issue_precision_ticket(workspace=workspace, loan=loan, revision=revision,
                        layout=DocumentLayoutValidator.load(definition), source_type="PawnLoan", source_id=loan.pk,
                        source_fingerprint=approval.fingerprint, actor=actor, request=None, legacy_profile_recovery=False)
                    return result.issue.pk, result.issue.pdf_hash, result.issue.artifact.name
            finally:
                connections.close_all()

        with patch("apps.tenant_apps.loans.services.ticket_documents.prepare_ticket_document", wraps=prepare_ticket_document) as prepare:
            with ThreadPoolExecutor(max_workers=2) as executor:
                first, second = list(executor.map(lambda _: issue(), range(2)))
            self.assertEqual(prepare.call_count, 1)
        self.assertEqual(first, second)
        with workspace_context(workspace.pk):
            self.assertEqual(LoanDocumentIssue.objects.count(), 1)
            saved = LoanDocumentIssue.objects.get(pk=first[0])
            self.assertEqual(saved.source_snapshot["approval_id"], approval.pk)
