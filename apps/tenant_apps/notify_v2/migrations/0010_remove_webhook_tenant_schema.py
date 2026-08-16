from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("notify_v2", "0009_enforce_workspace_ownership")]

    operations = [
        migrations.RemoveField(
            model_name="whatsappcloudwebhookreceipt",
            name="tenant_schema",
        ),
    ]
