# Generated by Django 5.0.1 on 2024-06-13 06:22

import djmoney.models.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("dea", "0011_alter_accounttransaction_amount_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ledgertransaction",
            name="amount",
            field=djmoney.models.fields.MoneyField(decimal_places=3, max_digits=13),
        ),
    ]
