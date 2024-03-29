# Generated by Django 5.0.1 on 2024-02-16 18:11

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invitations", "0004_auto_20230328_1430"),
        ("orgs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyInvitation",
            fields=[
                (
                    "invitation_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="invitations.invitation",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="orgs.company"
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
            bases=("invitations.invitation",),
        ),
    ]
