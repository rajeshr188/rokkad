from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0002_pawnloanapprovalsnapshot")]

    operations = [
        migrations.AlterField(
            model_name="loanchangelog",
            name="event_kind",
            field=models.CharField(
                max_length=40,
                choices=[
                    ("DRAFT_CREATED", "Draft Created"),
                    ("DRAFT_UPDATED", "Draft Updated"),
                    ("LICENSE_TRANSFERRED", "License Transferred"),
                    ("APPROVED", "Approved"),
                    ("RETURNED_TO_DRAFT", "Returned To Draft"),
                    ("CANCELLED", "Cancelled"),
                    ("DISBURSED", "Disbursed"),
                    ("REPAYMENT_RECORDED", "Repayment Recorded"),
                    ("ACCRUAL_FINALIZED", "Accrual Finalized"),
                    ("INTEREST_CAPITALIZED", "Interest Capitalized"),
                    ("RELEASE_COMPLETED", "Release Completed"),
                    ("CLOSED", "Closed"),
                    ("REVERSAL_RECORDED", "Reversal Recorded"),
                ],
            ),
        )
    ]
