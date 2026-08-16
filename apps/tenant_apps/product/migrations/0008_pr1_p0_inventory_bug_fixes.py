# Generated migration for PR-1: P0 Inventory Bug Fixes
# - Remove duplicate sku field
# - Fix merge() typos and issues
# - Fix StockStatement.created from auto_now to auto_now_add
# - Remove dead merge_lots() function
# - Fix SQL view OR 1>0 logic
# - Add Movement codes RM and SS

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0007_remove_product_jattributes_and_more"),
    ]

    operations = [
        # Fix StockStatement.created from auto_now to auto_now_add
        migrations.AlterField(
            model_name='stockstatement',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
