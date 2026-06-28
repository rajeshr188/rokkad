from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("girvi", "0025_rename_girvi_girvi_status_8c2f89_idx_girvi_girvi_status_08ea95_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="givenloan",
            name="disbursal_document_charge",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Document/processing charge deducted from borrower payout at disbursal.",
                max_digits=14,
            ),
        ),
        migrations.AddField(
            model_name="givenloan",
            name="disbursal_upfront_interest_deduction",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                help_text="Upfront interest deducted from borrower payout at disbursal.",
                max_digits=14,
            ),
        ),
    ]
