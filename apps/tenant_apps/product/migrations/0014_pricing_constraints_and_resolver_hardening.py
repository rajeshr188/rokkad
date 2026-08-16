from django.db import migrations, models
from django.db.models import Count, Q


def dedupe_pricing_rows(apps, schema_editor):
    PricingTierProductPrice = apps.get_model("product", "PricingTierProductPrice")
    Price = apps.get_model("product", "Price")

    duplicate_tier_prices = (
        PricingTierProductPrice.objects.values("pricing_tier_id", "product_id")
        .annotate(row_count=Count("id"))
        .filter(row_count__gt=1)
    )

    for duplicate in duplicate_tier_prices:
        rows = PricingTierProductPrice.objects.filter(
            pricing_tier_id=duplicate["pricing_tier_id"],
            product_id=duplicate["product_id"],
        ).order_by("id")
        rows.exclude(id=rows.first().id).delete()

    duplicate_party_prices = (
        Price.objects.values("party_id", "product_id")
        .annotate(row_count=Count("id"))
        .filter(row_count__gt=1)
    )

    for duplicate in duplicate_party_prices:
        rows = Price.objects.filter(
            party_id=duplicate["party_id"],
            product_id=duplicate["product_id"],
        ).order_by("id")
        rows.exclude(id=rows.first().id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("product", "0013_opening_balance_and_purchase_touch_nullable"),
    ]

    operations = [
        migrations.RunPython(dedupe_pricing_rows, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="pricingtierproductprice",
            constraint=models.UniqueConstraint(
                fields=("pricing_tier", "product"),
                name="uq_product_tierprice_tier_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="pricingtierproductprice",
            constraint=models.CheckConstraint(
                condition=Q(("purchase_price__gte", 0)),
                name="ck_product_tierprice_purchase_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="pricingtierproductprice",
            constraint=models.CheckConstraint(
                condition=Q(("selling_price__gte", 0)),
                name="ck_product_tierprice_selling_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="price",
            constraint=models.UniqueConstraint(
                fields=("party", "product"),
                name="uq_product_price_party_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="price",
            constraint=models.CheckConstraint(
                condition=Q(("purchase_price__gte", 0)),
                name="ck_product_price_purchase_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="price",
            constraint=models.CheckConstraint(
                condition=Q(("selling_price__gte", 0)),
                name="ck_product_price_selling_non_negative",
            ),
        ),
    ]
