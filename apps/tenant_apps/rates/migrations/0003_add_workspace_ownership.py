import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orgs", "0025_alter_company_schema_name"),
        ("rates", "0002_load_metal_rates"),
    ]

    operations = [
        migrations.AddField(
            model_name="rate",
            name="workspace",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="orgs.company",
            ),
        ),
        migrations.AddField(
            model_name="ratesource",
            name="workspace",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="orgs.company",
            ),
        ),
        migrations.AlterUniqueTogether(name="rate", unique_together=set()),
        migrations.AddConstraint(
            model_name="rate",
            constraint=models.UniqueConstraint(
                fields=("workspace", "metal", "currency", "timestamp", "purity"),
                name="rates_rate_workspace_quote_uniq",
            ),
        ),
    ]
