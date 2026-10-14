from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import override_settings
from django.utils.dateparse import parse_datetime

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle, restore_servicing_bundle
from apps.tenant_apps.loans.services.servicing_bundle_contract import read_bundle, STORAGE_PROFILE
from apps.tenant_apps.loans.services.storage_operations import create_storage_location, place_or_transfer_collateral
from apps.tenant_apps.loans.services.history_contract import HistoryError
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from apps.tenant_apps.loans.tests.test_servicing_bundle import destination
from apps.tenant_apps.data_portability.tests import test_business_package as package_fixtures


class PortableStorageTests(OpeningImportFixture):
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
    export = package_fixtures.BusinessPackageTests.export
    preview = package_fixtures.BusinessPackageTests.preview
    restore = package_fixtures.BusinessPackageTests.restore

    def locations(self):
        parent = None
        for level in ('BRANCH','VAULT','CABINET','BOX'):
            parent = create_storage_location(workspace=self.a, actor=self.actor,
                level=level, code=level, name=level, parent=parent)
        self.box = parent
        self.other_box = create_storage_location(workspace=self.a, actor=self.actor,
            level='BOX', code='BOX2', name='Second box',parent=parent.parent)

    def source(self):
        self.locations()
        origin=self.write()
        item=origin.loan.collateral_items.get()
        for location in (self.box,self.other_box):
            place_or_transfer_collateral(item.pk, destination_id=location.pk,
                reason='Source physical placement',actor=self.actor)
        return origin

    def test_storage_chain_roundtrip_and_future_transfer(self):
        with self.scoped():
            origin=self.source()
            content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=origin.loan_id)
        document,_=read_bundle(content)
        self.assertEqual(document['profile'],STORAGE_PROFILE)
        self.assertEqual(len(document['tables']['PawnStorageLocation']),5)
        self.assertEqual(len(document['tables']['PawnCollateralStorageMovement']),2)
        mapping=destination(self,document)
        with self.scoped(self.b):
            args=dict(workspace_id=self.b.pk,actor=self.actor,content=content,mapping=mapping)
            review=restore_servicing_bundle(**args)
            self.assertFalse(m.PawnStorageLocation.objects.exists())
            result=restore_servicing_bundle(**args,expected_sha256=review['sha256'],confirmed=True)
            item=m.PawnCollateralItem.objects.get(loan_id=result['loans'][0])
            self.assertEqual(item.current_storage_location.code,'BOX2')
            self.assertEqual(list(item.storage_movements.values_list('moved_at',flat=True)),
                [parse_datetime(row['moved_at']) for row in document['tables']['PawnCollateralStorageMovement']])
            box=m.PawnStorageLocation.objects.get(code='BOX')
            place_or_transfer_collateral(item.pk,destination_id=box.pk,reason='Actual destination transfer',actor=self.actor)
            item.refresh_from_db()
            self.assertEqual(item.current_storage_location_id,box.pk)
            exported,_=read_bundle(export_servicing_bundle(workspace_id=self.b.pk,actor=self.actor,loan_id=item.loan_id))
            self.assertEqual(len(exported['tables']['PawnCollateralStorageMovement']),3)

    def test_package_disjoint_loans_share_exact_storage_ancestors(self):
        with self.scoped():
            origin=self.source()
            review=deepcopy(self.review)
            review['source'].update(loan_id='loan-2',number='OLD00002',loan_sha256='b'*64)
            other=self.write(review=review)
            place_or_transfer_collateral(other.loan.collateral_items.get().pk,destination_id=self.box.pk,
                reason='Other source item',actor=self.actor)
            exported=self.export()
        with self.scoped(self.b):
            preview=self.preview(exported)
            receipt=self.restore(exported,preview)
            self.assertEqual(len(receipt.results),2)
            self.assertEqual(m.PawnStorageLocation.objects.count(),5)
            self.assertEqual(m.PawnCollateralStorageMovement.objects.count(),3)

    def test_forged_storage_projection_and_reversed_chain_are_held(self):
        from apps.tenant_apps.loans.tests.test_servicing_bundle import altered
        with self.scoped():
            origin=self.source()
            content=export_servicing_bundle(workspace_id=self.a.pk,actor=self.actor,loan_id=origin.loan_id)
        document,_=read_bundle(content)
        mapping=destination(self,document)
        with self.scoped(self.b):
            changed=altered(content,lambda doc:doc['tables']['PawnCollateralItem'][0].update(current_storage_location_id=None))
            with self.assertRaisesMessage(HistoryError,'exact movement chain'):
                restore_servicing_bundle(workspace_id=self.b.pk,actor=self.actor,content=changed,mapping=mapping)
            self.assertFalse(m.PawnLoan.objects.exists())
