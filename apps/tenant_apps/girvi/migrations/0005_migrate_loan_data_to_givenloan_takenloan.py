"""Retained migration node after removal of obsolete legacy-loan copying."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("girvi", "0004_create_givenloan_takenloan_standalone"),
    ]

    operations = []
