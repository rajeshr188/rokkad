"""Accept the versioned retained-origination-correction bundle without relaxing review."""
from importlib import import_module
from django.db import migrations

OLD = import_module('apps.tenant_apps.data_portability.migrations.0020_loan_restore_batch').GUARD
FUNCTION = OLD.split('CREATE TRIGGER')[0]
UPDATED = FUNCTION.replace('CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION', 1).replace(
    "'loan-servicing-bundle/1',", "'loan-servicing-bundle/1','loan-servicing-bundle/2','loan-servicing-bundle/3','loan-servicing-bundle/4',")


class Migration(migrations.Migration):
    dependencies = [('data_portability', '0023_business_package_receipt')]
    operations = [migrations.RunSQL(UPDATED, """
        DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM data_portability_loanrestorebatch WHERE profile IN ('loan-servicing-bundle/2','loan-servicing-bundle/3','loan-servicing-bundle/4'))
        THEN RAISE EXCEPTION 'Version-2 restore evidence must remain supported'; END IF;
        END; $$;
        """ + FUNCTION.replace('CREATE FUNCTION', 'CREATE OR REPLACE FUNCTION', 1))]
