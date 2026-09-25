from types import SimpleNamespace
from unittest.mock import patch

import fitz
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.documents import starter_layout
from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
from apps.tenant_apps.loans.forms import PawnDraftForm
from apps.tenant_apps.loans.services.imported_ticket_preview import imported_ticket_payload, render_imported_ticket_preview, render_imported_ticket_copy
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture


class ImportedTicketPreviewTests(OpeningImportFixture):
    def setUp(self):
        super().setUp()
        with self.scoped():
            self.origin = self.write()
            self.loan = self.origin.loan

    def test_frozen_original_terms_and_no_fabricated_approval(self):
        with self.scoped():
            # The PDF source is the frozen import, not a mutable model attribute.
            self.loan.principal_amount = 900
            payload, source, _ = imported_ticket_payload(self.loan)
            fields = {field.key: field.value for field in payload.fields}
            self.assertEqual(source['principal_amount'], '1000')
            self.assertEqual(self.loan.principal_amount, 900)
            self.assertEqual(fields['loan.number'], self.review['source']['number'])
            self.assertEqual(fields['loan.date'], self.review['terms']['original_date'])
            self.assertEqual(fields['approval.fingerprint'], 'Not available')
            self.assertFalse(self.loan.approval_snapshots.exists())
            with self.assertRaisesMessage(ValueError, 'approval snapshot'):
                PawnLoanDocumentProjectionBuilder.loan_ticket(self.loan)

    def test_fixed_and_precision_preview_render_without_issues_events_or_counter_changes(self):
        with self.scoped():
            before = self.snapshot()
            definition = starter_layout('loan_ticket', schema_version=4, layout_mode='ABSOLUTE_OVERLAY').canonical_dict()
            revision = SimpleNamespace(definition=definition, assets=SimpleNamespace(all=lambda: []))
            for layout in (None, revision):
                with self.subTest(precision=layout is not None), patch(
                        'apps.tenant_apps.loans.services.imported_ticket_preview.LoanDocumentLayoutService.resolve', return_value=layout):
                    content, name = render_imported_ticket_preview(loan=self.loan, actor=self.actor)
                    with fitz.open(stream=content, filetype='pdf') as pdf:
                        self.assertGreaterEqual(len(pdf), 1)
                        for page in pdf:
                            self.assertIn('RECONSTRUCTED IMPORT PREVIEW', page.get_text())
                    self.assertEqual(name, f'imported-ticket-{self.loan.pk}.pdf')
                self.assertEqual(before, self.snapshot())

    def test_route_button_no_cache_and_workspace_boundary(self):
        from apps.tenancy.testing import WorkspaceTestCase
        for workspace in (self.a, self.b):
            WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=workspace))
        self.enterContext(patch('django.templatetags.static.StaticNode.handle_simple', side_effect=lambda path: '/static/' + path))
        client = Client()
        client.force_login(self.actor)
        url = reverse('workspace_loans:pawn_imported_ticket_preview', args=[self.a.slug, self.loan.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 200, response.headers)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['X-Rokkad-Preview'], 'true')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(client.post(url).status_code, 405)
        wrong = client.get(reverse('workspace_loans:pawn_imported_ticket_preview', args=[self.b.slug, self.loan.pk]))
        self.assertEqual(wrong.status_code, 404)
        detail = client.get(reverse('workspace_loans:pawn_loan_detail', args=[self.a.slug, self.loan.pk]))
        self.assertContains(detail, 'Preview imported ticket PDF')
        self.assertNotContains(detail, 'A loan ticket is available after approval.')
        self.assertFalse(detail.context['can_print_ticket'])

        copy_url = reverse('workspace_loans:pawn_imported_ticket_copy', args=[self.a.slug, self.loan.pk])
        printed = client.get(copy_url)
        self.assertEqual(printed.status_code, 200)
        self.assertEqual(printed['X-Rokkad-Document-Kind'], 'imported-copy')
        self.assertNotIn('X-Rokkad-Preview', printed)
        self.assertIn('no-store', printed['Cache-Control'])
        self.assertEqual(client.post(copy_url).status_code, 405)
        self.assertEqual(client.get(reverse('workspace_loans:pawn_imported_ticket_copy', args=[self.b.slug, self.loan.pk])).status_code, 404)
        self.assertContains(detail, 'Print imported loan copy')

    def test_imported_copy_uses_small_footer_without_preview_watermark_or_writes(self):
        with self.scoped():
            before = self.snapshot()
            for mode in (None, 'ABSOLUTE_OVERLAY', 'FLOW'):
                revision = None if mode is None else SimpleNamespace(
                    definition=starter_layout('loan_ticket', schema_version=3 if mode == 'FLOW' else 4, layout_mode=mode).canonical_dict(),
                    assets=SimpleNamespace(all=lambda: []))
                with self.subTest(mode=mode), patch(
                        'apps.tenant_apps.loans.services.imported_ticket_preview.LoanDocumentLayoutService.resolve', return_value=revision):
                    content, name = render_imported_ticket_copy(loan=self.loan, actor=self.actor)
                    with fitz.open(stream=content, filetype='pdf') as pdf:
                        for page in pdf:
                            text = page.get_text()
                            self.assertIn('Reprinted from imported records', text)
                            self.assertNotIn('PREVIEW / NOT AN OFFICIAL ISSUE', text)
                            self.assertNotIn('RECONSTRUCTED IMPORT PREVIEW', text)
                        self.assertIn(self.review['source']['number'], ''.join(page.get_text() for page in pdf))
                    self.assertEqual(name, f'imported-loan-copy-{self.loan.pk}.pdf')
                    self.assertEqual(before, self.snapshot())

    def test_service_rejects_unauthorized_actor(self):
        with self.scoped(), self.assertRaises(PermissionDenied):
            render_imported_ticket_preview(loan=self.loan, actor=None)
        with self.scoped(), self.assertRaises(PermissionDenied):
            render_imported_ticket_copy(loan=self.loan, actor=None)

    def test_imported_guidance_remains_visible_with_a_saved_schedule(self):
        from django.template.loader import render_to_string
        html = render_to_string('loans/pawn/_print_guidance.html', {
            'loan': self.loan, 'request': SimpleNamespace(workspace=self.a),
            'can_preview_imported_ticket': True, 'can_print_ticket': False, 'can_print_schedule': True})
        self.assertIn('customer record', html)
        self.assertIn('Preview imported ticket PDF', html)
        self.assertIn('Key facts and repayment schedule', html)
        self.assertNotIn('A loan ticket describes approved terms', html)

    def test_changed_evidence_cannot_be_rendered(self):
        with self.scoped():
            self.loan.historical_import.source_sha256 = '0' * 64
            with self.assertRaisesMessage(ValueError, 'accepted source'):
                render_imported_ticket_preview(loan=self.loan, actor=self.actor)

    def test_unverified_source_valuation_is_not_promoted_to_appraisal(self):
        with self.scoped():
            opening = self.loan.loan_events.get(event_kind='MIGRATION_OPENING')
            from copy import deepcopy
            review = deepcopy(opening.payload['opening']['review'])
            review['collateral'][0]['valuation'] = {'status': 'UNVERIFIED', 'source_amount': '9999',
                'source_date': None, 'evidence_reference': 'Old undated source claim'}
            # In-memory evidence fixture; immutable production rows are not edited.
            document = {**self.origin.document, 'review': review}
            from apps.tenant_apps.loans.services.history_contract import digest
            self.loan.historical_import.document = document
            self.loan.historical_import.source_sha256 = digest(document)
            with patch('apps.tenant_apps.loans.services.imported_ticket_preview.read_opening_evidence',
                       return_value={**opening.payload['opening'], 'review': review}):
                _, source, _ = imported_ticket_payload(self.loan)
            self.assertIsNone(source['collateral'][0]['latest_appraised_value'])

    def test_series_picker_uses_prefix_instead_of_migration_code(self):
        with self.scoped():
            self.series.code = 'LINODE-1'
            self.series.save(update_fields=['code'])
            for prefix, label in [('WH', 'WH'), ('', 'No prefix')]:
                self.sequence.prefix = prefix
                self.sequence.save(update_fields=['prefix'])
                form = PawnDraftForm(workspace=self.a)
                choices = str(form['series'])
                self.assertIn('OLD-L / ' + label, choices)
                self.assertNotIn('LINODE-1', choices)

    def snapshot(self):
        return {model.__name__: list(model.objects.order_by('pk').values()) for model in (
            m.PawnLoan, m.PawnLoanEvent, m.PawnLoanApprovalSnapshot, m.LoanNumberSequence,
            m.LoanDocumentIssue, m.HistoricalLoanImport)}
