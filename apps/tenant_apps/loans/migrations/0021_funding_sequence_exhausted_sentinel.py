from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0020_funding_loan_database_guards"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="fundingloansequence",
            name="loans_funding_seq_max_valid",
        ),
        migrations.AddConstraint(
            model_name="fundingloansequence",
            constraint=models.CheckConstraint(
                condition=Q(maximum_value__isnull=True)
                | Q(next_value__lte=F("maximum_value") + 1),
                name="loans_funding_seq_max_valid",
            ),
        ),
    ]