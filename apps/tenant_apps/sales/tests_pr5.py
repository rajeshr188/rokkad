from decimal import Decimal

from django.contrib.auth import get_user_model
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.inventory.services import InventoryMovementService
from apps.tenant_apps.product.models import Category, Product, ProductType, ProductVariant, Stock, StockItem
from .models import Invoice, InvoiceItem, Receipt


User = get_user_model()


class SalesInventoryIntegrationTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_sales_pr5"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="sales_test_owner",
            email="sales_test_owner@example.com",
            password="testpass123",
        )
        tenant.name = "sales-test-company"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        self.suffix = str(abs(hash(self._testMethodName)))[:6]
        suffix = self.suffix
        self.customer = Customer.objects.create(
            firstname=f"Sales {suffix}",
            lastname="Customer",
        )
        self.category = Category.objects.create(name=f"Gold Sales {suffix}")
        self.product_type = ProductType.objects.create(name=f"Chain {suffix}")
        self.product = Product.objects.create(
            product_type=self.product_type,
            name=f"Sales Test Product {suffix}",
            description="Sales test product",
            category=self.category,
        )
        self.variant = ProductVariant.objects.create(
            sku=f"SAL-TEST-SKU-{suffix}",
            product_code=f"SAL-TEST-PC-{suffix}",
            name=f"Sales Test Variant {suffix}",
            product=self.product,
        )
        self.invoice = Invoice.objects.create(
            customer=self.customer,
            gold_rate=Decimal("7000.000"),
            silver_rate=Decimal("90.000"),
        )
        self.stock = Stock.objects.create(
            variant=self.variant,
            quantity=5,
            weight=Decimal("10.000"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6500.000"),
            is_unique=False,
            sku=f"L{suffix}",
        )
        InventoryMovementService.record_movement(
            subject=self.stock,
            movement_type_id="P",
            quantity=5,
            weight=Decimal("10.000"),
            reason="TEST_SEED",
        )

    def test_invoice_item_posts_lot_without_journal_entry(self):
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            product=self.stock,
            quantity=2,
            weight=Decimal("4.000"),
            touch=Decimal("91.600"),
        )

        txn = self.stock.stocktransaction_set.order_by("id").last()

        self.assertEqual(txn.movement_type_id, "S")
        self.assertEqual(txn.stock, self.stock)
        self.assertIsNone(txn.stock_item)
        self.assertIsNone(txn.journal_entry)
        self.assertEqual(self.stock.current_balance()["qty"], 3)
        self.assertEqual(self.stock.current_balance()["wt"], Decimal("6.000"))
        self.assertEqual(item.get_inventory_subject(), self.stock)

    def test_invoice_item_with_stock_item_posts_unique_subject(self):
        stock_item = StockItem.objects.create(
            variant=self.variant,
            quantity=1,
            weight=Decimal("2.500"),
            purchase_touch=Decimal("91.600"),
            purchase_rate=Decimal("6500.000"),
            serial_no=f"I{self.suffix}",
        )
        InventoryMovementService.record_movement(
            subject=stock_item,
            movement_type_id="AD",
            quantity=1,
            weight=Decimal("2.500"),
            reason="TEST_SEED_ITEM",
        )

        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            stock_item=stock_item,
            quantity=1,
            weight=Decimal("2.500"),
            touch=Decimal("91.600"),
        )

        txn = stock_item.transactions.order_by("id").last()

        self.assertEqual(txn.movement_type_id, "S")
        self.assertIsNone(txn.stock)
        self.assertEqual(txn.stock_item, stock_item)
        self.assertIsNone(txn.journal_entry)
        self.assertEqual(stock_item.current_balance()["qty"], 0)
        self.assertEqual(stock_item.current_balance()["wt"], Decimal("0.000"))
        self.assertEqual(item.get_inventory_subject(), stock_item)

    def test_invoice_item_update_reverses_and_reposts_inventory(self):
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            product=self.stock,
            quantity=1,
            weight=Decimal("2.000"),
            touch=Decimal("91.600"),
        )

        item.quantity = 3
        item.weight = Decimal("6.000")
        item.save()

        self.stock.refresh_from_db()
        movements = list(self.stock.stocktransaction_set.order_by("id").values_list("movement_type_id", flat=True))

        self.assertEqual(movements, ["P", "S", "SR", "S"])
        self.assertEqual(self.stock.current_balance()["qty"], 2)
        self.assertEqual(self.stock.current_balance()["wt"], Decimal("4.000"))

    def test_receipt_does_not_create_journal_entry_without_posted_voucher(self):
        receipt = Receipt.objects.create(
            customer=self.customer,
            total=Decimal("500.000"),
            description="Test receipt",
        )

        self.assertIsNone(receipt.get_journal_entry())
        self.assertIsNone(receipt.create_transactions())
        self.assertIsNone(receipt.reverse_transactions())
