"""Version 8 identifies retained aggregate opening correction semantics."""

from importlib import import_module

from django.db import migrations


OLD = import_module(
    "apps.tenant_apps.data_portability.migrations.0029_agreement_correction_profile"
).UPDATED
NEW = OLD.replace("'loan-servicing-bundle/7',", "'loan-servicing-bundle/7','loan-servicing-bundle/8',")
assert NEW != OLD


class Migration(migrations.Migration):
    dependencies = [
        ("data_portability", "0030_monitoring_lifecycle_profile"),
        ("loans", "0092_aggregate_checkpoint_corrections"),
    ]
    operations = [
        migrations.RunSQL(
            NEW,
            """
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM data_portability_loanrestorebatch
                WHERE profile='loan-servicing-bundle/8')
              THEN RAISE EXCEPTION 'Retained version-8 restores require compatible readers'; END IF;
            END; $$;
            """ + OLD,
        )
    ]
