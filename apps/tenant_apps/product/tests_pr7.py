from decimal import Decimal

from django.contrib.auth import get_user_model
from django_tenants.test.cases import TenantTestCase

from .inventory.services import InventoryMovementService
from .models import Category, Product, ProductType, ProductVariant, Stock, StockItem, StockStatement, StockTransaction


User = get_user_model()


class PhysicalAuditReconciliationTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_product_pr7"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="product_pr7_owner",
            email="product_pr7_owner@example.com",
            password="testpass123",
        )
        tenant.name = "product-pr7-company"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        suffix = str(abs(hash(self._testMethodName)))[:6]
        self.category = Category.objects.create(name=f"PR7 Gold {suffix}")
        self.product_type = ProductType.objects.create(name=f"PR7 Type {suffix}")
        self.product = Product.objects.create(
            product_type=self.product_type,
            name=f"PR7 Product {suffix}",
            description="PR-7 physical audit test product",
            category=self.category,
        )
        self.variant = ProductVariant.objects.create(
            sku=f"PR7SK{suffix}",
            product_code=f"PR7PC{suffix}",
            name=f"PR7 Variant {suffix}",
            product=self.product,
        )

    def test_record_physical_count_stores_system_and_variance_for_lot(self):
        stock = Stock.objects.create(
            variant=self.variant,
            quantity=5,
            weight=Decimal("10.000"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6000.000"),
            is_unique=False,
            sku="PR7LOT",
        )
        InventoryMovementService.record_movement(
            subject=stock,
            movement_type_id="P",
            quantity=5,
            weight=Decimal("10.000"),
            reason="PR7_TEST",
        )
        InventoryMovementService.record_movement(
            subject=stock,
            movement_type_id="S",
            quantity=1,
            weight=Decimal("2.000"),
            reason="PR7_TEST",
        )

        statement = InventoryMovementService.record_physical_count(
            subject=stock,
            physical_qty=3,
            physical_wt=Decimal("7.000"),
        )

        self.assertEqual(statement.method, "Physical")
        self.assertEqual(statement.status, StockStatement.StatusChoices.DISCREPANCY)
        self.assertEqual(statement.system_qty, 4)
        self.assertEqual(statement.system_wt, Decimal("8.000"))
        self.assertEqual(statement.physical_qty, 3)
        self.assertEqual(statement.physical_wt, Decimal("7.000"))
        self.assertEqual(statement.variance_qty, -1)
        self.assertEqual(statement.variance_wt, Decimal("-1.000"))
        self.assertEqual(stock.current_balance(), {"qty": 4, "wt": Decimal("8.000")})

    def test_reconcile_physical_count_posts_remove_adjustment_for_lot(self):
        stock = Stock.objects.create(
            variant=self.variant,
            quantity=5,
            weight=Decimal("10.000"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6000.000"),
            is_unique=False,
            sku="PR7LOT2",
        )
        InventoryMovementService.record_movement(
            subject=stock,
            movement_type_id="P",
            quantity=5,
            weight=Decimal("10.000"),
            reason="PR7_TEST",
        )

        statement = InventoryMovementService.record_physical_count(
            subject=stock,
            physical_qty=4,
            physical_wt=Decimal("8.500"),
        )
        adjustments = InventoryMovementService.reconcile_statement(statement)

        self.assertEqual(len(adjustments), 1)
        self.assertEqual(adjustments[0].movement_type_id, "R")
        self.assertEqual(adjustments[0].quantity, 1)
        self.assertEqual(adjustments[0].weight, Decimal("1.500"))
        statement.refresh_from_db()
        self.assertEqual(statement.status, StockStatement.StatusChoices.RECONCILED)
        self.assertIsNotNone(statement.reconciled_at)
        self.assertEqual(stock.current_balance(), {"qty": 4, "wt": Decimal("8.500")})

    def test_reconcile_physical_count_posts_add_adjustment_for_stock_item(self):
        item = StockItem.objects.create(
            variant=self.variant,
            quantity=1,
            weight=Decimal("2.500"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6000.000"),
            serial_no="PR7ITM1",
        )
        InventoryMovementService.record_movement(
            subject=item,
            movement_type_id="AD",
            quantity=1,
            weight=Decimal("2.500"),
            reason="PR7_TEST",
        )

        statement, adjustments = InventoryMovementService.perform_physical_audit(
            subject=item,
            physical_qty=1,
            physical_wt=Decimal("3.000"),
            reconcile=True,
        )

        self.assertEqual(statement.status, StockStatement.StatusChoices.RECONCILED)
        self.assertEqual(len(adjustments), 1)
        self.assertEqual(adjustments[0].movement_type_id, "AD")
        self.assertEqual(adjustments[0].quantity, 0)
        self.assertEqual(adjustments[0].weight, Decimal("0.500"))
        self.assertEqual(item.current_balance(), {"qty": 1, "wt": Decimal("3.000")})
        self.assertTrue(
            StockTransaction.objects.filter(
                stock_item=item,
                movement_type_id="AD",
                description__icontains="Physical reconciliation",
            ).exists()
        )