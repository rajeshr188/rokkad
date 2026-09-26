from importlib import import_module

from django.db import migrations, models
import django.db.models.deletion


ORIGINAL = import_module("apps.tenant_apps.rates.migrations.0003_rate_effective_at_rate_is_withdrawal_rate_reason_and_more").GUARD
ORIGINAL = ORIGINAL.split("CREATE TRIGGER")[0].replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
CONFIRMATION = """
    IF NEW.confirmed_from_id IS NOT NULL THEN
        IF NEW.supersedes_id IS NOT NULL OR NEW.is_withdrawal OR NEW.recorded_by_id IS NULL THEN
            RAISE EXCEPTION 'Daily confirmation requires actor and cannot be a correction or withdrawal';
        END IF;
        SELECT * INTO previous FROM rates_rate WHERE id = NEW.confirmed_from_id FOR UPDATE;
        IF NOT FOUND OR previous.workspace_id <> NEW.workspace_id OR previous.is_withdrawal
           OR EXISTS (SELECT 1 FROM rates_rate WHERE supersedes_id = previous.id) THEN
            RAISE EXCEPTION 'Confirmation source must be an available quote in the same Workspace';
        END IF;
        IF ROW(NEW.metal, NEW.currency, NEW.purity, NEW.rate_source_id, NEW.buying_rate, NEW.selling_rate)
           IS DISTINCT FROM ROW(previous.metal, previous.currency, previous.purity,
               previous.rate_source_id, previous.buying_rate, previous.selling_rate)
           OR NEW.effective_at <= previous.effective_at THEN
            RAISE EXCEPTION 'Daily confirmation must preserve prices and advance the effective time';
        END IF;
    END IF;
"""
UPDATED = ORIGINAL.replace("    NEW.source_snapshot =", CONFIRMATION + "    NEW.source_snapshot =")


class Migration(migrations.Migration):
    dependencies = [("rates", "0003_rate_effective_at_rate_is_withdrawal_rate_reason_and_more")]
    operations = [
        migrations.AddField(model_name="rate", name="confirmed_from",
            field=models.ForeignKey(blank=True, editable=False, null=True,
                on_delete=django.db.models.deletion.PROTECT, related_name="daily_confirmations", to="rates.rate")),
        migrations.RunSQL(UPDATED, ORIGINAL),
    ]
