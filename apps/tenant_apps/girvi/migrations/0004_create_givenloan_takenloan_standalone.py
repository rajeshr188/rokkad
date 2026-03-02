# Generated migration: Create GivenLoan and TakenLoan as standalone concrete models

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contact", "0003_alter_customer_options_and_more"),
        ("girvi", "add_custody_tracking"),
        ("product", "0004_auto_views"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create GivenLoan model as standalone concrete table
        migrations.CreateModel(
            name="GivenLoan",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("auto_post_to_accounting", models.BooleanField(default=True)),
                (
                    "loan_id",
                    models.CharField(
                        db_index=True,
                        help_text="Globally unique loan ID with series prefix (e.g., 'A00123')",
                        max_length=50,
                        unique=True,
                    ),
                ),
                (
                    "loan_date",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Loan Date",
                    ),
                ),
                (
                    "tenure",
                    models.PositiveIntegerField(
                        default=3, help_text="Loan tenure in months"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("Created", "Created"),
                            ("Approved", "Approved"),
                            ("Rejected", "Rejected"),
                            ("Disbursed", "Disbursed"),
                            ("Closed", "Closed"),
                            ("Released", "Released"),
                            ("Repledged", "Repledged"),
                            ("Sold", "Sold"),
                            ("Defaulted", "Defaulted"),
                            ("Auctioned", "Auctioned"),
                            ("Cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="Created",
                        max_length=20,
                    ),
                ),
                (
                    "interest_type",
                    models.CharField(
                        choices=[("Simple", "Simple"), ("Compound", "Compound")],
                        default="Simple",
                        max_length=10,
                    ),
                ),
                (
                    "borrower",
                    models.ForeignKey(
                        help_text="Customer receiving this loan",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="loans_received",
                        to="contact.customer",
                        verbose_name="Borrower",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "series",
                    models.ForeignKey(
                        help_text="Series - determines loan ID prefix and sequence (required)",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="girvi.series",
                        verbose_name="Series",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Given Loan (Pawn)",
                "verbose_name_plural": "Given Loans (Pawns)",
            },
        ),
        # Create TakenLoan model as standalone concrete table
        migrations.CreateModel(
            name="TakenLoan",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("auto_post_to_accounting", models.BooleanField(default=True)),
                (
                    "loan_id",
                    models.CharField(
                        db_index=True,
                        help_text="Globally unique loan ID with series prefix (e.g., 'A00123')",
                        max_length=50,
                        unique=True,
                    ),
                ),
                (
                    "loan_date",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        verbose_name="Loan Date",
                    ),
                ),
                (
                    "tenure",
                    models.PositiveIntegerField(
                        default=3, help_text="Loan tenure in months"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("Created", "Created"),
                            ("Approved", "Approved"),
                            ("Rejected", "Rejected"),
                            ("Disbursed", "Disbursed"),
                            ("Closed", "Closed"),
                            ("Released", "Released"),
                            ("Repledged", "Repledged"),
                            ("Sold", "Sold"),
                            ("Defaulted", "Defaulted"),
                            ("Auctioned", "Auctioned"),
                            ("Cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="Created",
                        max_length=20,
                    ),
                ),
                (
                    "interest_type",
                    models.CharField(
                        choices=[("Simple", "Simple"), ("Compound", "Compound")],
                        default="Simple",
                        max_length=10,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "lender",
                    models.ForeignKey(
                        help_text="Customer providing this loan to us",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="loans_given",
                        to="contact.customer",
                        verbose_name="Lender",
                    ),
                ),
                (
                    "original_loan",
                    models.ForeignKey(
                        blank=True,
                        help_text="Original GivenLoan being repledged",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="repledged_as",
                        to="girvi.givenloan",
                    ),
                ),
                (
                    "series",
                    models.ForeignKey(
                        help_text="Series - determines loan ID prefix and sequence (required)",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="girvi.series",
                        verbose_name="Series",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Taken Loan (Repledge)",
                "verbose_name_plural": "Taken Loans (Repledges)",
            },
        ),
        # Add constraints
        migrations.AddConstraint(
            model_name="givenloan",
            constraint=models.UniqueConstraint(
                fields=("series", "loan_id"), name="unique_givenloan_id_per_series"
            ),
        ),
        migrations.AddConstraint(
            model_name="takenloan",
            constraint=models.UniqueConstraint(
                fields=("series", "loan_id"), name="unique_takenloan_id_per_series"
            ),
        ),
        # Add indexes
        migrations.AddIndex(
            model_name="givenloan",
            index=models.Index(
                fields=["borrower", "status"], name="girvi_given_borrowe_276848_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="givenloan",
            index=models.Index(
                fields=["status", "loan_date"], name="girvi_given_status_f4e1f1_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="takenloan",
            index=models.Index(
                fields=["lender", "status"], name="girvi_taken_lender__3c1f46_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="takenloan",
            index=models.Index(
                fields=["original_loan"], name="girvi_taken_origina_ef0fa7_idx"
            ),
        ),
    ]
