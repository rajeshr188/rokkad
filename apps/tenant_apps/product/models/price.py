from django.db import models
from django.db.models import Q
from mptt.models import MPTTModel, TreeForeignKey


class PricingTier(MPTTModel):
    """
    base-tier will have basic purchase and selling price for the product-variants,
    consequent tiers can derive from base-tier and modify a set of price for the set of products
    """

    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    parent = TreeForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    minimum_quantity = models.PositiveIntegerField()

    class MPTTMeta:
        order_insertion_by = ["name"]

    def __str__(self):
        return self.name


class PricingTierProductPrice(models.Model):
    pricing_tier = models.ForeignKey(
        PricingTier, on_delete=models.CASCADE, related_name="price_list"
    )
    product = models.ForeignKey("ProductVariant", on_delete=models.CASCADE)
    purchase_price = models.DecimalField(decimal_places=3, max_digits=13)
    selling_price = models.DecimalField(decimal_places=3, max_digits=13)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pricing_tier", "product"],
                name="uq_product_tierprice_tier_product",
            ),
            models.CheckConstraint(
                condition=Q(purchase_price__gte=0),
                name="ck_product_tierprice_purchase_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(selling_price__gte=0),
                name="ck_product_tierprice_selling_non_negative",
            ),
        ]


# example usage
# product = Product.objects.get(id=1)
# customer = Customer.objects.get(id=1)
# qty=10

# Traverse the pricing tier hierarchy to get the effective selling price for the customer and product
# pricing_tier = customer.pricing_tier
# while pricing_tier:
#     pricing_tier_price = PricingTierProductPrice.objects.filter(pricing_tier=pricing_tier, product=product).first()
#     if pricing_tier_price:
#         if pricing_tier_price.minimum_quantity <= quantity:
#             selling_price = pricing_tier_price.selling_price
#             break
#         else:
#             pricing_tier = pricing_tier.parent_tier
#     else:
#         pricing_tier = pricing_tier.parent_tier

# Fallback to individual price for customer and product
# if not pricing_tier:
#     price = Price.objects.filter(product=product, customer=customer).first()
#     selling_price = price.selling_price if price else None


# this is fallback to individual pricing percustomer per product
class Price(models.Model):
    """
    price for each product variant that will be used by stock in determining selling/purchasing
    price based on the tier the customer belongs to
    """

    product = models.ForeignKey("ProductVariant", on_delete=models.CASCADE)
    contact = models.ForeignKey(
        "contact.Customer", on_delete=models.CASCADE, related_name="prices"
    )
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    # not required ?
    price_tier = models.ForeignKey(
        PricingTier,
        on_delete=models.CASCADE,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["contact", "product"],
                name="uq_product_price_contact_product",
            ),
            models.CheckConstraint(
                condition=Q(purchase_price__gte=0),
                name="ck_product_price_purchase_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(selling_price__gte=0),
                name="ck_product_price_selling_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.product} : {self.selling_price} {self.purchase_price}"
