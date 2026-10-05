"""Recorded source facts with supported shared continuation, under restricted RLS."""
import copy
import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.test import override_settings

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.history_contract import encode, parse, HistoryError, SCHEMA_V4
from apps.tenant_apps.loans.services.history_export import export_history
from apps.tenant_apps.loans.services.history_setup import _number
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.data_portability import loan_history
from apps.tenant_apps.data_portability.models import LoanHistoryBatch
from .fixtures import PortabilityFixture


def document(closed=False):
    items = [dict(id='low', description='Ring', metal='GOLD', quantity=1, gross_weight='10', net_weight='9',
        purity='90', principal='6000', monthly_rate='1'), dict(id='high', description='Chain', metal='GOLD', quantity=1,
        gross_weight='10', net_weight='9', purity='90', principal='4000', monthly_rate='3')]
    payment = dict(id='receipt-1', kind='PAYMENT', date='2026-01-20', reference='Receipt 1', original_actor=None,
        capture_purpose='RECORD_COMPLETED', amount='1000', principal='1000', interest='0', fees='0', closure=None,
        allocations=[dict(item='low', before='6000', principal='1000', after='5000'),
            dict(item='high', before='4000', principal='0', after='4000')])
    value = dict(manifest=dict(profile='loan-history/4', namespace='8e6c2138-e413-4f15-83fc-ad28a47f4fb1',
        as_of='2026-02-02', coverage='PARTIAL', exclusions=['binary_files','workspace_configuration','renewals','auctions','opening_positions']),
        loan=dict(id='Book A:42', number='00042', book_reference='Book A', source_reference='Book A page 42', state='ACTIVE',
            borrower=dict(source_system='paper', id='old-1'), licence_number='OLD-L', legacy_license_evidence=None,
            disbursed_on='2026-01-01', tenure_months=12, calculation_contract='TEST-V1', grace_days=3,
            contract='recorded-anniversary/3', currency_quantum='1', original_actor=None, collateral=items,
            payout=dict(advance_months=1, document_charge='10', proceeds='9810', basis='PROCEEDS'),
            monitoring=dict(method='LATEST_APPRAISAL', ltv='0.8', reason='Review current appraisals separately'),
            events=[payment], cutover=dict(principal='9000', interest='170', fees='0')))
    if closed:
        value['loan']['state']='CLOSED'
        value['loan']['events'].append(dict(id='close-1', kind='CLOSE', date='2026-02-02', reference='Closed book page 42',
            original_actor=None, capture_purpose='RECORD_COMPLETED', amount='9170', principal='9000', interest='170', fees='0',
            allocations=[dict(item='low',before='5000',principal='5000',after='0'),dict(item='high',before='4000',principal='4000',after='0')],
            closure=dict(number='R42',collector='Customer',returned_at=None,basis='RETURNED')))
        value['loan']['cutover']=dict(principal='0',interest='0',fees='0')
    return value


@override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
    'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class RecordedSourceHistoryTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        with self.scoped():
            self.commit(self.ready())
            licence=create_license(workspace=self.a,actor=self.actor,name='Historical',license_number='OLD-L',
                issued_on=date(2025,1,1),expires_on=date(2027,1,1))
            series=m.LoanSeries.objects.create(license=licence,name='Historical',code='H')
            product=m.LoanProduct.objects.create(workspace=self.a,code='H',name='Historical')
            version=m.LoanProductVersion.objects.create(product=product,version=1,status='RETIRED',repayment_structure='FLEXIBLE_PARTIAL_PAYMENT',
                amortisation_method='NONE',payment_frequency='FLEXIBLE',extra_payment_rule='REDUCE_PRINCIPAL',maximum_tenor_months=12,
                operational_grace_days=3,calculation_contract_version='TEST-V1',available_from=date(2026,9,1))
            self.mapping=dict(revision_id=licence.revisions.get().pk,series_id=series.pk,product_version_id=version.pk)
        self.args=dict(workspace_id=self.a.pk,actor=self.actor)

    def import_value(self, value):
        batch=loan_history.stage(**self.args,content=encode(value))
        before=m.PawnLoan.objects.count()
        approval=loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
        self.assertEqual(m.PawnLoan.objects.count(),before)
        origin=loan_history.commit(**self.args,batch_id=batch.public_id,approval=approval,confirmed=True)
        return batch,approval,origin

    def test_actual_lower_rate_split_retired_later_catalog_and_unknown_valuation(self):
        with self.scoped():
            batch,token,origin=self.import_value(document())
            loan=origin.loan
            self.assertFalse(loan.approval_snapshots.exists())
            self.assertEqual(loan.policy_snapshot.basis,'RECORDED_CONTRACT')
            self.assertEqual(loan.license_revision_id,self.mapping['revision_id'])
            lines=loan.loan_events.get(event_kind='REPAYMENT').repayment_allocation_lines.order_by('collateral_item_id')
            self.assertEqual([line.principal_applied for line in lines],[Decimal(1000),Decimal(0)])
            self.assertTrue(all(item.latest_appraised_value is None for item in loan.collateral_items.all()))
            self.assertEqual(collection_balance(loan,date(2026,2,1)).interest_outstanding,0)
            self.assertEqual(collection_balance(loan,date(2026,2,2)).interest_outstanding,170)
            self.assertEqual(parse(export_history(**self.args,loan_id=loan.pk)),document())
            self.assertEqual(loan_history.commit(**self.args,batch_id=batch.public_id,approval=token,confirmed=True).pk,origin.pk)

    def test_closed_history_roundtrip_custody_and_no_fake_return_time(self):
        with self.scoped():
            _,_,origin=self.import_value(document(True))
            self.assertEqual(origin.loan.state,'CLOSED')
            self.assertEqual({i.custody_state for i in origin.loan.collateral_items.all()},{'WITH_CUSTOMER'})
            self.assertTrue(all(i.returned_at is None for i in origin.loan.releases.get().items.all()))
            self.assertEqual(parse(export_history(**self.args,loan_id=origin.loan_id)),document(True))
            value=parse(export_history(**self.args,loan_id=origin.loan_id))
            value['manifest']['namespace']=str(uuid.uuid4())
            _,_,second=self.import_value(value)
            self.assertEqual(parse(export_history(**self.args,loan_id=second.loan_id)),value)

    def test_same_number_different_books_unique_local_searchable_alias(self):
        from apps.tenant_apps.loans.filters import PawnLoanFilter
        with self.scoped():
            _,_,first=self.import_value(document())
            other=document();other['loan'].update(id='Book B:42',book_reference='Book B',source_reference='Book B page 42')
            _,_,second=self.import_value(other)
            self.assertNotEqual(first.loan.loan_number,second.loan.loan_number)
            query=m.PawnLoan.objects.filter(workspace=self.a)
            self.assertEqual(PawnLoanFilter({'q':'00042'},queryset=query,workspace=self.a).qs.count(),2)
            self.assertEqual(PawnLoanFilter({'q':'Book B'},queryset=query,workspace=self.a).qs.get().pk,second.loan_id)

    def test_changed_source_retry_and_opening_identity_cannot_duplicate(self):
        with self.scoped():
            _,_,origin=self.import_value(document())
            value=document();value['loan']['book_reference']='Renamed book'
            batch=loan_history.stage(**self.args,content=encode(value))
            with self.assertRaisesMessage(HistoryError,'different accepted history'):
                loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
            self.assertEqual(m.PawnLoan.objects.count(),1)

    def test_financial_inconsistency_rolls_back_instead_of_changing_source(self):
        with self.scoped():
            for mutate in ('after','principal','interest','cutover','proceeds'):
                value=document()
                if mutate=='after':value['loan']['events'][0]['allocations'][0]['after']='4999'
                elif mutate=='cutover':value['loan']['cutover']['interest']='169'
                elif mutate=='proceeds':value['loan']['payout']['proceeds']='9811'
                else:value['loan']['events'][0][mutate]='1'
                batch=loan_history.stage(**self.args,content=encode(value))
                with self.assertRaises(HistoryError) as error:
                    loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
                self.assertEqual(error.exception.issue['category'],'HISTORICAL_INCONSISTENCY')
                self.assertFalse(m.PawnLoan.objects.exists())

    def test_duplicate_items_events_unknown_split_and_chronology_block(self):
        with self.scoped():
            for mutate in ('items','events','split','chronology'):
                value=document()
                if mutate=='items':value['loan']['collateral'][1]['id']='low'
                elif mutate=='events':value['loan']['events'].append(copy.deepcopy(value['loan']['events'][0]))
                elif mutate=='split':value['loan']['events'][0]['allocations'][0]['item']='unknown'
                else:value['loan']['events'][0]['date']='2025-12-31'
                batch=loan_history.stage(**self.args,content=encode(value))
                with self.assertRaises(HistoryError):loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
                self.assertFalse(m.PawnLoan.objects.exists())

    def test_unsupported_contract_is_distinct_from_inconsistent_amount(self):
        value=document();value['loan']['contract']='some-other-contract'
        with self.assertRaises(HistoryError) as error:encode(value)
        self.assertEqual(error.exception.issue['category'],'OPERATIONAL_READINESS')
        self.assertEqual(error.exception.issue['code'],'UNSUPPORTED_PROFILE_VALUE')

    def test_exact_party_mapping_and_workspace_access(self):
        with self.assertRaises(PermissionDenied):loan_history.stage(**self.args,content=encode(document()))
        with self.scoped():
            value=document();value['loan']['borrower']['id']='missing'
            batch=loan_history.stage(**self.args,content=encode(value))
            with self.assertRaisesMessage(HistoryError,'exactly'):
                loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
            with self.assertRaises(PermissionDenied):loan_history.get_batch(workspace_id=self.a.pk,actor=self.other_actor,batch_id=batch.public_id)
        with self.scoped(self.b):
            self.assertFalse(LoanHistoryBatch.objects.exists())
            with self.assertRaises(PermissionDenied):loan_history.get_batch(workspace_id=self.b.pk,actor=self.actor,batch_id=batch.public_id)

    def test_profile_and_import_evidence_immutable_under_restricted_role(self):
        with self.scoped():
            batch,_,origin=self.import_value(document())
            with self.assertRaises(DatabaseError),transaction.atomic():
                LoanHistoryBatch.objects.filter(pk=batch.pk).update(profile='loan-history/3')
            with self.assertRaises(DatabaseError),transaction.atomic():
                m.HistoricalLoanImport.objects.filter(pk=origin.pk).update(document={})

    def test_generated_number_respects_live_prefix_and_no_counters_consumed(self):
        with self.scoped():
            sequence=m.LoanNumberSequence.objects.create(series_id=self.mapping['series_id'],document_kind='PAWN_LOAN',prefix='P-',width=4,next_number=1,maximum_number=9999)
            self.import_value(document())
            sequence.refresh_from_db();self.assertEqual(sequence.next_number,1)
            second=document();second['loan'].update(id='another-source',number='00043',source_reference='Book A page 43')
            batch=loan_history.stage(**self.args,content=encode(second))
            with patch('apps.tenant_apps.loans.services.history_setup._number',return_value='P-0002'):
                with self.assertRaisesMessage(HistoryError,'future numbering range'):
                    loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
            self.assertEqual(m.PawnLoan.objects.count(),1)

    def test_published_contract_and_example(self):
        root=Path(settings.BASE_DIR)/'docs/contracts'
        self.assertEqual(json.loads((root/'loan-history-v4.schema.json').read_text()),SCHEMA_V4)
        self.assertEqual(parse((root/'examples/loan-history-recorded-v4.jsonl').read_bytes()),document(True))

    def test_same_book_number_changed_identity_blocked(self):
        with self.scoped():
            self.import_value(document())
            value=document();value['loan'].update(id='duplicate-source-id',book_reference='book a',number='00042')
            batch=loan_history.stage(**self.args,content=encode(value))
            with self.assertRaisesMessage(HistoryError,'already have an accepted identity'):
                loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)
            self.assertEqual(m.PawnLoan.objects.count(),1)

    def test_inactive_legacy_reference_admits_completed_history_only(self):
        from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference
        with self.scoped():
            licence=create_legacy_license_reference(workspace=self.a,actor=self.actor,name='Old book',source_label='OLD-UNKNOWN',evidence_reference='Old book cover')
            series=m.LoanSeries.objects.create(license=licence,name='Old book',code='LEGACY')
            self.mapping.update(revision_id=licence.revisions.get().pk,series_id=series.pk)
            value=document(True);value['loan'].update(licence_number='OLD-UNKNOWN',legacy_license_evidence='Original validity unknown; book checked')
            _,_,origin=self.import_value(value)
            self.assertFalse(origin.loan.license.is_active)
            self.assertIsNone(origin.loan.license.issued_on)
            self.assertEqual(parse(export_history(**self.args,loan_id=origin.loan_id)),value)
            missing=document();missing['loan'].update(id='different',number='00043')
            batch=loan_history.stage(**self.args,content=encode(missing))
            with self.assertRaisesMessage(HistoryError,'requires explicit'):
                loan_history.preview(**self.args,batch_id=batch.public_id,values=self.mapping)

    def test_legacy_schema_local_ids_share_namespace_without_colliding(self):
        from apps.tenant_apps.data_portability.models import SourceIdentity
        with self.scoped():
            for schema in ('jcl','jsk'):
                value=document();value['loan']['id']='42'
                system='legacy:'+uuid.UUID(value['manifest']['namespace']).hex+':'+schema
                value['loan']['borrower']['source_system']=system
                SourceIdentity.objects.create(workspace=self.a,identity=SourceIdentity.objects.get(source_system='paper',external_id='old-1').identity,source_system=system,external_id='old-1',accepted_digest='a'*64,local_digest='a'*64)
                _,_,origin=self.import_value(value)
                self.assertEqual(origin.source_id,schema+':42')
            self.assertEqual(m.PawnLoan.objects.count(),2)

    def test_later_direct_payment_preserves_split_purpose_and_requires_fresh_book_review(self):
        from django.utils import timezone
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.transaction_reviews import _store
        with self.scoped():
            _,_,origin=self.import_value(document())
            day=timezone.localdate()
            balance=collection_balance(origin.loan,day)
            record_pawn_loan_repayment(origin.loan_id,amount=balance.interest_outstanding+100,request_key='later-now',actor=self.actor)
            origin.loan.refresh_from_db()
            with self.assertRaisesMessage(HistoryError,'Verify the complete source book'):
                export_history(**self.args,loan_id=origin.loan_id)
            _store(origin.loan,self.actor,through_date=day,confirmed_complete=True,source_reference='Full book checked',request_key='after-now')
            value=parse(export_history(**self.args,loan_id=origin.loan_id))
            self.assertEqual(value['loan']['events'][-1]['capture_purpose'],'PERFORM_NOW')
            self.assertEqual(value['loan']['events'][-1]['allocations'][0]['item'],'high')
            value['manifest']['namespace']=str(uuid.uuid4())
            _,_,restored=self.import_value(value)
            self.assertEqual(parse(export_history(**self.args,loan_id=restored.loan_id)),value)

    def test_paper_settlement_unknown_handover_remains_unknown(self):
        with self.scoped():
            value=document(True)
            value['loan']['events'][-1]['closure'].update(basis='PAPER_SETTLEMENT',collector=None)
            _,_,origin=self.import_value(value)
            self.assertEqual({i.custody_state for i in origin.loan.collateral_items.all()},{'PAPER_CLOSED'})
            self.assertEqual(parse(export_history(**self.args,loan_id=origin.loan_id)),value)

    def test_original_actor_is_a_source_claim_separate_from_local_importer(self):
        with self.scoped():
            value=document();value['loan']['original_actor']='paper-owner'
            _,_,origin=self.import_value(value)
            self.assertEqual(origin.loan.disbursal_snapshot.evidence['recording']['original_actor'],'paper-owner')
            self.assertEqual(origin.loan.loan_events.get(event_kind='DISBURSAL').created_by_id,self.actor.pk)
            self.assertEqual(parse(export_history(**self.args,loan_id=origin.loan_id)),value)

    def test_export_restores_into_another_workspace_with_exact_party(self):
        with self.scoped():
            _,_,origin=self.import_value(document(True))
            content=export_history(**self.args,loan_id=origin.loan_id)
        with self.scoped(self.b):
            self.commit(self.ready(workspace=self.b),workspace=self.b)
            licence=create_license(workspace=self.b,actor=self.actor,name='Historical',license_number='OLD-L',issued_on=date(2025,1,1),expires_on=date(2027,1,1))
            series=m.LoanSeries.objects.create(license=licence,name='Historical',code='H')
            product=m.LoanProduct.objects.create(workspace=self.b,code='H',name='Historical')
            version=m.LoanProductVersion.objects.create(product=product,version=1,status='RETIRED',repayment_structure='FLEXIBLE_PARTIAL_PAYMENT',amortisation_method='NONE',payment_frequency='FLEXIBLE',extra_payment_rule='REDUCE_PRINCIPAL',maximum_tenor_months=12,operational_grace_days=3,calculation_contract_version='TEST-V1')
            args=dict(workspace_id=self.b.pk,actor=self.actor)
            batch=loan_history.stage(**args,content=content)
            token=loan_history.preview(**args,batch_id=batch.public_id,values=dict(revision_id=licence.revisions.get().pk,series_id=series.pk,product_version_id=version.pk))
            restored=loan_history.commit(**args,batch_id=batch.public_id,approval=token,confirmed=True)
            self.assertNotEqual(restored.loan_id,origin.loan_id)
            self.assertEqual(parse(export_history(**args,loan_id=restored.loan_id)),parse(content))

    def test_later_paper_receipt_and_closure_export_replay(self):
        from apps.tenant_apps.loans.services.pawn_repayment import _record_pawn_loan_repayment_at
        from apps.tenant_apps.loans.services.pawn_release import _release_pawn_loan_in_full_at
        from apps.tenant_apps.loans.services.paper_repayments import _evidence
        from apps.tenant_apps.loans.services.transaction_reviews import _store
        with self.scoped():
            _,_,origin=self.import_value(document())
            loan=origin.loan;day=date(2026,3,2)
            split={str(origin.references['items']['low']):'1000',str(origin.references['items']['high']):'0'}
            _record_pawn_loan_repayment_at(loan.pk,amount=Decimal(1340),request_key='later-paper',actor=self.actor,effective_date=day,
                recording_evidence=_evidence(received_on=day,receipt_reference='Later paper receipt',amount=Decimal(1340),item_principal_split=split))
            _release_pawn_loan_in_full_at(loan.pk,settlement_amount=Decimal(8000),request_key='later-close',actor=self.actor,
                interest_concession=Decimal(0),concession_reason='',effective_date=day,recorded_number='PAPER-R43',
                paper_evidence=dict(profile='recorded-history-closure/1',date_precision='DAY',original_release_number='PAPER-R43',number_basis='ORIGINAL_PAPER',paper_reference='Later paper closure',collector_name='Customer',original_actor=None,closure_basis='RETURNED'))
            loan.refresh_from_db()
            _store(loan,self.actor,through_date=day,confirmed_complete=True,source_reference='Book complete',request_key='later-checked')
            value=parse(export_history(**self.args,loan_id=loan.pk))
            self.assertEqual(value['loan']['events'][-1]['kind'],'CLOSE')
            self.assertEqual(value['loan']['events'][-1]['closure']['returned_at'],None)
            value['manifest']['namespace']=str(uuid.uuid4())
            _,_,restored=self.import_value(value)
            self.assertEqual(parse(export_history(**self.args,loan_id=restored.loan_id)),value)

    def test_later_current_closure_retains_actual_source_time_and_unknown_collector(self):
        from django.utils import timezone
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        from apps.tenant_apps.loans.services.transaction_reviews import _store
        with self.scoped():
            _,_,origin=self.import_value(document())
            loan=origin.loan;day=timezone.localdate()
            m.LoanNumberSequence.objects.create(series_id=loan.series_id,document_kind='PAWN_LOAN_RELEASE',prefix='R-',width=4,next_number=1,maximum_number=9999)
            release_pawn_loan_in_full(loan.pk,settlement_amount=collection_balance(loan,day).total_due,request_key='close-now',actor=self.actor)
            loan.refresh_from_db()
            _store(loan,self.actor,through_date=day,confirmed_complete=True,source_reference='Checked all transactions',request_key='closed-checked')
            value=parse(export_history(**self.args,loan_id=loan.pk))
            close=value['loan']['events'][-1]
            self.assertEqual(close['capture_purpose'],'PERFORM_NOW')
            self.assertIsNone(close['closure']['collector'])
            self.assertIsNotNone(close['closure']['returned_at'])
            value['manifest']['namespace']=str(uuid.uuid4())
            _,_,restored=self.import_value(value)
            self.assertEqual(parse(export_history(**self.args,loan_id=restored.loan_id)),value)

    def test_graph_with_reviewed_correction_cannot_be_silently_exported(self):
        from apps.tenant_apps.loans.services.recorded_corrections import preview_correction,record_correction
        with self.scoped():
            _,_,origin=self.import_value(document())
            event=origin.loan.loan_events.get(event_kind='REPAYMENT')
            data=dict(operation='VOID',target=event.pk,date=None,amount=None,reference='',before=None,reason='Paper receipt was voided',request_key=uuid.uuid4().hex)
            review,token=preview_correction(origin.loan_id,actor=self.actor,data=data)
            self.assertFalse(review['blockers'])
            record_correction(origin.loan_id,actor=self.actor,data=data,review_token=token,confirmed=True)
            with self.assertRaisesMessage(HistoryError,'wider portability'):
                export_history(**self.args,loan_id=origin.loan_id)

    def test_http_upload_review_schema_commit_and_original_book_detail(self):
        from types import SimpleNamespace
        from django.test import Client
        from django.urls import reverse
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.tenancy import testing
        testing.WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        client=Client();client.force_login(self.actor)
        with override_settings(ALLOWED_HOSTS=['testserver']):
            upload=reverse('workspace_portability:loan_upload',kwargs={'workspace_slug':self.a.slug})
            self.assertContains(client.get(upload),'Recorded agreement v4 schema')
            schema=reverse('workspace_portability:loan_schema',kwargs={'workspace_slug':self.a.slug})
            self.assertEqual(json.loads(client.get(schema+'?version=4').content),SCHEMA_V4)
            response=client.post(upload,{'source':SimpleUploadedFile('recorded.jsonl',encode(document(True)))})
            self.assertEqual(response.status_code,302)
            preview=client.post(response.url,{**self.mapping,'action':'preview'})
            self.assertContains(preview,'Source book: Book A')
            self.assertContains(preview,'Actual item principal split')
            self.assertContains(preview,'eligible collection at cutover')
            self.assertEqual(client.post(response.url,dict(action='commit',approval=preview.context['approval'],confirmed='yes')).status_code,302)
            with self.scoped():origin=m.HistoricalLoanImport.objects.get()
            detail=reverse('workspace_loans:pawn_loan_detail',kwargs={'workspace_slug':self.a.slug,'pk':origin.loan_id})
            self.assertContains(client.get(detail),'Original loan 00042 in source book Book A')
