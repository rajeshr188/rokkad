# Generated by Django 5.0.1 on 2024-02-17 04:24

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orgs", "0002_companyinvitation"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CompanyInvitation",
        ),
    ]
