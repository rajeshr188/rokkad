from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0055_dated_custody_business_day")]
    operations = [
        migrations.AddField(model_name="pawnloaneconomicpolicy", name="default_tenure_months",
            field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddConstraint(model_name="pawnloaneconomicpolicy", constraint=models.CheckConstraint(
            condition=models.Q(default_tenure_months__isnull=True) | models.Q(default_tenure_months__gte=1, default_tenure_months__lte=600),
            name="loans_econ_default_tenure_range")),
    ]
