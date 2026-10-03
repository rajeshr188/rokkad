from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("loans", "0050_merge_khata_label_batches")]
    operations = [
        migrations.AlterField(model_name="pawnloanprincipalopeningline", name="collateral_item",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name="principal_opening_lines", to="loans.pawncollateralitem")),
        migrations.AddConstraint(model_name="pawnloanprincipalopeningline",
            constraint=models.UniqueConstraint(fields=("loan_event", "collateral_item"), name="loans_open_event_item_uniq")),
    ]
