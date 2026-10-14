"""Actual guarded financial restores through staged files and browser review."""
from copy import deepcopy
from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4
from io import BytesIO
import json
import hashlib
from zipfile import ZipFile, ZIP_DEFLATED

from django.core.exceptions import PermissionDenied
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.db import connection
from django.test import override_settings
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.history_contract import HistoryError, encode
from apps.tenant_apps.loans.services.closed_position_contract import encode as encode_closed
from apps.tenant_apps.loans.tests.test_opening_restore import OpeningRestoreTests
from apps.tenant_apps.loans.tests.test_servicing_bundle import ServicingBundleTests
from apps.tenant_apps.data_portability import loan_restore
from apps.tenant_apps.data_portability.models import LoanRestoreBatch
from apps.tenant_apps.data_portability.tests.test_loan_history import document as history_document
from apps.tenant_apps.data_portability.loan_restore_views import DestinationForm
from apps.orgs.services.storage_references import validate_coverage, collect_references
from apps.tenant_apps.data_portability.tests.test_loan_archive import document as archive_document
from apps.tenant_apps.loans.services.history_contract import digest, dump


class LoanFileRestoreTests(OpeningRestoreTests):
    bundle_source = ServicingBundleTests.bundle_source

    def setUp(self):
        super().setUp()
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.storage_settings = override_settings(MEDIA_ROOT=self.media.name,
            STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
                      'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
        self.storage_settings.enable()
        self.addCleanup(self.storage_settings.disable)
        self.file_args = dict(workspace_id=self.b.pk, actor=self.actor)

    def closed_file(self):
        return encode_closed(dict(profile='loan-closed-position/1',
            source=dict(namespace=str(uuid4()), system='paper', loan_id='closed-1'),
            loan=dict(number='P-0001', borrower_reference=dict(system=self.review['mapping']['borrower_source_system'], id='old-1'),
                original_date=None, closed_on=None, original_principal=None, monthly_rate=None, tenure_months=None),
            position=dict(state='CLOSED', as_of='2021-02-02', currency='INR', principal='0', interest='0', fees='0',
                custody='RETURNED_TO_BORROWER', basis='OWNER_CLOSED_POSITION', evidence_reference='Checked source closing position'),
            earlier_history='UNAVAILABLE', retained_evidence=None))

    def run_file(self, content, mapping):
        batch = loan_restore.stage(**self.file_args, content=content)
        self.assertEqual(loan_restore.stage(**self.file_args, content=content).pk, batch.pk)
        token = loan_restore.preview(**self.file_args, batch_id=batch.public_id, values=mapping)
        self.assertFalse(m.PawnLoan.objects.exists())
        result = loan_restore.commit(**self.file_args, batch_id=batch.public_id, approval=token, confirmed=True)
        self.assertEqual(result.state, 'COMPLETED')
        self.assertEqual(loan_restore.commit(**self.file_args, batch_id=batch.public_id, approval=token, confirmed=True).results, result.results)
        self.assertEqual(m.PawnLoan.objects.count(), len(result.results))
        return result

    def test_file_opening_roundtrip_and_nonposting_review(self):
        content = self.source()
        key = loan_restore.classify(content)[1]['loans'][0]['key']
        with self.scoped(self.b):
            batch = self.run_file(content, {key:self.mapping})
            self.assertEqual(m.PawnLoan.objects.get(pk=batch.results[0]).state, 'ACTIVE')

    def test_file_servicing_roundtrip_and_nonposting_review(self):
        with patch('django.utils.timezone.localdate', return_value=date(2021,2,2)):
            origin, content = self.bundle_source()
            with self.scoped(self.b):
                batch = self.run_file(content, {str(origin.loan_id):self.mapping})
                self.assertEqual(batch.profile, 'loan-servicing-bundle/1')

    def test_file_closed_position_keeps_absent_terms_and_no_cash_history(self):
        with self.scoped(self.b):
            batch = self.run_file(self.closed_file(), {'position':{k:self.mapping[k] for k in ('borrower_id','series_id')}})
            loan = m.PawnLoan.objects.get(pk=batch.results[0])
            self.assertIsNone(loan.principal_amount)
            self.assertIsNone(loan.product_version_id)
            self.assertEqual(loan.loan_events.count(), 1)
            self.assertFalse(loan.releases.exists())
            self.assertFalse(loan.disbursal_snapshots.exists())
            with transaction.atomic(), self.assertRaises(DatabaseError):
                LoanRestoreBatch.objects.filter(pk=batch.pk).update(state='STAGED')

    def test_closed_zip_preserves_verified_source_and_exact_media(self):
        value = json.loads(self.closed_file())
        retained = archive_document()
        retained['source'].update(value['source'])
        retained['facts'].update(loan_number=value['loan']['number'], borrower_reference=value['loan']['borrower_reference'],
            opened_on=None, closed_on=None, original_principal=None, reported_balance='0')
        value['retained_evidence'] = retained
        image = b'preserved source image bytes'
        checksum = hashlib.sha256(image).hexdigest()
        claims = [dict(sha256=checksum, size=len(image), name='source.png', mime_type='image/png',
            source_evidence=dict(verified_source_file=dict(sha256=checksum)))]
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('position.json', encode_closed(value))
            archive.writestr('manifest.json', dump(dict(profile='loan-closed-position-bundle/1', position_sha256=digest(value),
                media=claims, earlier_history='UNAVAILABLE', financial_actions=[])))
            archive.writestr('media/'+checksum, image)
        with self.scoped(self.b):
            batch = self.run_file(output.getvalue(), {'position':{k:self.mapping[k] for k in ('borrower_id','series_id')}})
            loan = m.PawnLoan.objects.get(pk=batch.results[0])
            attachment = loan.historical_import.archive_evidence.attachments.get()
            with attachment.file.open('rb') as stream:
                self.assertEqual(stream.read(), image)
            self.assertFalse(loan.releases.exists())

    def test_file_tamper_and_changed_mapping_are_rejected_before_finance(self):
        with self.scoped(self.b):
            batch = loan_restore.stage(**self.file_args, content=self.closed_file())
            mapping = {'position':{k:self.mapping[k] for k in ('borrower_id','series_id')}}
            token = loan_restore.preview(**self.file_args, batch_id=batch.public_id, values=mapping)
            with batch.source.storage.open(batch.source.name, 'wb') as stream:
                stream.write(b'changed')
            with self.assertRaisesMessage(HistoryError, 'staged source changed'):
                loan_restore.commit(**self.file_args, batch_id=batch.public_id, approval=token, confirmed=True)
            self.assertFalse(m.PawnLoan.objects.exists())

    def test_restore_scope_and_database_source_immutability(self):
        with self.scoped(self.b):
            batch = loan_restore.stage(**self.file_args, content=self.closed_file())
            with transaction.atomic(), self.assertRaises(DatabaseError):
                LoanRestoreBatch.objects.filter(pk=batch.pk).update(source='another-file')
            with transaction.atomic(), self.assertRaises(DatabaseError):
                LoanRestoreBatch.objects.filter(pk=batch.pk).update(workspace_id=self.a.pk)
            from importlib import import_module
            reverse = import_module('apps.tenant_apps.data_portability.migrations.0020_loan_restore_batch').Migration.operations[-1].reverse_sql
            with self.assertRaisesMessage(DatabaseError, 'retained batches exist'), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(reverse)
        with self.scoped(self.a):
            self.assertFalse(LoanRestoreBatch.objects.exists())
            with self.assertRaises(PermissionDenied):
                loan_restore.get_batch(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id)

    def test_file_cancellation_removes_source_and_stale_approval_cannot_post(self):
        with self.scoped(self.b):
            batch = loan_restore.stage(**self.file_args, content=self.closed_file())
            token = loan_restore.preview(**self.file_args, batch_id=batch.public_id,
                values={'position':{k:self.mapping[k] for k in ('borrower_id','series_id')}})
            name, storage = batch.source.name, batch.source.storage
            self.assertIn(name, collect_references([self.b.pk]))
            with self.captureOnCommitCallbacks(execute=True):
                loan_restore.cancel(**self.file_args, batch_id=batch.public_id, confirmed=True)
            self.assertFalse(storage.exists(name))
            with self.assertRaises(PermissionDenied):
                loan_restore.commit(**self.file_args, batch_id=batch.public_id, approval=token, confirmed=True)
            self.assertFalse(m.PawnLoan.objects.exists())
            validate_coverage()

    def test_classifier_rejects_duplicates_unknown_and_expanded_zip_bounds(self):
        for content in (b'SELECT 1;', b'\xef\xbb\xbf', b'{"profile":"ordinary-loans-native-recovery/1"}',
                        b'{"profile":"loan-closed-position/1","profile":"loan-history/1"}'):
            with self.assertRaises(HistoryError):
                loan_restore.classify(content)
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', b'{"profile":"loan-servicing-bundle/1"}')
            archive.writestr('files/bomb', b'x'*(loan_restore.MAX_BYTES+1))
        with self.assertRaisesMessage(HistoryError, 'expanded'):
            loan_restore.classify(output.getvalue())
        self.assertEqual(loan_restore.classify(encode(history_document()))[0], 'loan-history/1')

    def test_preparation_does_not_approve_and_changed_mapping_cannot_commit(self):
        with self.scoped(self.b):
            batch = loan_restore.stage(**self.file_args, content=self.closed_file())
            values = {'position':{k:self.mapping[k] for k in ('borrower_id','series_id')}}
            prepared = loan_restore.prepare(**self.file_args, batch_id=batch.public_id, values=values)
            self.assertEqual(prepared.state, 'STAGED')
            self.assertFalse(prepared.preview)
            self.assertFalse(m.PawnLoan.objects.exists())
            token = loan_restore.preview(**self.file_args, batch_id=batch.public_id, values=values)
            with self.assertRaises(HistoryError):
                loan_restore.commit(**self.file_args, batch_id=batch.public_id, approval=token)
            changed = deepcopy(values)
            changed['position']['series_id'] = self.series.pk
            LoanRestoreBatch.objects.filter(pk=batch.pk).update(mapping=changed)
            with self.assertRaisesMessage(HistoryError, 'mappings changed'):
                loan_restore.commit(**self.file_args, batch_id=batch.public_id, approval=token, confirmed=True)
            self.assertFalse(m.PawnLoan.objects.exists())

    def test_closed_browser_upload_mapping_review_confirm_and_tenant_choices(self):
        from types import SimpleNamespace
        from apps.tenancy.testing import WorkspaceTestCase
        WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.b))
        self.client.force_login(self.actor)
        upload = reverse('workspace_portability:loan_upload', kwargs={'workspace_slug':self.b.slug})
        with self.scoped(self.b):
            response = self.client.post(upload, {'source':SimpleUploadedFile('closed.json', self.closed_file())})
            self.assertEqual(response.status_code, 302)
            self.assertIn('/loans/restore/', response.url)
            batch = LoanRestoreBatch.objects.get()
            page = self.client.get(response.url)
            self.assertContains(page, 'Review loan records')
            self.assertNotContains(page, 'name="loan-position-product_version_id"')
            self.assertNotContains(page, batch.source.name)
            values = {'action':'preview', 'loan-position-borrower_id':self.mapping['borrower_id'], 'loan-position-series_id':self.mapping['series_id']}
            page = self.client.post(response.url, values)
            self.assertContains(page, 'Confirm loan import')
            self.assertFalse(m.PawnLoan.objects.exists())
            token = page.context['approval']
            done = self.client.post(response.url, {'action':'commit','approval':token,'confirmed':'yes'})
            self.assertEqual(done.status_code, 302)
            self.assertContains(self.client.get(done.url), 'The supported records were restored')
            form = DestinationForm(workspace=self.b, closed_position=True)
            self.assertFalse(form.fields['series_id'].queryset.filter(pk=self.series.pk).exists())
            catalog = self.client.get(upload)
            self.assertContains(catalog, 'Supported imports and their coverage')
            self.assertContains(catalog, 'complete Workspace package is not yet available')

    def test_browser_customer_search_includes_inactive_and_binds_workspace_url(self):
        from types import SimpleNamespace
        from apps.tenancy.testing import WorkspaceTestCase
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.party.widgets import PartyAutocompleteWidget
        WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.b))
        with self.scoped(self.b):
            Party.objects.filter(pk=self.mapping['borrower_id']).update(display_name='Inactive imported borrower', status='INACTIVE')
        self.client.force_login(self.actor)
        url = reverse('workspace_portability:restore_borrowers', kwargs={'workspace_slug':self.b.slug})
        token = signing.dumps(url, salt=PartyAutocompleteWidget.token_salt)
        response = self.client.get(url, {'field_id':token,'term':'Inactive imported'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()['results']], [self.mapping['borrower_id']])
        other = reverse('workspace_portability:restore_borrowers', kwargs={'workspace_slug':self.a.slug})
        self.assertEqual(self.client.get(url, {'field_id':signing.dumps(other,salt=PartyAutocompleteWidget.token_salt)}).status_code, 404)
        self.client.force_login(self.other_actor)
        denied = self.client.get(url, {'field_id':token,'term':'Inactive imported'})
        self.assertIn(denied.status_code, (302,403,404))
        self.assertNotIn(b'Inactive imported borrower', denied.content)
