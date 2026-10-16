import json
from io import StringIO
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenancy.context import without_workspace_context
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.monitoring_readiness import get_monitoring_readiness
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from . import test_monitoring_valuation_basis as fixtures, test_collateral_reappraisal as collateral


class MonitoringWorkViewsTests(WorkspaceTestCase):
    setup_tenant=classmethod(fixtures.MonitoringValuationTests.setup_tenant.__func__)

    def setUp(self):
        collateral.CollateralReappraisalTests.make_loan(self)
        self.start_active_trial()
        self.client=self.make_workspace_client()
        self.client.force_login(self.actor)

    def test_readiness_includes_stopped_register_and_reports_actual_evidence_separately(self):
        m.LoanLicense.objects.filter(pk=self.loan.license_id).update(is_active=False)
        before=list(m.PawnLoanEvent.objects.values_list('pk','payload_fingerprint'))
        readiness=get_monitoring_readiness(workspace=self.tenant,environ={'ROKKAD_MONITOR_WORKSPACE_IDS':'999999'})
        self.assertEqual(readiness['summary'].loan_count,1)
        self.assertEqual(readiness['scopes'][0]['license'].pk,self.loan.license_id)
        self.assertEqual(readiness['assignment'],'NOT_LISTED')
        self.assertEqual(readiness['pending_count'],1)
        self.assertEqual(readiness['scopes'][0]['metals'][0]['price_status'],'STALE')
        self.assertEqual(list(m.PawnLoanEvent.objects.values_list('pk','payload_fingerprint')),before)

    def test_read_only_command_requires_explicit_context_and_reports_without_refresh(self):
        before=(m.LoanRiskSnapshot.objects.count(),m.LoanRiskEvent.objects.count(),m.PawnLoanEvent.objects.count())
        out=StringIO()
        with without_workspace_context():
            call_command('monitoring_status',workspace_id=[self.tenant.pk],stdout=out)
        report=json.loads(out.getvalue())
        self.assertEqual((report['workspace'],report['pending']),(self.tenant.pk,1))
        self.assertEqual((m.LoanRiskSnapshot.objects.count(),m.LoanRiskEvent.objects.count(),m.PawnLoanEvent.objects.count()),before)

    def test_work_filters_separate_unknown_valuation_from_measured_risk_and_pending(self):
        self.assertEqual(get_risk_portfolio(attention='assessment').paginator.count,1)
        refresh_loan_risk_snapshot(self.loan.pk,as_of_date=self.today)
        self.assertEqual(get_risk_portfolio(attention='assessment').paginator.count,0)
        self.assertEqual(get_risk_portfolio(attention='evidence').paginator.count,1)
        self.assertEqual(get_risk_portfolio(attention='measured').paginator.count,0)
        self.assertEqual(get_risk_portfolio(attention='transactions').paginator.count,0)

    def test_more_than_one_hundred_alerts_remain_reachable_with_old_critical_first(self):
        # Derivative UI fixtures, not admitted financial agreements. A retained
        # breach alert can outlive a failed replacement projection.
        loans=m.PawnLoan.objects.bulk_create([m.PawnLoan(workspace=self.tenant,
            license_id=self.loan.license_id,series_id=self.loan.series_id,borrower_id=self.loan.borrower_id,
            product_version_id=self.loan.product_version_id,loan_number=f'ALERT-{i:03}',
            principal_amount=1000,monthly_interest_rate=2,loan_date=self.loan.loan_date,state='ACTIVE') for i in range(101)])
        snapshots=m.LoanRiskSnapshot.objects.bulk_create([m.LoanRiskSnapshot(workspace=self.tenant,
            loan=loan,as_of_date=self.today,status='ERROR',error_message='Synthetic unavailable current evidence') for loan in loans])
        events=m.LoanRiskEvent.objects.bulk_create([m.LoanRiskEvent(workspace=self.tenant,loan=loan,
            snapshot=snapshot,event_type='LTV_CRITICAL_ENTERED' if i==0 else 'LTV_BREACH_ENTERED',
            as_of_date=self.today,trigger_key=f'ui-alert-{i}') for i,(loan,snapshot) in enumerate(zip(loans,snapshots))])
        m.LoanRiskAlert.objects.bulk_create([m.LoanRiskAlert(workspace=self.tenant,loan=loan,source_event=event,
            alert_kind='LTV_BREACH',severity='CRITICAL' if i==0 else 'HIGH',message='Retained breach',
            recommended_action='Review actual evidence') for i,(loan,event) in enumerate(zip(loans,events))])
        path=reverse('workspace_loans:pawn_risk_portfolio',args=[self.tenant.slug])
        first=self.client.get(path)
        self.assertEqual(first.status_code,200)
        self.assertEqual(first.context['alerts_page'].paginator.count,101)
        self.assertEqual(first.context['open_alert_rows'][0][0].loan_id,loans[0].pk)
        self.assertContains(first,'Next alerts')
        last=self.client.get(path,{'alert_page':5})
        self.assertEqual(len(last.context['open_alert_rows']),1)
        self.assertEqual(last.context['open_alert_rows'][0][0].loan_id,loans[-1].pk)
