# Generated by Django 5.0.1 on 2024-02-27 06:07

import django.contrib.postgres.fields.hstore
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("product", "0003_auto_20230723_1647"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="attributes",
            field=django.contrib.postgres.fields.hstore.HStoreField(
                blank=True, default=dict, null=True
            ),
        ),
    ]
