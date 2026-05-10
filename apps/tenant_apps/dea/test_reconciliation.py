from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.dea.models import AccountingPeriod, AccountType, JournalEntryVoucher, Ledger
from apps.tenant_apps.dea.models.bank import BankAccount, BankStatementLine
from apps.tenant_apps.dea.models.ledger import LedgerTransaction
from apps.tenant_apps.dea.services.reconciliation import ReconciliationService


User = get_user_model()


class ReconciliationServiceTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_dea_reconciliation"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="dea-recon-owner",
            email="dea-recon-owner@example.com",
            password="testpass123",
        )
        tenant.name = "dea-recon-tenant"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username="dea-recon-user",
            email="dea-recon-user@example.com",
            password="testpass123",
        )

    def test_auto_match_links_bank_lines_to_gl_transactions(self):
        period = AccountingPeriod.objects.create(
            name="Apr 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )
        asset_type = AccountType.objects.create(
            AccountType="Asset",
            description="Asset",
            code_prefix="1",
        )
        expense_type = AccountType.objects.create(
            AccountType="Expense",
            description="Expense",
            code_prefix="5",
        )
        bank_ledger = Ledger.objects.create(
            AccountType=asset_type,
            name="Bank Reconciliation Test Account",
            code="1.BANK.RECON.TEST",
        )
        offset_ledger = Ledger.objects.create(
            AccountType=expense_type,
            name="Offset Test Account",
            code="5.BANK.RECON.TEST",
        )
        bank_account = BankAccount.objects.create(
            name="Test Bank A/C",
            bank_name="Test Bank",
            account_number="123456",
            ledger=bank_ledger,
        )

        voucher = JournalEntryVoucher.objects.create(
            je_number="JE-RECON-1",
            je_date=period.start_date,
            entry_type="OTHER",
            description="Bank receipt",
            total_debit=Money(500, "INR"),
            total_credit=Money(500, "INR"),
            reviewed_by=self.user,
            reviewed_at=timezone.now(),
            created_by=self.user,
            updated_by=self.user,
        )
        txn = LedgerTransaction.objects.create(
            journal_entry=voucher,
            ledgerno=bank_ledger,
            ledgerno_dr=offset_ledger,
            amount=Money(500, "INR"),
            amount_base=Money(500, "INR"),
        )
        aware_created = timezone.make_aware(datetime.combine(period.start_date, time(10, 0)))
        LedgerTransaction.objects.filter(pk=txn.pk).update(created=aware_created)

        match_line = BankStatementLine.objects.create(
            bank_account=bank_account,
            statement_date=period.start_date,
            description="Bank receipt",
            amount=500,
            amount_currency="INR",
            running_balance=1500,
            running_balance_currency="INR",
        )
        unmatched_line = BankStatementLine.objects.create(
            bank_account=bank_account,
            statement_date=period.start_date,
            description="Unmatched charge",
            amount=-125,
            amount_currency="INR",
            running_balance=1375,
            running_balance_currency="INR",
        )

        matches = ReconciliationService.auto_match(bank_account, period, matched_by=self.user)

        self.assertEqual(len(matches), 1)
        self.assertTrue(match_line.is_reconciled)
        self.assertFalse(unmatched_line.is_reconciled)
        self.assertEqual(ReconciliationService.get_unmatched_bank_lines(bank_account, period).count(), 1)
        self.assertEqual(ReconciliationService.get_unmatched_gl_lines(bank_ledger, period).count(), 0)
