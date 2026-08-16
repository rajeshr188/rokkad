from django.db import migrations

from apps.tenancy.rls import EnableWorkspaceRLSForApp


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0066_enforce_workspace_ownership"),
    ]

    operations = [
        EnableWorkspaceRLSForApp(),
    ]
