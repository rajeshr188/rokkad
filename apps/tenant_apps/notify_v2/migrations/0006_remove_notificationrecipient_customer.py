from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("notify_v2", "0005_whatsappcloudintegration"),
    ]

    # Retained as a graph node for downstream migration compatibility. The
    # clean development baseline never creates the retired Customer field.
    operations = []
