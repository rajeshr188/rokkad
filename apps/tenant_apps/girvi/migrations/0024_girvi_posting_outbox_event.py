from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("girvi", "0023_custody_takenloan_foreign_keys"),
    ]

    operations = [
        migrations.CreateModel(
            name="GirviPostingOutboxEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("DISBURSAL", "Disbursal"),
                            ("REPAYMENT", "Repayment"),
                            ("RELEASE", "Release"),
                            ("ACCRUAL", "Accrual"),
                            ("AUCTION_RECOVERY", "Auction Recovery"),
                            ("SALE_RECOVERY", "Sale Recovery"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("dedupe_key", models.CharField(max_length=128, unique=True)),
                ("payload", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PROCESSING", "Processing"),
                            ("POSTED", "Posted"),
                            ("FAILED", "Failed"),
                            ("DEAD_LETTER", "Dead Letter"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("source_app", models.CharField(default="girvi", max_length=64)),
                ("source_model", models.CharField(max_length=64)),
                ("source_pk", models.CharField(max_length=64)),
                ("contract_version", models.PositiveSmallIntegerField(default=1)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("available_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("id",),
                "indexes": [
                    models.Index(fields=["status", "available_at"], name="girvi_girvi_status_8c2f89_idx"),
                    models.Index(fields=["event_type", "status"], name="girvi_girvi_event_t_113738_idx"),
                    models.Index(fields=["source_app", "source_model", "source_pk"], name="girvi_girvi_source__ca5934_idx"),
                ],
            },
        ),
    ]
