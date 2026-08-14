from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("loans", "0004_pawnloanaccountingevent_pawnloanaccountingoutbox"),
    ]

    operations = [
        migrations.CreateModel(
            name="PawnLoanInterestAccrual",
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
                ("period_number", models.PositiveIntegerField()),
                ("period_start", models.DateField()),
                ("period_end", models.DateField(db_index=True)),
                (
                    "period_fraction",
                    models.DecimalField(decimal_places=4, max_digits=8),
                ),
                (
                    "calculation_base",
                    models.DecimalField(decimal_places=12, max_digits=30),
                ),
                (
                    "unrounded_interest",
                    models.DecimalField(decimal_places=12, max_digits=30),
                ),
                (
                    "recognized_interest",
                    models.DecimalField(decimal_places=4, max_digits=18),
                ),
                ("finalized_at", models.DateTimeField(auto_now_add=True)),
                (
                    "accounting_event",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="interest_accrual",
                        to="loans.pawnloanaccountingevent",
                    ),
                ),
                (
                    "finalized_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="pawn_loan_interest_accruals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "loan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="interest_accruals",
                        to="loans.pawnloan",
                    ),
                ),
            ],
            options={"ordering": ("loan_id", "period_number")},
        ),
        migrations.AddConstraint(
            model_name="pawnloaninterestaccrual",
            constraint=models.UniqueConstraint(
                fields=("loan", "period_number"),
                name="loans_accrual_loan_period_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="pawnloaninterestaccrual",
            constraint=models.CheckConstraint(
                condition=models.Q(("period_number__gt", 0)),
                name="loans_accrual_period_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="pawnloaninterestaccrual",
            constraint=models.CheckConstraint(
                condition=models.Q(("period_end__gte", models.F("period_start"))),
                name="loans_accrual_dates_ordered",
            ),
        ),
        migrations.AddConstraint(
            model_name="pawnloaninterestaccrual",
            constraint=models.CheckConstraint(
                condition=models.Q(("period_fraction__gt", 0), ("period_fraction__lte", 1)),
                name="loans_accrual_fraction_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="pawnloaninterestaccrual",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("calculation_base__gte", 0),
                    ("unrounded_interest__gte", 0),
                    ("recognized_interest__gte", 0),
                ),
                name="loans_accrual_amounts_nonnegative",
            ),
        ),
    ]
