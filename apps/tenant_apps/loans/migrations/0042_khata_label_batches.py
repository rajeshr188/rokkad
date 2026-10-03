"""Extend the held-item guard; retain exact old payload and renderer contracts."""
from importlib import import_module

from django.db import migrations


OLD_GUARD = import_module("apps.tenant_apps.loans.migrations.0040_khata_labels").LABEL_GUARD.split("DROP TRIGGER", 1)[0]
NEW_GUARD = OLD_GUARD.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1).replace(
    "('ONE','ALL','EACH')", "('ONE','ALL','EACH','SELECTED')"
).replace(
    "array_agg((e->>'id')::bigint ORDER BY (e->>'id')::bigint)",
    "array_agg((e->>'id')::bigint ORDER BY ordinal)"
).replace(
    "jsonb_array_elements(NEW.payload->'items') e;",
    "jsonb_array_elements(NEW.payload->'items') WITH ORDINALITY AS labels(e, ordinal);"
).replace(
    "OR (label_mode='ONE' AND cardinality(ids)<>1)",
    "OR ids IS DISTINCT FROM (SELECT array_agg(v ORDER BY v) FROM unnest(ids) v)\n    OR (label_mode='ONE' AND cardinality(ids)<>1)"
)


class Migration(migrations.Migration):
    dependencies = [("loans", "0041_khata_series_status")]
    operations = [migrations.RunSQL(NEW_GUARD, OLD_GUARD.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))]
