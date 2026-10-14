"""Retain explicit monitoring choices in a separately versioned package."""
from importlib import import_module
from django.db import migrations

OLD = import_module('apps.tenant_apps.data_portability.migrations.0025_business_graph_profile').NEW
NEW = OLD.replace("('rokkad-business-package/1','rokkad-business-package/2')",
    "('rokkad-business-package/1','rokkad-business-package/2','rokkad-business-package/3')")


class Migration(migrations.Migration):
    dependencies = [('data_portability','0025_business_graph_profile'),
                    ('loans','0074_merge_monitoring_portability')]
    operations = [migrations.RunSQL(NEW, """
        DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM data_portability_businesspackagereceipt WHERE summary->>'profile'='rokkad-business-package/3')
        THEN RAISE EXCEPTION 'Retained monitoring-choice packages must remain supported'; END IF;
        END; $$;
        """+OLD)]
