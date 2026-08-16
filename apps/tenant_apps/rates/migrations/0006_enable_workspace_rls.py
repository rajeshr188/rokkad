from django.db import migrations

from apps.tenancy.rls import EnableWorkspaceRLS


class Migration(migrations.Migration):
    dependencies = [
        ("rates", "0005_enforce_workspace_ownership"),
    ]

    operations = [
        EnableWorkspaceRLS("RateSource"),
        EnableWorkspaceRLS("Rate"),
    ]
