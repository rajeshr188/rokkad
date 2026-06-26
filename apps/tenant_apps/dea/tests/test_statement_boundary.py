import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    Account,
    AccountingPeriod,
    AccountStatement,
    AccountTransaction,
    AccountType,
    AccountType_Ext,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    EntityType,
    ExposureLine,
    JournalEntry,
    Ledger,
    LedgerStatement,
    LedgerTransaction,
    TransactionType_DE,
    TransactionType_Ext,
    Voucher,
    VoucherStatus,
    VoucherType,
)
from apps.tenant_apps.dea.services.exposure_report import build_exposure_report
from apps.tenant_apps.dea.services.metal_balance_report import build_metal_balance_report
from apps.tenant_apps.party.models import Party


User = get_user_model()


class StatementBoundaryTests(TenantTestCase):
    test_schema_name = f"dea_statement_boundary_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-statement-boundary-owner",
            defaults={"email": "dea-statement-boundary-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-statement-boundary-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-statement-boundary-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-statement-boundary-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        self.period = AccountingPeriod.objects.create(
            name="June 2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )
        self._seed_account_masters()
        self.cash_ledger, self.capital_ledger = self._seed_ledgers()
        self.account = self._account()

    def test_period_close_statements_remain_monetary_when_commodity_records_exist(self):
        self._post_financial_rows()
        self._create_commodity_records()

        metal_report = build_metal_balance_report(as_of=self.period.end_date)
        exposure_report = build_exposure_report(as_of=self.period.end_date)
        self.period.close_period(self.user, notes="Statement boundary test")

        ledger_statements = LedgerStatement.objects.filter(period=self.period)
        account_statements = AccountStatement.objects.filter(period=self.period)

        self.assertGreaterEqual(ledger_statements.count(), 2)
        self.assertEqual(account_statements.count(), 1)
        self.assertEqual(
            set(ledger_statements.values_list("ClosingBalance_currency", flat=True)),
            {"INR"},
        )
        self.assertEqual(
            set(account_statements.values_list("ClosingBalance_currency", flat=True)),
            {"INR"},
        )
        self.assertEqual(
            set(account_statements.values_list("TotalCredit_currency", flat=True)),
            {"INR"},
        )
        self.assertEqual(
            set(account_statements.values_list("TotalDebit_currency", flat=True)),
            {"INR"},
        )
        self.assertFalse(
            LedgerStatement.objects.filter(
                ClosingBalance_currency__in=["GOLD", "SILVER", "XAU", "XAG"]
            ).exists()
        )
        self.assertFalse(
            AccountStatement.objects.filter(
                ClosingBalance_currency__in=["GOLD", "SILVER", "XAU", "XAG"]
            ).exists()
        )
        self.assertEqual(metal_report.totals_by_commodity[0].commodity_code, "GOLD")
        self.assertEqual(exposure_report.rows[0].commodity_code, "GOLD")

    def test_account_and_ledger_audit_ignore_commodity_exposure_and_movement_rows(self):
        self._post_financial_rows()
        self._create_commodity_records()

        self.cash_ledger.audit()
        account_statements = self.account.audit()

        ledger_statement = LedgerStatement.objects.get(ledgerno=self.cash_ledger)
        account_statement = account_statements[0]
        self.assertEqual(ledger_statement.ClosingBalance.currency.code, "INR")
        self.assertEqual(account_statement.ClosingBalance.currency.code, "INR")
        self.assertEqual(account_statement.TotalCredit.currency.code, "INR")
        self.assertEqual(account_statement.TotalDebit.currency.code, "INR")
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)

    def _post_financial_rows(self):
        voucher_type, _ = VoucherType.objects.get_or_create(
            name="STATEMENT_BOUNDARY",
            defaults={"description": "Statement boundary test voucher"},
        )
        voucher = Voucher.objects.create(
            voucher_no=f"STATEMENT-{uuid.uuid4().hex[:8]}",
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
        LedgerTransaction.objects.create(
            journal_entry=journal_entry,
            ledgerno_dr=self.cash_ledger,
            ledgerno=self.capital_ledger,
            amount=Money(Decimal("500.00"), "INR"),
            amount_base=Money(Decimal("500.00"), "INR"),
        )
        AccountTransaction.objects.create(
            journal_entry=journal_entry,
            ledgerno=self.cash_ledger,
            XactTypeCode=TransactionType_DE.objects.get(XactTypeCode="Dr"),
            XactTypeCode_ext=TransactionType_Ext.objects.get(XactTypeCode_ext="TEST"),
            Account=self.account,
            amount=Money(Decimal("500.00"), "INR"),
        )

    def _create_commodity_records(self):
        gold = Commodity.objects.create(code="GOLD", name="Gold")
        party = Party.objects.create(display_name="Statement Boundary Supplier")
        vault = CommodityAccount.objects.create(
            code="STATEMENT_GOLD_VAULT",
            name="Statement gold vault",
            commodity=gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        adjustment = CommodityAccount.objects.create(
            code="STATEMENT_GOLD_ADJUSTMENT",
            name="Statement gold adjustment",
            commodity=gold,
            purpose=CommodityAccount.Purpose.ADJUSTMENT,
        )
        source_content_type = ContentType.objects.get_for_model(AccountingPeriod)
        CommodityMovement.objects.create(
            movement_no="STATEMENT-GOLD-MOVE",
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
            idempotency_key="commodity:test:statement-boundary:movement",
        )
        ExposureLine.objects.create(
            exposure_no="STATEMENT-GOLD-EXPOSURE",
            source_content_type=source_content_type,
            source_object_id=self.period.pk,
            party=party,
            commodity=gold,
            side=ExposureLine.Side.PURCHASE,
            status=ExposureLine.Status.OPEN,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
            original_fine_weight=Decimal("91.600"),
            open_fine_weight=Decimal("91.600"),
            valuation_currency="INR",
            idempotency_key="commodity:test:statement-boundary:exposure",
        )

    def _seed_ledgers(self):
        asset_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset", "code_prefix": "1"},
        )
        equity_type, _ = AccountType.objects.get_or_create(
            AccountType="Equity",
            defaults={"description": "Equity", "code_prefix": "3"},
        )
        cash = Ledger.objects.create(
            AccountType=asset_type,
            name=f"STATEMENT_CASH_{uuid.uuid4().hex[:8]}",
            code=f"1.STMT.CASH.{uuid.uuid4().hex[:6]}",
            is_current_asset=True,
        )
        capital = Ledger.objects.create(
            AccountType=equity_type,
            name=f"STATEMENT_CAPITAL_{uuid.uuid4().hex[:8]}",
            code=f"3.STMT.CAP.{uuid.uuid4().hex[:6]}",
        )
        return cash, capital

    def _account(self):
        customer = Customer.objects.create(
            firstname="Statement",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
        )
        return Account.objects.create(
            contact=customer,
            entity=EntityType.objects.get(name="Person"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Debtor"),
        )

    def _seed_account_masters(self):
        debit_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        credit_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Cr",
            defaults={"name": "Credit"},
        )
        AccountType_Ext.objects.get_or_create(
            description="Debtor",
            defaults={"XactTypeCode": debit_code},
        )
        AccountType_Ext.objects.get_or_create(
            description="Creditor",
            defaults={"XactTypeCode": credit_code},
        )
        EntityType.objects.get_or_create(name="Person")
        TransactionType_Ext.objects.get_or_create(
            XactTypeCode_ext="TEST",
            defaults={"description": "Statement boundary test"},
        )
