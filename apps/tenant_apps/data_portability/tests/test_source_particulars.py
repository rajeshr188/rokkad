from copy import deepcopy
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.loans.selectors.pledge_book import _entry
from apps.tenant_apps.data_portability.models import LoanHistoryBatch, ImportBatch, ImportRow, ChildIdentity
from apps.tenant_apps.data_portability.source_particulars import imported_loan_particulars
from apps.tenant_apps.party.models import Party, PartyAddress


class SourceParticularsTests(OpeningImportFixture):
    def fixture(self, basis='RECORDED_TENURE'):
        origin=self.write()
        LoanHistoryBatch.objects.create(workspace=self.a, profile='legacy-opening/1',state='COMPLETED',
            result=origin,created_by=self.actor,source_sha256=origin.source_sha256,
            document={'opening':origin.document,'source_evidence':{'maturity_review':{'basis':basis,'tenure_months':3}}})
        master_row=ImportRow.objects.get(identity=self.source_party.identity)
        master=master_row.canonical
        address=PartyAddress.objects.create(party=origin.loan.borrower,line1='Mutable new address',city='Now')
        child=ChildIdentity.objects.create(parent=self.source_party.identity,profile='party-address/1',address=address)
        batch=ImportBatch.objects.create(workspace=self.a,source_name='fictional.jsonl',source_type='jsonl',
            source_system=self.review['mapping']['borrower_source_system'],source_sha256='a'*64,source_bytes=1,
            contract_version='party-address/1',state='READY',approval_digest='a'*64,created_by=self.actor)
        ImportRow.objects.create(batch=batch,source_row=1,external_id='address-1',identity=self.source_party.identity,child_identity=child,committed_at=timezone.now(),
            canonical={'id':'address-1','party_external_id':master_row.external_id,'address_type':'HOME','is_default':True,
                       'line1':'1 Frozen Street','city':'Then'})
        batch.state='COMPLETED';batch.committed_by=self.actor;batch.committed_at=timezone.now();batch.save()
        return origin,master

    def test_retained_identity_and_tenure_do_not_follow_current_party_edits(self):
        with self.scoped():
            origin,master=self.fixture()
            Party.objects.filter(pk=origin.loan.borrower_id).update(display_name='Changed later')
            result=imported_loan_particulars([origin.loan])[origin.loan_id]
            self.assertEqual(result['borrower'],master['name'])
            self.assertEqual(result['address'],'1 Frozen Street, Then')
            self.assertEqual(result['tenure_months'],3)
            loan=origin.loan
            loan.register_events=list(loan.loan_events.all());loan.register_disbursals=[];loan.register_releases=[]
            row=_entry(loan,{},start=loan.loan_date,end=timezone.localdate(),imported_particulars=result)
            self.assertEqual(row['borrower'],master['name'])
            self.assertIn('recorded in source',row['tenure'])
            self.assertIn('not proof',str(row['warnings']))
            self.assertNotIn('Changed later',str(row))

    def test_missing_maturity_assumption_is_not_original_recorded_tenure(self):
        with self.scoped():
            origin,_=self.fixture('OWNER_MISSING_MATURITY_RULE')
            result=imported_loan_particulars([origin.loan])[origin.loan_id]
            self.assertIsNone(result['tenure_months'])
            self.assertEqual(result['tenure_basis'],'OWNER_MISSING_MATURITY_RULE')

    def test_other_context_denied_and_no_batch_never_falls_back_to_current_identity(self):
        with self.scoped():
            origin=self.write()
            self.assertEqual(imported_loan_particulars([origin.loan]),{})
        with self.scoped(self.b),self.assertRaises(PermissionDenied):
            imported_loan_particulars([origin.loan])
