"""Match the existing India business date at the database evidence boundary."""
from importlib import import_module
from django.db import migrations

previous = import_module("apps.tenant_apps.loans.migrations.0053_dated_custody_restatements").restatement_guard
corrected = previous.replace("NEW.effective_date>CURRENT_DATE",
    "NEW.effective_date>(CURRENT_TIMESTAMP AT TIME ZONE 'Asia/Kolkata')::date")


class Migration(migrations.Migration):
    dependencies = [("loans", "0054_active_opening_line_guard")]
    operations = [migrations.RunSQL(corrected, previous)]
