"""Normal observations still freeze the current source; imported observations retain theirs."""
from importlib import import_module
from django.db import migrations, models

OLD = import_module('apps.tenant_apps.rates.migrations.0004_rate_daily_confirmation').UPDATED
START = "    NEW.source_snapshot = jsonb_build_object('name', source.name, 'location', source.location,\n                                            'tax_included', source.tax_included);"
REPLACEMENT = """
    IF NEW.portable_source <> '{}'::jsonb THEN
        IF NEW.recorded_by_id IS NULL
           OR NEW.portable_source->>'profile' IS DISTINCT FROM 'rate-source-transfer/1'
           OR jsonb_typeof(NEW.portable_source) IS DISTINCT FROM 'object'
           OR (SELECT count(*) FROM jsonb_object_keys(NEW.portable_source))<>5
           OR COALESCE(NEW.portable_source->>'namespace','') !~ '^[0-9a-f-]{36}$'
           OR COALESCE(NEW.portable_source->>'source_id','') !~ '^[1-9][0-9]*$'
           OR COALESCE(NEW.portable_source->>'sha256','') !~ '^[0-9a-f]{64}$'
           OR octet_length(NEW.portable_source::text)>65536
           OR NEW.portable_source->'snapshot' IS DISTINCT FROM NEW.source_snapshot
           OR jsonb_typeof(NEW.source_snapshot) IS DISTINCT FROM 'object'
           OR jsonb_typeof(NEW.source_snapshot->'name') IS DISTINCT FROM 'string'
           OR jsonb_typeof(NEW.source_snapshot->'location') IS DISTINCT FROM 'string'
           OR jsonb_typeof(NEW.source_snapshot->'tax_included') IS DISTINCT FROM 'boolean'
        THEN RAISE EXCEPTION 'Imported quote requires explicit frozen source evidence'; END IF;
    ELSE
        NEW.source_snapshot = jsonb_build_object('name', source.name, 'location', source.location,
                                            'tax_included', source.tax_included);
    END IF;
"""
assert START in OLD
NEW = OLD.replace(START,REPLACEMENT)
REVERSE = """DO $$ BEGIN
IF EXISTS (SELECT 1 FROM rates_rate WHERE portable_source<>'{}'::jsonb)
THEN RAISE EXCEPTION 'Imported quote evidence must remain supported'; END IF;
END; $$;"""+OLD


class Migration(migrations.Migration):
    dependencies=[('rates','0004_rate_daily_confirmation')]
    operations=[migrations.AddField(model_name='rate',name='portable_source',
        field=models.JSONField(default=dict,blank=True,editable=False)),migrations.RunSQL(NEW,REVERSE)]
