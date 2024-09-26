# Generated by Django 5.0.8 on 2024-09-21 05:22

import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("girvi", "0019_loanitemstoragebox"),
    ]

    operations = [
        migrations.AlterField(
            model_name="loanitemstoragebox",
            name="item_type",
            field=models.CharField(
                choices=[("gold", "Gold"), ("silver", "Silver"), ("bronze", "Bronze")],
                default="gold",
                max_length=6,
            ),
        ),
    ]
