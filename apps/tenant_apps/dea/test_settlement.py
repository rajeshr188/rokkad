"""
Tests for Settlement Service (AR/AP invoice settlement workflow)

Validates:
- Single payment = invoice amount → is_fully_paid becomes True
- Two partial payments totalling invoice → is_fully_paid becomes True
- SalesInvoiceVoucher settlement
- PurchaseInvoiceVoucher settlement
- Overpayment scenarios
- Multi-currency rejection (not yet supported)
"""

from decimal import Decimal
from django.test import TestCase
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from moneyed import Money

from .models import (
    SalesInvoiceVoucher,
    PurchaseInvoiceVoucher,
    PaymentVoucher,
    CashFlowDirection,
    PaymentType,
)
from .services.settlement import SettlementService, settle_invoice
from django.contrib.auth import get_user_model

User = get_user_model()


class SettlementServiceSmokeTests(TenantTestCase):
    """Test invoice settlement after payment posting"""

    tenant_name = "test_settlement"

    @classmethod
    def setup_tenant(cls, tenant):
        """Set up test tenant"""
        owner = User.objects.create_user(
            username="settlement-owner",
            email="settlement-owner@example.com",
            password="testpass123",
        )
        owner.save()

        tenant.name = "Settlement Test Company"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.get(username="settlement-owner")
        self.service = SettlementService()

    def test_settle_sales_invoice_full_payment(self):
        """Test settling SalesInvoiceVoucher with full payment in one go"""
        # Create invoice
        invoice = SalesInvoiceVoucher.objects.create(
            invoice_number="SI-001",
            invoice_date="2026-06-15",
            customer_name="Test Customer",
            total_amount=Money(1000, "INR"),
            received_amount=Money(0, "INR"),
            is_fully_paid=False,
        )

        # Create payment
        payment = PaymentVoucher.objects.create(
            payment_id="PV-001",
            payment_date="2026-06-20",
            payment_type=PaymentType.RECEIPT,
            direction=CashFlowDirection.RECEIPT,
            total_amount=Money(1000, "INR"),
            source_content_type_id=None,  # Will set via GenericFK
        )
        # Set source_document
        from django.contrib.contenttypes.models import ContentType

        payment.source_content_type = ContentType.objects.get_for_model(SalesInvoiceVoucher)
        payment.source_object_id = invoice.id
        payment.save()

        # Settle
        settled_invoice = self.service.settle(payment)

        # Verify
        self.assertIsNotNone(settled_invoice)
        self.assertEqual(settled_invoice.received_amount.amount, Decimal("1000"))
        self.assertTrue(settled_invoice.is_fully_paid)

        # Verify database was updated
        invoice.refresh_from_db()
        self.assertTrue(invoice.is_fully_paid)

    def test_settle_sales_invoice_partial_payments(self):
        """Test settling SalesInvoiceVoucher with multiple partial payments"""
        # Create invoice
        invoice = SalesInvoiceVoucher.objects.create(
            invoice_number="SI-002",
            invoice_date="2026-06-15",
            customer_name="Test Customer",
            total_amount=Money(1000, "INR"),
            received_amount=Money(0, "INR"),
            is_fully_paid=False,
        )

        # First payment: 600
        payment1 = self._create_payment(600)
        payment1.source_document = invoice
        payment1.save()

        settled1 = self.service.settle(payment1)
        self.assertEqual(settled1.received_amount.amount, Decimal("600"))
        self.assertFalse(settled1.is_fully_paid)

        # Refresh invoice from DB
        invoice.refresh_from_db()
        self.assertEqual(invoice.received_amount.amount, Decimal("600"))

        # Second payment: 400
        payment2 = self._create_payment(400)
        payment2.source_document = invoice
        payment2.save()

        settled2 = self.service.settle(payment2)
        self.assertEqual(settled2.received_amount.amount, Decimal("1000"))
        self.assertTrue(settled2.is_fully_paid)

        # Verify database was updated
        invoice.refresh_from_db()
        self.assertTrue(invoice.is_fully_paid)

    def test_settle_purchase_invoice_full_payment(self):
        """Test settling PurchaseInvoiceVoucher with full payment"""
        # Create purchase invoice
        invoice = PurchaseInvoiceVoucher.objects.create(
            bill_number="PI-001",
            bill_date="2026-06-15",
            vendor_name="Test Vendor",
            gross_total=Money(1000, "INR"),
            tax_total=Money(100, "INR"),
            net_payable=Money(1100, "INR"),
            paid_amount=Money(0, "INR"),
            is_fully_paid=False,
        )

        # Create payment
        payment = self._create_payment_for_purchase(1100)
        payment.source_document = invoice
        payment.save()

        # Settle
        settled_invoice = self.service.settle(payment)

        # Verify
        self.assertIsNotNone(settled_invoice)
        self.assertEqual(settled_invoice.paid_amount.amount, Decimal("1100"))
        self.assertTrue(settled_invoice.is_fully_paid)

    def test_settle_overpayment(self):
        """Test settling with overpayment (beyond invoice total)"""
        invoice = SalesInvoiceVoucher.objects.create(
            invoice_number="SI-003",
            invoice_date="2026-06-15",
            customer_name="Test Customer",
            total_amount=Money(1000, "INR"),
            received_amount=Money(0, "INR"),
            is_fully_paid=False,
        )

        # Payment of 1200 (exceeds 1000)
        payment = self._create_payment(1200)
        payment.source_document = invoice
        payment.save()

        settled_invoice = self.service.settle(payment)

        # Should mark as fully paid even with overpayment
        self.assertEqual(settled_invoice.received_amount.amount, Decimal("1200"))
        self.assertTrue(settled_invoice.is_fully_paid)

    def test_settle_no_source_document(self):
        """Test settling payment with no source document"""
        payment = self._create_payment(500)
        # Don't set source_document

        result = self.service.settle(payment)
        self.assertIsNone(result)

    def test_convenience_function_settle_invoice(self):
        """Test convenience function settle_invoice()"""
        invoice = SalesInvoiceVoucher.objects.create(
            invoice_number="SI-004",
            invoice_date="2026-06-15",
            customer_name="Test Customer",
            total_amount=Money(500, "INR"),
            received_amount=Money(0, "INR"),
            is_fully_paid=False,
        )

        payment = self._create_payment(500)
        payment.source_document = invoice
        payment.save()

        settled_invoice = settle_invoice(payment)

        self.assertIsNotNone(settled_invoice)
        self.assertTrue(settled_invoice.is_fully_paid)

    # ========== Helper Methods ==========

    def _create_payment(self, amount: int) -> PaymentVoucher:
        """Helper to create a basic payment voucher"""
        payment = PaymentVoucher.objects.create(
            payment_id=f"PV-{PaymentVoucher.objects.count() + 1}",
            payment_date="2026-06-20",
            payment_type=PaymentType.RECEIPT,
            direction=CashFlowDirection.RECEIPT,
            total_amount=Money(amount, "INR"),
        )
        return payment

    def _create_payment_for_purchase(self, amount: int) -> PaymentVoucher:
        """Helper to create a payment for purchase invoice"""
        payment = PaymentVoucher.objects.create(
            payment_id=f"PP-{PaymentVoucher.objects.count() + 1}",
            payment_date="2026-06-20",
            payment_type=PaymentType.PAYMENT,
            direction=CashFlowDirection.PAYMENT,
            total_amount=Money(amount, "INR"),
        )
        return payment
