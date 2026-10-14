"""Keep original package meaning; accept the explicit wider graph package."""
from importlib import import_module
from django.db import migrations

OLD = import_module('apps.tenant_apps.data_portability.migrations.0023_business_package_receipt').GUARD.split('CREATE TRIGGER')[0]
OLD = OLD.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)
NEW = OLD.replace("NEW.summary->>'profile' IS DISTINCT FROM 'rokkad-business-package/1'",
    "COALESCE(NEW.summary->>'profile','') NOT IN ('rokkad-business-package/1','rokkad-business-package/2')")


class Migration(migrations.Migration):
    dependencies = [('data_portability','0024_servicing_correction_profile'),('loans','0071_funding_return_reversal_projection'),('rates','0005_portable_quote_source')]
    operations = [migrations.RunSQL(NEW, """
        DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM data_portability_businesspackagereceipt WHERE summary->>'profile'='rokkad-business-package/2')
        THEN RAISE EXCEPTION 'Retained wider graph packages must remain supported'; END IF;
        END; $$;
        """+OLD)]
