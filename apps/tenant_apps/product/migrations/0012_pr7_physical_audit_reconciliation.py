from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0011_pr6_unified_balance_views"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockstatement",
            name="physical_qty",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockstatement",
            name="physical_wt",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="stockstatement",
            name="reconciled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockstatement",
            name="status",
            field=models.CharField(
                choices=[
                    ("Recorded", "Recorded"),
                    ("Discrepancy", "Discrepancy"),
                    ("Reconciled", "Reconciled"),
                ],
                default="Recorded",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="stockstatement",
            name="system_qty",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockstatement",
            name="system_wt",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="stockstatement",
            name="variance_qty",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="stockstatement",
            name="variance_wt",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True),
        ),
    ]