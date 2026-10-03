import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import fitz
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Membership, Role
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import (
    LoanLicense, LoanSeries, LoanNumberSequence, PawnLoan, PawnLoanApprovalSnapshot,
    PawnLoanDisbursalSnapshot, PawnLoanEvent, LoanPolicySnapshot, LoanDocumentIssue,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.loans.selectors.pledge_book import pledge_book_report, _entry
from apps.tenant_apps.loans.documents.pledge_book import render_pledge_book


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class PledgeBookTests(WorkspaceTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        tenant.owner = get_user_model().objects.create_user(username='pledge-owner-' + uuid.uuid4().hex[:8])
        tenant.creator = tenant.owner
        tenant.name = 'Fictional register workspace'

    def setUp(self):
        super().setUp()
        self.actor = self.tenant.owner
        role, _ = Role.objects.get_or_create(name='Owner')
        Membership.objects.get_or_create(user=self.actor, company=self.tenant, defaults={'role': role})
        self.start_active_trial()
        self.today = timezone.localdate()
        self.day = self.today - timedelta(days=10)
        self.license = LoanLicense.objects.create(workspace=self.tenant, name='Test licence', license_number='TEST-E', issued_on=self.day - timedelta(days=100), expires_on=self.today + timedelta(days=300))
        self.series = LoanSeries.objects.create(license=self.license, name='Legacy label', code='X')
        LoanNumberSequence.objects.create(series=self.series, document_kind='PAWN_LOAN', prefix='', width=5, maximum_number=99999)
        self.borrower = Party.objects.create(display_name='Current mutable name')
        self.loan = PawnLoan.objects.create(workspace=self.tenant, license=self.license, series=self.series,
            product_version=ensure_test_product_version(self.tenant), borrower=self.borrower, loan_number='00001',
            state='ACTIVE', principal_amount='10000', monthly_interest_rate='2', loan_date=self.day,
            tenure_months=12, created_by=self.actor, updated_by=self.actor)
        self.approval = PawnLoanApprovalSnapshot.objects.create(loan=self.loan, version=1, approved_by=self.actor,
            fingerprint='a'*64, payload={'loan_number':'00001','principal_amount':'10000','tenure_months':12,'monthly_interest_rate':'2',
                'collateral':[{'description':'Original gold ring','metal':'GOLD','quantity':2,'gross_weight':'3','net_weight':'2.8','latest_appraised_value':'20000','monthly_interest_rate':'2'}]})
        self.origin = self.event('DISBURSAL', self.day, {'principal':'10000','net_cash':'9800','advance_interest':'200','fees':'0'})
        policy = LoanPolicySnapshot.objects.create(loan=self.loan, interest_method='SIMPLE', partial_month_method='FULL_MONTH',
            valuation_method='LATEST_APPRAISAL', rounding_method='PER_ACCRUAL_PERIOD')
        PawnLoanDisbursalSnapshot.objects.create(loan=self.loan, approval_snapshot=self.approval, policy_snapshot=policy,
            loan_event=self.origin, gross_principal='10000', monthly_interest='200', advance_interest='200',
            deducted_fees='0', net_disbursed='9800', evidence={'fixture':'frozen'}, created_by=self.actor)

    def event(self, kind, day, values, **extra):
        return PawnLoanEvent.objects.create(loan=self.loan, event_kind=kind, effective_date=day,
            payload={'values':values, **extra.pop('payload', {})}, payload_fingerprint=uuid.uuid4().hex*2,
            idempotency_key=uuid.uuid4().hex, created_by=self.actor, **extra)

    def report(self, **overrides):
        values=dict(workspace=self.tenant, actor=self.actor, license_id=self.license.pk, start=self.day, end=self.today, cutoff=self.today)
        values.update(overrides)
        return pledge_book_report(**values)

    def ticket(self):
        return LoanDocumentIssue.objects.create(workspace=self.tenant, document_type='loan_ticket', source_type='PawnLoan',
            source_id=str(self.loan.pk), source_fingerprint='a'*64, payload_schema_version=2, payload_hash='b'*64,
            pdf_hash='c'*64, artifact='fictional.pdf', issued_by=self.actor,
            source_snapshot={'schema_version':2, 'workspace_id':self.tenant.pk, 'approval_id':self.approval.pk,
                'fields':{'borrower.name':'Frozen original name','borrower.address':'1 Original Street'}})

    def test_paid_evidence_and_closed_loans_retained_unpaid_approval_excluded(self):
        PawnLoan.objects.filter(pk=self.loan.pk).update(state='CLOSED')
        self.loan.pk=None; self.loan.loan_number='00002'; self.loan.state='APPROVED'
        self.loan.disbursal_snapshot=None; self.loan.policy_snapshot=None; self.loan.save()
        report=self.report()
        self.assertEqual([e['number'] for e in report.entries], ['00001'])
        self.assertEqual(report.excluded_count, 1)

    def test_original_snapshot_not_mutable_name_or_amount(self):
        self.ticket()
        PawnLoan.objects.filter(pk=self.loan.pk).update(principal_amount='12345', monthly_interest_rate='4')
        row=self.report().entries[0]
        self.assertEqual(row['borrower'], 'Frozen original name')
        self.assertEqual(row['address'], '1 Original Street')
        self.assertEqual(row['principal'], 'Rs 10,000')
        self.assertIn('2% / month', row['rates'])
        self.assertIn('Original gold ring', row['descriptions'])

    def test_missing_identity_and_ownership_are_not_guessed(self):
        row=self.report().entries[0]
        self.assertEqual(row['borrower'], 'Not recorded')
        self.assertEqual(row['owner'], 'Not recorded')
        self.assertNotIn(self.borrower.display_name, str(row))
        self.assertIn('original', str(row['warnings']).lower())

    def test_each_payment_and_reversal_preserved_without_counting_concession_as_cash(self):
        payment=self.event('REPAYMENT', self.day + timedelta(days=1), {'principal':'100','interest':'20','fees':'5'})
        self.event('RELEASE_RECEIPT', self.day + timedelta(days=2), {'principal':'9900','interest':'80','fees':'0','interest_concession':'10'})
        self.event('REVERSAL', self.day + timedelta(days=3), {'principal':'100','interest':'20','fees':'5'}, reversal_of=payment)
        row=self.report().entries[0]
        self.assertIn('REVERSED', row['payments'])
        self.assertIn('Rs 125', row['payments'])
        self.assertIn('Rs 9,980', row['payments'])
        self.assertIn('concession Rs 10', row['payments'])
        self.assertNotIn('Rs 9,990', row['payments'])
        self.assertIn('Redemption', row['closures'])
        earlier=self.report(end=self.day+timedelta(days=1),cutoff=self.day+timedelta(days=1)).entries[0]
        self.assertNotIn('REVERSED', earlier['payments'])
        self.assertNotIn('9,980', earlier['payments'])

    def test_late_recorded_receipt_uses_actual_business_date(self):
        event=self.event('REPAYMENT', self.day, {'principal':'0','interest':'50','fees':'0'})
        row=self.report().entries[0]
        self.assertIn(self.day.strftime('%d/%m/%Y'), row['payments'])
        self.assertIn('Rs 50', row['payments'])
        self.assertGreater(event.created_at.date(), event.effective_date)

    def test_opening_principal_is_not_remaining_balance_or_cutover_valuation(self):
        from apps.tenant_apps.loans.tests.test_opening_evidence import loan_reference, opening_event
        loan=loan_reference(); origin=opening_event(loan); origin.reversal_of_id=None
        loan.register_events=[origin]; loan.register_disbursals=[]; loan.register_releases=[]
        loan.loan_number='Source number'; loan.series=SimpleNamespace(pawn_display_name='No prefix')
        row=_entry(loan,{},start=date(2021,1,1),end=self.today)
        self.assertEqual(row['principal'],'Rs 1,000')
        self.assertNotIn('2,000',row['valuations'])
        self.assertEqual(row['tenure'],'Not recorded')
        self.assertIn('earlier payments',str(row['warnings']))

    def test_reversed_disbursal_still_requires_explicit_book_correction(self):
        self.event('REVERSAL',self.day+timedelta(days=1),{'principal':'10000'},reversal_of=self.origin)
        PawnLoan.objects.filter(pk=self.loan.pk).update(state='DRAFT')
        row=self.report().entries[0]
        self.assertIn('Disbursal correction/reversal',str(row['warnings']))

    def test_selector_does_not_write_or_load_files(self):
        with CaptureQueriesContext(connection) as queries:
            report=self.report()
        self.assertEqual(len(report.entries),1)
        self.assertLess(len(queries),25)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT','UPDATE','DELETE')) for q in queries))

    def test_five_ordinary_rows_fit_one_pair_and_six_require_two(self):
        report=self.report(); row=report.entries[0]
        for count,pages in ((5,2),(6,4)):
            report.entries=[dict(row,number=f'T{i:05d}') for i in range(count)]
            with fitz.open(stream=render_pledge_book(report),filetype='pdf') as document:
                self.assertEqual(sum('WORKING PREVIEW' in p.get_text() for p in document),pages)

    def test_series_scope_and_invalid_range_rejected(self):
        other=LoanLicense.objects.create(workspace=self.tenant, name='Other licence', license_number='OTHER', issued_on=self.day, expires_on=self.today+timedelta(days=300))
        series=LoanSeries.objects.create(license=other,name='Other',code='X')
        with self.assertRaises(LoanSeries.DoesNotExist):self.report(series_id=series.pk)
        with self.assertRaises(ValueError):self.report(cutoff=self.today+timedelta(days=1))
        with self.assertRaises(PermissionDenied):self.report(workspace=SimpleNamespace(pk=self.tenant.pk+1000))
        with self.assertRaises(PermissionDenied):self.report(actor=None)

    def test_pdf_facing_pair_and_no_persistent_issue_or_writes(self):
        report=self.report()
        before=LoanDocumentIssue.objects.count()
        pdf=render_pledge_book(report)
        with fitz.open(stream=pdf,filetype='pdf') as document:
            self.assertGreaterEqual(len(document),3)
            self.assertIn('Left',document[0].get_text())
            self.assertIn('Right',document[1].get_text())
            self.assertIn('00001',document[0].get_text())
            self.assertIn('00001',document[1].get_text())
            self.assertIn('Original gold ring',document[1].get_text())
            self.assertAlmostEqual(document[0].rect.width,595,delta=1)
        self.assertEqual(before,LoanDocumentIssue.objects.count())

    def test_long_entry_continues_on_aligned_pairs_without_lost_end(self):
        report=self.report()
        report.entries[0]['descriptions']='\n'.join(f'{i}. Long fictional collateral description with full particulars' for i in range(70))+'\nLAST-ARTICLE-END'
        pdf=render_pledge_book(report)
        with fitz.open(stream=pdf,filetype='pdf') as document:
            text='\n'.join(p.get_text() for p in document)
            self.assertIn('LAST-ARTICLE-END',text)
            self.assertIn('continuation',text)
            self.assertGreater(len(document),3)

    def test_landscape_capacity_and_all_fields_preserved(self):
        report = self.report()
        row = dict(report.entries[0], borrower='Original pawner', address='1 Original Street',
                   descriptions='Gold ring', rates='2% / month', valuations='Rs 20,000',
                   payments='Rs 125', closures='Redemption', owner='Other owner', recipients='Actual recipient')
        for count, pages in ((5, 1), (6, 2)):
            report.entries = [dict(row, number=f'T{i:05d}') for i in range(count)]
            with fitz.open(stream=render_pledge_book(report, 'landscape_a4'), filetype='pdf') as document:
                ledger = [p for p in document if 'WORKING PREVIEW' in p.get_text()]
                self.assertEqual(len(ledger), pages)
                for page in document:
                    self.assertAlmostEqual(page.rect.width, 842, delta=1)
                    self.assertAlmostEqual(page.rect.height, 595, delta=1)
                text = ledger[0].get_text()
                for expected in ('Original pawner', 'Original Street', 'Gold ring', '2%', '20,000',
                                 '125', 'Redemption', 'Other owner', 'Actual recipient', '10,000', '12'):
                    self.assertIn(expected, text)

    def test_landscape_long_entry_continuation_and_layout_validation(self):
        report = self.report()
        report.entries[0]['descriptions'] = '\n'.join(f'{i}. Long fictional collateral description' for i in range(70)) + '\nLAST-ARTICLE-END'
        with fitz.open(stream=render_pledge_book(report, 'landscape_a4'), filetype='pdf') as document:
            text = '\n'.join(page.get_text() for page in document)
            self.assertIn('LAST-ARTICLE-END', text)
            self.assertIn('continuation', text)
            self.assertGreater(len(document), 2)
        with self.assertRaises(ValueError):
            render_pledge_book(report, 'unsupported')

    def test_guide_form_and_scoped_pdf_route(self):
        client=self.make_workspace_client();client.force_login(self.actor)
        url=reverse('workspace_loans:pledge_book_preview',args=[self.tenant.slug])
        self.assertContains(client.get(url),'Pledge book (Form E)')
        data={'license':self.license.pk,'start':self.day.isoformat(),'end':self.today.isoformat(),'cutoff':self.today.isoformat()}
        self.assertContains(client.get(url,data),'00001')
        response=client.get(url,{**data,'format':'pdf'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertIn('no-store',response['Cache-Control'])
        response = client.get(url, {**data, 'layout': 'landscape_a4'})
        self.assertContains(response, 'value="landscape_a4" selected')
        self.assertContains(response, 'form="pledge-book-filters"')
        response = client.get(url, {**data, 'layout': 'landscape_a4', 'format': 'pdf'})
        self.assertEqual(response['Content-Type'], 'application/pdf')
        with fitz.open(stream=response.content, filetype='pdf') as document:
            self.assertGreater(document[0].rect.width, document[0].rect.height)
        response = client.get(url, {**data, 'layout': 'unknown', 'format': 'pdf'})
        self.assertContains(response, 'Select a valid choice')
        self.assertNotEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(client.post(url,data).status_code,405)
