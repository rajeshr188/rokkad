# Generated by Django 5.0.1 on 2024-02-17 04:25

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orgs", "0003_delete_companyinvitation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyInvitation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "accepted",
                    models.BooleanField(default=False, verbose_name="accepted"),
                ),
                (
                    "key",
                    models.CharField(max_length=64, unique=True, verbose_name="key"),
                ),
                ("sent", models.DateTimeField(null=True, verbose_name="sent")),
                (
                    "email",
                    models.EmailField(
                        max_length=254, unique=True, verbose_name="e-mail address"
                    ),
                ),
                (
                    "created",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="created"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="orgs.company"
                    ),
                ),
                (
                    "inviter",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="inviter",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
