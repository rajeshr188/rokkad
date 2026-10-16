"""Version 6 retains immutable collateral transcription corrections."""
from importlib import import_module
from django.db import migrations

PREVIOUS = import_module("apps.tenant_apps.data_portability.migrations.0027_borrower_correction_profile").UPDATED
UPDATED = PREVIOUS.replace("'loan-servicing-bundle/5',", "'loan-servicing-bundle/5','loan-servicing-bundle/6',")


class Migration(migrations.Migration):
    dependencies = [("data_portability", "0027_borrower_correction_profile"), ("loans", "0078_collateral_fact_corrections")]
    operations = [migrations.RunSQL(UPDATED, """
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM data_portability_loanrestorebatch WHERE profile='loan-servicing-bundle/6')
 THEN RAISE EXCEPTION 'Version-6 restore evidence prevents downgrade'; END IF;
END; $$;
""" + PREVIOUS)]
