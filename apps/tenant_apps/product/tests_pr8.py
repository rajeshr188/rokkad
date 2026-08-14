from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Max
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase

from apps.orgs.models import Membership, Role

from .inventory.services import InventoryMovementService
from .models import Category, Product, ProductType, ProductVariant, Stock, StockItem
from .tests_utils import ensure_inventory_movements


User = get_user_model()


class InventoryListingModesTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_product_pr8"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="product_pr8_owner",
            email="product_pr8_owner@example.com",
            password="testpass123",
        )
        tenant.name = "product-pr8-company"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        connection.set_tenant(self.tenant)
        ensure_inventory_movements()
        suffix = str(abs(hash(self._testMethodName)))[:6]
        self.user = User.objects.create_user(
            username=f"pr8_user_{suffix}",
            email=f"pr8_user_{suffix}@example.com",
            password="testpass123",
        )
        role = Role.objects.order_by("id").first()
        if role is None:
            max_id = Role.objects.aggregate(max_id=Max("id"))["max_id"] or 0
            role = Role.objects.create(id=max_id + 1000, name=f"pr8-role-{suffix[:4]}")
        Membership.objects.get_or_create(
            user=self.user,
            company=self.tenant,
            defaults={"role": role},
        )
        membership = Membership.objects.get(user=self.user, company=self.tenant)
        if membership.role is None:
            membership.role = role
            membership.save(update_fields=["role"])
        self.user.profile.workspace = self.tenant
        self.user.profile.save(update_fields=["workspace"])
        self.client.force_login(self.user)

        self.category = Category.objects.create(name=f"PR8 Gold {suffix}")
        self.product_type = ProductType.objects.create(name=f"PR8 Type {suffix}")
        self.product = Product.objects.create(
            product_type=self.product_type,
            name=f"PR8 Product {suffix}",
            description="PR-8 inventory list test product",
            category=self.category,
        )
        self.variant = ProductVariant.objects.create(
            sku=f"PR8SK{suffix}",
            product_code=f"PR8PC{suffix}",
            name=f"PR8 Variant {suffix}",
            product=self.product,
        )

        self.lot = Stock.objects.create(
            variant=self.variant,
            quantity=5,
            weight=Decimal("10.000"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6000.000"),
            is_unique=False,
            sku=f"PR8LOT{suffix}",
        )
        InventoryMovementService.record_movement(
            subject=self.lot,
            movement_type_id="P",
            quantity=5,
            weight=Decimal("10.000"),
            reason="PR8_TEST",
        )

        self.item = StockItem.objects.create(
            variant=self.variant,
            quantity=1,
            weight=Decimal("2.500"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6000.000"),
            serial_no=f"P8I{suffix[:5]}",
        )
        InventoryMovementService.record_movement(
            subject=self.item,
            movement_type_id="AD",
            quantity=1,
            weight=Decimal("2.500"),
            reason="PR8_TEST",
        )

        self.zero_item = StockItem.objects.create(
            variant=self.variant,
            quantity=1,
            weight=Decimal("1.000"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6000.000"),
            serial_no=f"P8Z{suffix[:5]}",
        )
        InventoryMovementService.record_movement(
            subject=self.zero_item,
            movement_type_id="AD",
            quantity=1,
            weight=Decimal("1.000"),
            reason="PR8_TEST",
        )
        InventoryMovementService.record_movement(
            subject=self.zero_item,
            movement_type_id="S",
            quantity=1,
            weight=Decimal("1.000"),
            reason="PR8_TEST",
        )

    def test_lots_mode_lists_only_lots(self):
        response = self.client.get(reverse("product_stock_list"), {"mode": "lots"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lot.lot_no)
        self.assertNotContains(response, self.item.serial_no)

    def test_items_mode_lists_only_items(self):
        response = self.client.get(reverse("product_stock_list"), {"mode": "items"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.serial_no)
        self.assertNotContains(response, self.lot.lot_no)

    def test_unified_mode_lists_lots_and_items(self):
        response = self.client.get(reverse("product_stock_list"), {"mode": "unified"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.lot.lot_no)
        self.assertContains(response, self.item.serial_no)

    def test_non_zero_filter_excludes_zero_balance_subjects(self):
        response = self.client.get(
            reverse("product_stock_list"),
            {"mode": "items", "non_zero_only": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.serial_no)
        self.assertNotContains(response, self.zero_item.serial_no)
