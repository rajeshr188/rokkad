from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("notify_v2", "0001_initial"),
    ]

    # Retained as a graph node for downstream migration compatibility. The
    # clean development baseline creates the Party field in 0001 directly.
    operations = []
