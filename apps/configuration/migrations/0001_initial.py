# Generated manually for centralized configuration preferences.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orgs", "0024_alter_auditlog_action"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspacePreferenceModel",
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
                    "section",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default=None,
                        max_length=150,
                        null=True,
                        verbose_name="Section Name",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        db_index=True,
                        max_length=150,
                        verbose_name="Name",
                    ),
                ),
                (
                    "raw_value",
                    models.TextField(
                        blank=True,
                        null=True,
                        verbose_name="Raw Value",
                    ),
                ),
                (
                    "instance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="configuration_preferences",
                        to="orgs.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "workspace preference",
                "verbose_name_plural": "workspace preferences",
                "unique_together": {("instance", "section", "name")},
            },
        ),
        migrations.CreateModel(
            name="PreferenceAuditLog",
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
                    "scope",
                    models.CharField(
                        choices=[
                            ("global", "Global"),
                            ("workspace", "Workspace"),
                            ("user", "User"),
                        ],
                        max_length=20,
                    ),
                ),
                ("key", models.CharField(db_index=True, max_length=300)),
                ("old_value", models.TextField(blank=True, null=True)),
                ("new_value", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="preference_audit_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "subject_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="preference_audit_subjects",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="preference_audit_logs",
                        to="orgs.company",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["scope", "key"], name="configurati_scope_6eb5c8_idx"),
                    models.Index(fields=["workspace", "scope"], name="configurati_workspa_71282d_idx"),
                    models.Index(fields=["subject_user", "scope"], name="configurati_subject_c26281_idx"),
                ],
            },
        ),
    ]
