from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("loans", "0052_remove_collateralintakebatch_loans_intake_workspace_ref_uniq_and_more")]

    operations = [
        migrations.AddField(
            model_name="loanrisksnapshot",
            name="source_provenance",
            field=models.JSONField(default=dict),
        ),
    ]
