import django.db.models.deletion
from importlib import import_module
from django.db import migrations, models

LOAN_MODELS = import_module(
    "apps.tenant_apps.loans.migrations.0065_backfill_workspace"
).LOAN_MODELS


def workspace_field():
    return models.ForeignKey(
        editable=False,
        on_delete=django.db.models.deletion.PROTECT,
        related_name="+",
        to="orgs.company",
    )


class Migration(migrations.Migration):
    dependencies = [("loans", "0065_backfill_workspace")]

    operations = [
        migrations.AlterField(
            model_name=model_name.lower(),
            name="workspace",
            field=workspace_field(),
        )
        for model_name in LOAN_MODELS
    ]
