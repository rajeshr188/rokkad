# Generated migration for PR-2: Add Union FK Check Constraints
# Ensures exactly one of (stock_id, stock_item_id) is set on StockTransaction and StockStatement

from django.db import migrations


def add_constraints(apps, schema_editor):
    """Add check constraints for union FK semantics."""
    schema_editor.execute("""
        ALTER TABLE product_stocktransaction
        ADD CONSTRAINT check_union_fk_txn 
        CHECK (
            (stock_id IS NOT NULL AND stock_item_id IS NULL) OR
            (stock_id IS NULL AND stock_item_id IS NOT NULL)
        );
    """)
    
    schema_editor.execute("""
        ALTER TABLE product_stockstatement
        ADD CONSTRAINT check_union_fk_stmt 
        CHECK (
            (stock_id IS NOT NULL AND stock_item_id IS NULL) OR
            (stock_id IS NULL AND stock_item_id IS NOT NULL)
        );
    """)


def remove_constraints(apps, schema_editor):
    """Remove check constraints for rollback."""
    schema_editor.execute("""
        ALTER TABLE product_stocktransaction
        DROP CONSTRAINT IF EXISTS check_union_fk_txn;
    """)
    
    schema_editor.execute("""
        ALTER TABLE product_stockstatement
        DROP CONSTRAINT IF EXISTS check_union_fk_stmt;
    """)


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0009_pr2_add_stockitem_and_union_fk"),
    ]

    operations = [
        migrations.RunPython(add_constraints, remove_constraints),
    ]
