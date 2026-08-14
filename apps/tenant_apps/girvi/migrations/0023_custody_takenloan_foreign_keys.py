import django.db.models.deletion
from django.core.exceptions import ValidationError
from django.db import migrations, models


def validate_custody_refs_point_to_taken_loans(apps, schema_editor):
    LoanItem = apps.get_model("girvi", "LoanItem")
    RepledgeHistory = apps.get_model("girvi", "RepledgeHistory")
    TakenLoan = apps.get_model("girvi", "TakenLoan")

    taken_loan_ids = set(TakenLoan.objects.values_list("id", flat=True))

    invalid_item_ids = list(
        LoanItem.objects.exclude(repledged_to_id__isnull=True)
        .exclude(repledged_to_id__in=taken_loan_ids)
        .values_list("id", "repledged_to_id")[:20]
    )
    invalid_history_ids = list(
        RepledgeHistory.objects.exclude(taken_loan_id__in=taken_loan_ids)
        .values_list("id", "taken_loan_id")[:20]
    )

    if invalid_item_ids or invalid_history_ids:
        raise ValidationError(
            "Cannot migrate Girvi custody FKs to TakenLoan because some custody "
            "records point to legacy Loan rows that do not exist as TakenLoan rows. "
            f"Invalid LoanItem refs: {invalid_item_ids}; "
            f"invalid RepledgeHistory refs: {invalid_history_ids}."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("girvi", "0022_givenloan_borrower_party_takenloan_lender_party_and_more"),
    ]

    operations = [
        migrations.RunPython(
            validate_custody_refs_point_to_taken_loans,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="loanitem",
            name="repledged_to",
            field=models.ForeignKey(
                blank=True,
                help_text="Active repledge - item is currently with this lender",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="active_custody_items",
                to="girvi.takenloan",
            ),
        ),
        migrations.AlterField(
            model_name="repledgehistory",
            name="taken_loan",
            field=models.ForeignKey(
                help_text="The TakenLoan where this item was used as collateral",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="repledge_history_items",
                to="girvi.takenloan",
            ),
        ),
    ]
