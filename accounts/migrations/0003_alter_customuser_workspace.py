# Generated by Django 5.0.1 on 2024-02-24 17:18

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_customuser_workspace"),
        ("orgs", "0009_alter_company_options_alter_role_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="workspace",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="orgs.company",
            ),
        ),
    ]