import hashlib
import uuid
from datetime import timedelta
from unittest.mock import patch

import fitz
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenant_apps.loans.models import (PledgeBook, PledgeBookReview, PledgeBookBatch, PledgeBookEntry, PawnLoan,
    PawnLoanApprovalSnapshot, PawnLoanEvent, LoanPolicySnapshot, PawnLoanDisbursalSnapshot)
from apps.tenant_apps.loans.selectors.pledge_activity import daily_activity
from apps.tenant_apps.loans.services.pledge_book import open_book, pending_report, review_entry, batch_plan, finalise_batch
from apps.tenant_apps.loans.tests.test_pledge_book import PledgeBookTests


class PledgeBatchTests(PledgeBookTests):
    def book(self, **overrides):
        self.book_data = dict(series=self.series.pk, title='Fictional book', layout='landscape_a4',
            starts_on=self.day, first_page=11, opening_note='Earlier paper register through prior day.', reviewed=True)
        self.book_data.update(overrides)
        return open_book(workspace=self.tenant, actor=self.actor, data=self.book_data)

    def review_data(self, book, **overrides):
        row = pending_report(book, actor=self.actor, cutoff=self.today).entries[0]
        data = dict(request_key=uuid.uuid4().hex, basis_sha256=row['basis_sha256'],
            source_reference='Original ticket TEST/1', notes='Missing original owner declaration remains unresolved; no invented facts.',
            borrower='Original example pawner', address='1 Original Street', reviewed=True)
        data.update(overrides)
        return data

    def reviewed_book(self, **overrides):
        book = self.book(**overrides)
        self.review_values = self.review_data(book)
        review_entry(workspace=self.tenant, actor=self.actor, book_id=book.pk, loan_id=self.loan.pk, data=self.review_values)
        return book

    def batch_data(self, book, **overrides):
        mode = overrides.get('mode', 'partial')
        plan = batch_plan(book, actor=self.actor, cutoff=self.today, mode=mode)
        data = dict(cutoff=self.today, mode=mode, request_key=uuid.uuid4().hex, review_sha256=plan['review_sha256'], reviewed=True)
        data.update(overrides)
        return data

    def finalise(self, book, data=None):
        return finalise_batch(workspace=self.tenant, actor=self.actor, book_id=book.pk, data=data or self.batch_data(book))

    def add_loan(self, number, day=None):
        day = day or self.day
        loan = PawnLoan.objects.create(workspace=self.tenant, license=self.license, series=self.series,
            product_version=self.loan.product_version, borrower=self.borrower, loan_number=number,
            state='ACTIVE', principal_amount='10000', monthly_interest_rate='2', loan_date=day,
            tenure_months=12, created_by=self.actor, updated_by=self.actor)
        approval = PawnLoanApprovalSnapshot.objects.create(loan=loan, version=1, approved_by=self.actor,
            fingerprint='b'*64, payload={**self.approval.payload, 'loan_number': number})
        event = PawnLoanEvent.objects.create(loan=loan, event_kind='DISBURSAL', effective_date=day,
            payload={'values': {'principal': '10000'}}, payload_fingerprint='b'*64, idempotency_key=uuid.uuid4().hex, created_by=self.actor)
        policy = LoanPolicySnapshot.objects.create(loan=loan, interest_method='SIMPLE', partial_month_method='FULL_MONTH',
            valuation_method='LATEST_APPRAISAL', rounding_method='PER_ACCRUAL_PERIOD')
        PawnLoanDisbursalSnapshot.objects.create(loan=loan, approval_snapshot=approval, policy_snapshot=policy,
            loan_event=event, gross_principal='10000', monthly_interest='200', advance_interest='0',
            deducted_fees='0', net_disbursed='10000', evidence={'fixture': 'test'}, created_by=self.actor)
        return loan

    def review_pending(self, book):
        for row in pending_report(book, actor=self.actor, cutoff=self.today).entries:
            review_entry(workspace=self.tenant, actor=self.actor, book_id=book.pk, loan_id=row['loan_id'], data=dict(
                basis_sha256=row['basis_sha256'], request_key=uuid.uuid4().hex, source_reference='Paper TEST',
                notes='Original gaps remain explicit for follow-up.', reviewed=True))

    def test_full_batch_leaves_partial_pending_and_late_loan_uses_next_page(self):
        book = self.book(starts_on=self.day-timedelta(days=1))
        for i in range(2, 7):
            self.add_loan(f'{i:05d}')
        self.review_pending(book)
        batch = self.finalise(book, self.batch_data(book, mode='full'))
        self.assertEqual(batch.entries.count(), 5)
        self.assertEqual((batch.first_page, batch.last_page), (11, 11))
        self.assertEqual(len(pending_report(book, actor=self.actor, cutoff=self.today).entries), 1)
        partial = self.finalise(book)
        self.assertEqual((partial.first_page, partial.last_page), (12, 12))
        late = self.add_loan('EARLIER', day=self.day-timedelta(days=1))
        self.review_pending(book)
        late_batch = self.finalise(book)
        self.assertEqual((late_batch.first_page, late_batch.last_page), (13, 13))
        self.assertEqual(late_batch.snapshot['entries'][0]['date'], late.loan_date.isoformat())
        self.assertEqual(pending_report(book, actor=self.actor, cutoff=self.today).excluded_count, 0)

    def test_missing_or_changed_artifact_is_not_regenerated_and_inventory_keeps_it(self):
        from apps.orgs.services.storage_references import collect_references, validate_coverage
        book = self.reviewed_book(); batch = self.finalise(book)
        validate_coverage()
        self.assertIn((self.tenant.pk, 'issued_documents'), collect_references([self.tenant.pk])[batch.artifact.name])
        client = self.make_workspace_client(); client.force_login(self.actor)
        url = reverse('workspace_loans:pledge_book_download', args=[self.tenant.slug, book.pk, batch.pk])
        with batch.artifact.storage.open(batch.artifact.name, 'wb') as file:
            file.write(b'Changed bytes')
        self.assertEqual(client.get(url).status_code, 409)
        batch.artifact.storage.delete(batch.artifact.name)
        self.assertEqual(client.get(url).status_code, 404)

    def test_sql_rejects_page_overlap_and_duplicate_loan_entries(self):
        book = self.reviewed_book(); batch = self.finalise(book)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PledgeBookBatch.objects.bulk_create([PledgeBookBatch(workspace=self.tenant, book=book,
                first_page=batch.first_page, last_page=batch.last_page, cutoff=self.today, mode='partial',
                snapshot={'test': True}, snapshot_sha256='a'*64, review_sha256='a'*64,
                artifact='fake.pdf', artifact_sha256='a'*64, template_version='test', request_key='overlap', created_by=self.actor)])
        entry = PledgeBookEntry.objects.get(loan=self.loan)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PledgeBookEntry.objects.bulk_create([PledgeBookEntry(workspace=self.tenant, batch=batch, loan=self.loan,
                first_page=entry.first_page, last_page=entry.last_page, created_by=self.actor)])

    def test_book_duplicate_setup_is_safe_and_cannot_change_layout(self):
        book = self.book()
        self.assertEqual(open_book(workspace=self.tenant, actor=self.actor, data=self.book_data).pk, book.pk)
        with self.assertRaises(ValueError):
            open_book(workspace=self.tenant, actor=self.actor, data={**self.book_data, 'layout': 'facing_a4'})
        self.assertFalse(PledgeBookBatch.objects.exists())

    def test_source_review_required_and_gaps_preserved(self):
        book = self.book()
        with self.assertRaisesMessage(ValueError, 'source review'):
            self.finalise(book)
        data = self.review_data(book)
        review = review_entry(workspace=self.tenant, actor=self.actor, book_id=book.pk, loan_id=self.loan.pk, data=data)
        self.assertEqual(review_entry(workspace=self.tenant, actor=self.actor, book_id=book.pk, loan_id=self.loan.pk, data=data).pk, review.pk)
        with self.assertRaises(ValueError):
            review_entry(workspace=self.tenant, actor=self.actor, book_id=book.pk, loan_id=self.loan.pk, data={**data, 'notes': 'Changed'})
        batch = self.finalise(book)
        self.assertEqual(batch.snapshot['entries'][0]['owner'], 'Not recorded')
        self.assertIn('unresolved', ' '.join(batch.snapshot['entries'][0]['warnings']))
        self.assertEqual(batch.snapshot['entries'][0]['borrower'], 'Original example pawner')

    def test_known_fields_cannot_be_overridden_and_new_source_invalidates_review(self):
        book = self.reviewed_book()
        with self.assertRaisesMessage(ValueError, 'frozen evidence'):
            review_entry(workspace=self.tenant, actor=self.actor, book_id=book.pk, loan_id=self.loan.pk,
                data=self.review_data(book, tenure='999 months'))
        self.ticket()
        self.assertIsNone(pending_report(book, actor=self.actor, cutoff=self.today).entries[0]['review_id'])

    def test_exact_reprint_retry_hash_and_page_mapping(self):
        book = self.reviewed_book()
        data = self.batch_data(book)
        batch = self.finalise(book, data)
        self.assertEqual(self.finalise(book, data).pk, batch.pk)
        with self.assertRaisesMessage(ValueError, 'changed'):
            self.finalise(book, {**data, 'request_key': uuid.uuid4().hex})
        with self.assertRaisesMessage(ValueError, 'different details'):
            self.finalise(book, {**data, 'mode': 'full'})
        self.assertEqual(PledgeBookBatch.objects.count(), 1)
        self.assertEqual((batch.first_page, batch.last_page), (11, 11))
        entry = PledgeBookEntry.objects.get(loan=self.loan)
        self.assertEqual((entry.first_page, entry.last_page), (11, 11))
        self.assertEqual(pending_report(book, actor=self.actor, cutoff=self.today).entries, [])
        with batch.artifact.open('rb') as file:
            original = file.read()
        self.assertEqual(hashlib.sha256(original).hexdigest(), batch.artifact_sha256)
        with fitz.open(stream=original, filetype='pdf') as doc:
            self.assertIn('Page 11', doc[0].get_text())
            self.assertNotIn('WORKING PREVIEW', doc[0].get_text())
        self.event('REPAYMENT', self.today, {'principal': '0', 'interest': '100', 'fees': '0'})
        with patch('apps.tenant_apps.loans.documents.pledge_book.render_pledge_book', side_effect=AssertionError('Must not regenerate')):
            client = self.make_workspace_client(); client.force_login(self.actor)
            response = client.get(reverse('workspace_loans:pledge_book_download', args=[self.tenant.slug, book.pk, batch.pk]))
        self.assertEqual(response.content, original)
        self.assertIn('no-store', response['Cache-Control'])

    def test_facing_sheets_receive_distinct_numbers(self):
        book = self.reviewed_book(layout='facing_a4')
        batch = self.finalise(book)
        self.assertEqual((batch.first_page, batch.last_page), (11, 12))
        entry = PledgeBookEntry.objects.get(loan=self.loan)
        self.assertEqual((entry.first_page, entry.last_page), (11, 12))

    def test_partial_mode_and_stale_review_protect_allocation(self):
        book = self.reviewed_book()
        full = self.batch_data(book, mode='full')
        with self.assertRaisesMessage(ValueError, 'No full pages'):
            self.finalise(book, full)
        data = self.batch_data(book)
        self.event('REPAYMENT', self.today, {'principal': '0', 'interest': '100', 'fees': '0'})
        with self.assertRaisesMessage(ValueError, 'changed'):
            self.finalise(book, data)
        self.assertFalse(PledgeBookBatch.objects.exists())
        batch = self.finalise(book)
        self.assertEqual(batch.first_page, 11)

    def test_render_failure_consumes_no_page_and_no_entry(self):
        book = self.reviewed_book()
        with patch('apps.tenant_apps.loans.services.pledge_book.render_pledge_book', side_effect=ValueError('render failed')):
            with self.assertRaisesMessage(ValueError, 'render failed'):
                self.finalise(book)
        self.assertFalse(PledgeBookBatch.objects.exists())
        self.assertFalse(PledgeBookEntry.objects.exists())
        self.assertEqual(self.finalise(book).first_page, 11)

    def test_database_failure_compensates_new_file_and_rolls_back_pages(self):
        from django.core.files.storage import default_storage
        book = self.reviewed_book()
        with patch('apps.tenant_apps.loans.services.pledge_book.PledgeBookEntry.objects.create', side_effect=ValueError('entry failed')), patch.object(default_storage, 'delete', wraps=default_storage.delete) as delete:
            with self.assertRaisesMessage(ValueError, 'entry failed'):
                self.finalise(book)
            self.assertEqual(delete.call_count, 1)
            self.assertFalse(default_storage.exists(delete.call_args.args[0]))
        self.assertFalse(PledgeBookBatch.objects.exists())
        self.assertEqual(self.finalise(book).first_page, 11)

    def test_daily_activity_recorded_date_finds_late_closure_and_reference(self):
        book = self.reviewed_book()
        batch = self.finalise(book)
        receipt = self.event('RELEASE_RECEIPT', self.day + timedelta(days=1), {'principal': '10000', 'interest': '100', 'fees': '0'})
        rows = daily_activity(book, actor=self.actor, start=self.today, end=self.today)
        row = next(r for r in rows if r['event'].pk == receipt.pk)
        self.assertTrue(row['late']); self.assertFalse(row['included'])
        self.assertIn('pages 11-11', row['reference'])
        self.assertIn('10,100', row['detail'])
        self.assertEqual(daily_activity(book, actor=self.actor, start=self.today, end=self.today, basis='business'), [])
        reversal = self.event('REVERSAL', self.today, {'principal': '10000'}, reversal_of=receipt)
        self.assertTrue(any('Reversal of event' in r['detail'] for r in daily_activity(book, actor=self.actor, start=self.today, end=self.today)))

    def test_ui_open_review_save_download_and_csrf(self):
        from apps.tenancy.testing import WorkspaceClient
        book = self.book()
        client = self.make_workspace_client(); client.force_login(self.actor)
        url = reverse('workspace_loans:pledge_book_detail', args=[self.tenant.slug, book.pk])
        self.assertContains(client.get(url), 'Needs source review')
        review_url = reverse('workspace_loans:pledge_book_review', args=[self.tenant.slug, book.pk, self.loan.pk])
        self.assertContains(client.get(review_url), 'Review original evidence')
        self.assertEqual(client.post(review_url, self.review_data(book)).status_code, 302)
        response = client.get(url)
        self.assertContains(response, 'Source reviewed')
        data = self.batch_data(book)
        csrf_client = WorkspaceClient(self.tenant, enforce_csrf_checks=True); csrf_client.force_login(self.actor)
        self.assertEqual(csrf_client.post(url, data).status_code, 403)
        self.assertFalse(PledgeBookBatch.objects.exists())
        self.assertEqual(client.post(url, data).status_code, 302)
        self.assertContains(client.get(url), 'Print / exact reprint PDF')
        self.assertContains(client.get(reverse('workspace_loans:pledge_book_activity', args=[self.tenant.slug, book.pk])), 'Daily activity')

    def test_member_and_expired_workspace_cannot_finalise(self):
        book = self.reviewed_book()
        member = get_user_model().objects.create_user(username='pledge-member')
        role, _ = Role.objects.get_or_create(name='Member')
        Membership.objects.create(company=self.tenant, user=member, role=role)
        with self.assertRaises(PermissionDenied):
            finalise_batch(workspace=self.tenant, actor=member, book_id=book.pk, data=self.batch_data(book))
        from apps.tenancy.testing import expire_workspace_trial
        expire_workspace_trial(self.tenant, days_ago=30)
        with self.assertRaises(PermissionDenied):
            self.finalise(book)

    def test_sql_immutability_and_cross_parent_rls(self):
        book = self.reviewed_book(); batch = self.finalise(book)
        review = PledgeBookReview.objects.get(loan=self.loan)
        entry = PledgeBookEntry.objects.get(loan=self.loan)
        models = (PledgeBook, PledgeBookReview, PledgeBookBatch, PledgeBookEntry)
        for model, row in zip(models, (book, review, batch, entry)):
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.filter(pk=row.pk).update(created_by=self.actor)
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(f'DELETE FROM {model._meta.db_table} WHERE id=%s', [row.pk])
        name = 'pledge_rls_' + uuid.uuid4().hex[:12]
        other = Company.objects.create(name='Other book', schema_name=name, owner=self.actor, creator=self.actor)
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {name} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {name}')
            cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {name}')
            cursor.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {name}')
            cursor.execute(f'SET LOCAL ROLE {name}')
            cursor.execute("SELECT set_config('app.workspace_id', %s, true)", [str(other.pk)])
            for model in models:
                self.assertFalse(model.objects.exists())
            with self.assertRaises(DatabaseError), transaction.atomic():
                PledgeBookReview.objects.bulk_create([PledgeBookReview(workspace=other, loan=self.loan, basis_sha256='a'*64,
                    source_reference='forged', notes='forged', created_by=self.actor, request_key='foreign')])
            cursor.execute("SELECT set_config('app.workspace_id', '', true)")
            for model in models:
                self.assertFalse(model.objects.exists())
            cursor.execute('RESET ROLE')
            cursor.execute(f'DROP OWNED BY {name}'); cursor.execute(f'DROP ROLE {name}')
