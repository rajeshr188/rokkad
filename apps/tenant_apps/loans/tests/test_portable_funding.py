from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import override_settings
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import funding_loans as funding
from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle,restore_servicing_bundle
from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle,FUNDING_PROFILE
from apps.tenant_apps.loans.services.servicing_funding import funding_position
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.loans.tests.test_servicing_bundle import destination,altered
from apps.tenant_apps.data_portability.tests import test_business_package as fixture
from apps.tenant_apps.party.models import Party


class PortableFundingTests(OpeningImportFixture):
    def test_corrected_customer_then_funding_package_preserves_both_agreements(self):
        from uuid import uuid4
        from apps.tenant_apps.loans.services.borrower_corrections import preview_borrower_correction, record_borrower_correction
        with self.scoped():
            origin = self.write()
            customer = Party.objects.create(display_name='Correct funding pawn customer')
            facts = dict(borrower_id=customer.pk, reference='Actual original register', reason='Wrong customer selected', request_key=uuid4().hex)
            _, token = preview_borrower_correction(origin.loan_id, actor=self.actor, data=facts)
            record_borrower_correction(origin.loan_id, actor=self.actor, data=facts, review_token=token, confirmed=True)
            lender = Party.objects.create(display_name='Independent funding lender')
            funded = self.activate(origin.loan.collateral_items.get(), lender)
            before = funding_position(funded)
            content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
            graph, _ = read_bundle(content)
            self.assertEqual((graph['profile'], graph['financial_profile']), ('loan-servicing-bundle/5', FUNDING_PROFILE))
            exported = self.export()
        with self.scoped(self.b):
            review = self.preview(exported)
            self.restore(exported, review)
            loan = m.PawnLoan.objects.get()
            self.assertEqual(loan.change_log.get(event_kind='BORROWER_CORRECTED').metadata['borrower_correction']['after']['id'], loan.borrower_id)
            self.assertEqual(funding_position(m.FundingLoan.objects.get()), before)

    export=fixture.BusinessPackageTests.export
    preview=fixture.BusinessPackageTests.preview
    restore=fixture.BusinessPackageTests.restore

    def setUp(self):
        super().setUp()
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)/'source'
        self.directory.mkdir()
        override=override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
            'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}},MEDIA_ROOT=Path(self.temp.name)/'storage')
        override.enable()
        self.addCleanup(override.disable)
        self.today=timezone.localdate()

    def activate(self,item,lender,key='first'):
        draft=funding.create_funding_loan_draft(funding.CreateFundingLoanDraft(item.workspace_id,lender.pk),actor=self.actor)
        return funding.activate_funding_loan(funding.ActivateFundingLoan(item.workspace_id,draft.pk,Decimal('1000'),Decimal('2'),
            self.today,self.today+timedelta(days=90),Decimal('.8'),Decimal('.01'),
            (funding.FundingCollateralInput(item.pk,Decimal('1500')),),key),actor=self.actor).funding_loan

    def source(self):
        origin=self.write()
        lender=Party.objects.create(display_name='Source funding lender')
        item=origin.loan.collateral_items.get()
        loan=self.activate(item,lender)
        return origin,item,loan,lender

    def repay_return(self,item,loan,key='first'):
        funding.record_funding_repayment(funding.RecordFundingRepayment(loan.workspace_id,loan.pk,Decimal('1000'),self.today,'repay-'+key),actor=self.actor)
        return funding.return_funding_collateral(funding.ReturnFundingCollateral(loan.workspace_id,loan.pk,(item.pk,),self.today,'return-'+key),actor=self.actor)

    def test_active_roundtrip_future_servicing_reexport_and_counter(self):
        from django.core.files.base import ContentFile
        from apps.tenant_apps.loans.services.servicing_bundle_contract import sha
        from apps.tenant_apps.loans.web.portable_documents import source_copies
        import base64
        with self.scoped():
            origin,item,loan,lender=self.source()
            artifact=b'%PDF-1.4\noriginal source pawn copy\n%%EOF'
            m.LoanDocumentIssue.objects.create(workspace=self.a,document_type='loan_ticket',source_type='PawnLoan',source_id=str(origin.loan_id),
                source_fingerprint='a'*64,payload_schema_version=2,payload_hash='b'*64,pdf_hash=sha(artifact),artifact=ContentFile(artifact,name='source.pdf'),
                issued_by=self.actor,source_snapshot={'schema_version':2,'workspace_id':self.a.pk,'fields':{}})
            before=funding_position(loan)
            content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=origin.loan_id)
            document,_=read_bundle(content)
            self.assertEqual(document['profile'],FUNDING_PROFILE)
            exported=self.export()
        with self.scoped(self.b):
            review=self.preview(exported)
            self.assertFalse(m.FundingLoan.objects.exists())
            receipt=self.restore(exported,review)
            restored=m.FundingLoan.objects.get()
            self.assertEqual(funding_position(restored),before)
            self.assertNotEqual(restored.pk,loan.pk)
            item=m.PawnCollateralItem.objects.get()
            copies=source_copies(item.loan)
            self.assertEqual(len(copies),1)
            self.assertEqual(base64.b64decode(copies[0]['retained_files'][copies[0]['pdf_sha256']]),artifact)
            self.assertFalse(m.LoanDocumentIssue.objects.exists())
            self.assertEqual(item.custody_state,'WITH_FUNDING_LENDER')
            local,_=read_bundle(export_servicing_bundle(workspace_id=self.b.pk,actor=self.actor,loan_id=item.loan_id))
            self.assertEqual(local['funding_positions'][str(restored.pk)],before)
            self.assertEqual(self.restore(exported,review).pk,receipt.pk)
            self.repay_return(item,restored,'destination')
            funding.begin_funding_settlement(funding.BeginFundingSettlement(self.b.pk,restored.pk),actor=self.actor)
            funding.close_funding_loan(funding.CloseFundingLoan(self.b.pk,restored.pk),actor=self.actor)
            restored.refresh_from_db()
            self.assertEqual(funding_position(restored)['state'],'CLOSED')
            next_loan=funding.create_funding_loan_draft(funding.CreateFundingLoanDraft(self.b.pk,restored.lender_id),actor=self.actor)
            self.assertEqual(next_loan.funding_number,'FL-000002')

    def test_closed_then_repledged_item_replays_in_custody_order(self):
        with self.scoped():
            origin,item,first,lender=self.source()
            self.repay_return(item,first)
            funding.begin_funding_settlement(funding.BeginFundingSettlement(self.a.pk,first.pk),actor=self.actor)
            funding.close_funding_loan(funding.CloseFundingLoan(self.a.pk,first.pk),actor=self.actor)
            item.refresh_from_db()
            second=self.activate(item,lender,'second')
            exported=self.export()
        with self.scoped(self.b):
            self.restore(exported,self.preview(exported))
            self.assertEqual(list(m.FundingLoan.objects.order_by('funding_number').values_list('state',flat=True)),['CLOSED','ACTIVE'])
            self.assertEqual(m.FundingPledgeItem.objects.filter(released_at__isnull=True).count(),1)
            self.assertEqual(m.PawnCollateralCustodyEvent.objects.count(),3)

    def test_return_reversal_is_retained_and_can_be_returned_again(self):
        with self.scoped():
            origin,item,loan,lender=self.source()
            returned=self.repay_return(item,loan)
            funding.reverse_funding_return(funding.ReverseFundingReturn(self.a.pk,loan.pk,returned.pk,self.today,'Handover cancelled','undo-return'),actor=self.actor)
            exported=self.export()
        with self.scoped(self.b):
            self.restore(exported,self.preview(exported))
            restored=m.FundingLoan.objects.get()
            item=m.PawnCollateralItem.objects.get()
            self.assertEqual(item.custody_state,'WITH_FUNDING_LENDER')
            funding.return_funding_collateral(funding.ReturnFundingCollateral(self.b.pk,restored.pk,(item.pk,),self.today,'actual-return'),actor=self.actor)
            self.assertEqual(m.FundingReturnReversal.objects.count(),1)
            self.assertEqual(m.FundingReturn.objects.count(),2)

    def test_pledge_reversal_retains_neutral_financial_and_custody_evidence(self):
        with self.scoped():
            origin,item,loan,lender=self.source()
            funding.record_funding_repayment(funding.RecordFundingRepayment(self.a.pk,loan.pk,Decimal('1000'),self.today,'settle-pledge'),actor=self.actor)
            funding.begin_funding_settlement(funding.BeginFundingSettlement(self.a.pk,loan.pk),actor=self.actor)
            funding.reverse_funding_pledge(funding.ReverseFundingPledge(self.a.pk,loan.pk,self.today,'Cancelled source funding','undo-pledge'),actor=self.actor)
            exported=self.export()
        with self.scoped(self.b):
            self.restore(exported,self.preview(exported))
            self.assertTrue(all(Decimal(value)==0 for value in funding_position(m.FundingLoan.objects.get())['recorded'].values()))
            self.assertEqual(m.PawnCollateralItem.objects.get().custody_state,'IN_VAULT')
            self.assertEqual(m.FundingPledgeReversal.objects.count(),1)

    def test_missing_exact_lender_and_forged_position_hold_without_writes(self):
        with self.scoped():
            origin,item,loan,lender=self.source()
            content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=origin.loan_id)
        document,_=read_bundle(content)
        mapping=destination(self,document)
        with self.scoped(self.b):
            args=dict(workspace_id=self.b.pk,actor=self.actor,content=content,mapping=mapping)
            with self.assertRaisesMessage(ValueError,'exact source lender'):
                restore_servicing_bundle(**args)
            changed=altered(content,lambda doc:doc['funding_positions'][str(loan.pk)]['recorded'].update(principal='1'))
            with self.assertRaisesMessage(ValueError,'Funding financial position differs'):
                restore_servicing_bundle(**{**args,'content':changed})
            self.assertFalse(m.FundingLoan.objects.exists())
            self.assertFalse(m.PawnLoan.objects.exists())

    def test_false_return_reversal_cannot_reactivate_without_inverse_custody(self):
        from django.db import connection,transaction,DatabaseError
        with self.scoped():
            origin,item,loan,lender=self.source()
            returned=self.repay_return(item,loan)
            with self.assertRaisesMessage(DatabaseError,'exact inverse custody'),transaction.atomic():
                m.FundingReturnReversal.objects.create(workspace=self.a,funding_return=returned,
                    effective_date=self.today,request_key='false-return',request_fingerprint='a'*64,reason='Missing movement',actor=self.actor)
                pledge_item=m.FundingPledgeItem.objects.get()
                pledge_item.released_at=None
                pledge_item.save(update_fields=['released_at'])
                connection.check_constraints()
            self.assertFalse(m.FundingReturnReversal.objects.exists())

    def test_shared_pledge_partial_return_and_financial_reversal_form_one_graph(self):
        from copy import deepcopy
        from apps.tenant_apps.loans.services import servicing_bundle
        with self.scoped():
            first=self.write()
            review=deepcopy(self.review)
            review['source'].update(loan_id='second-pawn',number='OLD00002',loan_sha256='b'*64)
            second=self.write(review=review)
            items=(first.loan.collateral_items.get(),second.loan.collateral_items.get())
            lender=Party.objects.create(display_name='One source lender')
            draft=funding.create_funding_loan_draft(funding.CreateFundingLoanDraft(self.a.pk,lender.pk),actor=self.actor)
            loan=funding.activate_funding_loan(funding.ActivateFundingLoan(self.a.pk,draft.pk,Decimal('1000'),Decimal('2'),
                self.today,self.today+timedelta(days=90),Decimal('.8'),Decimal('.01'),
                tuple(funding.FundingCollateralInput(item.pk,Decimal('1500')) for item in items),'shared-pledge'),actor=self.actor).funding_loan
            funding.accrue_funding_interest(funding.AccrueFundingInterest(self.a.pk,loan.pk,1,self.today,'interest'),actor=self.actor)
            funding.assess_funding_fee(funding.AssessFundingFee(self.a.pk,loan.pk,Decimal('5'),self.today,'fee'),actor=self.actor)
            paid=funding.record_funding_repayment(funding.RecordFundingRepayment(self.a.pk,loan.pk,Decimal('200'),self.today,'paid'),actor=self.actor)
            funding.reverse_funding_event(funding.ReverseFundingEvent(self.a.pk,loan.pk,paid.pk,self.today,'Receipt corrected','reverse-payment'),actor=self.actor)
            funding.return_funding_collateral(funding.ReturnFundingCollateral(self.a.pk,loan.pk,(items[0].pk,),self.today,'partial-return'),actor=self.actor)
            before=funding_position(loan)
            doc,_=read_bundle(servicing_bundle.export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=first.loan_id))
            self.assertEqual({r['id'] for r in doc['tables']['PawnLoan']},{first.loan_id,second.loan_id})
            self.assertEqual(len(doc['tables']['FundingLoan']),1)
            exported=self.export()
        with self.scoped(self.b):
            self.restore(exported,self.preview(exported))
            self.assertEqual(m.PawnLoan.objects.count(),2)
            restored=m.FundingLoan.objects.get()
            self.assertEqual(funding_position(restored),before)
            self.assertEqual(sorted(m.PawnCollateralItem.objects.values_list('custody_state',flat=True)),['IN_VAULT','WITH_FUNDING_LENDER'])
            funding.record_funding_repayment(funding.RecordFundingRepayment(self.b.pk,restored.pk,Decimal('1025'),self.today,'new-complete-receipt'),actor=self.actor)
            self.assertTrue(all(Decimal(value)==0 for value in funding_position(restored)['recorded'].values()))
