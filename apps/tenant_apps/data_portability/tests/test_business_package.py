from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import DatabaseError, transaction, connection
from django.test import override_settings

from apps.tenant_apps.data_portability import business_package as package, contracts, services
from apps.tenant_apps.data_portability.models import BusinessPackageReceipt, PartyIdentity
from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services import business_setup_portability as setup
from apps.tenant_apps.loans.services.closed_position import preview_closed_position, admit_closed_position
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.party.models import Party, PartyPhoto, PartyDocument, PartyCodeSequence


class BusinessPackageTests(OpeningImportFixture):
    def test_borrower_correction_package_restores_both_customers_and_original_checkpoint(self):
        from uuid import uuid4
        from apps.tenant_apps.loans.services.borrower_corrections import preview_borrower_correction, record_borrower_correction
        with self.scoped():
            origin = self.write()
            target = Party.objects.create(display_name='Correct package customer')
            facts = dict(borrower_id=target.pk, reference='Checked signed register', reason='Original customer mistaken', request_key=uuid4().hex)
            _, token = preview_borrower_correction(origin.loan_id, actor=self.actor, data=facts)
            record_borrower_correction(origin.loan_id, actor=self.actor, data=facts, review_token=token, confirmed=True)
            exported = self.export()
        with self.scoped(self.b):
            review = self.preview(exported)
            self.assertFalse(loans.PawnLoan.objects.exists())
            receipt = self.restore(exported, review)
            restored = loans.PawnLoan.objects.get()
            correction = restored.change_log.get(event_kind='BORROWER_CORRECTED').metadata['borrower_correction']
            self.assertNotEqual(correction['before']['id'], correction['after']['id'])
            self.assertEqual(restored.borrower_id, correction['after']['id'])
            frozen = restored.loan_events.get(event_kind='MIGRATION_OPENING').payload['opening']['review']['mapping']
            self.assertEqual(frozen['borrower_id'], correction['before']['id'])
            self.assertTrue(Party.objects.filter(pk=correction['before']['id']).exists())
            self.assertEqual(self.restore(exported, review).pk, receipt.pk)

    def setUp(self):
        super().setUp()
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)/'source'
        self.directory.mkdir()
        self.override = override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
            'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}, MEDIA_ROOT=Path(self.temp.name)/'storage')
        self.override.enable()
        self.addCleanup(self.override.disable)

    def export(self):
        with patch.object(services, 'require_export_snapshot'):
            return package.write_package(workspace_id=self.a.pk, actor=self.actor, directory=self.directory, _consistent_snapshot=True)

    def preview(self, doc):
        return package.preview_package(workspace_id=self.b.pk, actor=self.actor, directory=self.directory, expected_sha256=doc['sha256'])

    def restore(self, doc, review):
        return package.restore_package(workspace_id=self.b.pk, actor=self.actor, directory=self.directory,
            expected_sha256=doc['sha256'], approval=review['approval'], confirmed=True)

    def test_closed_package_restores_setup_customers_counters_and_retries(self):
        with self.scoped():
            doc = dict(profile='loan-closed-position/1',
                source=dict(namespace=self.review['source']['namespace'],system='paper',loan_id='closed-23'),
                loan=dict(number='H-00023',borrower_reference=dict(system=self.source_party.source_system,id=self.source_party.external_id),
                    original_date=None,closed_on=None,original_principal=None,monthly_rate=None,tenure_months=None),
                position=dict(state='CLOSED',as_of='2021-02-02',currency='INR',principal='0',interest='0',fees='0',
                    custody='RETURNED_TO_BORROWER',basis='OWNER_CLOSED_POSITION',evidence_reference='Synthetic owner checked position'),
                earlier_history='UNAVAILABLE',retained_evidence=None)
            values = dict(workspace_id=self.a.pk, actor=self.actor, borrower_id=self.source_party.identity.party_id, series_id=self.series.pk)
            _, token = preview_closed_position(document=doc, **values)
            admit_closed_position(document=doc, review_token=token, confirmed=True, **values)
            self.sequence.refresh_from_db()
            self.assertEqual(self.sequence.next_number,24)
            exported = self.export()
            original_code=self.source_party.identity.party.party_code
        with self.scoped(self.b):
            review = self.preview(exported)
            self.assertFalse(Party.objects.exists())
            self.assertFalse(loans.LoanLicense.objects.exists())
            receipt = self.restore(exported,review)
            self.assertEqual(self.restore(exported,review).pk, receipt.pk)
            self.assertEqual(loans.PawnLoan.objects.get().state,'CLOSED')
            self.assertFalse(loans.LoanLicense.objects.get().is_active)
            self.assertEqual(loans.LoanNumberSequence.objects.get(document_kind='PAWN_LOAN').next_number,24)
            self.assertEqual(receipt.summary['counts']['loans'],1)
            self.assertEqual(Party.objects.get().party_code,original_code)
            self.assertEqual(PartyCodeSequence.objects.get(key='PARTY').next_number,2)
            with receipt.source.open('rb') as source:
                self.assertEqual(package.exchange.sha(source.read()),receipt.source_file_sha256)

    def test_active_supported_graph_reconciles_then_rolls_back_late_failure(self):
        from io import BytesIO
        from PIL import Image
        import hashlib
        with self.scoped():
            origin=self.write()
            output=BytesIO()
            Image.new('RGB',(5,5),'green').save(output,format='PNG')
            data=output.getvalue()
            photo=loans.PawnCollateralPhoto(workspace=self.a,collateral_item=origin.loan.collateral_items.get(),
                original_filename='source.png',mime_type='image/png',sha256=hashlib.sha256(data).hexdigest(),
                byte_size=len(data),workflow_source='POST_APPROVAL',captured_by=self.actor)
            photo.file.save('source.png',ContentFile(data),save=False)
            photo.save()
            exported = self.export()
        storage_root=Path(self.temp.name)/'storage'
        baseline={p for p in storage_root.rglob('*') if p.is_file()}
        with self.scoped(self.b):
            review = self.preview(exported)
            self.assertFalse(loans.PawnLoan.objects.exists())
            self.assertEqual({p for p in storage_root.rglob('*') if p.is_file()},baseline)
            original_log=package.AuditLog.log
            def fail_at_completion(*args, **kwargs):
                if kwargs.get('description','').startswith('Restored and reconciled an atomic'):
                    raise RuntimeError('late audit failure')
                return original_log(*args, **kwargs)
            with patch.object(package.AuditLog,'log',side_effect=fail_at_completion):
                with self.assertRaises(RuntimeError):
                    self.restore(exported,review)
            self.assertFalse(loans.LoanLicense.objects.exists())
            self.assertEqual({p for p in storage_root.rglob('*') if p.is_file()},baseline)
            receipt = self.restore(exported,review)
            self.assertEqual(len(receipt.results),1)
            self.assertEqual(loans.PawnLoan.objects.get().principal_amount,1000)
            with loans.PawnCollateralPhoto.objects.get().file.open('rb') as stream:
                self.assertEqual(stream.read(),data)

    def test_media_preview_cleanup_and_exact_customer_document_bytes(self):
        from io import BytesIO
        from PIL import Image
        with self.scoped():
            party = self.source_party.identity.party
            doc = PartyDocument(party=party, document_type='OTHER',title='Retained source', metadata={'source_note':'paper'},is_verified=True)
            doc.file.save('source.txt',ContentFile(b'original private customer evidence'),save=False)
            doc.save()
            output=BytesIO()
            Image.new('RGB',(5,5),'blue').save(output,format='PNG')
            self.a.logo.save('business.png',ContentFile(output.getvalue()),save=False)
            self.a.loan_workflow='SIMPLE'
            self.a.save(update_fields=['logo','loan_workflow'])
            exported = self.export()
            source_name = doc.file.name
        with self.scoped(self.b):
            review = self.preview(exported)
            self.assertFalse(PartyDocument.objects.exists())
            receipt = self.restore(exported,review)
            restored = PartyDocument.objects.get()
            self.assertNotEqual(restored.file.name, source_name)
            self.assertFalse(restored.is_verified)
            self.assertTrue(restored.metadata['package_source_verification']['is_verified'])
            with restored.file.open('rb') as stream:
                self.assertEqual(stream.read(),b'original private customer evidence')
            self.assertEqual(receipt.summary['files'],2)
            restored_workspace=package.Company.all_objects.get(pk=self.b.pk)
            self.assertEqual(restored_workspace.loan_workflow,'SIMPLE')
            self.assertEqual(restored_workspace.owner_id,self.actor.pk)
            self.assertEqual(restored_workspace.slug,self.b.slug)
            with restored_workspace.logo.open('rb') as stream:
                self.assertEqual(stream.read(),output.getvalue())

    def test_changed_missing_media_and_nonempty_destination_are_held(self):
        with self.scoped():
            doc = self.export()
        with self.scoped(self.b):
            Party.objects.create(display_name='Existing destination')
            with self.assertRaisesMessage(ValueError,'not empty'):
                self.preview(doc)
        raw = (self.directory/'setup.json').read_bytes()
        (self.directory/'setup.json').write_bytes(raw+b' ')
        with self.scoped():
            with self.assertRaisesMessage(ValueError,'setup bytes changed'):
                package.read_package(self.directory,expected_sha256=doc['sha256'])

    def test_missing_required_blob_and_foreign_setup_binding_are_held(self):
        with self.scoped():
            obj=PartyDocument(party=self.source_party.identity.party,document_type='OTHER',title='Required blob')
            obj.file.save('evidence.txt',ContentFile(b'required bytes'),save=False)
            obj.save()
            doc=self.export()
        checksum=next(iter(doc['files']))
        (self.directory/'media'/checksum).unlink()
        with self.scoped(self.b):
            with self.assertRaises(OSError):
                self.preview(doc)
            self.assertFalse(Party.objects.exists())
        from copy import deepcopy
        tables=json.loads((self.directory/'setup.json').read_bytes())
        altered=deepcopy(tables)
        altered['loans.LoanSeries'][0]['license_id']=99999999
        with self.assertRaisesMessage(ValueError,'foreign setup reference'):
            setup.validate_tables(altered)

    def test_receipt_immutability_foreign_results_and_rls(self):
        with self.scoped():
            exported=self.export()
        with self.scoped(self.b):
            review=self.preview(exported)
            receipt=self.restore(exported,review)
            with self.assertRaises(DatabaseError),transaction.atomic():
                BusinessPackageReceipt.objects.filter(pk=receipt.pk).update(summary={})
            with self.assertRaises(DatabaseError),transaction.atomic():
                BusinessPackageReceipt.objects.filter(pk=receipt.pk).delete()
            with self.assertRaises(DatabaseError),transaction.atomic():
                invalid=BusinessPackageReceipt(workspace_id=self.b.pk,source_sha256='a'*64,source_file_sha256='b'*64,
                    summary={'profile':package.PROFILE,'counts':{'loans':1}},results=[99999999],created_by=self.actor)
                invalid.source.name=f'business_package/{self.b.pk}/{invalid.public_id}/source.json'
                invalid.save()
        with self.scoped():
            self.assertFalse(BusinessPackageReceipt.objects.filter(pk=receipt.pk).exists())
        with self.assertRaises(PermissionDenied):
            package.preview_package(workspace_id=self.b.pk,actor=self.actor,directory=self.directory,expected_sha256=exported['sha256'])

    def test_schema_has_no_arbitrary_models_or_authority_and_unsupported_data_is_held(self):
        self.assertEqual(len(setup.ROWS),22)
        self.assertEqual(len(setup.GRAPH_ROWS),24)
        self.assertEqual(len(setup.MONITORING_ROWS),24)
        for schema in (setup.ROWS,setup.GRAPH_ROWS,setup.MONITORING_ROWS):
            for fields in schema.values():
                self.assertNotIn('workspace_id',fields)
                self.assertNotIn('created_by_id',fields)
        with self.scoped():
            with patch.object(loans.KhataAccount.objects,'filter') as query:
                query.return_value.exists.return_value=True
                with self.assertRaisesMessage(ValueError,'unsupported KhataAccount'):
                    self.export()

    def test_unconnected_unpaid_funding_draft_is_declared_and_counter_preserved(self):
        from apps.tenant_apps.loans.services.funding_loans import CreateFundingLoanDraft,create_funding_loan_draft
        with self.scoped():
            create_funding_loan_draft(CreateFundingLoanDraft(self.a.pk,self.source_party.identity.party_id),actor=self.actor)
            exported=self.export()
            self.assertEqual(exported['profile'],package.GRAPH_PROFILE)
            self.assertIn('unconnected funding drafts/cancellations',exported['exclusions'][4])
        with self.scoped(self.b):
            self.restore(exported,self.preview(exported))
            self.assertFalse(loans.FundingLoan.objects.exists())
            self.assertEqual(loans.FundingLoanSequence.objects.get().next_value,2)

    def test_standing_terms_monitoring_and_quote_history_keep_dates_and_scope(self):
        from apps.tenant_apps.rates.models import RateSource, Rate
        from decimal import Decimal
        with self.scoped():
            policy=loans.PawnLoanEconomicPolicy.objects.create(workspace=self.a,license=self.series.license,
                series=self.series,effective_from=date(2020,1,1),default_tenure_months=12,
                default_entry_purpose='PAPER',currency_quantum=Decimal('1'))
            monitor=loans.LoanMonitoringPolicy.objects.create(workspace=self.a,license=self.series.license,version=1,
                effective_from=date(2020,1,1),compliance_profile='owner review',ltv_warning_ratio='.7',
                ltv_breach_ratio='.8',ltv_critical_ratio='1',eligible_custody_states=['IN_VAULT'],severity_mapping={'WATCH':'WARNING'})
            source=RateSource.objects.create(workspace=self.a,name='Owner quote',location='Town')
            quote=Rate.objects.create(workspace=self.a,rate_source=source,buying_rate=100,selling_rate=110)
            exported=self.export()
        with self.scoped(self.b):
            review=self.preview(exported)
            self.restore(exported,review)
            copied=loans.PawnLoanEconomicPolicy.objects.get()
            self.assertNotEqual(copied.series_id,policy.series_id)
            self.assertEqual(copied.default_tenure_months,12)
            self.assertEqual(copied.default_entry_purpose,'PAPER')
            self.assertEqual(copied.currency_quantum,1)
            self.assertEqual(copied.effective_from,policy.effective_from)
            self.assertEqual(loans.LoanMonitoringPolicy.objects.get().created_at,monitor.created_at)
            self.assertEqual(loans.LoanMonitoringPolicy.objects.get().valuation_basis,'ORIGINAL_AGREEMENT')
            self.assertEqual(Rate.objects.get().timestamp,quote.timestamp)

    def test_bronze_quote_and_current_metal_choice_survive_business_package(self):
        from django.utils import timezone
        from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
        from apps.tenant_apps.rates.models import Rate, RateSource
        with self.scoped():
            self.write()
            source = RateSource.objects.create(workspace=self.a, name='Fictional bronze source', location='Local')
            quote = Rate.objects.create(workspace=self.a, rate_source=source, metal='Bronze',
                buying_rate=Decimal('0.60'), selling_rate=Decimal('0.75'))
            create_loan_monitoring_policy(workspace=self.a, actor=self.actor, effective_from=timezone.localdate(),
                compliance_profile='Current bronze price monitoring', valuation_basis='CALCULATED_METAL_VALUE',
                ltv_warning_ratio='.7', ltv_breach_ratio='.8', ltv_critical_ratio='.9')
            exported = self.export()
            self.assertEqual(exported['profile'], package.MONITORING_PROFILE)
        with self.scoped(self.b):
            review = self.preview(exported)
            self.restore(exported, review)
            copied = Rate.objects.get(metal='Bronze')
            self.assertEqual((copied.buying_rate, copied.selling_rate, copied.purity, copied.effective_at),
                             (quote.buying_rate, quote.selling_rate, quote.purity, quote.effective_at))
            self.assertEqual(loans.LoanMonitoringPolicy.objects.get().valuation_basis, 'CALCULATED_METAL_VALUE')

    def test_monitoring_choice_package_preserves_scopes_amendments_and_original_loan(self):
        from django.utils import timezone
        from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
        from apps.tenant_apps.loans.selectors.monitoring_policy import resolve_monitoring_policy
        from apps.tenant_apps.loans.services.storage_operations import create_storage_location
        from apps.tenant_apps.rates.models import RateSource,Rate
        from apps.tenant_apps.rates.portable_quotes import PROFILE as quote_profile
        with self.scoped():
            origin=self.write()
            original_method=origin.loan.policy_snapshot.valuation_method
            location=create_storage_location(workspace=self.a,actor=self.actor,level='BRANCH',code='M3',name='Source branch')
            source=RateSource.objects.create(workspace=self.a,name='Source market',location='Source town')
            quote=Rate.objects.create(workspace=self.a,rate_source=source,buying_rate=3000,selling_rate=3100)
            original_quote=dict(quote.source_snapshot)
            source.name='Updated source name'
            source.save(update_fields=['name'])
            values=dict(effective_from=date(2020,1,1),compliance_profile='Source monitoring',
                ltv_warning_ratio='.7',ltv_breach_ratio='.8',ltv_critical_ratio='.9',
                rate_freshness_days=7,appraisal_freshness_days=90)
            first=create_loan_monitoring_policy(workspace=self.a,actor=self.actor,**values)
            current=create_loan_monitoring_policy(workspace=self.a,actor=self.actor,**{
                **values,'effective_from':timezone.localdate(),'supersedes':first,
                'amendment_reason':'Owner chooses current metal monitoring','valuation_basis':'CALCULATED_METAL_VALUE'})
            override=create_loan_monitoring_policy(workspace=self.a,actor=self.actor,
                **{**values,'license':self.series.license,'valuation_basis':'LOWER_OF_CALCULATED_AND_APPRAISAL'})
            exported=self.export()
            self.assertEqual(exported['profile'],package.MONITORING_PROFILE)
            tables=json.loads((self.directory/'setup.json').read_text())
            self.assertEqual([row['valuation_basis'] for row in tables['loans.LoanMonitoringPolicy']],
                ['ORIGINAL_AGREEMENT','CALCULATED_METAL_VALUE','LOWER_OF_CALCULATED_AND_APPRAISAL'])
        with self.scoped(self.b):
            review=self.preview(exported)
            self.assertFalse(loans.LoanMonitoringPolicy.objects.exists())
            receipt=self.restore(exported,review)
            self.assertEqual(receipt.summary['profile'],package.MONITORING_PROFILE)
            self.assertEqual(self.restore(exported,review).pk,receipt.pk)
            copied=list(loans.LoanMonitoringPolicy.objects.order_by('pk'))
            self.assertEqual(copied[1].supersedes_id,copied[0].pk)
            self.assertNotEqual(copied[1].supersedes_id,first.pk)
            for before,after in zip((first,current,override),copied):
                self.assertEqual((after.valuation_basis,after.effective_from,after.created_at,after.amendment_reason),
                    (before.valuation_basis,before.effective_from,before.created_at,before.amendment_reason))
                self.assertEqual(after.created_by_id,self.actor.pk)
                self.assertEqual(after.workspace_id,self.b.pk)
            loan=loans.PawnLoan.objects.get()
            self.assertEqual(loan.policy_snapshot.valuation_method,original_method)
            copied_quote=Rate.objects.get()
            self.assertEqual(copied_quote.source_snapshot,original_quote)
            self.assertEqual(copied_quote.timestamp,quote.timestamp)
            self.assertEqual(copied_quote.portable_source['profile'],quote_profile)
            self.assertNotEqual(loans.PawnStorageLocation.objects.get().public_id,location.public_id)
            self.assertEqual(resolve_monitoring_policy(workspace_id=self.b.pk,license_id=loan.license_id,
                as_of_date=timezone.localdate()).valuation_basis,'LOWER_OF_CALCULATED_AND_APPRAISAL')
            self.assertEqual(resolve_monitoring_policy(workspace_id=self.b.pk,license_id=None,
                as_of_date=timezone.localdate()).valuation_basis,'CALCULATED_METAL_VALUE')
            with self.assertRaises(DatabaseError),transaction.atomic():
                BusinessPackageReceipt.objects.filter(pk=receipt.pk).update(summary={})
            from importlib import import_module
            migration=import_module('apps.tenant_apps.data_portability.migrations.0026_monitoring_setup_profile')
            with self.assertRaisesMessage(DatabaseError,'Retained monitoring-choice packages'),transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(migration.Migration.operations[0].reverse_sql)

    def test_new_setup_profile_rejects_unknown_missing_and_downgraded_monitoring_choice(self):
        import copy
        with self.scoped():
            loans.LoanMonitoringPolicy.objects.create(workspace=self.a,version=1,effective_from=date(2020,1,1),
                compliance_profile='Reviewed appraisal monitoring',valuation_basis='LATEST_APPRAISAL',
                ltv_warning_ratio='.7',ltv_breach_ratio='.8',ltv_critical_ratio='.9',
                eligible_custody_states=['IN_VAULT'],severity_mapping={'strategy':'derived-v1'})
            exported=self.export()
            tables=json.loads((self.directory/'setup.json').read_text())
            self.assertEqual(tables['loans.LoanMonitoringPolicy'][0]['valuation_basis'],'LATEST_APPRAISAL')
            invalid=copy.deepcopy(tables)
            invalid['loans.LoanMonitoringPolicy'][0]['valuation_basis']='UNKNOWN'
            with self.assertRaisesMessage(ValueError,'Unsupported portable enum'):
                setup.validate_tables(invalid,version=3)
            invalid=copy.deepcopy(tables)
            del invalid['loans.LoanMonitoringPolicy'][0]['valuation_basis']
            with self.assertRaisesMessage(ValueError,'Unexpected setup fields'):
                setup.validate_tables(invalid,version=3)
            for version in (1,2):
                with self.assertRaisesMessage(ValueError,'newer business setup profile'):
                    setup.export_setup(workspace_id=self.a.pk,actor=self.actor,save_file=lambda field:None,version=version)
            # Recompute the manifest hash so rejection proves the versioned
            # schema prevents a downgrade, independently of checksum checking.
            exported['profile']=package.GRAPH_PROFILE
            exported['sha256']=contracts.digest({k:v for k,v in exported.items() if k!='sha256'})
            (self.directory/'package.json').write_text(contracts.dump(exported))
            with self.assertRaisesMessage(ValueError,'Unexpected setup fields'):
                package.read_package(self.directory,expected_sha256=exported['sha256'])

    def test_confirmation_binds_actor_source_and_unactivated_destination(self):
        from apps.tenancy.testing import start_workspace_trial
        with self.scoped():
            exported=self.export()
        with self.scoped(self.b):
            review=self.preview(exported)
            with self.assertRaisesMessage(ValueError,'Confirm the reviewed'):
                package.restore_package(workspace_id=self.b.pk,actor=self.actor,directory=self.directory,
                    expected_sha256=exported['sha256'],approval=review['approval'])
            with self.assertRaises(PermissionDenied):
                package.restore_package(workspace_id=self.b.pk,actor=self.other_actor,directory=self.directory,
                    expected_sha256=exported['sha256'],approval=review['approval'],confirmed=True)
            start_workspace_trial(workspace=self.b)
            with self.assertRaisesMessage(ValueError,'without subscription'):
                self.restore(exported,review)

    def test_printing_configuration_and_assets_restore_without_new_document_issue(self):
        from apps.tenant_apps.loans.documents import starter_layout, built_in_print_profile
        from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
        from apps.tenant_apps.loans.services.print_profiles import LoanDocumentPrintProfileService
        from io import BytesIO
        from PIL import Image
        with self.scoped():
            revision=LoanDocumentLayoutService.create_layout(workspace=self.a,actor=self.actor,
                document_type='loan_ticket',name='Transfer layout',definition=starter_layout('loan_ticket').canonical_dict())
            output=BytesIO()
            Image.new('RGB',(10,10),'red').save(output,format='PNG')
            asset=LoanDocumentLayoutService.add_asset(revision=revision,actor=self.actor,key='logo',kind='IMAGE',content=output.getvalue(),filename='logo.png')
            revision=LoanDocumentLayoutService.publish(revision=revision,actor=self.actor)
            LoanDocumentLayoutService.assign(revision=revision,workspace=self.a,series=self.series,actor=self.actor)
            definition=built_in_print_profile('A4_SIDE_BY_SIDE')
            profile=LoanDocumentPrintProfileService.create_profile(workspace=self.a,actor=self.actor,
                document_type='loan_ticket',name=definition.name,definition=definition.canonical_dict())
            profile=LoanDocumentPrintProfileService.publish(revision=profile,actor=self.actor)
            LoanDocumentPrintProfileService.assign(revision=profile,workspace=self.a,series=self.series,actor=self.actor)
            exported=self.export()
        with self.scoped(self.b):
            review=self.preview(exported)
            self.restore(exported,review)
            self.assertEqual(loans.LoanDocumentLayoutRevision.objects.get().content_hash,revision.content_hash)
            self.assertEqual(loans.LoanDocumentPrintProfileRevision.objects.get().content_hash,profile.content_hash)
            self.assertEqual(loans.LoanDocumentAsset.objects.get().sha256,asset.sha256)
            self.assertEqual(loans.LoanDocumentLayoutAssignment.objects.get().series_id,loans.LoanSeries.objects.get().pk)
            self.assertFalse(loans.LoanDocumentIssue.objects.exists())
