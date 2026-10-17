"""Separate the screen default from financial agreement configuration."""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from apps.tenancy.rls import EnableWorkspaceRLS


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0092_aggregate_checkpoint_corrections"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="LoanEntryPreference",
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
                    "workspace",
                    models.ForeignKey(
                        editable=False,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="orgs.company",
                    ),
                ),
                (
                    "license",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="loans.loanlicense",
                    ),
                ),
                (
                    "series",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="loans.loanseries",
                    ),
                ),
                (
                    "purpose",
                    models.CharField(
                        choices=[
                            ("INHERIT", "Follow broader default"),
                            ("DIRECT", "Create and pay now"),
                            ("PAPER", "Record from paper"),
                        ],
                        max_length=12,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("workspace", "license", "series"),
                        nulls_distinct=False,
                        name="loans_entry_preference_scope_uniq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(purpose__in=("INHERIT", "DIRECT", "PAPER")),
                        name="loans_entry_preference_purpose",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(series__isnull=True)
                        | models.Q(license__isnull=False),
                        name="loans_entry_preference_series_scope",
                    ),
                ]
            },
        ),
        EnableWorkspaceRLS("LoanEntryPreference"),
        migrations.RunSQL(
            """
        CREATE FUNCTION loans_entry_preference_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.license_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM loans_loanlicense WHERE id=NEW.license_id AND workspace_id=NEW.workspace_id)
          THEN RAISE EXCEPTION 'Entry preference licence belongs to another Workspace'; END IF;
          IF NEW.series_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM loans_loanseries WHERE id=NEW.series_id AND license_id=NEW.license_id AND workspace_id=NEW.workspace_id)
          THEN RAISE EXCEPTION 'Entry preference register has a conflicting scope'; END IF;
          RETURN NEW;
        END; $$;
        CREATE TRIGGER loans_entry_preference_scope_guard BEFORE INSERT OR UPDATE ON loans_loanentrypreference
        FOR EACH ROW EXECUTE FUNCTION loans_entry_preference_scope_guard();
        """,
            "DROP TRIGGER loans_entry_preference_scope_guard ON loans_loanentrypreference; DROP FUNCTION loans_entry_preference_scope_guard();",
        ),
    ]
