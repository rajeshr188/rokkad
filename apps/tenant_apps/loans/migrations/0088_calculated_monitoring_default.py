from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0087_merge_monitoring_policy_lock")]

    operations = [migrations.AlterField(
        model_name="loanmonitoringpolicy", name="valuation_basis",
        field=models.CharField(max_length=40,
            default="CALCULATED_METAL_VALUE", db_default="CALCULATED_METAL_VALUE",
            choices=[
                ("ORIGINAL_AGREEMENT", "Use each loan's saved valuation method"),
                ("CALCULATED_METAL_VALUE", "Current calculated metal value"),
                ("LATEST_APPRAISAL", "Latest approved appraisal"),
                ("LOWER_OF_CALCULATED_AND_APPRAISAL", "Lower of current metal value and approved appraisal"),
            ]),
    )]
