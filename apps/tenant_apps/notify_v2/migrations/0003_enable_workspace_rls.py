from django.db import migrations

from apps.tenancy.rls import EnableWorkspaceRLSForApp


class Migration(migrations.Migration):
    dependencies = [("notify_v2", "0002_initial")]
    operations = [EnableWorkspaceRLSForApp()]
