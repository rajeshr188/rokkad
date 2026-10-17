"""Retain independent entry defaults in a new setup/package contract."""

from importlib import import_module
from django.db import migrations

OLD = import_module(
    "apps.tenant_apps.data_portability.migrations.0030_monitoring_lifecycle_profile"
).NEW
NEW = OLD.replace(
    "'rokkad-business-package/4')",
    "'rokkad-business-package/4','rokkad-business-package/5')",
)
assert NEW != OLD


class Migration(migrations.Migration):
    dependencies = [
        ("data_portability", "0031_aggregate_correction_profile"),
        ("loans", "0093_loan_entry_preference"),
    ]
    operations = [
        migrations.RunSQL(
            NEW,
            """
        DO $$ BEGIN
          IF EXISTS (SELECT 1 FROM data_portability_businesspackagereceipt WHERE summary->>'profile'='rokkad-business-package/5')
          THEN RAISE EXCEPTION 'Retained entry-preference packages must remain supported'; END IF;
        END; $$;
    """ + OLD,
        )
    ]
