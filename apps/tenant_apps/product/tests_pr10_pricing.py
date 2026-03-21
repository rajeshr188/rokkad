from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django_tenants.test.cases import TenantTestCase

from .models import Category, Price, PricingTier, PricingTierProductPrice, Product, ProductType, ProductVariant
from .services import resolve_effective_price


User = get_user_model()


class PricingHardeningTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="pricing_test_owner",
            email="pricing_test_owner@example.com",
            password="testpass123",
        )
        tenant.name = "pricing-test-company"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        from apps.tenant_apps.contact.models import Customer

        self.Customer = Customer
        self.category = Category.objects.create(name="Pricing Category")
        self.product_type = ProductType.objects.create(name="Pricing Type", has_variants=True)
        self.product = Product.objects.create(
            product_type=self.product_type,
            category=self.category,
            name="Pricing Product",
            description="Pricing Product Description",
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="PRICING-SKU-1",
            product_code="PRICING-PC-1",
            name="Pricing Variant 1",
        )
        self.base_tier = PricingTier.objects.create(name="Base Tier", minimum_quantity=1)
        self.child_tier = PricingTier.objects.create(
            name="Child Tier", minimum_quantity=1, parent=self.base_tier
        )

    def _new_customer(self, name):
        return self.Customer.objects.create(firstname=name)

    def test_resolver_returns_tier_price_when_override_missing(self):
        contact = self._new_customer("TierOnlyContact")
        contact.pricing_tier = self.child_tier
        PricingTierProductPrice.objects.create(
            pricing_tier=self.base_tier,
            product=self.variant,
            purchase_price=Decimal("91.125"),
            selling_price=Decimal("99.875"),
        )

        resolved = resolve_effective_price(contact=contact, product=self.variant)

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.source, "tier")
        self.assertEqual(resolved.tier, self.base_tier)
        self.assertEqual(resolved.purchase_price, Decimal("91.125"))
        self.assertEqual(resolved.selling_price, Decimal("99.875"))

    def test_resolver_applies_contact_override_after_tier_lookup(self):
        contact = self._new_customer("OverrideContact")
        contact.pricing_tier = self.child_tier
        PricingTierProductPrice.objects.create(
            pricing_tier=self.base_tier,
            product=self.variant,
            purchase_price=Decimal("80.000"),
            selling_price=Decimal("90.000"),
        )
        Price.objects.create(
            product=self.variant,
            contact=contact,
            purchase_price=Decimal("88.00"),
            selling_price=Decimal("108.00"),
            price_tier=self.base_tier,
        )

        resolved = resolve_effective_price(contact=contact, product=self.variant)

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.source, "contact_override")
        self.assertEqual(resolved.purchase_price, Decimal("88.00"))
        self.assertEqual(resolved.selling_price, Decimal("108.00"))

    def test_resolver_works_without_pricing_tier_attribute(self):
        contact = self._new_customer("NoTierContact")
        Price.objects.create(
            product=self.variant,
            contact=contact,
            purchase_price=Decimal("75.00"),
            selling_price=Decimal("98.00"),
            price_tier=self.base_tier,
        )

        resolved = resolve_effective_price(contact=contact, product=self.variant)

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.source, "contact_override")
        self.assertEqual(resolved.purchase_price, Decimal("75.00"))
        self.assertEqual(resolved.selling_price, Decimal("98.00"))

    def test_pricing_tier_product_constraint_blocks_duplicates(self):
        PricingTierProductPrice.objects.create(
            pricing_tier=self.base_tier,
            product=self.variant,
            purchase_price=Decimal("91.000"),
            selling_price=Decimal("101.000"),
        )

        with self.assertRaises(IntegrityError):
            PricingTierProductPrice.objects.create(
                pricing_tier=self.base_tier,
                product=self.variant,
                purchase_price=Decimal("92.000"),
                selling_price=Decimal("102.000"),
            )

    def test_price_constraint_blocks_duplicates(self):
        contact = self._new_customer("DuplicateContact")
        Price.objects.create(
            product=self.variant,
            contact=contact,
            purchase_price=Decimal("80.00"),
            selling_price=Decimal("120.00"),
            price_tier=self.base_tier,
        )

        with self.assertRaises(IntegrityError):
            Price.objects.create(
                product=self.variant,
                contact=contact,
                purchase_price=Decimal("81.00"),
                selling_price=Decimal("121.00"),
                price_tier=self.base_tier,
            )
