from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django_tenants.test.cases import TenantTestCase
from django.urls import reverse

from . import views
from .forms import ProductForm, ProductVariantForm
from .inventory.services import InventoryMovementService
from .models import (
	AssignedProductAttribute,
	AssignedVariantAttribute,
	Attribute,
	AttributeValue,
	Category,
	Product,
	ProductType,
	ProductVariant,
	Stock,
	StockItem,
	StockTransaction,
	StockStatement,
	Movement,
)


User = get_user_model()


class InventoryServiceLayerTests(TenantTestCase):
	"""Test the inventory service layer (PR-3)."""
	
	@classmethod
	def setup_tenant(cls, tenant):
		user = User.objects.create_user(
			username="inventory_test_owner",
			email="inventory_test_owner@example.com",
			password="testpass123",
		)
		tenant.name = "inventory-test-company"
		tenant.owner = user
		tenant.creator = user

	def setUp(self):
		self.variant = ProductVariant.objects.create(
			sku="TEST-SKU",
			product_code="TEST-PC",
			name="Test Variant",
		)
		self.stock = Stock.objects.create(
			variant=self.variant,
			quantity=100,
			weight=Decimal('100.000'),
			purchase_touch=Decimal('750.000'),
			purchase_rate=Decimal('50.000'),
			is_unique=False,
			sku="LOT-001",
		)
		
	def test_record_movement_stock(self):
		"""Test recording movement for a Stock (lot)."""
		txn = InventoryMovementService.record_movement(
			subject=self.stock,
			movement_type_id='P',
			quantity=50,
			weight=Decimal('50.000'),
			reason='TEST_PURCHASE',
		)
		
		self.assertIsInstance(txn, StockTransaction)
		self.assertEqual(txn.stock, self.stock)
		self.assertIsNone(txn.stock_item)
		self.assertEqual(txn.quantity, 50)
		self.assertEqual(txn.weight, Decimal('50.000'))
		self.assertEqual(txn.movement_type_id, 'P')
		
	def test_record_movement_stock_item(self):
		"""Test recording movement for a StockItem (unique unit)."""
		item = StockItem.objects.create(
			variant=self.variant,
			weight=Decimal('10.000'),
			quantity=1,
			purchase_touch=Decimal('750.000'),
			purchase_rate=Decimal('50.000'),
			serial_no='ITEM-001',
		)
		
		txn = InventoryMovementService.record_movement(
			subject=item,
			movement_type_id='AD',
			quantity=1,
			weight=Decimal('10.000'),
			reason='TEST_ADD',
		)
		
		self.assertIsInstance(txn, StockTransaction)
		self.assertIsNone(txn.stock)
		self.assertEqual(txn.stock_item, item)
		
	def test_record_movement_invalid_movement_type(self):
		"""Test that invalid movement type raises exception."""
		with self.assertRaises(Movement.DoesNotExist):
			InventoryMovementService.record_movement(
				subject=self.stock,
				movement_type_id='INVALID',
				quantity=10,
				weight=Decimal('10.000'),
			)
			
	def test_create_checkpoint(self):
		"""Test creating a checkpoint (statement)."""
		# Record some movements first
		InventoryMovementService.record_movement(
			subject=self.stock,
			movement_type_id='P',
			quantity=50,
			weight=Decimal('50.000'),
		)
		InventoryMovementService.record_movement(
			subject=self.stock,
			movement_type_id='S',
			quantity=10,
			weight=Decimal('10.000'),
		)
		
		# Create checkpoint
		stmt = InventoryMovementService.create_checkpoint(self.stock, method='Auto')
		
		self.assertIsInstance(stmt, StockStatement)
		self.assertEqual(stmt.stock, self.stock)
		self.assertIsNone(stmt.stock_item)
		self.assertEqual(stmt.Closing_qty, self.stock.quantity + 50 - 10)
		self.assertEqual(stmt.total_qty_in, 50)
		self.assertEqual(stmt.total_qty_out, 10)
		
	def test_split_lot(self):
		"""Test splitting a lot into two child lots."""
		balance = self.stock.current_balance()
		
		splits = InventoryMovementService.split_lot(
			parent_stock=self.stock,
			splits=[
				{
					'quantity': balance['qty'] // 2,
					'weight': balance['wt'] / Decimal(2),
					'is_unique': False,
				},
				{
					'quantity': balance['qty'] // 2,
					'weight': balance['wt'] / Decimal(2),
					'is_unique': False,
				},
			],
			reason='TEST_SPLIT',
		)
		
		self.assertEqual(len(splits), 2)
		self.assertTrue(all(isinstance(s, Stock) for s in splits))
		
		# Verify transactions recorded
		txns = StockTransaction.objects.filter(
			stock__in=splits
		).filter(movement_type_id='AD')
		self.assertEqual(txns.count(), 2)
		
	def test_merge_lots(self):
		"""Test merging multiple lots."""
		# Create two additional lots
		stock2 = Stock.objects.create(
			variant=self.variant,
			quantity=50,
			weight=Decimal('50.000'),
			purchase_touch=Decimal('750.000'),
			purchase_rate=Decimal('50.000'),
			is_unique=False,
			sku="LOT-002",
		)
		
		merged = InventoryMovementService.merge_lots(
			lots=[self.stock, stock2],
			reason='TEST_MERGE',
		)
		
		self.assertIsInstance(merged, Stock)
		self.assertNotEqual(merged.pk, self.stock.pk)
		self.assertNotEqual(merged.pk, stock2.pk)
		
		# Verify parent relationships tracked
		self.assertEqual(self.stock.parent_stock, None)  # Original lots unchanged
		# Verify transactions recorded
		txns = StockTransaction.objects.filter(
			stock=merged,
			movement_type_id='AD'
		)
		self.assertTrue(txns.exists())
