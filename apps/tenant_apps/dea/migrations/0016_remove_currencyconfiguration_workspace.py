from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("dea", "0015_add_current_asset_liability_flags"),
        ("orgs", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="currencyconfiguration",
            name="workspace",
        ),
    ]
