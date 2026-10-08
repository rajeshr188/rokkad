from datetime import date
from unittest.mock import patch

from apps.tenant_apps.data_portability.models import SourceIdentity
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.tests.test_opening_restore import OpeningRestoreTests
from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle, restore_servicing_bundle
from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle
from apps.tenant_apps.data_portability.tests import test_loan_history_v4 as recorded
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.tests.test_opening_auctions import CheckpointAuctionTests
from apps.tenant_apps.loans.tests.test_recorded_auctions import on
from apps.tenant_apps.data_portability.tests import test_loan_history as approved
from django.core.files.base import ContentFile
from django.test import override_settings
from apps.tenant_apps.loans.services.history_contract import dump, digest, HistoryError
from apps.tenant_apps.loans.services.servicing_bundle_contract import sha
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED


def altered(content, mutate):
    document, files = read_bundle(content)
    mutate(document)
    document['sha256'] = sha(dump({k:v for k,v in document.items() if k!='sha256'}).encode())
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json',dump(document))
        for key, data in files.items():
            archive.writestr('files/'+key,data)
    return output.getvalue()


def destination(case, document):
    with case.scoped(case.b):
        if not SourceIdentity.objects.filter(external_id='old-1').exists():
            case.commit(case.ready(workspace=case.b), workspace=case.b)
        identity = SourceIdentity.objects.get(external_id='old-1').identity
        mapping = {}
        for pk, source in document['setup'].items():
            SourceIdentity.objects.get_or_create(workspace=case.b, source_system=source['borrower']['source_system'], external_id=source['borrower']['id'], defaults=dict(identity=identity, accepted_digest='a'*64, local_digest='a'*64))
            licence = m.LoanLicense.objects.filter(workspace=case.b, license_number=source['licence_number']).first()
            if licence is None:
                licence = create_license(workspace=case.b, actor=case.actor, name='Restore '+pk, license_number=source['licence_number'], issued_on=date(2020,1,1), expires_on=date(2027,1,1))
            series = m.LoanSeries.objects.create(license=licence, name='Restore', code='R'+pk)
            product = m.LoanProduct.objects.create(workspace=case.b, code='R'+pk, name='Restore')
            version = m.LoanProductVersion.objects.create(product=product, version=1, status='RETIRED', maximum_tenor_months=12, **source['product'])
            mapping[pk] = dict(borrower_id=identity.party_id, revision_id=licence.revisions.get().pk, series_id=series.pk, product_version_id=version.pk)
        return mapping


def roundtrip(case, content):
    document, files = read_bundle(content)
    args = dict(workspace_id=case.b.pk, actor=case.actor, content=content, mapping=destination(case, document))
    with case.scoped(case.b):
        from django.core.files.storage import default_storage
        with patch.object(default_storage,'delete',wraps=default_storage.delete) as deleted:
            preview = restore_servicing_bundle(**args)
        for call in deleted.call_args_list:
            case.assertFalse(default_storage.exists(call.args[0]))
        if document['tables']['PawnCollateralPhoto']:
            case.assertTrue(deleted.called)
        case.assertFalse(m.PawnLoan.objects.exists())
        result = restore_servicing_bundle(**args, expected_sha256=preview['sha256'], confirmed=True)
        case.assertEqual(len(result['loans']), len(document['tables']['PawnLoan']))
    return result


class ServicingBundleTests(OpeningRestoreTests):
    def test_bundle_command_preview_and_confirmed_commit(self):
        from django.core.management import call_command, CommandError
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from io import StringIO
        import json
        with on(date(2021,2,2)):
            origin, content = self.bundle_source()
            with TemporaryDirectory() as directory, self.scoped(self.b):
                source = Path(directory)/'source.zip'
                mapping = Path(directory)/'mapping.json'
                source.write_bytes(content)
                mapping.write_text(dump({str(origin.loan_id):self.mapping}))
                args = dict(workspace_id=self.b.pk,actor_id=self.actor.pk,source=str(source),mapping=str(mapping))
                output = StringIO()
                call_command('restore_loan_servicing',**args,stdout=output)
                preview = json.loads(output.getvalue())
                self.assertFalse(m.PawnLoan.objects.exists())
                with self.assertRaises(CommandError):
                    call_command('restore_loan_servicing',**args,commit=True,stdout=StringIO())
                call_command('restore_loan_servicing',**args,commit=True,expected_sha256=preview['sha256'],stdout=StringIO())
                self.assertEqual(m.PawnLoan.objects.count(),1)

    def test_bundle_invalid_zip_setup_and_changed_source_retry_hold(self):
        with on(date(2021,2,2)):
            origin, content = self.bundle_source()
            args = dict(workspace_id=self.b.pk,actor=self.actor,mapping={str(origin.loan_id):self.mapping})
            unsafe = BytesIO()
            with ZipFile(unsafe,'w') as archive:
                archive.writestr('../manifest.json','{}')
            with self.scoped(self.b):
                for invalid in (b'not a zip', unsafe.getvalue(), altered(content,lambda d:d.update(profile='loan-servicing-bundle/999')),
                    altered(content,lambda d:d.update(namespace=42)),
                    altered(content,lambda d:d['setup'][str(origin.loan_id)]['product'].update(secret_field='not allowed')),
                    altered(content,lambda d:d['positions'][str(origin.loan_id)]['coverage'].clear())):
                    with self.assertRaises(HistoryError):
                        restore_servicing_bundle(**args,content=invalid)
                    self.assertFalse(m.PawnLoan.objects.exists())
            restored = self.restore_bundle(origin,content)
            changed = altered(content,lambda d:d['positions'][str(origin.loan_id)].update(exposure='999'))
            with self.scoped(self.b):
                with self.assertRaisesMessage(HistoryError,'already has accepted'):
                    restore_servicing_bundle(**args,content=changed)
                self.assertEqual(list(m.PawnLoan.objects.values_list('pk',flat=True)),restored['loans'])

    def test_bundle_forged_complete_review_and_unknown_enum_hold(self):
        with on(date(2021,2,2)):
            origin, content=self.bundle_source()
            def fake(doc):
                doc['positions'][str(origin.loan_id)]['coverage'].update(complete=True,status='CONFIRMED')
            with self.scoped(self.b):
                args=dict(workspace_id=self.b.pk,actor=self.actor,mapping={str(origin.loan_id):self.mapping})
                with self.assertRaisesMessage(HistoryError,'missing its required book review'):
                    restore_servicing_bundle(**args,content=altered(content,fake))
                with self.assertRaisesMessage(HistoryError,'enum'):
                    restore_servicing_bundle(**args,content=altered(content,lambda doc:doc['tables']['PawnLoan'][0].update(state='UNKNOWN_STATE')))
                self.assertFalse(m.PawnLoan.objects.exists())

    def test_bundle_recomputed_digest_cannot_change_receipt_allocation(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.event_recording import _fingerprint
        with on(date(2021,2,2)):
            origin, content = self.bundle_source(lambda pk: record_pawn_loan_repayment(pk, amount=210, request_key='partial', actor=self.actor))
            def change(doc):
                event = next(r for r in doc['tables']['PawnLoanEvent'] if r['event_kind']=='REPAYMENT')
                event['payload']['repayment']['amount_received']='211'
                event['payload_fingerprint']=_fingerprint(event['payload'])
                event['idempotency_key']=f"loans:{event['loan_id']}:REPAYMENT:{event['payload_fingerprint']}"
            with self.scoped(self.b):
                with self.assertRaisesMessage(HistoryError,'receipt amount'):
                    restore_servicing_bundle(workspace_id=self.b.pk, actor=self.actor, content=altered(content,change), mapping={str(origin.loan_id):self.mapping})
                self.assertFalse(m.PawnLoan.objects.exists())

    def test_bundle_missing_child_foreign_mapping_and_unconfirmed_commit_hold(self):
        with on(date(2021,2,2)):
            origin, content = self.bundle_source()
            args=dict(workspace_id=self.b.pk, actor=self.actor, content=content, mapping={str(origin.loan_id):self.mapping})
            with self.scoped(self.b):
                with self.assertRaises(HistoryError):
                    restore_servicing_bundle(**args, confirmed=True)
                changed = altered(content, lambda d:d['tables']['PawnCollateralItem'].clear())
                with self.assertRaises(HistoryError):
                    restore_servicing_bundle(**dict(args,content=changed))
                with self.assertRaises(m.LoanLicenseRevision.DoesNotExist):
                    restore_servicing_bundle(**dict(args,mapping={str(origin.loan_id):dict(self.mapping,revision_id=self.review['mapping']['licence_revision_id'])}))
                self.assertFalse(m.PawnLoan.objects.exists())

    def bundle_source(self, action=None):
        with self.scoped():
            origin = self.write()
            if action:
                action(origin.loan_id)
            content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
        document, _ = read_bundle(content)
        with self.scoped(self.b):
            identity = SourceIdentity.objects.get(external_id='old-1').identity
            borrower = document['setup'][str(origin.loan_id)]['borrower']
            SourceIdentity.objects.create(workspace=self.b, identity=identity,
                source_system=borrower['source_system'], external_id=borrower['id'],
                accepted_digest='a'*64, local_digest='a'*64)
        return origin, content

    def restore_bundle(self, origin, content):
        args = dict(workspace_id=self.b.pk, actor=self.actor, content=content, mapping={str(origin.loan_id):self.mapping})
        with self.scoped(self.b):
            preview = restore_servicing_bundle(**args)
            self.assertFalse(m.PawnLoan.objects.exists())
            result = restore_servicing_bundle(**args, expected_sha256=preview['sha256'], confirmed=True)
        return result

    def test_bundle_opening_payment_release_reversal(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        def actions(loan_id):
            record_pawn_loan_repayment(loan_id, amount=210, request_key='partial', actor=self.actor)
            release = release_pawn_loan_in_full(loan_id, settlement_amount=800, request_key='release', actor=self.actor)
            reverse_pawn_loan_event(release.loan_event.pk, actor=self.actor, reason='Cancelled handover')
        with patch('django.utils.timezone.localdate', return_value=date(2021, 2, 2)):
            origin, content = self.bundle_source(actions)
            self.restore_bundle(origin, content)

    def test_bundle_closed_opening(self):
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        with patch('django.utils.timezone.localdate', return_value=date(2021, 2, 2)):
            origin, content = self.bundle_source(lambda pk:release_pawn_loan_in_full(pk, settlement_amount=1010, request_key='release', actor=self.actor))
            self.restore_bundle(origin, content)

    def test_bundle_opening_preview_commit_and_retry(self):
        with patch('django.utils.timezone.localdate', return_value=date(2021, 2, 2)):
            origin, content = self.bundle_source()
            args = dict(workspace_id=self.b.pk, actor=self.actor, content=content, mapping={str(origin.loan_id):self.mapping})
            with self.scoped(self.b):
                preview = restore_servicing_bundle(**args)
                self.assertFalse(m.PawnLoan.objects.exists())
                restored = restore_servicing_bundle(**args, expected_sha256=preview['sha256'], confirmed=True)
                self.assertEqual(m.PawnLoan.objects.count(), 1)
                self.assertNotEqual(restored['loans'][0], origin.loan_id)
                self.assertTrue(restore_servicing_bundle(**args, expected_sha256=preview['sha256'], confirmed=True)['already_restored'])


class RecordedBundleTests(recorded.RecordedSourceHistoryTests):
    def test_bundle_mixed_completed_batch_preserves_unknown_cash_and_original_number(self):
        from uuid import uuid4
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent, preview_recorded_history, admit_recorded_history
        from apps.tenant_apps.loans.services.paper_closures import preview_paper_closures, complete_paper_closures
        with on(date(2026, 10, 5)):
            with self.scoped():
                args = self.paper_setup()
                loans = []
                for number in ('P-0020', 'P-0021'):
                    args['data'].update(number=number, source_reference='Book / ' + number)
                    args['intent_token'] = new_recording_intent(workspace=self.a, actor=self.actor)
                    _, token = preview_recorded_history(**args)
                    loans.append(admit_recorded_history(**args, review_token=token, confirmed=True)[0])
                from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
                for loan in loans:
                    review_data = dict(through_date=date(2026, 10, 5), confirmed_complete=True,
                        source_reference='Checked source through today', request_key=str(uuid4()), future_capture='ROKKAD_ONLY')
                    _, token = preview_transaction_review(loan.pk, actor=self.actor, **review_data)
                    confirm_transaction_review(loan.pk, actor=self.actor, review_token=token, acknowledged=True, **review_data)
                preview = preview_paper_closures(workspace=self.a, actor=self.actor,
                    loan_ids=[loan.pk for loan in loans], closure_date=date(2026, 10, 5))
                rows = [dict(loan_id=row['loan'].pk, amount=str(row['amount']),
                    basis='PAPER_SETTLEMENT', number='', paid_by='', collector_name='') for row in preview['rows']]
                rows[1].update(basis='RETURNED', number='OLD-CLOSE-21', paid_by='Family payer',
                    collector_name=loans[1].borrower.display_name)
                complete_paper_closures(workspace=self.a, actor=self.actor, request_key=uuid4(),
                    quote_token=preview['token'], confirmed=True, paper_reference='Closing register', rows=rows)
                from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
                for loan in loans:
                    loan.refresh_from_db()
                    self.assertTrue(transaction_completeness(loan, date(2026, 10, 5)).complete)
                    self.assertEqual(loan.transaction_reviews.order_by('-pk').first().future_capture, 'PAPER_MIXED')
                content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=loans[0].pk)
            roundtrip(self, content)
            with self.scoped(self.b):
                batch = m.PawnReleaseBatch.objects.get()
                self.assertEqual(batch.lines.count(), 2)
                unknown = batch.lines.get(paid_by='')
                self.assertEqual(unknown.release.loan.collateral_items.get().custody_state, 'PAPER_CLOSED')
                self.assertEqual(unknown.release.loan_event.payload['release']['paper_closure']['batch_id'], batch.pk)
                returned = batch.lines.exclude(paid_by='').get()
                self.assertEqual(returned.release.loan_event.payload['release']['paper_closure']['original_release_number'], 'OLD-CLOSE-21')
                self.assertEqual(returned.release.loan.collateral_items.get().custody_state, 'WITH_CUSTOMER')

    def test_bundle_shared_release_batch_members_are_not_truncated(self):
        from uuid import uuid4
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent,preview_recorded_history,admit_recorded_history
        from apps.tenant_apps.loans.services.paper_closures import preview_paper_closures,complete_paper_closures
        with on(date(2026,10,5)):
            with self.scoped():
                args=self.paper_setup()
                loans=[]
                for number in ('P-0010','P-0011'):
                    args['data'].update(number=number,source_reference='Book / '+number)
                    args['intent_token']=new_recording_intent(workspace=self.a,actor=self.actor)
                    _,token=preview_recorded_history(**args)
                    loans.append(admit_recorded_history(**args,review_token=token,confirmed=True)[0])
                preview=preview_paper_closures(workspace=self.a,actor=self.actor,loan_ids=[r.pk for r in loans],closure_date=date(2026,10,5))
                complete_paper_closures(workspace=self.a,actor=self.actor,request_key=uuid4(),quote_token=preview['token'],confirmed=True,paper_reference='Separate paper receipts',
                    rows=[dict(loan_id=row['loan'].pk,amount=str(row['amount']),paid_by='Payer',collector_name=row['loan'].borrower.display_name) for row in preview['rows']])
                content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=loans[0].pk)
                self.assertEqual(len(read_bundle(content)[0]['tables']['PawnLoan']),2)
            roundtrip(self,content)

    def test_bundle_closed_receipt_and_settlement_correction(self):
        from apps.tenant_apps.loans.services.recorded_corrections import preview_correction,record_correction
        with on(date(2026,2,2)):
            with self.scoped():
                _,_,origin=self.import_value(recorded.document(True))
                event=origin.loan.loan_events.get(event_kind='REPAYMENT')
                item=origin.loan.collateral_items.order_by('pk').first()
                data=dict(operation='REPLACE',target=event.pk,date='2026-01-20',amount='500',reference='Actual receipt',before=None,reason='Checked amount against book',request_key='closed-correction',
                    item_principal_split={str(item.pk):'500'},settlement=dict(cash_received='9675',cash_paid='0',interest_offset='0',reference='Confirmed actual final payment',confirmed_unchanged=True))
                _,token=preview_correction(origin.loan_id,actor=self.actor,data=data)
                record_correction(origin.loan_id,actor=self.actor,data=data,review_token=token,confirmed=True)
                content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=origin.loan_id)
            roundtrip(self,content)

    def paper_setup(self):
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
        m.LoanProductVersion.objects.filter(pk=self.mapping['product_version_id']).update(status='ACTIVE')
        for kind, prefix in [('PAWN_LOAN','P-'),('PAWN_LOAN_RELEASE','R-')]:
            m.LoanNumberSequence.objects.create(series_id=self.mapping['series_id'],document_kind=kind,prefix=prefix,width=4,maximum_number=9999)
        data=dict(borrower_id=SourceIdentity.objects.get(external_id='old-1').identity.party_id,
            series_id=self.mapping['series_id'],product_version_id=self.mapping['product_version_id'],number='P-0010',date='2026-09-27',principal='10000',rate='2',tenure=12,
            advance_months=0,cash_paid='10000',source_reference='Book / loan10',description='Ring',metal='GOLD',quantity=1,gross_weight='10',net_weight='9',purity='90',
            monitoring_method='LATEST_APPRAISAL',monitoring_ltv='0.8',monitoring_reason='Monitor current appraisal separately',complete_through='2026-10-05',final_state='ACTIVE',confirmed_history=True,confirmed_rule=True,events=[])
        return dict(workspace=self.a,actor=self.actor,intent_token=new_recording_intent(workspace=self.a,actor=self.actor),data=data)

    def test_bundle_changed_contract_retains_superseded_origins(self):
        from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history, admit_recorded_history
        from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction,record_contract_correction
        with on(date(2026,10,5)):
            with self.scoped():
                args=self.paper_setup()
                _,token=preview_recorded_history(**args)
                loan,_=admit_recorded_history(**args,review_token=token,confirmed=True)
                data=dict(date='2026-09-27',principal='12000',rate='3',cash_paid='12000',reference='Original book checked',reason='Incorrect original terms',request_key='correct-contract')
                _,token=preview_contract_correction(loan.pk,actor=self.actor,data=data)
                record_contract_correction(loan.pk,actor=self.actor,data=data,review_token=token,confirmed=True)
                content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=loan.pk)
            roundtrip(self,content)

    def test_bundle_closed_archive_admission_keeps_archive_binding(self):
        from apps.tenant_apps.data_portability.tests.test_loan_archive import document as archive_document
        from apps.tenant_apps.loans.services.archive import accept_evidence
        from apps.tenant_apps.loans.services.archive_admission import preview_archive_admission,admit_archive_history
        with on(date(2026,10,5)):
            with self.scoped():
                args=self.paper_setup()
                args['data'].update(final_state='CLOSED',events=[dict(kind='CLOSE',amount='10200',date='2026-10-05',reference='receipt:1',number='R-0009',rate=None,tenure=None,recipient='Borrower')])
                value=archive_document()
                value['source'].update(system='legacy:491cf2e499eb499cb55568f3a8d5caaa:jcl',loan_id='girvi_loan:10')
                value['facts'].update(loan_number='P-0010',opened_on='2026-09-27',closed_on='2026-10-05',original_principal='10000',reported_balance='0',borrower_reference=None,
                    collateral=[dict(description='Ring',quantity=1,gross_weight='10',net_weight='9')],payments=[dict(id='receipt:1',date='2026-10-05',amount='10200')])
                evidence=accept_evidence(workspace_id=self.a.pk,actor=self.actor,document=value,expected_sha256=digest(value),confirmed=True)
                args.update(evidence_id=evidence.public_id,reconciliation='Original agreement, cashbook and signed return receipt checked; borrower verified.')
                _,token=preview_archive_admission(**args)
                loan,_=admit_archive_history(**args,review_token=token,confirmed=True)
                content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=loan.pk)
            result=roundtrip(self,content)
            with self.scoped(self.b):
                imported=m.PawnLoan.objects.get(pk=result['loans'][0])
                self.assertEqual(imported.historical_import.archive_evidence.document,value)

    def test_bundle_linked_paper_renewal_graph(self):
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent, preview_recorded_history, admit_recorded_history
        with on(date(2026,10,5)):
            with self.scoped():
                m.LoanProductVersion.objects.filter(pk=self.mapping['product_version_id']).update(status='ACTIVE')
                for kind, prefix in [('PAWN_LOAN','P-'),('PAWN_LOAN_RELEASE','R-')]:
                    m.LoanNumberSequence.objects.create(series_id=self.mapping['series_id'], document_kind=kind, prefix=prefix, width=4, maximum_number=9999)
                data = dict(borrower_id=SourceIdentity.objects.get(external_id='old-1').identity.party_id,
                    series_id=self.mapping['series_id'], product_version_id=self.mapping['product_version_id'], number='P-0010', date='2026-09-27',
                    principal='10000', rate='2', tenure=12, advance_months=0, cash_paid='10000', source_reference='Book / loan10',
                    description='Ring', metal='GOLD', quantity=1, gross_weight='10', net_weight='9', purity='90', monitoring_method='LATEST_APPRAISAL',
                    monitoring_ltv='0.8', monitoring_reason='Monitor current appraisal separately', complete_through='2026-10-05', final_state='ACTIVE', confirmed_history=True, confirmed_rule=True,
                    events=[dict(kind='RENEW', amount='2000', date='2026-09-29', reference='Receipt10', number='P-0011', rate='1.5', tenure=12, recipient='')])
                args = dict(workspace=self.a, actor=self.actor, intent_token=new_recording_intent(workspace=self.a, actor=self.actor), data=data)
                _, token = preview_recorded_history(**args)
                loan, _ = admit_recorded_history(**args, review_token=token, confirmed=True)
                content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
                self.assertEqual(len(read_bundle(content)[0]['tables']['PawnLoan']),2)
            roundtrip(self, content)

    def test_bundle_recorded_history_capture_and_reexport(self):
        from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with patch('django.utils.timezone.localdate', return_value=date(2026, 2, 2)):
            with self.scoped():
                _, _, origin = self.import_value(recorded.document())
                loan = origin.loan
                facts = dict(through_date=date(2026,2,2), confirmed_complete=True, source_reference='Checked source book', request_key='source-capture', future_capture='ROKKAD_ONLY')
                _, token = preview_transaction_review(loan.pk, actor=self.actor, **facts)
                confirm_transaction_review(loan.pk, actor=self.actor, **facts, review_token=token, acknowledged=True)
                record_pawn_loan_repayment(loan.pk, amount=200, request_key='current-receipt', actor=self.actor)
                content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
            doc, _ = read_bundle(content)
            with self.scoped(self.b):
                self.commit(self.ready(workspace=self.b), workspace=self.b)
                identity = SourceIdentity.objects.get(external_id='old-1').identity
                source = doc['setup'][str(loan.pk)]
                SourceIdentity.objects.create(workspace=self.b, identity=identity, source_system=source['borrower']['source_system'], external_id=source['borrower']['id'], accepted_digest='a'*64, local_digest='a'*64)
                licence = create_license(workspace=self.b, actor=self.actor, name='Restore', license_number='OLD-L', issued_on=date(2025,1,1), expires_on=date(2027,1,1))
                series = m.LoanSeries.objects.create(license=licence, name='Restore', code='R')
                product = m.LoanProduct.objects.create(workspace=self.b, code='R', name='Restore')
                version = m.LoanProductVersion.objects.create(product=product, version=1, status='RETIRED', maximum_tenor_months=12, **source['product'])
                mapping = {str(loan.pk):dict(borrower_id=identity.party_id, revision_id=licence.revisions.get().pk, series_id=series.pk, product_version_id=version.pk)}
                args = dict(workspace_id=self.b.pk, actor=self.actor, content=content, mapping=mapping)
                preview = restore_servicing_bundle(**args)
                restored = restore_servicing_bundle(**args, expected_sha256=preview['sha256'], confirmed=True)
                imported = m.PawnLoan.objects.get(pk=restored['loans'][0])
                self.assertFalse(imported.transaction_reviews.filter(future_capture='ROKKAD_ONLY').exists())
                self.assertEqual(imported.historical_import.references['portable']['document'], doc)
                reexport = export_servicing_bundle(workspace_id=self.b.pk, actor=self.actor, loan_id=imported.pk)
                self.assertEqual(read_bundle(reexport)[0]['positions'][str(imported.pk)]['recorded'],doc['positions'][str(loan.pk)]['recorded'])

    def test_bundle_recorded_closed_source(self):
        with on(date(2026,2,2)):
            with self.scoped():
                _, _, origin = self.import_value(recorded.document(True))
                content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
            roundtrip(self, content)

    def test_bundle_recorded_receipt_correction(self):
        from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with on(date(2026,2,2)):
            with self.scoped():
                _, _, origin = self.import_value(recorded.document())
                payment = record_pawn_loan_repayment(origin.loan_id, amount=1000, request_key='correct', actor=self.actor)
                data = dict(operation='REPLACE', target=payment.loan_event.pk, date='2026-02-02', amount='50', reference='Checked actual receipt', before=None, reason='Transcription correction', request_key='correction')
                _, token = preview_correction(origin.loan_id, actor=self.actor, data=data)
                record_correction(origin.loan_id, actor=self.actor, data=data, review_token=token, confirmed=True)
                content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=origin.loan_id)
            roundtrip(self, content)


class AuctionBundleTests(CheckpointAuctionTests):
    def bundle_auction(self, reverse=False):
        from apps.tenant_apps.loans.services import pawn_auctions as auctions
        from apps.tenant_apps.loans.services.transaction_reviews import _store
        from apps.tenant_apps.loans.services.opening_servicing import opening_payment_balance
        from apps.tenant_apps.loans.tests.factories import prepare_test_auction_service
        with self.scoped():
            with on(date(2021,5,1)):
                origin = self.write()
                loan = origin.loan
                _store(loan, self.actor, through_date=date(2021,5,1), confirmed_complete=True, source_reference='Checked test book', request_key='notice-review')
                auction = auctions.initiate_pawn_loan_auction(loan.pk, scheduled_date=date(2021,6,30), request_key='sale', actor=self.actor)
                prepare_test_auction_service(auction, self.actor, date(2021,5,1))
            with on(date(2021,6,30)):
                _store(loan, self.actor, through_date=date(2021,6,30), confirmed_complete=True, source_reference='Checked test book', request_key='sale-review')
                auctions.start_pawn_loan_auction(auction.pk, actor=self.actor)
                quote, _ = opening_payment_balance(loan, as_of_date=date(2021,6,30))
                auctions.complete_pawn_loan_auction(auction.pk, recovery_amount=quote.total_due, buyer_name='Buyer', actor=self.actor)
                if reverse:
                    auctions.reverse_pawn_loan_auction(auction.pk, reason='Sale cancelled', actor=self.actor)
                content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
        with on(date(2021,6,30)):
            return roundtrip(self, content)

    def test_bundle_opening_auction(self):
        self.bundle_auction()

    def test_bundle_opening_paired_auction_reverse(self):
        self.bundle_auction(True)


@override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.InMemoryStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ApprovedBundleTests(approved.LoanHistoryTests):
    @classmethod
    def setUpTestData(cls):
        from .recovery_fixtures import lock_recovery_fixture_tables
        lock_recovery_fixture_tables()
        super().setUpTestData()

    def test_bundle_native_payout_photo_and_later_receipt(self):
        self.native_bundle()

    def test_bundle_native_linked_current_renewal(self):
        self.native_bundle(renew=True)

    def test_bundle_native_linked_current_renewal_reversal(self):
        self.native_bundle(renew=True,reverse=True)

    def native_bundle(self, *, renew=False, reverse=False):
        from decimal import Decimal
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.tenant_apps.loans.services import CreatePawnDraftCommand, CollateralDraftInput, create_pawn_draft, append_collateral_photo, approve_pawn_loan
        from apps.tenant_apps.loans.services.pawn_disbursal import disburse_pawn_loan
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.rates.models import Rate, RateSource
        from django.utils import timezone
        with on(date(2026,10,5)):
            with self.scoped():
                licence = create_license(workspace=self.a, actor=self.actor, name='Current', license_number='CURRENT', issued_on=date(2026,1,1), expires_on=date(2027,12,31))
                series = m.LoanSeries.objects.create(license=licence,name='Current',code='C')
                m.LoanNumberSequence.objects.create(series=series,document_kind='PAWN_LOAN',prefix='C-',width=5,maximum_number=10000)
                m.LoanProductVersion.objects.filter(pk=self.mapping['product_version_id']).update(status='ACTIVE')
                Rate.objects.create(rate_source=RateSource.objects.create(name='Local',location='Local'),buying_rate=10000,selling_rate=10100,effective_at=timezone.now())
                m.PawnLoanEconomicPolicy.objects.create(workspace=self.a,advance_interest_periods=0)
                m.PawnMetalInterestRatePolicy.objects.create(workspace=self.a,metal='GOLD',monthly_interest_rate=2)
                borrower = SourceIdentity.objects.get(external_id='old-1').identity.party_id
                loan=create_pawn_draft(CreatePawnDraftCommand(workspace_id=self.a.pk,borrower_id=borrower,license_id=licence.pk,series_id=series.pk,
                    product_version_id=self.mapping['product_version_id'],principal_amount=Decimal('50000'),monthly_interest_rate=Decimal('2'),loan_date=date(2026,10,5),tenure_months=3,
                    collateral=(CollateralDraftInput(description='Ring',metal='GOLD',gross_weight=Decimal('20'),net_weight=Decimal('18'),purity_percentage=Decimal('91.6'),latest_appraised_value=Decimal('120000'),allocated_principal=Decimal('50000')),)),actor=self.actor)
                photo = append_collateral_photo(loan.collateral_items.get().pk,upload=SimpleUploadedFile('ring.jpg',b'\xff\xd8\xff\xe0original-photo',content_type='image/jpeg'),actor=self.actor)
                approve_pawn_loan(loan.pk,actor=self.actor)
                disburse_pawn_loan(loan.pk,effective_date=date(2026,10,5),actor=self.actor)
                record_pawn_loan_repayment(loan.pk,amount='100',request_key='later',actor=self.actor)
                if renew:
                    from apps.tenant_apps.loans.services.pawn_renewals import preview_pawn_loan_renewal_plan,renew_pawn_loan,reverse_pawn_loan_renewal,RetainedCollateralInput
                    values = dict(mode='TOP_UP_RENEW',principal_paid=Decimal(0),top_up_amount=Decimal('10000'),
                        successor_license_id=licence.pk,successor_series_id=series.pk,successor_product_version_id=loan.product_version_id,
                        tenure_months=3,retained_collateral=(RetainedCollateralInput(loan.collateral_items.get().pk,Decimal('60000')),))
                    preview = preview_pawn_loan_renewal_plan(loan.pk,**values)
                    result = renew_pawn_loan(loan.pk,**values,renewal_date=date(2026,10,5),request_key='bundle-renewal',expected_preview_fingerprint=preview.fingerprint,actor=self.actor)
                    if reverse:
                        reverse_pawn_loan_renewal(result.renewal.pk,reason='Cancelled same-day renewal',actor=self.actor)
                content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=loan.pk)
            result=roundtrip(self,content)
            with self.scoped(self.b):
                imported=m.PawnLoan.objects.get(pk=result['loans'][0])
                self.assertEqual(imported.approval_snapshots.get().payload['historical_approval']['actor'],str(self.actor.pk))
                restored_photo=imported.collateral_items.get().photos.get()
                with restored_photo.file.open('rb') as stream:
                    self.assertEqual(stream.read(),b'\xff\xd8\xff\xe0original-photo')

    def test_bundle_retained_source_packet_exact_workspace_recovery(self):
        from apps.tenant_apps.loans.services import pawn_recovery as recovery
        from apps.tenancy.context import workspace_context
        from django.db import connection
        with on(date(2021,1,31)):
            with self.scoped():
                _,_,origin = self.run_import(approved.document())
                artifact = b'%PDF-1.4\nretained original copy\n%%EOF'
                m.LoanDocumentIssue.objects.create(workspace=self.a,document_type='loan_ticket',source_type='PawnLoan',source_id=str(origin.loan_id),
                    source_fingerprint='a'*64,payload_schema_version=2,payload_hash='b'*64,pdf_hash=sha(artifact),artifact=ContentFile(artifact,name='source.pdf'),
                    issued_by=self.actor,source_snapshot={'schema_version':2,'workspace_id':self.a.pk,'fields':{}})
                content = export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=origin.loan_id)
            roundtrip(self,content)
            with workspace_context(self.b.pk):
                archive = recovery.export_archive(workspace=self.b,actor=self.actor)
                original = recovery._read(archive,sha(archive))[0]
                # Exact recovery is independently exercised using the owner test
                # connection and an emptied test-only destination of identical ID.
                self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
                connection.check_constraints()
                with connection.cursor() as cursor:
                    for model in recovery._models():
                        cursor.execute(f'ALTER TABLE "{model._meta.db_table}" DISABLE TRIGGER USER')
                    for model in reversed(recovery._models()):
                        cursor.execute(f'DELETE FROM "{model._meta.db_table}" WHERE workspace_id=%s',[self.b.pk])
                    connection.check_constraints()
                    for model in recovery._models():
                        cursor.execute(f'ALTER TABLE "{model._meta.db_table}" ENABLE TRIGGER USER')
                args = dict(workspace=self.b,actor=self.actor,content=archive,expected_sha256=sha(archive))
                self.assertFalse(recovery.restore_archive(**args)['committed'])
                self.assertTrue(recovery.restore_archive(**args,commit=True)['committed'])
                new_archive = recovery.export_archive(workspace=self.b,actor=self.actor)
                restored = recovery._read(new_archive,sha(new_archive))[0]
                for key in ('tables','files','reconciliation','schema','guards_sha256'):
                    self.assertEqual(original[key],restored[key],key)

    def test_bundle_approved_history_original_approval_and_exact_source_pdf(self):
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        from apps.tenant_apps.loans.web.portable_documents import source_copies
        with on(date(2021,1,31)):
            with self.scoped():
                _, _, origin = self.run_import(approved.document())
                loan = origin.loan
                original_approval = loan.approval_snapshots.get().payload['historical_approval']
                artifact = b'%PDF-1.4\noriginal issued source bytes\n%%EOF'
                issue = m.LoanDocumentIssue.objects.create(workspace=self.a, document_type='loan_ticket', source_type='PawnLoan', source_id=str(loan.pk),
                    source_fingerprint='a'*64, payload_schema_version=2, payload_hash='b'*64, pdf_hash=sha(artifact), artifact=ContentFile(artifact,name='original.pdf'), issued_by=self.actor,
                    source_snapshot={'schema_version':2,'workspace_id':self.a.pk,'fields':{'borrower.name':'Original source customer'}})
                content = export_servicing_bundle(workspace_id=self.a.pk, actor=self.actor, loan_id=loan.pk)
            restored = roundtrip(self,content)
            with self.scoped(self.b):
                imported = m.PawnLoan.objects.get(pk=restored['loans'][0])
                self.assertEqual(imported.approval_snapshots.get().payload['historical_approval'],original_approval)
                details = dict(PawnLoanDocumentProjectionBuilder.loan_ticket(imported).details)
                self.assertEqual(details['Original approval time (source claim)'],original_approval['at'])
                self.assertFalse(m.LoanDocumentIssue.objects.exists())
                copies = source_copies(imported)
                self.assertEqual(len(copies),1)
                import base64
                self.assertEqual(base64.b64decode(copies[0]['retained_files'][sha(artifact)]),artifact)
                from django.test import RequestFactory
                from apps.tenant_apps.loans.web.portable_documents import source_document
                request = RequestFactory().get('/source-copy.pdf')
                request.user, request.workspace = self.actor, self.b
                self.assertEqual(source_document(request, imported.pk, 0).content, artifact)
                from apps.tenant_apps.data_portability.loan_history_views import export
                request = RequestFactory().post('/export')
                request.user, request.workspace = self.actor, self.b
                response = export(request, imported.pk)
                self.assertEqual(response['Content-Type'],'application/zip')
                self.assertEqual(read_bundle(response.content)[0]['profile'],'loan-servicing-bundle/1')
                from django.db import DatabaseError, transaction
                with self.assertRaises(DatabaseError),transaction.atomic():
                    m.HistoricalLoanImport.objects.filter(loan=imported).update(references={})
                again = export_servicing_bundle(workspace_id=self.b.pk, actor=self.actor, loan_id=imported.pk)
                self.assertEqual(read_bundle(again)[0]['tables']['HistoricalLoanImport'][0]['references']['portable']['files'][sha(artifact)],base64.b64encode(artifact).decode())
