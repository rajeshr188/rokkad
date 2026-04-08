from decimal import Decimal

from django.contrib.auth import get_user_model
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import Category, Product, ProductType, ProductVariant, Stock, StockItem
from .models import Payment, Purchase, PurchaseItem


User = get_user_model()


class PurchaseInventoryIntegrationTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_purchase_pr4"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="purchase_test_owner",
            email="purchase_test_owner@example.com",
            password="testpass123",
        )
        tenant.name = "purchase-test-company"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        suffix = self._testMethodName
        self.supplier = Customer.objects.create(
            firstname=f"Test {suffix}",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
        )
        self.category = Category.objects.create(name=f"Gold {suffix}")
        self.product_type = ProductType.objects.create(name=f"Ring {suffix}")
        self.product = Product.objects.create(
            product_type=self.product_type,
            name=f"Test Ring {suffix}",
            description="Purchase test product",
            category=self.category,
        )
        self.variant = ProductVariant.objects.create(
            sku=f"PUR-TEST-SKU-{suffix}",
            product_code=f"PUR-TEST-PC-{suffix}",
            name=f"Purchase Test Variant {suffix}",
            product=self.product,
        )
        self.purchase = Purchase.objects.create(
            supplier=self.supplier,
            gold_rate=Decimal("6500.000"),
            silver_rate=Decimal("80.000"),
        )

    def test_purchase_item_posts_lot_without_journal_entry(self):
        item = PurchaseItem.objects.create(
            invoice=self.purchase,
            product=self.variant,
            quantity=2,
            weight=Decimal("10.500"),
            touch=Decimal("91.600"),
        )

        stock = item.stock_item
        txn = stock.stocktransaction_set.get(movement_type_id="P")

        self.assertIsInstance(stock, Stock)
        self.assertEqual(stock.quantity, 2)
        self.assertEqual(txn.stock, stock)
        self.assertIsNone(txn.stock_item)
        self.assertIsNone(txn.journal_entry)

    def test_purchase_item_with_huid_posts_stock_item(self):
        item = PurchaseItem.objects.create(
            invoice=self.purchase,
            product=self.variant,
            quantity=1,
            weight=Decimal("5.250"),
            touch=Decimal("91.600"),
            huid="HUID001",
        )

        stock_item = item.stock_items.get()
        txn = stock_item.transactions.get(movement_type_id="P")

        self.assertIsInstance(stock_item, StockItem)
        self.assertEqual(stock_item.quantity, 1)
        self.assertEqual(stock_item.huid, "HUID001")
        self.assertIsNone(txn.stock)
        self.assertEqual(txn.stock_item, stock_item)
        self.assertIsNone(txn.journal_entry)

    def test_purchase_item_update_reverses_and_reposts_inventory(self):
        item = PurchaseItem.objects.create(
            invoice=self.purchase,
            product=self.variant,
            quantity=1,
            weight=Decimal("4.000"),
            touch=Decimal("91.600"),
        )

        stock = item.stock_item
        item.weight = Decimal("6.000")
        item.quantity = 3
        item.save()

        stock.refresh_from_db()
        movements = list(stock.stocktransaction_set.order_by("id").values_list("movement_type_id", flat=True))

        self.assertEqual(stock.weight, Decimal("6.000"))
        self.assertEqual(stock.quantity, 3)
        self.assertEqual(movements, ["P", "PR", "P"])
        self.assertEqual(stock.current_balance()["qty"], 3)
        self.assertEqual(stock.current_balance()["wt"], Decimal("6.000"))

    def test_payment_does_not_create_journal_entry_without_posted_voucher(self):
        payment = Payment.objects.create(
            supplier=self.supplier,
            total=Decimal("1000.000"),
            description="Test payment",
        )

        self.assertIsNone(payment.get_journal_entry())
        self.assertIsNone(payment.create_transactions())
        self.assertIsNone(payment.reverse_transactions())
