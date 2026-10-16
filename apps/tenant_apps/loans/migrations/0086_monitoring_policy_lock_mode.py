"""Keep policy serialization compatible with monitoring evidence foreign keys."""
from importlib import import_module

from django.db import migrations


# Preserve every historical evidence/scope/overlap check. Replace only the
# parent-row lock mode, retaining the installed trigger and function identity.
PREVIOUS = import_module(
    "apps.tenant_apps.loans.migrations.0007_monitoring_policy_amendments"
).GUARD.split("CREATE TRIGGER", 1)[0].replace(
    "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
assert PREVIOUS.count("FOR UPDATE;") == 1
CURRENT = PREVIOUS.replace("FOR UPDATE;", "FOR NO KEY UPDATE;", 1)


class Migration(migrations.Migration):
    # Independent of undeployed financial-correction migrations, like Party's
    # deployed branch. The joining migration is a no-op for the complete checkout.
    dependencies = [("loans", "0084_merged_borrower_guard")]
    operations = [migrations.RunSQL(CURRENT, reverse_sql=PREVIOUS)]
