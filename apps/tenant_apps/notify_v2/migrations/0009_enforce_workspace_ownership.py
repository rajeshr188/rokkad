import django.db.models.deletion
from django.db import migrations, models


OWNED_MODELS = (
    "notificationartifact",
    "notificationattemptlog",
    "notificationbatch",
    "notificationevent",
    "notificationeventtype",
    "notificationjob",
    "notificationpolicy",
    "notificationrecipient",
    "notificationtemplate",
    "whatsappcloudwebhookreceipt",
)


def workspace_field():
    return models.ForeignKey(
        editable=False,
        on_delete=django.db.models.deletion.PROTECT,
        related_name="+",
        to="orgs.company",
    )


class Migration(migrations.Migration):
    dependencies = [("notify_v2", "0008_backfill_workspace")]

    operations = [
        migrations.AlterField(
            model_name=model_name,
            name="workspace",
            field=workspace_field(),
        )
        for model_name in OWNED_MODELS
    ]
