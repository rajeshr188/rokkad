from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("product", "0014_pricing_constraints_and_resolver_hardening"),
    ]

    # Retained as a graph node for downstream migration compatibility. The
    # clean development baseline creates Party-owned prices from 0002 onward.
    operations = []
