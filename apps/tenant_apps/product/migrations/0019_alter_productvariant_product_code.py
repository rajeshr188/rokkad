# Generated by Django 5.0.8 on 2024-09-18 10:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("product", "0018_alter_productvariant_product_code_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productvariant",
            name="product_code",
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
