"""New monitoring defaults must not rewrite existing or portable policy choices."""
from django.forms.models import model_to_dict
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory, TransactionTestCase
from django.utils import timezone
from uuid import uuid4

from apps.tenancy.testing import WorkspaceTestCase, historical_migration_database
from apps.tenancy.context import workspace_context
from apps.orgs.models import Company, Membership, Role
from apps.tenant_apps.loans.models import LoanMonitoringPolicy
from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
from apps.tenant_apps.loans.tests.test_monitoring_valuation_basis import MonitoringValuationTests as _Fixtures
from apps.tenant_apps.loans.tests.test_collateral_reappraisal import CollateralReappraisalTests as _Collateral
from apps.tenant_apps.loans.web.economic_forms import LoanMonitoringPolicyForm
from apps.tenant_apps.loans.web.economic_setup import pawn_economics_setup


class MonitoringDefaultTests(WorkspaceTestCase):
    setup_tenant = classmethod(_Fixtures.setup_tenant.__func__)

    @classmethod
    def get_test_schema_name(cls):
        return "calculated-monitoring-default"

    def setUp(self):
        super().setUp()
        _Collateral.make_loan(self)

    def data(self, **changes):
        data = model_to_dict(self.policy, fields=LoanMonitoringPolicyForm.Meta.fields)
        data.update(license="", supersedes=self.policy.pk, effective_from=timezone.localdate(),
            amendment_reason="Reviewed current metal monitoring", valuation_basis="CALCULATED_METAL_VALUE")
        data.update(changes)
        return data

    def page(self, query=None):
        request = RequestFactory().get("/", query or {})
        request.user, request.workspace = self.actor, self.tenant
        return pawn_economics_setup(request)

    def test_new_scope_uses_calculated_default_in_model_form_and_service(self):
        self.assertEqual(LoanMonitoringPolicy().valuation_basis, "CALCULATED_METAL_VALUE")
        values = self.data(supersedes="", license=self.loan.license.pk)
        values.pop("valuation_basis")
        form = LoanMonitoringPolicyForm(values, workspace=self.tenant, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        policy = create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **form.cleaned_data)
        self.assertEqual(policy.valuation_basis, "CALCULATED_METAL_VALUE")
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.valuation_basis, "ORIGINAL_AGREEMENT")

    def test_ordinary_setup_opens_latest_workspace_amendment_and_renders_predecessor(self):
        response = self.page()
        self.assertContains(response, "Amend monitoring policy")
        self.assertContains(response, f'name="monitoring-supersedes" value="{self.policy.pk}"')
        self.assertContains(response, "You are amending the latest policy for")
        self.assertContains(response, 'new_monitoring=1#monitoring-policy')

    def test_new_scope_route_stays_separate_and_warns_against_an_unlinked_overlap(self):
        self.assertContains(self.page({"new_monitoring": "1"}), "Monitoring policies are already saved")
        form = LoanMonitoringPolicyForm(self.data(supersedes=""), workspace=self.tenant, actor=self.actor)
        self.assertFalse(form.is_valid())
        self.assertIn("choose Amend", str(form.errors))
        self.assertEqual(LoanMonitoringPolicy.objects.count(), 1)

    def test_amendment_from_rendered_values_creates_linked_version_with_old_facts_intact(self):
        original = model_to_dict(self.policy)
        form = LoanMonitoringPolicyForm(self.data(), workspace=self.tenant, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        policy = create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **form.cleaned_data)
        self.assertEqual(policy.supersedes_id, self.policy.pk)
        self.assertEqual(policy.valuation_basis, "CALCULATED_METAL_VALUE")
        self.policy.refresh_from_db()
        self.assertEqual(model_to_dict(self.policy), original)
        self.assertContains(self.page(), f'name="monitoring-supersedes" value="{policy.pk}"')

    def test_omitted_amendment_method_preserves_explicit_lower_of(self):
        data = self.data(valuation_basis="LOWER_OF_CALCULATED_AND_APPRAISAL")
        form = LoanMonitoringPolicyForm(data, workspace=self.tenant, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        self.policy = create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **form.cleaned_data)
        data = self.data()
        data.pop("valuation_basis")
        form = LoanMonitoringPolicyForm(data, workspace=self.tenant, actor=self.actor)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['valuation_basis'], "LOWER_OF_CALCULATED_AND_APPRAISAL")

    def test_new_scope_link_preserves_setup_navigation(self):
        response = self.page({"setup_step": "terms", "setup_path": "paper"})
        self.assertContains(response, "new_monitoring=1")
        self.assertContains(response, "setup_path=paper")


class MonitoringDefaultMigrationTests(TransactionTestCase):
    def test_new_default_preserves_populated_policy_history(self):
        actor = get_user_model().objects.create_user(username=uuid4().hex)
        workspace = Company.objects.create(name="Monitoring default upgrade", schema_name=uuid4().hex,
            owner=actor, creator=actor)
        membership = Membership.objects.create(user=actor, company=workspace,
            role=Role.objects.get_or_create(name="Owner")[0])
        policies = []
        with workspace_context(workspace.pk):
            for basis in ("ORIGINAL_AGREEMENT", "LOWER_OF_CALCULATED_AND_APPRAISAL"):
                policies.append(LoanMonitoringPolicy.objects.create(workspace=workspace, version=len(policies)+1,
                    effective_from=timezone.localdate(), supersedes=policies[-1] if policies else None,
                    amendment_reason="Retained choice", compliance_profile="Explicit retained policy", valuation_basis=basis,
                    ltv_warning_ratio=".7", ltv_breach_ratio=".8", ltv_critical_ratio=".9",
                    eligible_custody_states=["IN_VAULT"], severity_mapping={"strategy":"derived-v1"}, created_by=actor))
        before = [("loans", "0087_merge_monitoring_policy_lock")]
        after = [("loans", "0088_calculated_monitoring_default")]
        with historical_migration_database(self, before, [membership, *policies]) as (target, old_apps):
            old = old_apps.get_model("loans", "LoanMonitoringPolicy")
            retained = list(old.objects.using(target.alias).order_by('pk').values())
            executor = MigrationExecutor(target)
            executor.migrate(after)
            new = executor.loader.project_state(after).apps.get_model("loans", "LoanMonitoringPolicy")
            self.assertEqual(list(new.objects.using(target.alias).order_by('pk').values()), retained)
            with target.cursor() as cursor:
                cursor.execute("SELECT column_default FROM information_schema.columns WHERE table_name='loans_loanmonitoringpolicy' AND column_name='valuation_basis'")
                self.assertIn("CALCULATED_METAL_VALUE", cursor.fetchone()[0])
