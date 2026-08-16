from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0059_rename_loan_event_relations"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pawnloandisbursalsnapshot",
            old_name="accounting_event",
            new_name="loan_event",
        ),
        migrations.RenameField(
            model_name="pawnloaninterestaccrual",
            old_name="accounting_event",
            new_name="loan_event",
        ),
        migrations.RenameField(
            model_name="pawnloanrepaymentallocationline",
            old_name="accounting_event",
            new_name="loan_event",
        ),
        migrations.RenameField(
            model_name="pawnloanprincipalclosingline",
            old_name="accounting_event",
            new_name="loan_event",
        ),
        migrations.RenameField(
            model_name="pawnloanprincipalopeningline",
            old_name="accounting_event",
            new_name="loan_event",
        ),
        migrations.RenameField(
            model_name="pawnloanrelease",
            old_name="accounting_event",
            new_name="loan_event",
        ),
        migrations.RenameField(
            model_name="pawnloanreleasereversal",
            old_name="accounting_event",
            new_name="loan_event",
        ),
        migrations.RenameField(
            model_name="pawnloanauction",
            old_name="accounting_event",
            new_name="loan_event",
        ),
        migrations.RenameField(
            model_name="pawnloanauctionreversal",
            old_name="accounting_event",
            new_name="loan_event",
        ),
    ]
