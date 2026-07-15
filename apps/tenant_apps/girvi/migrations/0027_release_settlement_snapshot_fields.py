from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("girvi", "0026_givenloan_disbursal_deduction_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="release",
            name="accrual_interest_gross",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                verbose_name="Accrual Interest Gross",
            ),
        ),
        migrations.AddField(
            model_name="release",
            name="interest_basis_variance",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                verbose_name="Interest Basis Variance",
            ),
        ),
        migrations.AddField(
            model_name="release",
            name="interest_paid_snapshot",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                verbose_name="Interest Paid Snapshot",
            ),
        ),
        migrations.AddField(
            model_name="release",
            name="selector_interest_quote",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                verbose_name="Selector Interest Quote",
            ),
        ),
        migrations.AddField(
            model_name="release",
            name="settlement_basis",
            field=models.CharField(
                default="SELECTOR_COMPATIBILITY",
                help_text="Source used for final release settlement interest.",
                max_length=32,
                verbose_name="Settlement Basis",
            ),
        ),
        migrations.AddField(
            model_name="release",
            name="settlement_interest_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                verbose_name="Settlement Interest Amount",
            ),
        ),
        migrations.AddField(
            model_name="release",
            name="settlement_principal_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                verbose_name="Settlement Principal Amount",
            ),
        ),
        migrations.AddField(
            model_name="release",
            name="settlement_total_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=14,
                verbose_name="Settlement Total Amount",
            ),
        ),
    ]
