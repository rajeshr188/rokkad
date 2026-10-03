import copy
import csv
import io
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import Client, override_settings
from django.urls import reverse

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.loans.services.history_import import balance_values
from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
from apps.tenant_apps.data_portability import guided_openings as service, opening_register as register
from apps.tenant_apps.data_portability.guided_opening_views import template_bytes
from apps.tenant_apps.data_portability.models import GuidedOpeningBatch
from apps.tenant_apps.data_portability.parsers import PortabilityError, parse_source


def row(**changes):
    return dict(zip(register.COLUMNS, (
        'old-1', 'OLD00001', 'borrower-1', 'Fictional Borrower', '',
        '01/01/2021', '3', 'item-1', 'Two fictional gold rings', 'GOLD', '2',
        '10', '9', '75', '1000', '1000', '1', '10', '0', 'yes', 'yes',
    )), **changes)


def csv_bytes(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=register.COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


class GuidedOpeningTests(OpeningImportFixture):
    def setUp(self):
        super().setUp()
        self.base = {'workspace_id': self.a.pk, 'actor': self.actor}
        self.mapping = {'settings': {
            'revision_id': self.review['mapping']['licence_revision_id'], 'series_id': self.series.pk,
            'cutover': '2021-02-02', 'grace_days': 3, 'reference': 'Fictional register, reconciled 02/02/2021',
            'rule_confirmed': True,
        }, 'borrowers': {'borrower-1': 'NEW'}}

    def staged(self, rows=None, **changes):
        return service.stage(**{**self.base, 'source_key': 'fictional-ledger',
            'filename': 'fictional.csv', 'content': csv_bytes(rows or [row()]), **changes})

    def reviewed(self, batch=None, mapping=None):
        batch = batch or self.staged()
        result = service.preview(**self.base, batch_id=batch.public_id, mapping=mapping or self.mapping)
        self.assertEqual(result[0].preview['issues'], [])
        return result

    def admit(self, batch, token, **changes):
        return service.commit(**{**self.base, 'batch_id': batch.public_id, 'approval': token, 'confirmed': True, **changes})

    def test_preview_commit_replay_and_release_use_existing_financial_engine(self):
        with self.scoped():
            parties = Party.objects.count()
            products = m.LoanProduct.objects.count()
            batch, token = self.reviewed()
            self.assertEqual(Party.objects.count(), parties)
            self.assertEqual(m.LoanProduct.objects.count(), products)
            self.assertFalse(m.PawnLoan.objects.exists())
            self.assertEqual(batch.preview['totals'], {'principal': '1000', 'interest': '10', 'fees': '0'})
            result = self.admit(batch, token)
            self.assertEqual(result.state, 'COMPLETED')
            self.assertEqual(self.admit(batch, token).results, result.results)
            loan = m.PawnLoan.objects.get()
            self.assertEqual(loan.collateral_items.get().quantity, 2)
            self.assertEqual(list(loan.loan_events.values_list('event_kind', flat=True)), ['MIGRATION_OPENING'])
            self.assertFalse(m.PawnLoanDisbursalSnapshot.objects.exists())
            self.assertFalse(m.CollateralAppraisal.objects.exists())
            self.sequence.refresh_from_db()
            self.assertEqual(self.sequence.next_number, 1)
            self.assertEqual(balance_values(loan, date(2021, 2, 2)), {'principal': '1000', 'interest': '10', 'fees': '0'})
            with patch('django.utils.timezone.localdate', return_value=date(2021, 2, 3)):
                release_pawn_loan_in_full(loan.pk, settlement_amount=1010, request_key='guided-release', actor=self.actor)
            self.assertEqual(self.admit(batch, token).results, result.results)
            self.assertEqual(balance_values(loan, date(2021, 2, 3))['principal'], '0')

    def test_exact_file_reopens_and_changed_file_cannot_duplicate_source_debt(self):
        with self.scoped():
            batch, token = self.reviewed()
            self.assertEqual(self.staged(filename='renamed.csv').pk, batch.pk)
            self.admit(batch, token)
            self.assertEqual(self.staged().pk, batch.pk)
            changed = self.staged([row(description='Changed source item')])
            mapping = copy.deepcopy(self.mapping)
            mapping['borrowers']['borrower-1'] = Party.objects.get(display_name='Fictional Borrower').party_code
            changed, approval = service.preview(**self.base, batch_id=changed.public_id, mapping=mapping)
            self.assertIsNone(approval)
            self.assertTrue(changed.preview['issues'])
            self.assertEqual(m.PawnLoan.objects.count(), 1)

    def test_multiple_items_count_loan_balances_once(self):
        with self.scoped():
            batch, token = self.reviewed(self.staged([row(), row(item_ref='item-2')]))
            self.assertEqual(batch.preview['loans'], 1)
            self.assertEqual(batch.preview['totals'], {'principal': '2000', 'interest': '10', 'fees': '0'})
            self.admit(batch, token)
            self.assertEqual(m.PawnCollateralItem.objects.count(), 2)

    def test_later_batch_reuses_source_customer_and_holds_inactive_match(self):
        with self.scoped():
            batch, token = self.reviewed()
            self.admit(batch, token)
            party = Party.objects.get(display_name='Fictional Borrower')
            mapping = copy.deepcopy(self.mapping)
            mapping['borrowers']['borrower-1'] = party.party_code
            second = self.staged([row(loan_ref='old-2', loan_number='OLD00002')])
            second, token = self.reviewed(second, mapping)
            self.assertEqual(second.preview['borrowers']['borrower-1']['mode'], 'bound')
            self.admit(second, token)
            self.assertEqual(Party.objects.filter(display_name='Fictional Borrower').count(), 1)
            self.assertEqual(m.PawnLoan.objects.count(), 2)
            Party.objects.filter(pk=party.pk).update(status='INACTIVE')
            third = self.staged([row(loan_ref='old-3', loan_number='OLD00003')])
            third, token = service.preview(**self.base, batch_id=third.public_id, mapping=mapping)
            self.assertIsNone(token)
            self.assertIn('not active', third.preview['issues'][0]['message'])

    def test_commit_failure_on_second_loan_rolls_back_first_and_new_customer(self):
        with self.scoped():
            batch, token = self.reviewed(self.staged([row(), row(loan_ref='old-2', loan_number='OLD00002')]))
            parties = Party.objects.count()
            real = service.commit_opening_import
            calls = []
            def fail_second(**kwargs):
                calls.append(kwargs)
                if len(calls) == 2:
                    raise ValueError('Destination changed during commit')
                return real(**kwargs)
            with patch.object(service, 'commit_opening_import', side_effect=fail_second), self.assertRaises(PortabilityError):
                self.admit(batch, token)
            self.assertFalse(m.PawnLoan.objects.exists())
            self.assertEqual(Party.objects.count(), parties)
            self.assertFalse(m.LoanProduct.objects.filter(code__startswith='IMPORT-').exists())

    def test_number_collision_and_wrong_licence_series_are_held(self):
        with self.scoped():
            batch = self.staged([row(loan_number='H-00001')])
            batch, token = service.preview(**self.base, batch_id=batch.public_id, mapping=self.mapping)
            self.assertIsNone(token)
            self.assertTrue(batch.preview['issues'])
            self.assertFalse(m.PawnLoan.objects.exists())
            self.sequence.refresh_from_db()
            self.assertEqual(self.sequence.next_number, 1)

    def test_limits_and_missing_columns_rejected_before_staging(self):
        with self.scoped():
            with self.assertRaises(PortabilityError):
                self.staged([row(loan_ref=str(i)) for i in range(21)])
            with self.assertRaises(PortabilityError):
                self.staged(content=b'loan_ref,borrower_ref\nx,y\n')
            with self.assertRaises(PortabilityError):
                self.staged(source_key='different register')
            self.assertFalse(GuidedOpeningBatch.objects.exists())

    def test_bad_rows_hold_entire_batch_and_blank_is_not_zero(self):
        with self.scoped():
            parties = Party.objects.count()
            for changes in ({'outstanding_principal': '900'}, {'unpaid_fees': ''}, {'first_month_paid': 'no'},
                            {'in_vault': 'no'}, {'net_weight_g': ''}, {'unpaid_interest': '9999'}):
                with self.subTest(changes=changes):
                    batch = self.staged([row(), row(loan_ref='bad-2', loan_number='OLD00002', **changes)])
                    batch, token = service.preview(**self.base, batch_id=batch.public_id, mapping=self.mapping)
                    self.assertIsNone(token)
                    self.assertEqual(batch.state, 'STAGED')
                    self.assertEqual(len(batch.preview['issues']), 1)
                    self.assertEqual(Party.objects.count(), parties)
                    self.assertFalse(m.PawnLoan.objects.exists())

    def test_stale_customer_requires_review_and_rolls_back_every_loan(self):
        with self.scoped():
            party = self.source_party.identity.party
            mapping = copy.deepcopy(self.mapping)
            mapping['borrowers']['borrower-1'] = party.party_code
            batch, token = self.reviewed(mapping=mapping)
            Party.objects.filter(pk=party.pk).update(display_name='Changed after preview')
            with self.assertRaisesMessage(PortabilityError, 'changed after review'):
                self.admit(batch, token)
            self.assertFalse(m.PawnLoan.objects.exists())
            batch.refresh_from_db()
            self.assertEqual(batch.state, 'READY')

    def test_confirmation_expiry_tampering_and_foreign_workspace(self):
        with self.scoped():
            batch, token = self.reviewed()
            with self.assertRaises(PortabilityError):
                self.admit(batch, token, confirmed=False)
            with self.assertRaises(PortabilityError):
                self.admit(batch, token + 'changed')
            with patch('django.core.signing.time.time', return_value=9999999999), self.assertRaises(PortabilityError):
                self.admit(batch, token)
            with self.assertRaises(PermissionDenied):
                self.admit(batch, token, actor=self.other_actor)
        with self.scoped(self.b):
            self.assertFalse(GuidedOpeningBatch.objects.exists())
            with self.assertRaises(PermissionDenied):
                service.get_batch(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id)
            with self.assertRaises(DatabaseError), transaction.atomic():
                GuidedOpeningBatch.objects.bulk_create([GuidedOpeningBatch(workspace=self.a, source_key='forged', source_name='x.csv',
                    source_sha256='a' * 64, created_by=self.actor, document={'profile': register.PROFILE, 'rows': [[2, row()]]})])

    def test_source_and_completion_immutable_cancel_clears_private_rows(self):
        with self.scoped():
            batch, token = self.reviewed()
            for change in ({'document': {}}, {'workspace_id': self.b.pk}, {'source_sha256': 'b' * 64},
                           {'state': 'COMPLETED', 'results': []}):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    GuidedOpeningBatch.objects.filter(pk=batch.pk).update(**change)
            self.admit(batch, token)
            with self.assertRaises(DatabaseError), transaction.atomic():
                GuidedOpeningBatch.objects.filter(pk=batch.pk).update(preview={})
            pending = self.staged([row(loan_ref='other')])
            cancelled = service.cancel(**self.base, batch_id=pending.public_id, confirmed=True)
            self.assertEqual(cancelled.document, {})
            self.assertEqual(cancelled.mapping, {})
            self.assertEqual(cancelled.state, 'CANCELLED')

    def test_template_roundtrip_and_formula_rejection(self):
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(template_bytes()))
        ws = wb.active
        for col, value in enumerate(row().values(), 1):
            ws.cell(2, col, value)
        output = io.BytesIO()
        wb.save(output)
        with self.scoped():
            batch = self.staged(content=output.getvalue(), filename='register.xlsx')
            self.reviewed(batch)
        ws.cell(2, 15, '=1000')
        output = io.BytesIO()
        wb.save(output)
        with self.assertRaises(PortabilityError):
            parse_source(output.getvalue(), 'register.xlsx')

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
    def test_browser_owner_upload_preview_confirm_guide_and_csrf(self):
        WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.actor)
        kwargs = {'workspace_slug': self.a.slug}
        upload = reverse('workspace_portability:guided_upload', kwargs=kwargs)
        response = client.get(upload)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response.headers['Cache-Control'])
        csrf = client.cookies['csrftoken'].value
        self.assertEqual(client.post(upload, {}).status_code, 403)
        response = client.post(upload, {'csrfmiddlewaretoken': csrf, 'source_key': 'fictional-ledger',
            'file': SimpleUploadedFile('register.csv', csv_bytes([row()]), 'text/csv')})
        self.assertEqual(response.status_code, 302)
        detail = response.url
        self.assertContains(client.get(detail), 'Customer matches')
        data = {**self.mapping['settings'], 'mode_0': 'NEW', 'action': 'preview', 'csrfmiddlewaretoken': csrf}
        response = client.post(detail, data)
        self.assertContains(response, 'Import 1 existing loans')
        approval = response.context['approval']
        response = client.post(detail, {'action': 'commit', 'approval': approval, 'confirmed': 'yes', 'csrfmiddlewaretoken': csrf})
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get(detail), '1 existing loans imported.')
        self.assertEqual(client.get(reverse('workspace_portability:guided_template', kwargs=kwargs)).status_code, 200)
        self.assertEqual(client.get(reverse('workspace_portability:guided_guide', kwargs=kwargs)).status_code, 200)
