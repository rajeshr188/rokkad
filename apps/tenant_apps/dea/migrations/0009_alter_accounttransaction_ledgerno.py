# Generated by Django 5.0.1 on 2024-04-14 18:06

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dea", "0008_alter_ledgerbalance_options_alter_ledger_accounttype"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accounttransaction",
            name="ledgerno",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="aleg",
                to="dea.ledger",
            ),
        ),
    ]
