# Generated migration for PR-1: P0 Inventory Bug Fixes
# - Remove duplicate sku field
# - Fix merge() typos and issues
# - Fix split() journal_entry parameter
# - Make journal_entry nullable on StockTransaction
# - Fix StockStatement.created from auto_now to auto_now_add
# - Remove dead merge_lots() function
# - Fix SQL view OR 1>0 logic
# - Add Movement codes RM and SS

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dea", "0001_initial"),
        ("product", "0007_remove_product_jattributes_and_more"),
    ]

    operations = [
        # Make journal_entry nullable on StockTransaction
        migrations.AlterField(
            model_name='stocktransaction',
            name='journal_entry',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='stxns',
                to='dea.journalentry'
            ),
        ),
        # Fix StockStatement.created from auto_now to auto_now_add
        migrations.AlterField(
            model_name='stockstatement',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
