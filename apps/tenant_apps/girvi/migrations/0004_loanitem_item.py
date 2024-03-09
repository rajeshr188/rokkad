# Generated by Django 5.0.1 on 2024-02-27 06:07

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("girvi", "0003_alter_loan_pic"),
        ("product", "0004_alter_product_attributes"),
    ]

    operations = [
        migrations.AddField(
            model_name="loanitem",
            name="item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="product.productvariant",
            ),
        ),
    ]