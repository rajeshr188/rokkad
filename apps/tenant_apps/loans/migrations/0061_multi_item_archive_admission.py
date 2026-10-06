"""Permit explicitly reconciled itemized archive evidence; keep all bindings."""
from importlib import import_module
from django.db import migrations

OLD = import_module("apps.tenant_apps.loans.migrations.0042_archive_admission_link").Migration.operations[1].sql.split("CREATE TRIGGER", 1)[0]
NEW = OLD.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1).replace(
    "NEW.document->>'profile' IS DISTINCT FROM 'archive-admission/1'",
    "COALESCE(NEW.document->>'profile', '') NOT IN ('archive-admission/1','archive-admission/2')")


class Migration(migrations.Migration):
    dependencies = [("loans", "0060_review_future_capture")]
    operations = [migrations.RunSQL(NEW, OLD.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1))]
