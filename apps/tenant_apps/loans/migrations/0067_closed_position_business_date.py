"""Compare accepted positions with India's business date, not UTC session date."""
from importlib import import_module
from django.db import migrations


original = import_module("apps.tenant_apps.loans.migrations.0065_closed_position_admission").GUARD
start = original.index("CREATE FUNCTION loans_closed_position_complete()")
end = original.index("CREATE CONSTRAINT TRIGGER loans_closed_position_complete", start)
reverse = original[start:end].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
forward = reverse.replace("e.effective_date>CURRENT_DATE",
    "e.effective_date>(statement_timestamp() AT TIME ZONE 'Asia/Kolkata')::date")
assert forward != reverse


class Migration(migrations.Migration):
    dependencies = [("loans", "0066_retained_source_search_fields")]
    operations = [migrations.RunSQL(forward, reverse)]
