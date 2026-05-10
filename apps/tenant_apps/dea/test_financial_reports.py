from datetime import date
import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.dea.models import AccountingPeriod, AccountType, Ledger
from apps.tenant_apps.dea.services.reports import ReportsService


User = get_user_model()


class FinancialReportsServiceTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_dea_financial_reports"

    @classmethod
    def setup_tenant(cls, tenant):
        user, _ = User.objects.get_or_create(
            username="dea-report-owner",
            defaults={"email": "dea-report-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = "dea-report-tenant"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.service = ReportsService()

        unique_suffix = uuid.uuid4().hex[:8]

        self.period = AccountingPeriod.objects.create(
            name="Jan 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        self.asset_type = AccountType.objects.create(
            AccountType="Asset",
            description="Asset",
            code_prefix="1",
        )
        self.liability_type = AccountType.objects.create(
            AccountType="Liability",
            description="Liability",
            code_prefix="2",
        )
        self.equity_type = AccountType.objects.create(
            AccountType="Equity",
            description="Equity",
            code_prefix="3",
        )
        self.income_type = AccountType.objects.create(
            AccountType="Income",
            description="Income",
            code_prefix="4",
        )
        self.expense_type = AccountType.objects.create(
            AccountType="Expense",
            description="Expense",
            code_prefix="5",
        )

        Ledger.objects.create(
            AccountType=self.asset_type,
            name=f"Cash Report Test {unique_suffix}",
            code=f"1.REPORT.CASH.{unique_suffix}",
            is_current_asset=True,
        )
        Ledger.objects.create(
            AccountType=self.liability_type,
            name=f"Payable Report Test {unique_suffix}",
            code=f"2.REPORT.PAYABLE.{unique_suffix}",
            is_current_liability=True,
        )
        Ledger.objects.create(
            AccountType=self.equity_type,
            name=f"Capital Report Test {unique_suffix}",
            code=f"3.REPORT.CAPITAL.{unique_suffix}",
        )
        Ledger.objects.create(
            AccountType=self.income_type,
            name=f"Sales Report Test {unique_suffix}",
            code=f"4.REPORT.SALES.{unique_suffix}",
            is_operating_revenue=True,
        )
        Ledger.objects.create(
            AccountType=self.expense_type,
            name=f"Expense Report Test {unique_suffix}",
            code=f"5.REPORT.EXPENSE.{unique_suffix}",
            is_operating_expense=True,
        )

    def test_trial_balance_smoke(self):
        report = self.service.trial_balance(self.period, include_prior=True)
        self.assertEqual(report.title, "Trial Balance")
        self.assertIn("debit", report.totals)
        self.assertIn("credit", report.totals)

    def test_income_statement_smoke(self):
        report = self.service.income_statement(self.period)
        self.assertEqual(report.title, "Profit & Loss Statement")
        self.assertIn("net_profit", report.totals)

    def test_balance_sheet_smoke(self):
        report = self.service.balance_sheet(self.period)
        self.assertEqual(report.title, "Balance Sheet")
        self.assertIn("assets", report.totals)
        self.assertIn("liab_equity", report.totals)

    def test_cash_flow_smoke(self):
        report = self.service.cash_flow_statement(self.period)
        self.assertEqual(report.title, "Cash Flow Statement")
        self.assertIn("net_cash_flow", report.totals)

    def test_aging_smoke(self):
        ar = self.service.ar_aging(self.period)
        ap = self.service.ap_aging(self.period)
        self.assertEqual(ar.title, "Accounts Receivable Aging")
        self.assertEqual(ap.title, "Accounts Payable Aging")
        self.assertIn("total", ar.totals)
        self.assertIn("total", ap.totals)
