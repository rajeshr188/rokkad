import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rates", "0004_backfill_workspace")]

    operations = [
        migrations.AlterField(
            model_name="rate",
            name="workspace",
            field=models.ForeignKey(
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="orgs.company",
            ),
        ),
        migrations.AlterField(
            model_name="ratesource",
            name="workspace",
            field=models.ForeignKey(
                editable=False,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="orgs.company",
            ),
        ),
    ]
