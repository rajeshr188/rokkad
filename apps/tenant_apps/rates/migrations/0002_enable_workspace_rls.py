from django.db import migrations

from apps.tenancy.rls import EnableWorkspaceRLSForApp


class Migration(migrations.Migration):
    dependencies = [("rates", "0001_initial")]
    operations = [EnableWorkspaceRLSForApp()]
