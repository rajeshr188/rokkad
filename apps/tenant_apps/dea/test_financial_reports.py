from datetime import date
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.dea.models import (
    AccountingPeriod,
    AccountType,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    ExposureLine,
    JournalEntry,
    Ledger,
    LedgerTransaction,
    RateFixing,
    Voucher,
    VoucherStatus,
    VoucherType,
)
from apps.tenant_apps.dea.services.metal_balance_report import (
    build_metal_balance_report,
)
from apps.tenant_apps.dea.services.reports import ReportsService
from apps.tenant_apps.party.models import Party


User = get_user_model()


class FinancialReportsServiceTests(TenantTestCase):
    test_schema_name = f"test_dea_financial_reports_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        user, _ = User.objects.get_or_create(
            username="dea-report-owner",
            defaults={"email": "dea-report-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"dea-report-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.service = ReportsService()
        self.user = User.objects.create_user(
            username=f"dea-report-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-report-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )

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

        self.cash = Ledger.objects.create(
            AccountType=self.asset_type,
            name=f"Cash Report Test {unique_suffix}",
            code=f"1.REPORT.CASH.{unique_suffix}",
            is_current_asset=True,
        )
        self.payable = Ledger.objects.create(
            AccountType=self.liability_type,
            name=f"Payable Report Test {unique_suffix}",
            code=f"2.REPORT.PAYABLE.{unique_suffix}",
            is_current_liability=True,
        )
        self.capital = Ledger.objects.create(
            AccountType=self.equity_type,
            name=f"Capital Report Test {unique_suffix}",
            code=f"3.REPORT.CAPITAL.{unique_suffix}",
        )
        self.sales = Ledger.objects.create(
            AccountType=self.income_type,
            name=f"Sales Report Test {unique_suffix}",
            code=f"4.REPORT.SALES.{unique_suffix}",
            is_operating_revenue=True,
        )
        self.expense = Ledger.objects.create(
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

    def test_trial_balance_reports_financial_debit_and_credit_sides(self):
        self._post_ledger_pair(
            debit_ledger=self.cash,
            credit_ledger=self.capital,
            amount=Money(Decimal("500.00"), "INR"),
            amount_base=Money(Decimal("500.00"), "INR"),
        )

        report = self.service.trial_balance(self.period)

        self.assertEqual(report.totals["debit"], Money(Decimal("500.000"), "INR"))
        self.assertEqual(report.totals["credit"], Money(Decimal("500.000"), "INR"))
        self.assertTrue(report.totals["in_balance"])

    def test_trial_balance_uses_base_currency_for_non_base_monetary_posting(self):
        self._post_ledger_pair(
            debit_ledger=self.cash,
            credit_ledger=self.capital,
            amount=Money(Decimal("10.00"), "USD"),
            amount_base=Money(Decimal("830.00"), "INR"),
        )

        report = self.service.trial_balance(self.period)

        self.assertEqual(report.totals["debit"], Money(Decimal("830.000"), "INR"))
        self.assertEqual(report.totals["credit"], Money(Decimal("830.000"), "INR"))
        self.assertTrue(report.totals["in_balance"])
        self.assertEqual({line.balance.currency.code for line in report.lines}, {"INR"})

    def test_trial_balance_ignores_commodity_records_and_metal_report_data(self):
        self._post_ledger_pair(
            debit_ledger=self.cash,
            credit_ledger=self.capital,
            amount=Money(Decimal("500.00"), "INR"),
            amount_base=Money(Decimal("500.00"), "INR"),
        )
        baseline_report = self.service.trial_balance(self.period)
        baseline_lines = [
            (line.ledger_code, line.balance)
            for line in baseline_report.lines
            if line.ledger_code
        ]
        financial_journal_count = JournalEntry.objects.count()
        financial_ledger_txn_count = LedgerTransaction.objects.count()

        self._create_commodity_noise()
        metal_report = build_metal_balance_report(as_of=self.period.end_date)
        report = self.service.trial_balance(self.period)

        self.assertEqual(report.totals["debit"], baseline_report.totals["debit"])
        self.assertEqual(report.totals["credit"], baseline_report.totals["credit"])
        self.assertTrue(report.totals["in_balance"])
        self.assertEqual(
            [(line.ledger_code, line.balance) for line in report.lines if line.ledger_code],
            baseline_lines,
        )
        self.assertEqual(JournalEntry.objects.count(), financial_journal_count)
        self.assertEqual(LedgerTransaction.objects.count(), financial_ledger_txn_count)
        self.assertEqual(metal_report.totals_by_commodity[0].commodity_code, "GOLD")
        self.assertEqual(
            metal_report.totals_by_commodity[0].fine_weight,
            Decimal("91.600"),
        )

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

    def _post_ledger_pair(self, *, debit_ledger, credit_ledger, amount, amount_base):
        voucher_type, _ = VoucherType.objects.get_or_create(
            name="REPORT_TEST",
            defaults={"description": "Report test voucher"},
        )
        voucher = Voucher.objects.create(
            voucher_no=f"REPORT-{uuid.uuid4().hex[:8]}",
            voucher_type=voucher_type,
            voucher_date=self.period.end_date,
            status=VoucherStatus.POSTED,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(AccountingPeriod),
            doc_object_id=self.period.pk,
        )
        journal_entry = JournalEntry.objects.create(
            voucher=voucher,
            posted_by=self.user,
            period=self.period,
        )
        return LedgerTransaction.objects.create(
            journal_entry=journal_entry,
            ledgerno_dr=debit_ledger,
            ledgerno=credit_ledger,
            amount=amount,
            amount_base=amount_base,
        )

    def _create_commodity_noise(self):
        gold = Commodity.objects.create(code="GOLD", name="Gold")
        party = Party.objects.create(display_name="Financial report commodity party")
        vault = CommodityAccount.objects.create(
            code="REPORT_GOLD_VAULT",
            name="Report gold vault",
            commodity=gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        adjustment = CommodityAccount.objects.create(
            code="REPORT_GOLD_ADJUSTMENT",
            name="Report gold adjustment",
            commodity=gold,
            purpose=CommodityAccount.Purpose.ADJUSTMENT,
        )
        source_content_type = ContentType.objects.get_for_model(AccountingPeriod)

        CommodityMovement.objects.create(
            movement_no="REPORT-GOLD-MOVE",
            movement_date=self.period.end_date,
            source_content_type=source_content_type,
            source_object_id=self.period.pk,
            commodity=gold,
            gross_weight=Decimal("100.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("91.600"),
            from_account=adjustment,
            to_account=vault,
            movement_type=CommodityMovement.MovementType.PURCHASE_RECEIPT,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
            idempotency_key="commodity:test:financial-report:movement",
        )
        exposure = ExposureLine.objects.create(
            exposure_no="REPORT-GOLD-EXPOSURE",
            source_content_type=source_content_type,
            source_object_id=self.period.pk,
            party=party,
            commodity=gold,
            side=ExposureLine.Side.PURCHASE,
            status=ExposureLine.Status.OPEN,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
            original_fine_weight=Decimal("91.600"),
            open_fine_weight=Decimal("91.600"),
            rate_basis="Report test unfixed exposure",
            valuation_currency="INR",
            idempotency_key="commodity:test:financial-report:exposure",
        )
        RateFixing.objects.create(
            fixing_no="REPORT-GOLD-FIXING",
            fixing_date=self.period.end_date,
            party=party,
            commodity=gold,
            side=ExposureLine.Side.PURCHASE,
            fine_weight=Decimal("10.000"),
            rate=Decimal("6200.0000"),
            currency="INR",
            valuation_amount=Decimal("62000.00"),
            status=RateFixing.Status.POSTED,
            idempotency_key="commodity:test:financial-report:fixing",
            narration=f"Standalone fixing row for exposure {exposure.exposure_no}",
        )
