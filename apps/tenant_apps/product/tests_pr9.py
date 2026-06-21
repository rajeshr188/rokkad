from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django_tenants.test.cases import TenantTestCase
from django_tenants.utils import schema_context

from .inventory.services import InventoryMovementService
from .models import Category, Product, ProductType, ProductVariant, Stock, StockItem
from .tests_utils import ensure_inventory_movements


class InventoryCleanupAndHardeningTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_product_pr9"

    @classmethod
    def setup_tenant(cls, tenant):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="product_pr9_owner",
            email="product_pr9_owner@example.com",
            password="testpass123",
        )
        tenant.name = "product-pr9-company"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        suffix = str(abs(hash(self._testMethodName)))[:6]
        self._schema_name = self.tenant.schema_name
        with schema_context(self._schema_name):
            ensure_inventory_movements()
            self.category = Category.objects.create(name=f"PR9 Gold {suffix}")
            self.product_type = ProductType.objects.create(name=f"PR9 Type {suffix}")
            self.product = Product.objects.create(
                product_type=self.product_type,
                name=f"PR9 Product {suffix}",
                description="PR-9 hardening test product",
                category=self.category,
            )
            self.variant = ProductVariant.objects.create(
                sku=f"PR9SK{suffix}",
                product_code=f"PR9PC{suffix}",
                name=f"PR9 Variant {suffix}",
                product=self.product,
            )
            self.stock = Stock.objects.create(
                variant=self.variant,
                quantity=10,
                weight=Decimal("10.000"),
                purchase_touch=Decimal("91.600"),
                purchase_rate=Decimal("6000.000"),
                is_unique=True,
                sku=f"PR9LOT{suffix}",
            )
            InventoryMovementService.record_movement(
                subject=self.stock,
                movement_type_id="P",
                quantity=10,
                weight=Decimal("10.000"),
                reason="PR9_BASELINE",
            )

    def test_record_movement_locks_stock_row_for_hardening(self):
        with schema_context(self._schema_name):
            with patch(
                "apps.tenant_apps.product.inventory.services.movements.Stock.objects.select_for_update"
            ) as lock_mock:
                lock_filter = lock_mock.return_value.filter
                lock_filter.return_value.exists.return_value = True

                InventoryMovementService.record_movement(
                    subject=self.stock,
                    movement_type_id="P",
                    quantity=1,
                    weight=Decimal("1.000"),
                    reason="PR9_LOCK_TEST",
                )

                self.assertTrue(lock_mock.called)
                lock_filter.assert_called_with(pk=self.stock.pk)

    def test_record_movement_locks_stock_item_row_for_hardening(self):
        with schema_context(self._schema_name):
            item = StockItem.objects.create(
                variant=self.variant,
                quantity=1,
                weight=Decimal("2.000"),
                purchase_touch=Decimal("91.600"),
                purchase_rate=Decimal("6000.000"),
                serial_no="P9IT001",
            )

            with patch(
                "apps.tenant_apps.product.inventory.services.movements.StockItem.objects.select_for_update"
            ) as lock_mock:
                lock_filter = lock_mock.return_value.filter
                lock_filter.return_value.exists.return_value = True

                InventoryMovementService.record_movement(
                    subject=item,
                    movement_type_id="AD",
                    quantity=1,
                    weight=Decimal("2.000"),
                    reason="PR9_LOCK_TEST",
                )

                self.assertTrue(lock_mock.called)
                lock_filter.assert_called_with(pk=item.pk)

    def test_stock_split_no_longer_branches_on_is_unique_flag(self):
        with schema_context(self._schema_name):
            split = self.stock.split(wt=Decimal("10.000"), qty=10, is_unique=False)
            self.assertIsNotNone(split)
            self.assertEqual(split.current_balance()["qty"], 10)
            self.assertEqual(split.current_balance()["wt"], Decimal("10.000"))

    def test_data_quality_command_runs(self):
        with schema_context(self._schema_name):
            call_command("check_inventory_data_quality", sample_size=5)
