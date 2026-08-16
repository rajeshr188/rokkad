from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0057_retire_accounting_outbox"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="PawnLoanAccountingEvent",
            new_name="PawnLoanEvent",
        ),
    ]
