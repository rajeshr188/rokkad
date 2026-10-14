from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0072_risk_evidence_guards")]

    operations = [migrations.AddField(
        model_name="loanmonitoringpolicy", name="valuation_basis",
        field=models.CharField(max_length=40, default="ORIGINAL_AGREEMENT", db_default="ORIGINAL_AGREEMENT", choices=[
            ("ORIGINAL_AGREEMENT", "Use each loan's saved valuation method"),
            ("CALCULATED_METAL_VALUE", "Current calculated metal value"),
            ("LATEST_APPRAISAL", "Latest approved appraisal"),
            ("LOWER_OF_CALCULATED_AND_APPRAISAL", "Lower of current metal value and approved appraisal"),
        ]),
    ), migrations.AddConstraint(
        model_name="loanmonitoringpolicy",
        constraint=models.CheckConstraint(condition=models.Q(valuation_basis__in=(
            "ORIGINAL_AGREEMENT", "CALCULATED_METAL_VALUE", "LATEST_APPRAISAL", "LOWER_OF_CALCULATED_AND_APPRAISAL")),
            name="loans_monitor_valuation_basis_valid"),
    )]
