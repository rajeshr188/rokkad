from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("girvi", "0027_release_settlement_snapshot_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="GirviNumberSequence",
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
                    "document_kind",
                    models.CharField(
                        choices=[
                            ("GIVEN_LOAN", "Given Loan"),
                            ("TAKEN_LOAN", "Taken Loan"),
                            ("GIVEN_LOAN_RELEASE", "Given Loan Release"),
                            ("TAKEN_LOAN_SETTLEMENT", "Taken Loan Settlement"),
                        ],
                        max_length=32,
                    ),
                ),
                ("prefix", models.CharField(max_length=16)),
                ("width", models.PositiveIntegerField(default=5)),
                ("next_number", models.PositiveIntegerField(default=1)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "last_allocated_number",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("last_allocated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("notes", models.TextField(blank=True, default="")),
                (
                    "series",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="number_sequences",
                        to="girvi.series",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="girvi_number_sequences_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("series_id", "document_kind"),
            },
        ),
        migrations.AddConstraint(
            model_name="girvinumbersequence",
            constraint=models.UniqueConstraint(
                fields=("series", "document_kind"),
                name="unique_girvi_number_sequence_per_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="girvinumbersequence",
            constraint=models.CheckConstraint(
                condition=models.Q(("width__gt", 0)),
                name="girvi_number_sequence_width_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="girvinumbersequence",
            constraint=models.CheckConstraint(
                condition=models.Q(("next_number__gt", 0)),
                name="girvi_number_sequence_next_positive",
            ),
        ),
        migrations.AddIndex(
            model_name="girvinumbersequence",
            index=models.Index(
                fields=["document_kind", "is_active"],
                name="girvi_girvi_documen_6bd642_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="girvinumbersequence",
            index=models.Index(
                fields=["series", "document_kind", "is_active"],
                name="girvi_girvi_series__353ec4_idx",
            ),
        ),
    ]
