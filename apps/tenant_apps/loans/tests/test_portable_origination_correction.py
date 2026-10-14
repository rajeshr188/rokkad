from copy import deepcopy
from datetime import date
from uuid import uuid4
from django.db import connection

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.history_contract import HistoryError
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.services.origination_corrections import retained_attempt_event_ids
from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle, restore_servicing_bundle
from apps.tenant_apps.loans.services.servicing_bundle_contract import CORRECTION_PROFILE, read_bundle
from apps.tenant_apps.loans.services.servicing_origination_correction import validate_source_correction
from apps.tenant_apps.loans.tests.test_origination_corrections import OriginationCorrectionTests
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture


class PortableOriginationCorrectionTests(OriginationCorrectionTests):
    """Run the named PC-06 tests; inherited source tests remain unchanged."""
    scoped = PortabilityFixture.scoped

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role_sql=connection.ops.quote_name('correction_port_'+uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {cls.role_sql} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {cls.role_sql}')
            cursor.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {cls.role_sql}')
            cursor.execute(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {cls.role_sql}')

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute('RESET ROLE')
            cursor.execute(f'DROP OWNED BY {cls.role_sql}')
            cursor.execute(f'DROP ROLE {cls.role_sql}')
        super().tearDownClass()

    def test_corrected_source_roundtrip_and_future_anniversary(self):
        from dateutil.relativedelta import relativedelta
        from datetime import timedelta
        from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
        self.data['events'] = [dict(kind='PAYMENT', amount='100',
            date=(self.original_day + timedelta(days=1)).isoformat(),
            reference='Actual receipt', number='', rate=None, tenure=None, recipient='')]
        loan, _ = self.confirm()
        content = export_servicing_bundle(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk)
        document, files = read_bundle(content)
        source_attempts = retained_attempt_event_ids(loan)
        self.assertEqual(document['profile'], CORRECTION_PROFILE)
        self.actor.is_superuser = True
        self.actor.save(update_fields=['is_superuser'])
        target = Company.objects.create(name='PC06 destination', slug='pc06-'+uuid4().hex,
            owner=self.actor, creator=self.actor)
        with without_workspace_context(), self.scoped(target):
            borrower = Party.objects.create(display_name='Exact source borrower')
            identity = PartyIdentity.objects.create(workspace=target, party=borrower)
            source = document['setup'][str(loan.pk)]
            SourceIdentity.objects.create(workspace=target, identity=identity,
                source_system=source['borrower']['source_system'], external_id=source['borrower']['id'],
                accepted_digest='a'*64, local_digest='a'*64)
            license = create_license(workspace=target, actor=self.actor, name='Matching source',
                license_number=source['licence_number'], issued_on=date(2020,1,1), expires_on=date(2099,1,1))
            series = m.LoanSeries.objects.create(license=license, name='Imported', code='P')
            product = m.LoanProduct.objects.create(workspace=target, name='Servicing', code='P')
            version = m.LoanProductVersion.objects.create(product=product, version=1, status='RETIRED',
                maximum_tenor_months=1200, **source['product'])
            mapping = {str(loan.pk):dict(borrower_id=borrower.pk, revision_id=license.revisions.get().pk,
                series_id=series.pk, product_version_id=version.pk)}
            args = dict(workspace_id=target.pk, actor=self.actor, content=content, mapping=mapping)
            preview = restore_servicing_bundle(**args)
            self.assertFalse(m.PawnLoan.objects.exists())
            result = restore_servicing_bundle(**args, expected_sha256=preview['sha256'], confirmed=True)
            restored = m.PawnLoan.objects.get(pk=result['loans'][0])
            attempts = retained_attempt_event_ids(restored)
            self.assertEqual(len(attempts), 2)
            self.assertNotEqual(attempts, source_attempts)
            self.assertEqual(get_servicing_position(restored, as_of_date=self.today).balance.principal_outstanding, 2000)
            boundary = self.original_day + relativedelta(months=1)
            self.assertEqual(get_servicing_position(restored, as_of_date=boundary).balance.interest_outstanding, 0)
            self.assertEqual(get_servicing_position(restored, as_of_date=boundary+timedelta(days=1)).balance.interest_outstanding, 80)
            exported = export_servicing_bundle(workspace_id=target.pk, actor=self.actor, loan_id=restored.pk)
            again, _ = read_bundle(exported)
            self.assertEqual(again['positions'][str(restored.pk)]['recorded'], document['positions'][str(loan.pk)]['recorded'])
            self.assertEqual(len(again['tables']['PawnLoanEvent']), len(document['tables']['PawnLoanEvent']))
            self.assertTrue(restore_servicing_bundle(**args, expected_sha256=preview['sha256'], confirmed=True)['already_restored'])

    def test_bad_correction_pair_held_before_destination_write(self):
        loan, _ = self.confirm()
        content = export_servicing_bundle(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk)
        document, _ = read_bundle(content)
        snapshot = next(row for row in document['tables']['PawnLoanDisbursalSnapshot'] if row['basis']=='RECORDED')
        changed = deepcopy(snapshot)
        changed['evidence']['recording']['origination_correction']['attempts'][0]['payout_sha256'] = '0'*64
        with self.assertRaisesMessage(HistoryError, 'retained payout/reversal'):
            validate_source_correction(changed, document['tables'])
