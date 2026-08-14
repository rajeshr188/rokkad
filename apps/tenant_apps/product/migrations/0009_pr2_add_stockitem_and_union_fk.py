# Generated migration for PR-2: Introduce StockItem + Union FK Columns
# Creates StockItem model and adds union FK columns to StockTransaction and StockStatement
# Additive schema changes - no data deletion or behavior switch yet

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0008_pr1_p0_inventory_bug_fixes"),
    ]

    operations = [
        # Add parent_stock self-FK to Stock for lineage tracking
        migrations.AddField(
            model_name='stock',
            name='parent_stock',
            field=models.ForeignKey(
                blank=True,
                help_text='Parent lot if this was created via merge/split operation',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='children',
                to='product.stock'
            ),
        ),
        # Create StockItem model
        migrations.CreateModel(
            name='StockItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('quantity', models.IntegerField(default=1)),
                ('weight', models.DecimalField(decimal_places=3, max_digits=10)),
                ('serial_no', models.CharField(blank=True, max_length=8, null=True, unique=True)),
                ('huid', models.CharField(blank=True, max_length=7, null=True, unique=True)),
                ('purchase_touch', models.DecimalField(decimal_places=3, max_digits=10)),
                ('purchase_rate', models.DecimalField(blank=True, decimal_places=3, max_digits=10, null=True)),
                ('status', models.CharField(
                    choices=[('Available', 'Available'), ('Sold', 'Sold'), ('Damaged', 'Damaged'), ('Lost', 'Lost'), ('Reserved', 'Reserved')],
                    default='Available',
                    max_length=10
                )),
                ('parent_stock', models.ForeignKey(
                    blank=True,
                    help_text='Parent lot if created via split operation',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='split_items',
                    to='product.stock'
                )),
                ('variant', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_items',
                    to='product.productvariant'
                )),
            ],
            options={
                'ordering': ('-created',),
            },
        ),
        # Make stock nullable on StockTransaction and add stock_item
        migrations.AlterField(
            model_name='stocktransaction',
            name='stock',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='product.stock'
            ),
        ),
        migrations.AddField(
            model_name='stocktransaction',
            name='stock_item',
            field=models.ForeignKey(
                blank=True,
                help_text='Union FK: either stock_id or stock_item_id must be set',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='transactions',
                to='product.stockitem'
            ),
        ),
        # Make stock nullable on StockStatement and add stock_item
        migrations.AlterField(
            model_name='stockstatement',
            name='stock',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='product.stock'
            ),
        ),
        migrations.AddField(
            model_name='stockstatement',
            name='stock_item',
            field=models.ForeignKey(
                blank=True,
                help_text='Union FK: either stock_id or stock_item_id must be set',
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='statements',
                to='product.stockitem'
            ),
        ),
    ]
