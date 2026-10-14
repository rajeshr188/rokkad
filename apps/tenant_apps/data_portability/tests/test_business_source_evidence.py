from datetime import date,timedelta
from unittest.mock import patch
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference, assert_series_can_issue, update_license
from apps.tenant_apps.loans.services.license_continuation import verify_legacy_license, numbering_review_digest
from apps.tenant_apps.loans.services.portable_licence_evidence import PROFILE as LICENCE_PROFILE
from apps.tenant_apps.data_portability import business_package as package, services
from apps.tenant_apps.data_portability.tests import test_business_package as fixture
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.rates.models import Rate,RateSource
from apps.tenant_apps.rates.portable_quotes import PROFILE as QUOTE_PROFILE


class BusinessSourceEvidenceTests(OpeningImportFixture):
    export=fixture.BusinessPackageTests.export
    preview=fixture.BusinessPackageTests.preview
    restore=fixture.BusinessPackageTests.restore

    def setUp(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        super().setUp()
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)/'source'
        self.directory.mkdir()
        override=override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
            'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}},MEDIA_ROOT=Path(self.temp.name)/'storage')
        override.enable()
        self.addCleanup(override.disable)

    def test_changed_quote_source_retained_and_new_observation_remains_current(self):
        with self.scoped():
            self.write()
            source=RateSource.objects.create(name='Original market',location='Original town')
            quote=Rate.objects.create(rate_source=source,buying_rate=3000,selling_rate=3100,recorded_by=self.actor)
            original_time=quote.timestamp
            original_snapshot=dict(quote.source_snapshot)
            source.name='Renamed market'
            source.save(update_fields=['name'])
            exported=self.export()
            self.assertEqual(exported['profile'],package.GRAPH_PROFILE)
        with self.scoped(self.b):
            receipt=self.restore(exported,self.preview(exported))
            restored=Rate.objects.get()
            self.assertEqual(restored.source_snapshot,original_snapshot)
            self.assertEqual(restored.timestamp,original_time)
            self.assertEqual(restored.rate_source.name,'Renamed market')
            self.assertEqual(restored.portable_source['profile'],QUOTE_PROFILE)
            self.assertFalse(m.LoanLicense.objects.get().is_active)
            current=Rate.objects.create(rate_source=restored.rate_source,buying_rate=3200,selling_rate=3300,recorded_by=self.actor)
            self.assertEqual(current.source_snapshot['name'],'Renamed market')
            self.assertEqual(current.portable_source,{})
            restored.refresh_from_db()
            self.assertEqual(restored.source_snapshot,original_snapshot)

    def test_source_attestation_is_not_a_destination_attestation_or_lending_permission(self):
        with self.scoped():
            self.write()
            license=create_legacy_license_reference(workspace=self.a,actor=self.actor,name='Source attested',
                source_label='ATTEST-L',evidence_reference='Old book grouping')
            series=m.LoanSeries.objects.create(license=license,name='Attested',code='AT')
            sequences=[m.LoanNumberSequence.objects.create(series=series,document_kind=kind,prefix=prefix,width=5,maximum_number=99999)
                for kind,prefix in (('PAWN_LOAN','AT'),('PAWN_LOAN_RELEASE','ATR'))]
            today=timezone.localdate()
            verify_legacy_license(workspace_id=self.a.pk,license_id=license.pk,actor=self.actor,
                issued_on=today-timedelta(days=100),expires_on=today+timedelta(days=365),issuing_authority='Source authority',
                supporting_document=None,source_sha256='a'*64,source_as_of=today,source_reference='Owner source book',
                confirmed_complete=True,counters={row.pk:0 for row in sequences},expected_revision_id=license.revisions.get().pk,
                expected_numbering_digest=numbering_review_digest(sequences),document_deferral_reason='Original document retained off site')
            source_proof=license.revisions.get(kind='ATTESTATION').verification_evidence
            exported=self.export()
        with self.scoped(self.b):
            self.restore(exported,self.preview(exported))
            restored=m.LoanLicense.objects.get(license_number='ATTEST-L')
            self.assertFalse(restored.is_active)
            revision=restored.revisions.order_by('-revision_number').first()
            self.assertEqual(revision.kind,'IMPORTED_SOURCE')
            self.assertEqual(revision.verification_evidence['profile'],LICENCE_PROFILE)
            self.assertEqual(revision.verification_evidence['source_kind'],'ATTESTATION')
            self.assertEqual(revision.verification_evidence['original_evidence'],source_proof)
            self.assertFalse(m.LoanLicenseRevision.objects.filter(kind='ATTESTATION').exists())
            series=m.LoanSeries.objects.get(code='AT')
            restored.is_active=True
            restored.save(update_fields=['is_active'])
            with self.assertRaisesMessage(ValueError,'Review and save the imported licence'):
                assert_series_can_issue(series)
            update_license(restored,actor=self.actor)
            series.refresh_from_db()
            assert_series_can_issue(series)
            self.assertEqual(restored.revisions.order_by('-revision_number').first().kind,'AMENDMENT')

    def test_legacy_quote_keeps_its_original_date_and_provenance_on_reexport(self):
        from apps.tenant_apps.rates.portable_quotes import source_evidence
        with self.scoped():
            self.write()
            source=RateSource.objects.create(name='Legacy market',location='Original town')
            snapshot=dict(name=source.name,location=source.location,tax_included=source.tax_included,legacy=True)
            proof=source_evidence(namespace=self.review['source']['namespace'],row=dict(id=99,source_snapshot=snapshot))
            original_time=timezone.now()-timedelta(days=20)
            quote=Rate.objects.create(rate_source=source,buying_rate=3000,selling_rate=3100,effective_at=original_time,
                source_snapshot=snapshot,portable_source=proof,recorded_by=self.actor)
            exported=self.export()
        with self.scoped(self.b):
            self.restore(exported,self.preview(exported))
            restored=Rate.objects.get()
            self.assertEqual(restored.source_snapshot,snapshot)
            self.assertEqual(restored.portable_source,proof)
            self.assertEqual(restored.effective_at,original_time)
            self.assertEqual((timezone.now()-restored.effective_at).days,20)
            from apps.tenant_apps.loans.services import business_setup_portability as setup
            tables=setup.export_setup(workspace_id=self.b.pk,actor=self.actor,save_file=lambda field:None,version=2)
            self.assertEqual(tables['rates.Rate'][0]['portable_source'],proof)
            self.assertEqual(tables['rates.Rate'][0]['source_snapshot'],snapshot)

    def test_imported_proof_cannot_bypass_quote_hash_or_withdrawal_guards(self):
        from copy import deepcopy
        from django.db import transaction,DatabaseError
        from apps.tenant_apps.rates.portable_quotes import source_evidence
        with self.scoped():
            source=RateSource.objects.create(name='Source market',location='Local')
            snapshot=dict(name=source.name,location=source.location,tax_included=source.tax_included,legacy=True)
            proof=source_evidence(namespace=self.review['source']['namespace'],row=dict(id=99,source_snapshot=snapshot))
            bad=deepcopy(proof)
            bad['sha256']='0'*64
            with self.assertRaisesMessage(ValidationError,'Imported quote source evidence'):
                Rate.objects.create(rate_source=source,buying_rate=3000,selling_rate=3100,
                    source_snapshot=snapshot,portable_source=bad,recorded_by=self.actor)
            quote=Rate.objects.create(rate_source=source,buying_rate=3000,selling_rate=3100,
                source_snapshot=snapshot,portable_source=proof,recorded_by=self.actor)
            with self.assertRaisesMessage(DatabaseError,'Withdrawal must preserve'),transaction.atomic():
                Rate.objects.bulk_create([Rate(workspace=self.a,rate_source=source,buying_rate=3001,selling_rate=3100,
                    metal=quote.metal,purity=quote.purity,currency=quote.currency,effective_at=quote.effective_at,
                    is_withdrawal=True,supersedes=quote,reason='Invalid imported withdrawal',recorded_by=self.actor,
                    source_snapshot=snapshot,portable_source=proof)])
            self.assertEqual(Rate.objects.count(),1)
