from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0056_standard_loan_tenure")]
    operations = [
        migrations.AddField(model_name="pawnloaneconomicpolicy", name="default_entry_purpose",
            field=models.CharField(max_length=12, default="INHERIT", choices=[
                ("INHERIT", "Inherit broader default"), ("DIRECT", "Create and pay now"),
                ("PAPER", "Record from paper")])),
        migrations.AddConstraint(model_name="pawnloaneconomicpolicy",
            constraint=models.CheckConstraint(condition=models.Q(default_entry_purpose__in=("INHERIT", "DIRECT", "PAPER")),
                                              name="loans_econ_entry_purpose_valid")),
    ]
