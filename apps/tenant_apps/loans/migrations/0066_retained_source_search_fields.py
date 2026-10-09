"""Database-derived search metadata; retained documents and their hashes are untouched."""
from django.db import migrations, models
from django.db.models.fields.json import KT


class Migration(migrations.Migration):
    dependencies = [("loans", "0065_closed_position_admission")]
    operations = [migrations.AddField(model_name="historicalloanevidence", name=name,
        field=models.GeneratedField(expression=KT(f"document__facts__{key}"),
            output_field=models.TextField(), db_persist=True))
        for name, key in (("search_loan_number", "loan_number"),
                          ("search_borrower_name", "borrower_name"),
                          ("search_opened_on", "opened_on"))]
