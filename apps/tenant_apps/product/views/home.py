from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..models import (
    Attribute,
    AttributeValue,
    Price,
    Product,
    ProductType,
    ProductVariant,
    PricingTier,
    PricingTierProductPrice,
    Stock,
    StockItem,
    StockStatement,
    StockTransaction,
)


@login_required
@for_htmx(use_block="content")
def home(request):
    stock_count = Stock.objects.count()
    stock_item_count = StockItem.objects.count()
    physical_statements = StockStatement.objects.filter(method="Physical")

    ctx = {
        "stats": {
            "product_types": ProductType.objects.count(),
            "products": Product.objects.count(),
            "variants": ProductVariant.objects.count(),
            "attributes": Attribute.objects.count(),
            "attribute_values": AttributeValue.objects.count(),
        },
        "inventory_stats": {
            "lots": stock_count,
            "items": stock_item_count,
            "subjects": stock_count + stock_item_count,
            "transactions": StockTransaction.objects.count(),
            "physical_statements": physical_statements.count(),
            "pending_reconciliation": physical_statements.filter(
                status=StockStatement.StatusChoices.DISCREPANCY
            ).count(),
        },
        "pricing_stats": {
            "tiers": PricingTier.objects.count(),
            "tier_prices": PricingTierProductPrice.objects.count(),
            "overrides": Price.objects.count(),
        },
    }
    return render(request, "product/home.html", ctx)
