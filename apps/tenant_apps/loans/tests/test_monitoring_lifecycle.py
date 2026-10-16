"""Policy schedule and scope changes append evidence without restating loans."""
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.forms.models import model_to_dict
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.monitoring_policy import resolve_monitoring_policy
from apps.tenant_apps.loans.services.monitoring_policies import (
    create_loan_monitoring_policy, cancellation_values, POLICY_SETTINGS,
)
from .test_monitoring_valuation_basis import MonitoringValuationTests as _Fixture
from .test_collateral_reappraisal import CollateralReappraisalTests as _Collateral


class MonitoringLifecycleTests(WorkspaceTestCase):
    setup_tenant = classmethod(_Fixture.setup_tenant.__func__)

    @classmethod
    def get_test_schema_name(cls):
        return 'monitoring-lifecycle'

    def setUp(self):
        _Collateral.make_loan(self)

    def change(self, prior=None, **changes):
        prior = prior or self.policy
        values = {name: getattr(prior, name) for name in POLICY_SETTINGS}
        values.update(license=prior.license, supersedes=prior, effective_from=self.today,
            amendment_reason='Reviewed monitoring change')
        values.update(changes)
        return create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **values)

    def resolved(self, day=None, license_id=None):
        return resolve_monitoring_policy(workspace_id=self.tenant.pk,
            license_id=license_id, as_of_date=day or self.today)

    def test_explicit_urgent_change_replaces_pending_schedule_and_preserves_history(self):
        before = model_to_dict(self.policy)
        financial = list(self.loan.loan_events.values_list('pk', 'payload_fingerprint'))
        scheduled = self.change(effective_from=self.today+timedelta(days=20), ltv_breach_ratio=Decimal('.85'))
        with self.assertRaises(ValidationError):
            self.change(scheduled, effective_from=self.today)
        urgent = self.change(scheduled, effective_from=self.today, replaces_scheduled=True,
            valuation_basis='CALCULATED_METAL_VALUE')
        self.assertEqual(self.resolved().pk, urgent.pk)
        self.assertEqual(self.resolved(self.today+timedelta(days=30)).pk, urgent.pk)
        self.assertEqual(self.resolved(self.today-timedelta(days=1)).pk, self.policy.pk)
        self.policy.refresh_from_db()
        self.assertEqual(model_to_dict(self.policy), before)
        self.assertEqual(list(self.loan.loan_events.values_list('pk','payload_fingerprint')), financial)

    def test_cancel_pending_changes_retains_current_settings_instead_of_reactivating_future_rows(self):
        scheduled = self.change(effective_from=self.today+timedelta(days=10), valuation_basis='LATEST_APPRAISAL')
        values = cancellation_values(scheduled)
        values['amendment_reason'] = 'Cancel the reviewed future change'
        cancelled = create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **values)
        for name in POLICY_SETTINGS:
            self.assertEqual(getattr(cancelled,name),getattr(self.policy,name))
        self.assertEqual(self.resolved(self.today+timedelta(days=20)).pk, cancelled.pk)
        with self.assertRaises(ValidationError):
            cancellation_values(cancelled)
        with self.assertRaises(ValidationError):
            create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **values)

    def override(self, **changes):
        values = {name:getattr(self.policy,name) for name in POLICY_SETTINGS}
        values.update(license=self.loan.license, effective_from=self.today)
        values.update(changes)
        return create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **values)

    def test_retirement_inherits_workspace_and_its_later_amendments(self):
        override = self.override(valuation_basis='LATEST_APPRAISAL')
        retired = self.change(override, scope_action='RETIRE')
        self.assertEqual(self.resolved(license_id=self.loan.license_id).pk, self.policy.pk)
        current = self.change(valuation_basis='CALCULATED_METAL_VALUE')
        self.assertEqual(self.resolved(license_id=self.loan.license_id).pk, current.pk)
        self.assertEqual(m.LoanMonitoringPolicy.objects.get(pk=retired.pk).scope_action,'RETIRE')

    def test_cancel_first_future_override_returns_to_workspace_without_inventing_settings(self):
        future = self.override(effective_from=self.today+timedelta(days=5))
        values = cancellation_values(future)
        self.assertEqual(values['scope_action'],'RETIRE')
        values['amendment_reason']='Cancel the first planned override'
        create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **values)
        self.assertEqual(self.resolved(self.today+timedelta(days=10), self.loan.license_id).pk,self.policy.pk)

    def test_normal_workspace_retirement_backdating_and_unnecessary_replacement_are_rejected(self):
        for changes in ({'scope_action':'RETIRE'}, {'replaces_scheduled':True},
                        {'effective_from':self.today-timedelta(days=1)}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.change(**changes)
        values={name:getattr(self.policy,name) for name in POLICY_SETTINGS}
        values.update(supersedes=self.policy,effective_from=self.today,amendment_reason='No authority')
        with self.assertRaises(PermissionDenied):
            create_loan_monitoring_policy(workspace=self.tenant,actor=None,**values)

    def review_values(self, **changes):
        values={name:getattr(self.policy,name) for name in POLICY_SETTINGS}
        values.update(license=None,supersedes=self.policy,effective_from=self.today,
            amendment_reason='Reviewed scope and evidence impact',valuation_basis='CALCULATED_METAL_VALUE')
        values.update(changes)
        return values

    def test_impact_preview_is_read_only_and_confirmation_binds_source_and_acknowledgement(self):
        from apps.tenant_apps.loans.services.monitoring_policy_reviews import preview_monitoring_policy, confirm_monitoring_policy
        from apps.tenant_apps.rates.models import Rate
        before=list(m.LoanMonitoringPolicy.objects.values())
        financial=list(self.loan.loan_events.values_list('pk','payload_fingerprint'))
        values=self.review_values()
        review,token=preview_monitoring_policy(workspace=self.tenant,actor=self.actor,**values)
        self.assertEqual((review['total_active'],review['affected'],len(review['sample'])),(1,1,1))
        self.assertEqual(list(m.LoanMonitoringPolicy.objects.values()),before)
        with self.assertRaises(ValidationError):
            confirm_monitoring_policy(workspace=self.tenant,actor=self.actor,review_token=token,**values)
        Rate.objects.create(rate_source=self.source,buying_rate=3500,selling_rate=3600)
        with self.assertRaisesMessage(ValidationError,'source evidence changed'):
            confirm_monitoring_policy(workspace=self.tenant,actor=self.actor,review_token=token,
                acknowledged=True,**values)
        _,token=preview_monitoring_policy(workspace=self.tenant,actor=self.actor,**values)
        current=confirm_monitoring_policy(workspace=self.tenant,actor=self.actor,review_token=token,
            acknowledged=True,**values)
        self.assertEqual(current.supersedes_id,self.policy.pk)
        self.assertEqual(list(self.loan.loan_events.values_list('pk','payload_fingerprint')),financial)

    def test_workspace_impact_excludes_overrides_and_retirement_includes_fallback(self):
        from apps.tenant_apps.loans.services.monitoring_policy_reviews import preview_monitoring_policy
        override=self.override(valuation_basis='LATEST_APPRAISAL')
        review,_=preview_monitoring_policy(workspace=self.tenant,actor=self.actor,**self.review_values())
        self.assertEqual((review['total_active'],review['affected']),(1,0))
        values={name:getattr(override,name) for name in POLICY_SETTINGS}
        values.update(license=self.loan.license,supersedes=override,effective_from=self.today,
            amendment_reason='Return to Workspace monitoring',scope_action='RETIRE')
        review,_=preview_monitoring_policy(workspace=self.tenant,actor=self.actor,**values)
        self.assertEqual(review['affected'],1)
        self.assertFalse(review['fallback_unavailable'])

    def test_scheduled_intraday_evidence_expires_the_impact_review_without_another_save(self):
        from datetime import datetime, time
        from unittest.mock import patch
        from apps.tenant_apps.rates.models import Rate
        from apps.tenant_apps.loans.services.monitoring_policy_reviews import preview_monitoring_policy, confirm_monitoring_policy
        base=timezone.make_aware(datetime.combine(self.today,time(12)))
        future=base+timedelta(minutes=2)
        with patch('django.utils.timezone.now',return_value=base):
            Rate.objects.create(rate_source=self.source,buying_rate=3500,selling_rate=3600,effective_at=future)
            values=self.review_values()
            _,token=preview_monitoring_policy(workspace=self.tenant,actor=self.actor,**values)
        with patch('django.utils.timezone.now',return_value=future),self.assertRaisesMessage(ValidationError,'Scheduled evidence'):
            confirm_monitoring_policy(workspace=self.tenant,actor=self.actor,review_token=token,acknowledged=True,**values)

    def test_cancel_first_future_workspace_configuration_restores_unavailable_monitoring(self):
        from apps.orgs.models import Company,Membership,Role
        from apps.tenancy.context import without_workspace_context,workspace_context
        from apps.tenant_apps.loans.selectors.monitoring_policy import LoanRiskAssessmentError
        with without_workspace_context():
            workspace=Company.objects.create(name='Future-only scope',schema_name=uuid4().hex,
                owner=self.actor,creator=self.actor)
            Membership.objects.create(company=workspace,user=self.actor,role=Role.objects.get_or_create(name='Owner')[0])
            with workspace_context(workspace.pk):
                values={name:getattr(self.policy,name) for name in POLICY_SETTINGS}
                pending=create_loan_monitoring_policy(workspace=workspace,actor=self.actor,
                    effective_from=self.today+timedelta(days=7),**values)
                create_loan_monitoring_policy(workspace=workspace,actor=self.actor,
                    **dict(cancellation_values(pending),amendment_reason='Cancel the first future configuration'))
                for day in (self.today,self.today+timedelta(days=10)):
                    with self.assertRaises(LoanRiskAssessmentError):
                        resolve_monitoring_policy(workspace_id=workspace.pk,license_id=None,as_of_date=day)

    def test_change_after_preview_and_foreign_prepared_inputs_are_rejected(self):
        from dataclasses import replace
        from apps.tenant_apps.loans.services.monitoring_policy_reviews import preview_monitoring_policy, confirm_monitoring_policy
        from apps.tenant_apps.loans.selectors.monitoring_inputs import monitoring_inputs_for_policy
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_observation
        values=self.review_values()
        _,token=preview_monitoring_policy(workspace=self.tenant,actor=self.actor,**values)
        with self.assertRaises(ValidationError):
            confirm_monitoring_policy(workspace=self.tenant,actor=self.actor,review_token=token,
                acknowledged=True,**dict(values,ltv_warning_ratio=Decimal('.6')))
        inputs=monitoring_inputs_for_policy(self.loan,as_of_date=self.today,policy=self.policy)
        with self.assertRaises(ValueError):
            get_pawn_loan_collateral_observation(self.loan.pk,as_of_date=self.today,
                _inputs=replace(inputs,loan_id=self.loan.pk+1))

    def test_web_cancellation_requires_review_then_preserves_current_policy_settings(self):
        from django.urls import reverse
        from django.forms import BooleanField
        future=self.change(effective_from=self.today+timedelta(days=5),valuation_basis='LATEST_APPRAISAL')
        self.start_active_trial()
        client=self.make_workspace_client()
        client.force_login(self.actor)
        path=reverse('workspace_loans:pawn_economics_setup',args=[self.tenant.slug])
        page=client.get(path,{'cancel_monitoring':future.pk})
        self.assertEqual(page.status_code,200,page.headers)
        form=page.context['monitoring_form']
        data={'action':'monitoring'}
        for name,field in form.fields.items():
            value=form[name].value()
            if isinstance(field,BooleanField):
                if value:
                    data[form[name].html_name]='on'
            else:
                data[form[name].html_name]='' if value is None else str(value)
        data['monitoring-amendment_reason']='Cancel the pending schedule after reviewing impact'
        preview=client.post(path,data)
        self.assertContains(preview,'Review monitoring impact')
        self.assertEqual(m.LoanMonitoringPolicy.objects.count(),2)
        token=preview.context['monitoring_review_token']
        self.assertTrue(token,preview.context['monitoring_form'].errors)
        confirmed=client.post(path,dict(data,monitoring_confirm='1',monitoring_acknowledged='on',
            monitoring_review_token=token))
        self.assertEqual(confirmed.status_code,302)
        self.assertEqual(self.resolved().valuation_basis,self.policy.valuation_basis)

    def test_ordinary_browser_hidden_false_does_not_display_cancellation(self):
        from django.urls import reverse
        self.start_active_trial()
        client=self.make_workspace_client()
        client.force_login(self.actor)
        path=reverse('workspace_loans:pawn_economics_setup',args=[self.tenant.slug])
        page=client.get(path)
        form=page.context['monitoring_form']
        values={form[name].html_name:'' if form[name].value() is None else str(form[name].value())
            for name in form.fields if name!='replaces_scheduled'}
        values.update(action='monitoring')
        values['monitoring-cancel_scheduled']='False'
        values['monitoring-amendment_reason']='Review an ordinary amendment'
        preview=client.post(path,values)
        self.assertTrue(preview.context['monitoring_review_token'],preview.context['monitoring_form'].errors)
        self.assertFalse(preview.context['monitoring_cancelling'])
        self.assertNotContains(preview,'Cancel the scheduled changes and retain')

    def test_impact_compares_effective_policy_and_explains_preceding_schedule(self):
        from apps.tenant_apps.loans.services.monitoring_policy_reviews import preview_monitoring_policy
        scheduled=self.change(effective_from=self.today+timedelta(days=5),valuation_basis='LATEST_APPRAISAL')
        values=self.review_values(supersedes=scheduled,replaces_scheduled=True)
        review,_=preview_monitoring_policy(workspace=self.tenant,actor=self.actor,**values)
        method=next(row for row in review['changes'] if row['field']=='Valuation basis')
        self.assertEqual(method['before'],self.policy.get_valuation_basis_display())
        self.assertEqual([row['version'] for row in review['displaced']],[scheduled.version])
        later,_=preview_monitoring_policy(workspace=self.tenant,actor=self.actor,
            **self.review_values(supersedes=scheduled,effective_from=self.today+timedelta(days=10)))
        self.assertEqual([row['version'] for row in later['preceding']],[scheduled.version])

    def test_database_guard_enforces_immutable_lineage_under_restricted_role(self):
        scheduled = self.change(effective_from=self.today+timedelta(days=5))
        role=connection.ops.quote_name('monitor_lifecycle_'+uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {role}')
            cursor.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}')
            cursor.execute(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}')
            cursor.execute(f'SET LOCAL ROLE {role}')
        try:
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanMonitoringPolicy.objects.filter(pk=scheduled.pk).update(scope_action='RETIRE')
            values={name:getattr(scheduled,name) for name in POLICY_SETTINGS}
            raw=m.LoanMonitoringPolicy(workspace=self.tenant, supersedes=scheduled,
                version=scheduled.version+1, effective_from=self.today, created_by=self.actor,
                created_at=timezone.now(), amendment_reason='Invalid unreviewed earlier date',**values)
            with self.assertRaises(DatabaseError), transaction.atomic():
                raw.save_base(raw=True)
            raw.pk=None
            raw.replaces_scheduled=True
            with transaction.atomic():
                raw.save_base(raw=True)
            self.assertEqual(self.resolved().pk,raw.pk)
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SET LOCAL ROLE NONE')
                cursor.execute(f'DROP OWNED BY {role}')
                cursor.execute(f'DROP ROLE {role}')
