from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import historical_migration_database
from apps.tenant_apps.loans.models import LoanMonitoringPolicy


class MonitoringLifecycleMigrationTests(TransactionTestCase):
    def test_populated_policy_history_survives_upgrade_and_safe_reversal(self):
        actor=get_user_model().objects.create_user(username=uuid4().hex)
        workspace=Company.objects.create(name='Lifecycle upgrade',schema_name=uuid4().hex,owner=actor,creator=actor)
        membership=Membership.objects.create(user=actor,company=workspace,
            role=Role.objects.get_or_create(name='Owner')[0])
        with workspace_context(workspace.pk):
            first=LoanMonitoringPolicy.objects.create(workspace=workspace,version=1,effective_from=timezone.localdate(),
                compliance_profile='Retained explicit method',valuation_basis='LATEST_APPRAISAL',
                ltv_warning_ratio='.7',ltv_breach_ratio='.8',ltv_critical_ratio='.9',
                eligible_custody_states=['IN_VAULT'],severity_mapping={'strategy':'derived-v1'},created_by=actor)
        before=[('loans','0088_calculated_monitoring_default')]
        after=[('loans','0089_monitoring_policy_lifecycle')]
        with historical_migration_database(self,before,[membership,first]) as (target,old_apps):
            old=old_apps.get_model('loans','LoanMonitoringPolicy')
            original=list(old.objects.using(target.alias).values())
            executor=MigrationExecutor(target)
            executor.migrate(after)
            new=executor.loader.project_state(after).apps.get_model('loans','LoanMonitoringPolicy')
            upgraded=list(new.objects.using(target.alias).values())
            self.assertEqual([{k:v for k,v in row.items() if k not in {'scope_action','replaces_scheduled'}} for row in upgraded],original)
            self.assertEqual([(row['scope_action'],row['replaces_scheduled']) for row in upgraded],[('APPLY',False)])
            with target.cursor() as cursor:
                cursor.execute("SELECT pg_get_functiondef('loans_guard_monitoring_policy()'::regprocedure)")
                self.assertIn('FOR NO KEY UPDATE;',cursor.fetchone()[0])
            executor.migrate(before)
            self.assertEqual(list(old.objects.using(target.alias).values()),original)
