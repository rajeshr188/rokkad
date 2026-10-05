"""Owner-requested fictional Lakshmi example through the ordinary New loan route."""
from datetime import date
from decimal import Decimal

from django.test import override_settings
from django.urls import reverse

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.economic_policies import create_pawn_economic_configuration, create_pawn_loan_fee_policy
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from . import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(ROOT_URLCONF='django_project.workspace_urls', STORAGES={
    'default': {'BACKEND':'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class GeneratedLakshmiAcceptanceTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history

    @classmethod
    def get_test_schema_name(cls):
        return 'ld08-generated-lakshmi'

    def setUp(self):
        super().setUp()
        self.prepare_history()
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.actor)
        self.original_date = date(2026,4,5)
        product = m.LoanProduct.objects.create(workspace=self.tenant,code='LD08-FLEX',name='Fictional flexible agreement')
        self.product = m.LoanProductVersion.objects.create(workspace=self.tenant,product=product,version=1,
            status='ACTIVE',repayment_structure='FLEXIBLE_PARTIAL_PAYMENT',amortisation_method='NONE',
            payment_frequency='AT_MATURITY',minimum_tenor_months=1,maximum_tenor_months=600,
            extra_payment_rule='REDUCE_PRINCIPAL',calculation_contract_version='TEST-V1')
        create_pawn_loan_fee_policy(workspace=self.tenant,license=self.series.license,code='DOCUMENT_CHARGE',
            name='Document charge',calculation_type='FIXED',value=Decimal('10'),effective_from=self.original_date,actor=self.actor)

    def submit_example(self, *, quantum='0.01', closed=True):
        create_pawn_economic_configuration(workspace=self.tenant,series=self.series,license=self.series.license,
            gold_monthly_interest_rate=Decimal('2'),silver_monthly_interest_rate=Decimal('1.5'),
            valuation_method='CALCULATED_METAL_VALUE',maximum_ltv_ratio=Decimal('0.8'),
            default_tenure_months=12,advance_interest_periods=1,currency_quantum=Decimal(quantum),
            default_entry_purpose='PAPER',effective_from=self.original_date,actor=self.actor)
        path = reverse('workspace_loans:pawn_loan_create',args=[self.tenant.slug])
        page = self.client.get(path)
        self.assertEqual(page.context['entry_purpose'],'paper')
        values = dict(borrower_id=self.data['borrower_id'],series_id=self.series.pk,product_version_id=self.product.pk,
            number='LD08-FICTIONAL-001',date=self.original_date.isoformat(),source_reference='FICTIONAL acceptance book / page 1',
            routine_entry='on',entry_mode='paper',intent_token=page.context['intent_token'],action='preview',
            payout_basis='CASH',confirmed_history='on',complete_through=self.today.isoformat(),
            final_state='CLOSED' if closed else 'ACTIVE',**{'collateral-TOTAL_FORMS':'2','collateral-INITIAL_FORMS':'0',
                'events-TOTAL_FORMS':'3' if closed else '2','events-INITIAL_FORMS':'0'})
        for index,item in enumerate([
            dict(description='Fictional gold chain',metal='GOLD',quantity='1',gross_weight='10',net_weight='9',purity_percentage='90',allocated_principal='10000'),
            dict(description='Fictional silver anklets',metal='SILVER',quantity='2',gross_weight='100',net_weight='90',purity_percentage='90',allocated_principal='5000')]):
            values.update({'collateral-'+str(index)+'-'+key:value for key,value in item.items()})
        may_interest = '250.88' if quantum=='0.01' else '251'
        june_interest = '213.38' if quantum=='0.01' else '213'
        rows = [dict(kind='PAYMENT',date='2026-04-20',amount='1275',reference='FICTIONAL receipt 1',item_principal_1='1000',item_principal_2='275'),
            dict(kind='PAYMENT',date='2026-05-10',amount=str(Decimal('2000')+Decimal(may_interest)),reference='FICTIONAL receipt 2',item_principal_1='1500',item_principal_2='500'),
            dict(kind='CLOSE',date='2026-06-08',amount=str(Decimal('11725')+Decimal(june_interest)),reference='FICTIONAL return receipt',
                closure_basis='RETURNED',recipient='Fictional borrower',number='R-0090')]
        for index,row in enumerate(rows if closed else rows[:2]):
            values.update({'events-'+str(index)+'-'+key:value for key,value in row.items()})
        preview = self.client.post(path,values)
        self.assertIsNotNone(preview.context['review'],(preview.context['form'].errors,preview.context['formset'].errors))
        result = self.client.post(path,dict(values,action='confirm',confirm_review='on',review_token=preview.context['review_token']))
        self.assertEqual(result.status_code,302)
        loan = m.PawnLoan.objects.get(loan_number=values['number'])
        self.assertEqual((loan.tenure_months,loan.disbursal_snapshot.advance_interest,loan.disbursal_snapshot.deducted_fees,
                          loan.disbursal_snapshot.net_disbursed),(12,Decimal('275'),Decimal('10'),Decimal('14715')))
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertEqual(loan.policy_snapshot.currency_quantum,Decimal(quantum))
        return loan,preview.context['review']

    def test_paise_policy_complete_paper_history_becomes_ordinary_closed_loan(self):
        loan,review = self.submit_example()
        self.assertEqual([(Decimal(r['interest']),Decimal(r['principal'])) for r in review['rows'][1:]],
            [(Decimal('0'),Decimal('1275')),(Decimal('250.88'),Decimal('2000')),(Decimal('213.38'),Decimal('11725'))])
        self.assertEqual(loan.state,'CLOSED')
        self.assertEqual(collection_balance(loan,self.today).total_due,0)
        self.assertEqual(list(loan.collateral_items.values_list('custody_state',flat=True)),['WITH_CUSTOMER','WITH_CUSTOMER'])
        response = self.client.get(reverse('loans:pawn_loan_list'),{'q':loan.loan_number,'state':'CLOSED'})
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertNotContains(response,'data-historical-record')

    def test_whole_rupee_standing_policy_and_next_charge_boundary(self):
        loan,_ = self.submit_example(quantum='1',closed=False)
        self.assertEqual(collection_balance(loan,date(2026,5,5)).principal_outstanding,Decimal('13725'))
        self.assertEqual(collection_balance(loan,date(2026,5,5)).interest_outstanding,0)
        self.assertEqual(collection_balance(loan,date(2026,5,6)).interest_outstanding,Decimal('251'))
        self.assertEqual(collection_balance(loan,date(2026,6,5)).interest_outstanding,0)
        self.assertEqual(collection_balance(loan,date(2026,6,6)).total_due,Decimal('11938'))
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
        from apps.tenant_apps.rates.models import Rate, RateSource
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant,effective_from=self.today,version=1,
            compliance_profile='Fictional current coverage',ltv_warning_ratio=Decimal('0.7'),
            ltv_breach_ratio=Decimal('0.8'),ltv_critical_ratio=Decimal('0.9'),
            eligible_custody_states=['IN_VAULT','WITH_FUNDING_LENDER'],
            severity_mapping={'strategy':'derived-v1'},created_by=self.actor)
        before = get_pawn_loan_collateral_valuation(loan.pk,as_of_date=self.today)
        self.assertIsNone(before.eligible_collateral_value)
        source = RateSource.objects.create(name='Fictional current prices',location='Test only')
        for metal,price in (('Gold',2000),('Silver',200)):
            Rate.objects.create(rate_source=source,metal=metal,buying_rate=price,selling_rate=price)
        after = get_pawn_loan_collateral_valuation(loan.pk,as_of_date=self.today)
        self.assertEqual(after.eligible_collateral_value,Decimal('32400'))
        self.assertIsNotNone(after.ltv.ltv_ratio)
        self.assertNotIn('TRANSACTIONS_UNCONFIRMED',get_pawn_loan_risk_assessment(loan.pk,as_of_date=self.today).flags)
        loan.disbursal_snapshot.refresh_from_db()
        self.assertEqual(loan.disbursal_snapshot.gross_principal,Decimal('15000'))
