# Generated by Django 5.0.8 on 2024-10-07 06:18

import colorfield.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orgs", "0013_alter_companyinvitation_email_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="theme",
            field=colorfield.fields.ColorField(
                default="#FF0000", image_field=None, max_length=25, samples=None
            ),
        ),
    ]
