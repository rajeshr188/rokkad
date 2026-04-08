from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0010_pr2_add_union_fk_constraints"),
        ("sales", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoiceitem",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="sold_items",
                to="product.stock",
            ),
        ),
        migrations.AddField(
            model_name="invoiceitem",
            name="stock_item",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="sold_items",
                to="product.stockitem",
            ),
        ),
        migrations.AddConstraint(
            model_name="invoiceitem",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(product__isnull=False) & models.Q(stock_item__isnull=True))
                    | (models.Q(product__isnull=True) & models.Q(stock_item__isnull=False))
                ),
                name="sales_invoiceitem_exactly_one_subject",
            ),
        ),
    ]