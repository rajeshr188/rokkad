from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from .inventory.services import InventoryMovementService
from .models import Category, Product, ProductType, ProductVariant, Stock, StockItem
from .tests_utils import ensure_inventory_movements


User = get_user_model()


class InventoryBalanceViewTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_product_pr6"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="product_pr6_owner",
            email="product_pr6_owner@example.com",
            password="testpass123",
        )
        tenant.name = "product-pr6-company"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        connection.set_tenant(self.tenant)
        ensure_inventory_movements()
        suffix = str(abs(hash(self._testMethodName)))[:6]
        self.category = Category.objects.create(name=f"PR6 Gold {suffix}")
        self.product_type = ProductType.objects.create(name=f"PR6 Type {suffix}")
        self.product = Product.objects.create(
            product_type=self.product_type,
            name=f"PR6 Product {suffix}",
            description="PR-6 balance test product",
            category=self.category,
        )
        self.variant = ProductVariant.objects.create(
            sku=f"PR6SK{suffix}",
            product_code=f"PR6PC{suffix}",
            name=f"PR6 Variant {suffix}",
            product=self.product,
        )

    def _fetch_balance_row(self, subject_type, subject_id):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT balance_qty, balance_wt, in_qty, out_qty, in_wt, out_wt
                FROM inventory_balance
                WHERE subject_type = %s AND subject_id = %s
                """,
                [subject_type, subject_id],
            )
            return cursor.fetchone()

    def test_inventory_balance_view_matches_stock_balance(self):
        stock = Stock.objects.create(
            variant=self.variant,
            quantity=5,
            weight=Decimal("10.000"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6000.000"),
            is_unique=False,
            sku="PR6LOT",
        )
        InventoryMovementService.record_movement(
            subject=stock,
            movement_type_id="P",
            quantity=5,
            weight=Decimal("10.000"),
            reason="PR6_TEST",
        )
        InventoryMovementService.record_movement(
            subject=stock,
            movement_type_id="S",
            quantity=2,
            weight=Decimal("4.000"),
            reason="PR6_TEST",
        )

        row = self._fetch_balance_row("LOT", stock.pk)

        self.assertIsNotNone(row)
        self.assertEqual(row[0], 3)
        self.assertEqual(row[1], Decimal("6.000"))
        self.assertEqual(stock.current_balance(), {"qty": 3, "wt": Decimal("6.000")})
        self.assertEqual(stock.get_quantity(), 3)
        self.assertEqual(stock.get_weight(), Decimal("6.000"))

    def test_inventory_balance_view_matches_stock_item_balance(self):
        item = StockItem.objects.create(
            variant=self.variant,
            quantity=1,
            weight=Decimal("2.500"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6000.000"),
            serial_no="PR6ITM1",
        )
        InventoryMovementService.record_movement(
            subject=item,
            movement_type_id="AD",
            quantity=1,
            weight=Decimal("2.500"),
            reason="PR6_TEST",
        )
        InventoryMovementService.record_movement(
            subject=item,
            movement_type_id="S",
            quantity=1,
            weight=Decimal("2.500"),
            reason="PR6_TEST",
        )

        row = self._fetch_balance_row("ITEM", item.pk)

        self.assertIsNotNone(row)
        self.assertEqual(row[0], 0)
        self.assertEqual(row[1], Decimal("0.000"))
        self.assertEqual(item.current_balance(), {"qty": 0, "wt": Decimal("0.000")})
