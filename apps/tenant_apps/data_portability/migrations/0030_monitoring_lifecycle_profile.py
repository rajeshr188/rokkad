"""Preserve lifecycle actions in a new business package contract."""
from importlib import import_module
from django.db import migrations

OLD = import_module('apps.tenant_apps.data_portability.migrations.0026_monitoring_setup_profile').NEW
NEW = OLD.replace("'rokkad-business-package/3')", "'rokkad-business-package/3','rokkad-business-package/4')")
assert NEW != OLD


class Migration(migrations.Migration):
    dependencies = [('data_portability', '0029_agreement_correction_profile'),
                    ('loans', '0089_monitoring_policy_lifecycle')]
    operations = [migrations.RunSQL(NEW, """
        DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM data_portability_businesspackagereceipt WHERE summary->>'profile'='rokkad-business-package/4')
        THEN RAISE EXCEPTION 'Retained monitoring lifecycle packages must remain supported'; END IF;
        END; $$;
        """ + OLD)]
