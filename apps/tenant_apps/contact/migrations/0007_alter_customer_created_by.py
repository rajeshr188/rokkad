# Generated by Django 5.0.1 on 2024-03-15 11:03

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contact", "0006_alter_customer_created_by"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="customer",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="customers_created",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Created By",
            ),
        ),
    ]
