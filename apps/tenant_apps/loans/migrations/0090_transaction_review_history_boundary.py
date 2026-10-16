"""Bind book reviews to accepted checkpoints, including unknown original dates."""
from importlib import import_module
from django.db import migrations

PREVIOUS = import_module('apps.tenant_apps.loans.migrations.0060_review_future_capture').FORWARD.split(
    'CREATE OR REPLACE FUNCTION loans_notice_review_guard()',1)[0]
CURRENT = PREVIOUS.replace('NEW.through_date >= l.loan_date', '''NEW.through_date >= COALESCE(
     (SELECT e.effective_date FROM loans_pawnloanevent e
       WHERE e.loan_id=l.id AND e.workspace_id=l.workspace_id AND e.event_kind='MIGRATION_OPENING'),
     l.loan_date)''')
assert CURRENT != PREVIOUS


class Migration(migrations.Migration):
    dependencies = [('loans','0089_monitoring_policy_lifecycle')]
    operations = [migrations.RunSQL(CURRENT,reverse_sql=PREVIOUS)]
