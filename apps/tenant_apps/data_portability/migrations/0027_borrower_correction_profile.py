"""Version 5 adds exact former/current Party mapping to supported financial graphs."""
from importlib import import_module
from django.db import migrations

PREVIOUS = import_module("apps.tenant_apps.data_portability.migrations.0024_servicing_correction_profile").UPDATED
UPDATED = PREVIOUS.replace("'loan-servicing-bundle/4',", "'loan-servicing-bundle/4','loan-servicing-bundle/5',")


class Migration(migrations.Migration):
    dependencies = [("data_portability", "0026_monitoring_setup_profile"), ("loans", "0076_merge_borrower_correction")]
    operations = [migrations.RunSQL(UPDATED, """
DO $$ BEGIN
 IF EXISTS (SELECT 1 FROM data_portability_loanrestorebatch WHERE profile='loan-servicing-bundle/5')
 THEN RAISE EXCEPTION 'Version-5 restore evidence prevents downgrade'; END IF;
END; $$;
""" + PREVIOUS)]
