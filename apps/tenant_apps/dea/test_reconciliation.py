"""
Bank Reconciliation Tests

Comprehensive smoke tests for bank reconciliation functionality:
- CSV import
- Auto-matching by date and amount
- Manual matching/unmatching
- Reconciliation summary statistics
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from moneyed import Money, INR

from apps.tenant_apps.dea.models import (
    AccountingPeriod,
    AccountType,
    BankAccount,
    BankStatementLine,
    ReconciliationMatch,
    Ledger,
    LedgerTransaction,
    JournalEntry,
    Voucher,
    VoucherType,
)
from apps.tenant_apps.dea.services.reconciliation import ReconciliationService

User = get_user_model()


class ReconciliationServiceSmokeTests(TenantTestCase):
    """Smoke tests for bank reconciliation service"""

    @staticmethod
    def get_test_schema_name():
        return "test_dea_reconciliation"

    @classmethod
    def setup_tenant(cls, tenant):
        """Set up tenant for tests"""
        user = User.objects.create_user(
            username="dea-recon-owner",
            email="dea-recon-owner@example.com",
            password="testpass123",
        )
        tenant.name = "dea-recon-tenant"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        """Set up test data"""
        super().setUp()
        connection.set_tenant(self.tenant)

        # Create test user
        self.user = User.objects.create_user(
            username="dea-recon-user",
            email="dea-recon-user@example.com",
            password="testpass123",
        )

        # Create accounting period
        self.period = AccountingPeriod.objects.create(
            name="Apr 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            is_active=True,
        )

        # Create asset account type
        self.asset_type = AccountType.objects.create(name="Asset")

        # Create bank ledger
        self.bank_ledger = Ledger.objects.create(
            name="Bank Cash",
            account_type=self.asset_type,
            code="1000",
        )

        # Create bank account
        self.bank_account = BankAccount.objects.create(
            name="Current Account",
            bank_name="Test Bank",
            account_number="987654321",
            ledger=self.bank_ledger,
            currency="INR",
        )

        # Create voucher type
        self.voucher_type = VoucherType.objects.create(
            name="PAYMENT", display_name="Payment"
        )

    def test_bank_statement_line_creation_smoke(self):
        """Test creating bank statement lines"""
        line = BankStatementLine.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 4, 5),
            description="Test Deposit",
            amount=Decimal("5000.00"),
            running_balance=Decimal("15000.00"),
        )

        self.assertEqual(line.bank_account, self.bank_account)
        self.assertEqual(line.amount, Decimal("5000.00"))
        self.assertFalse(line.is_reconciled)

    def test_auto_match_smoke(self):
        """Test auto-matching bank lines to GL transactions"""
        # Create bank statement lines
        bank_line1 = BankStatementLine.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 4, 5),
            description="Payment received",
            amount=Decimal("5000.00"),
        )
        bank_line2 = BankStatementLine.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 4, 10),
            description="Cheque issued",
            amount=Decimal("2500.00"),
        )

        # Create corresponding GL transactions
        voucher1 = Voucher.objects.create(voucher_type=self.voucher_type)
        je1 = JournalEntry.objects.create(voucher=voucher1, posted_by=self.user)
        je1.created = timezone.make_aware(timezone.datetime(2026, 4, 5, 10, 0, 0))
        je1.save()

        gl_line1 = LedgerTransaction.objects.create(
            journal_entry=je1,
            ledgerno_dr=self.bank_ledger,
            ledgerno=None,
            amount=Money("5000.00", INR),
        )

        voucher2 = Voucher.objects.create(voucher_type=self.voucher_type)
        je2 = JournalEntry.objects.create(voucher=voucher2, posted_by=self.user)
        je2.created = timezone.make_aware(timezone.datetime(2026, 4, 10, 10, 0, 0))
        je2.save()

        gl_line2 = LedgerTransaction.objects.create(
            journal_entry=je2,
            ledgerno_dr=self.bank_ledger,
            ledgerno=None,
            amount=Money("2500.00", INR),
        )

        # Auto-match
        matches = ReconciliationService.auto_match(
            bank_account=self.bank_account,
            period=self.period,
            matched_by=self.user,
        )

        self.assertEqual(len(matches), 2, "Should match 2 bank lines")
        
        bank_line1.refresh_from_db()
        bank_line2.refresh_from_db()
        self.assertTrue(bank_line1.is_reconciled)
        self.assertTrue(bank_line2.is_reconciled)

    def test_auto_match_with_tolerance_smoke(self):
        """Test auto-matching with amount tolerance"""
        bank_line = BankStatementLine.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 4, 5),
            description="Payment with rounding",
            amount=Decimal("5000.50"),
        )

        voucher = Voucher.objects.create(voucher_type=self.voucher_type)
        je = JournalEntry.objects.create(voucher=voucher, posted_by=self.user)
        je.created = timezone.make_aware(timezone.datetime(2026, 4, 5, 10, 0, 0))
        je.save()

        gl_line = LedgerTransaction.objects.create(
            journal_entry=je,
            ledgerno_dr=self.bank_ledger,
            ledgerno=None,
            amount=Money("5000.00", INR),
        )

        # No tolerance match should fail
        matches = ReconciliationService.auto_match(
            bank_account=self.bank_account,
            period=self.period,
            tolerance=Decimal("0.00"),
        )
        self.assertEqual(len(matches), 0)

        # Reset
        bank_line.is_reconciled = False
        bank_line.save()

        # With tolerance should succeed
        matches = ReconciliationService.auto_match(
            bank_account=self.bank_account,
            period=self.period,
            tolerance=Decimal("1.00"),
        )
        self.assertEqual(len(matches), 1)

    def test_manual_match_smoke(self):
        """Test manual matching of bank line to GL transaction"""
        bank_line = BankStatementLine.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 4, 8),
            description="Manual match test",
            amount=Decimal("3000.00"),
        )

        voucher = Voucher.objects.create(voucher_type=self.voucher_type)
        je = JournalEntry.objects.create(voucher=voucher, posted_by=self.user)

        gl_line = LedgerTransaction.objects.create(
            journal_entry=je,
            ledgerno_dr=self.bank_ledger,
            ledgerno=None,
            amount=Money("3000.00", INR),
        )

        # Manual match
        match = ReconciliationService.manual_match(
            bank_line_id=bank_line.id,
            ledger_transaction_id=gl_line.id,
            matched_by=self.user,
        )

        self.assertIsNotNone(match)
        self.assertTrue(match.is_manual)
        
        bank_line.refresh_from_db()
        self.assertTrue(bank_line.is_reconciled)

    def test_unmatch_smoke(self):
        """Test unmatching a previously matched bank line"""
        bank_line = BankStatementLine.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 4, 12),
            description="To be unmatched",
            amount=Decimal("1000.00"),
            is_reconciled=True,
        )

        voucher = Voucher.objects.create(voucher_type=self.voucher_type)
        je = JournalEntry.objects.create(voucher=voucher, posted_by=self.user)

        gl_line = LedgerTransaction.objects.create(
            journal_entry=je,
            ledgerno_dr=self.bank_ledger,
            ledgerno=None,
            amount=Money("1000.00", INR),
        )

        ReconciliationMatch.objects.create(
            bank_statement_line=bank_line,
            ledger_transaction=gl_line,
            matched_by=self.user,
        )

        # Unmatch
        ReconciliationService.unmatch(bank_line_id=bank_line.id)

        bank_line.refresh_from_db()
        self.assertFalse(bank_line.is_reconciled)
        self.assertFalse(
            ReconciliationMatch.objects.filter(
                bank_statement_line=bank_line
            ).exists()
        )

    def test_get_unmatched_bank_lines_smoke(self):
        """Test retrieving unmatched bank lines"""
        matched_line = BankStatementLine.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 4, 5),
            description="Matched",
            amount=Decimal("5000.00"),
            is_reconciled=True,
        )

        unmatched_line = BankStatementLine.objects.create(
            bank_account=self.bank_account,
            statement_date=date(2026, 4, 10),
            description="Unmatched",
            amount=Decimal("2500.00"),
            is_reconciled=False,
        )

        unmatched = ReconciliationService.get_unmatched_bank_lines(
            self.bank_account, self.period
        )

        self.assertEqual(unmatched.count(), 1)
        self.assertIn(unmatched_line, list(unmatched))

    def test_bank_statement_summary_smoke(self):
        """Test bank statement summary statistics"""
        for i in range(5):
            BankStatementLine.objects.create(
                bank_account=self.bank_account,
                statement_date=date(2026, 4, i + 1),
                description=f"Line {i+1}",
                amount=Decimal("1000.00"),
                is_reconciled=(i < 3),
            )

        summary = ReconciliationService.get_bank_statement_summary(
            self.bank_account, self.period
        )

        self.assertEqual(summary["total_lines"], 5)
        self.assertEqual(summary["reconciled_lines"], 3)
        self.assertEqual(summary["unmatched_lines"], 2)
        self.assertEqual(summary["reconciliation_percentage"], 60.0)
        self.assertEqual(summary["total_amount"], Decimal("5000.00"))
