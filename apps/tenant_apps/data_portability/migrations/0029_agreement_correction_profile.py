"""Version 7 retains revised direct agreement and monthly recognition identity."""
from importlib import import_module
from django.db import migrations

PREVIOUS = import_module("apps.tenant_apps.data_portability.migrations.0028_collateral_correction_profile").UPDATED
UPDATED = PREVIOUS.replace("'loan-servicing-bundle/6',", "'loan-servicing-bundle/6','loan-servicing-bundle/7',")


class Migration(migrations.Migration):
    dependencies = [("data_portability", "0028_collateral_correction_profile"), ("loans", "0079_agreement_financial_corrections")]
    operations = [migrations.RunSQL(UPDATED, """
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM data_portability_loanrestorebatch WHERE profile='loan-servicing-bundle/7')
 THEN RAISE EXCEPTION 'Version-7 restore evidence prevents downgrade'; END IF;
END; $$;
""" + PREVIOUS)]
