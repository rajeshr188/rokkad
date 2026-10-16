"""Append explicit schedule replacement and scope retirement evidence."""
from importlib import import_module
from django.db import migrations, models

PREVIOUS = import_module('apps.tenant_apps.loans.migrations.0086_monitoring_policy_lock_mode').CURRENT
CURRENT = PREVIOUS.replace(
    'OR NEW.effective_from < prior.effective_from OR NEW.version <= prior.version',
    'OR (NEW.effective_from < prior.effective_from AND NOT NEW.replaces_scheduled) OR NEW.version <= prior.version')
assert CURRENT != PREVIOUS
CURRENT = CURRENT.replace('  IF NEW.supersedes_id IS NOT NULL THEN', """
  IF (NEW.scope_action = 'RETIRE' OR NEW.replaces_scheduled) AND NEW.supersedes_id IS NULL THEN
    RAISE EXCEPTION 'Monitoring lifecycle evidence requires its predecessor';
  END IF;
  IF NEW.supersedes_id IS NOT NULL THEN""")
REVERSE = """
DO $$ BEGIN
IF EXISTS (SELECT 1 FROM loans_loanmonitoringpolicy WHERE scope_action <> 'APPLY' OR replaces_scheduled)
THEN RAISE EXCEPTION 'Retained monitoring lifecycle evidence requires compatible readers'; END IF;
END; $$;
""" + PREVIOUS


class Migration(migrations.Migration):
    dependencies = [('loans', '0088_calculated_monitoring_default')]
    operations = [
        migrations.AddField(model_name='loanmonitoringpolicy', name='scope_action',
            field=models.CharField(max_length=8, choices=[('APPLY', 'Use these monitoring settings'),
                ('RETIRE', 'Return this scope to its default')], default='APPLY', db_default='APPLY')),
        migrations.AddField(model_name='loanmonitoringpolicy', name='replaces_scheduled',
            field=models.BooleanField(default=False, db_default=False)),
        migrations.AddConstraint(model_name='loanmonitoringpolicy', constraint=models.CheckConstraint(
            condition=models.Q(scope_action__in=('APPLY', 'RETIRE')), name='loans_monitor_scope_action_valid')),
        migrations.AddConstraint(model_name='loanmonitoringpolicy', constraint=models.CheckConstraint(
            condition=models.Q(scope_action='APPLY', replaces_scheduled=False) | models.Q(supersedes__isnull=False),
            name='loans_monitor_lifecycle_has_prior')),
        migrations.RunSQL(CURRENT, reverse_sql=REVERSE),
    ]
