"""
End-to-End Integration Tests for AR/AP Settlement with Posting Engine

Validates that PaymentVoucher posting triggers automatic invoice settlement.
Tests both SalesInvoiceVoucher and PurchaseInvoiceVoucher settlement flows.
"""

from decimal import Decimal
from django.test import TransactionTestCase
from moneyed import Money, INR
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.dea.models import (
    Tenant,
    TenantUser,
    VoucherType,
    Ledger,
    Account,
    AccountType,
    SalesInvoiceVoucher,
    PurchaseInvoiceVoucher,
    PaymentVoucher,
    Company,
    AccountingPeriod,
    JournalEntry,
)
from apps.tenant_apps.dea.posting.engine import BasePostingEngine
from apps.tenant_apps.dea.posting.context import PostingContext


class SettlementIntegrationSmokeTests(TenantTestCase):
    """End-to-end tests for payment posting and automatic settlement"""

    schema_name = "test_settlement_integration"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create tenant and user for this schema
        cls.tenant = Tenant.objects.create(
            schema_name=cls.schema_name,
            name="Test Settlement Tenant",
            domain_url="settlement-test.local",
        )

    def setUp(self):
        """Set up common test data"""
        # Create tenant owner/admin user
        owner = TenantUser.objects.create_user(
            email="owner@settlement-test.local",
            password="testpass",
            is_staff=True,
            is_superuser=True,
        )
        owner.tenant = self.tenant
        owner.save()

        # Create company in tenant
        self.company = Company.objects.create(
            tenant=self.tenant,
            name="Test Company",
            creator=owner,
        )

        # Create accounting period
        self.period = AccountingPeriod.objects.create(
            name="FY 2025",
            start_date="2025-01-01",
            end_date="2025-12-31",
            is_active=True,
        )

        # Create account types
        self.asset_type = AccountType.objects.create(name="Asset")
        self.liability_type = AccountType.objects.create(name="Liability")
        self.income_type = AccountType.objects.create(name="Income")

        # Create ledgers
        self.cash_ledger = Ledger.objects.create(
            name="Cash",
            account_type=self.asset_type,
            code="1000",
            description="Cash and cash equivalents",
        )
        self.ar_ledger = Ledger.objects.create(
            name="Accounts Receivable",
            account_type=self.asset_type,
            code="1200",
            description="Customer receivables",
        )
        self.sales_ledger = Ledger.objects.create(
            name="Sales Revenue",
            account_type=self.income_type,
            code="4000",
            description="Revenue from sales",
        )
        self.ap_ledger = Ledger.objects.create(
            name="Accounts Payable",
            account_type=self.liability_type,
            code="2000",
            description="Supplier payables",
        )

        # Create account for customer
        self.customer_account = Account.objects.create(
            name="Customer Account",
            account_type=self.asset_type,
        )

        # Create account for supplier
        self.supplier_account = Account.objects.create(
            name="Supplier Account",
            account_type=self.liability_type,
        )

        # Create voucher types
        self.sales_invoice_type = VoucherType.objects.create(
            name="SALES_INVOICE", display_name="Sales Invoice"
        )
        self.payment_type = VoucherType.objects.create(
            name="PAYMENT", display_name="Payment"
        )

        # Create posting engine instance
        self.engine = BasePostingEngine()
        self.user = owner

    def test_sales_invoice_payment_settlement_flow(self):
        """
        Test full flow: Create Sales Invoice → Post → Create Payment → Post → Settlement

        Expected: Payment posting triggers SettlementService which updates
        is_fully_paid on SalesInvoiceVoucher
        """
        # Create sales invoice
        invoice = SalesInvoiceVoucher.objects.create(
            company=self.company,
            invoice_number="INV-001",
            invoice_date="2025-01-15",
            total_amount=Money(1000, INR),
            taxable_amount=Money(1000, INR),
            cgst_amount=Money(0, INR),
            sgst_amount=Money(0, INR),
            igst_amount=Money(0, INR),
        )

        # Create and post sales invoice
        from apps.tenant_apps.dea.models import Voucher, VoucherStatus

        invoice_voucher = Voucher.objects.create(
            voucher_type=self.sales_invoice_type,
            business_doc=invoice,
            status=VoucherStatus.DRAFT.value,
        )

        # Post invoice
        ctx = PostingContext(voucher=invoice_voucher, doc=invoice, user_id=self.user.id)
        je1 = self.engine.post(ctx)

        self.assertIsNotNone(je1, "Invoice posting should create JournalEntry")

        # Invoice should not be marked as paid yet
        invoice.refresh_from_db()
        self.assertFalse(invoice.is_fully_paid, "Invoice should not be paid yet")

        # Create payment voucher
        payment = PaymentVoucher.objects.create(
            company=self.company,
            total_amount=Money(1000, INR),
            principal_amount=Money(1000, INR),
            interest_amount=Money(0, INR),
            source_document=invoice,  # Link to sales invoice
        )

        # Create and post payment
        payment_voucher = Voucher.objects.create(
            voucher_type=self.payment_type,
            business_doc=payment,
            status=VoucherStatus.DRAFT.value,
        )

        ctx2 = PostingContext(
            voucher=payment_voucher, doc=payment, user_id=self.user.id
        )
        je2 = self.engine.post(ctx2)

        self.assertIsNotNone(je2, "Payment posting should create JournalEntry")

        # After payment posting, invoice should be marked as fully paid
        invoice.refresh_from_db()
        self.assertTrue(
            invoice.is_fully_paid,
            "Invoice should be marked as fully paid after payment posting",
        )
        self.assertEqual(
            invoice.received_amount,
            Money(1000, INR),
            "Invoice received_amount should be updated",
        )

    def test_partial_payment_settlement(self):
        """
        Test partial payment: Payment < Invoice amount should not mark as fully paid
        """
        from apps.tenant_apps.dea.models import Voucher, VoucherStatus

        # Create sales invoice for 1000
        invoice = SalesInvoiceVoucher.objects.create(
            company=self.company,
            invoice_number="INV-002",
            invoice_date="2025-01-15",
            total_amount=Money(1000, INR),
            taxable_amount=Money(1000, INR),
            cgst_amount=Money(0, INR),
            sgst_amount=Money(0, INR),
            igst_amount=Money(0, INR),
        )

        # Post invoice
        invoice_voucher = Voucher.objects.create(
            voucher_type=self.sales_invoice_type,
            business_doc=invoice,
            status=VoucherStatus.DRAFT.value,
        )

        ctx = PostingContext(voucher=invoice_voucher, doc=invoice, user_id=self.user.id)
        self.engine.post(ctx)

        # Create partial payment (600 of 1000)
        payment = PaymentVoucher.objects.create(
            company=self.company,
            total_amount=Money(600, INR),
            principal_amount=Money(600, INR),
            interest_amount=Money(0, INR),
            source_document=invoice,
        )

        # Post partial payment
        payment_voucher = Voucher.objects.create(
            voucher_type=self.payment_type,
            business_doc=payment,
            status=VoucherStatus.DRAFT.value,
        )

        ctx2 = PostingContext(
            voucher=payment_voucher, doc=payment, user_id=self.user.id
        )
        self.engine.post(ctx2)

        # Invoice should NOT be fully paid
        invoice.refresh_from_db()
        self.assertFalse(
            invoice.is_fully_paid,
            "Partial payment should not mark invoice as fully paid",
        )
        self.assertEqual(
            invoice.received_amount,
            Money(600, INR),
            "Invoice received_amount should be 600",
        )

        # Create second payment for remaining 400
        payment2 = PaymentVoucher.objects.create(
            company=self.company,
            total_amount=Money(400, INR),
            principal_amount=Money(400, INR),
            interest_amount=Money(0, INR),
            source_document=invoice,
        )

        # Post second payment
        payment_voucher2 = Voucher.objects.create(
            voucher_type=self.payment_type,
            business_doc=payment2,
            status=VoucherStatus.DRAFT.value,
        )

        ctx3 = PostingContext(
            voucher=payment_voucher2, doc=payment2, user_id=self.user.id
        )
        self.engine.post(ctx3)

        # After second payment, invoice should be fully paid
        invoice.refresh_from_db()
        self.assertTrue(
            invoice.is_fully_paid,
            "After both payments, invoice should be fully paid",
        )
        self.assertEqual(
            invoice.received_amount,
            Money(1000, INR),
            "Invoice received_amount should be 1000",
        )

    def test_purchase_invoice_payment_settlement(self):
        """
        Test PurchaseInvoiceVoucher settlement when payment is posted
        """
        from apps.tenant_apps.dea.models import Voucher, VoucherStatus

        # Create purchase invoice for 1100 (1000 net + 100 tax)
        invoice = PurchaseInvoiceVoucher.objects.create(
            company=self.company,
            invoice_number="PINV-001",
            invoice_date="2025-01-15",
            net_payable=Money(1000, INR),
            tax_amount=Money(100, INR),
            total_amount=Money(1100, INR),
        )

        # Post invoice
        invoice_voucher = Voucher.objects.create(
            voucher_type=self.sales_invoice_type,
            business_doc=invoice,
            status=VoucherStatus.DRAFT.value,
        )

        ctx = PostingContext(voucher=invoice_voucher, doc=invoice, user_id=self.user.id)
        self.engine.post(ctx)

        # Create payment for full amount
        payment = PaymentVoucher.objects.create(
            company=self.company,
            total_amount=Money(1100, INR),
            principal_amount=Money(1100, INR),
            interest_amount=Money(0, INR),
            source_document=invoice,
        )

        # Post payment
        payment_voucher = Voucher.objects.create(
            voucher_type=self.payment_type,
            business_doc=payment,
            status=VoucherStatus.DRAFT.value,
        )

        ctx2 = PostingContext(
            voucher=payment_voucher, doc=payment, user_id=self.user.id
        )
        self.engine.post(ctx2)

        # Purchase invoice should be marked as fully paid
        invoice.refresh_from_db()
        self.assertTrue(
            invoice.is_fully_paid,
            "Purchase invoice should be marked as fully paid after payment",
        )
        self.assertEqual(
            invoice.paid_amount,
            Money(1100, INR),
            "Purchase invoice paid_amount should be 1100",
        )

    def test_payment_without_source_invoice_no_settlement(self):
        """
        Test that payment without source_document doesn't cause settlement errors
        """
        from apps.tenant_apps.dea.models import Voucher, VoucherStatus

        # Create payment with no source_document
        payment = PaymentVoucher.objects.create(
            company=self.company,
            total_amount=Money(500, INR),
            principal_amount=Money(500, INR),
            interest_amount=Money(0, INR),
            source_document=None,  # No source
        )

        # Post payment - should not raise error
        payment_voucher = Voucher.objects.create(
            voucher_type=self.payment_type,
            business_doc=payment,
            status=VoucherStatus.DRAFT.value,
        )

        try:
            ctx = PostingContext(
                voucher=payment_voucher, doc=payment, user_id=self.user.id
            )
            je = self.engine.post(ctx)
            self.assertIsNotNone(je, "Payment should post successfully without settlement")
        except Exception as e:
            self.fail(
                f"Payment posting should not fail for payment without source_document: {e}"
            )

    def test_settlement_multiple_journal_entries(self):
        """
        Test that multiple payments correctly accumulate on invoice settlement
        """
        from apps.tenant_apps.dea.models import Voucher, VoucherStatus

        # Create invoice
        invoice = SalesInvoiceVoucher.objects.create(
            company=self.company,
            invoice_number="INV-003",
            invoice_date="2025-01-15",
            total_amount=Money(2000, INR),
            taxable_amount=Money(2000, INR),
            cgst_amount=Money(0, INR),
            sgst_amount=Money(0, INR),
            igst_amount=Money(0, INR),
        )

        # Post invoice
        invoice_voucher = Voucher.objects.create(
            voucher_type=self.sales_invoice_type,
            business_doc=invoice,
            status=VoucherStatus.DRAFT.value,
        )

        ctx = PostingContext(voucher=invoice_voucher, doc=invoice, user_id=self.user.id)
        self.engine.post(ctx)

        # Create three payments: 700, 800, 500
        payment_amounts = [Money(700, INR), Money(800, INR), Money(500, INR)]

        for i, amount in enumerate(payment_amounts):
            payment = PaymentVoucher.objects.create(
                company=self.company,
                total_amount=amount,
                principal_amount=amount,
                interest_amount=Money(0, INR),
                source_document=invoice,
            )

            payment_voucher = Voucher.objects.create(
                voucher_type=self.payment_type,
                business_doc=payment,
                status=VoucherStatus.DRAFT.value,
            )

            ctx2 = PostingContext(
                voucher=payment_voucher, doc=payment, user_id=self.user.id
            )
            self.engine.post(ctx2)

            invoice.refresh_from_db()
            expected_amount = sum([a.amount for a in payment_amounts[: i + 1]])
            self.assertEqual(
                invoice.received_amount.amount,
                expected_amount,
                f"After payment {i+1}, received_amount should be {expected_amount}",
            )

        # After all payments, invoice should be fully paid
        invoice.refresh_from_db()
        self.assertTrue(
            invoice.is_fully_paid,
            "Invoice should be fully paid after all payments",
        )
