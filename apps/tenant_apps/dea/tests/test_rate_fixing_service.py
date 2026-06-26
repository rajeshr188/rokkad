import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    Account,
    AccountingPeriod,
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
    LedgerTransaction,
    RateFixing,
    RateFixingAllocation,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherStatus,
)
from apps.tenant_apps.dea.services.rate_fixing import (
    PURCHASE_RATE_FIXING_VOUCHER_TYPE,
    SALE_RATE_FIXING_VOUCHER_TYPE,
    PurchaseRateFixingPayload,
    SaleRateFixingPayload,
    post_purchase_rate_fixing,
    post_sale_rate_fixing,
)
from apps.tenant_apps.dea.services.unfixed_purchase import (
    UnfixedPurchasePostingPayload,
    post_unfixed_purchase,
)
from apps.tenant_apps.dea.services.unfixed_sale import (
    UnfixedSalePostingPayload,
    post_unfixed_sale,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class PurchaseRateFixingServiceTests(TenantTestCase):
    test_schema_name = f"dea_rate_fixing_{uuid.uuid4().hex[:8]}"
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
            username="dea-rate-fixing-owner",
            defaults={"email": "dea-rate-fixing-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-rate-fixing-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-rate-fixing-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-rate-fixing-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        self.period = AccountingPeriod.objects.create(
            name="June 2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )
        self._seed_account_masters()
        self.ledgers = self._seed_ledgers()
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.party = Party.objects.create(display_name="Rate Fixing Supplier")
        self.supplier_customer = Customer.objects.create(
            firstname="Rate",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
        )
        self.supplier_account = Account.objects.create(
            contact=self.supplier_customer,
            entity=EntityType.objects.get(name="Organisation"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Creditor"),
        )
        self.vault = CommodityAccount.objects.create(
            code="RATE_FIXING_GOLD_VAULT",
            name="Rate fixing gold vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        self.supplier_commodity_account = CommodityAccount.objects.create(
            code="RATE_FIXING_GOLD_SUPPLIER",
            name="Rate fixing supplier gold payable",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.PARTY_PAYABLE,
            party=self.party,
        )
        self.exposure = post_unfixed_purchase(
            self._unfixed_payload(),
            actor=self.user,
        ).exposure

    def test_purchase_rate_fixing_posts_payable_and_closes_exposure(self):
        result = post_purchase_rate_fixing(self._fixing_payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, PURCHASE_RATE_FIXING_VOUCHER_TYPE)
        self.assertEqual(result.rate_fixing.status, RateFixing.Status.POSTED)
        self.assertEqual(result.rate_fixing.voucher, result.voucher)
        self.assertEqual(result.rate_fixing.fine_weight, Decimal("91.600"))
        self.assertEqual(result.rate_fixing.rate, Decimal("6200.0000"))
        self.assertEqual(result.rate_fixing.valuation_amount, Decimal("567920.00"))

        self.exposure.refresh_from_db()
        self.assertEqual(self.exposure.status, ExposureLine.Status.FIXED)
        self.assertEqual(self.exposure.fixed_status, CommodityMovement.FixedStatus.FIXED)
        self.assertEqual(self.exposure.open_fine_weight, Decimal("0.000"))

        allocation = RateFixingAllocation.objects.get(rate_fixing=result.rate_fixing)
        self.assertEqual(allocation.exposure, self.exposure)
        self.assertEqual(allocation.fine_weight, Decimal("91.600"))
        self.assertEqual(allocation.amount, Decimal("567920.00"))

        ledger_txn = LedgerTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(ledger_txn.ledgerno_dr, self.ledgers["INVENTORY"])
        self.assertEqual(ledger_txn.ledgerno, self.ledgers["ACCOUNTS_PAYABLE"])
        self.assertEqual(ledger_txn.amount.amount, Decimal("567920.000"))
        self.assertEqual(str(ledger_txn.amount.currency), "INR")

        account_txn = AccountTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(account_txn.Account, self.supplier_account)
        self.assertEqual(account_txn.ledgerno, self.ledgers["ACCOUNTS_PAYABLE"])
        self.assertEqual(account_txn.XactTypeCode_id, "Cr")
        self.assertEqual(account_txn.amount.amount, Decimal("567920.00"))

        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.filter(voucher=result.voucher).count(), 2)
        self.assertEqual(RateFixing.objects.count(), 1)

    def test_purchase_rate_fixing_is_idempotent_for_same_payload(self):
        first = post_purchase_rate_fixing(self._fixing_payload(), actor=self.user)
        second = post_purchase_rate_fixing(self._fixing_payload(), actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.rate_fixing.pk, second.rate_fixing.pk)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(RateFixing.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(RateFixingAllocation.objects.count(), 1)

    def test_purchase_rate_fixing_can_partially_fix_exposure(self):
        result = post_purchase_rate_fixing(
            self._fixing_payload(fine_weight=Decimal("50.000")),
            actor=self.user,
        )

        self.exposure.refresh_from_db()
        self.assertEqual(self.exposure.status, ExposureLine.Status.PARTIALLY_FIXED)
        self.assertEqual(
            self.exposure.fixed_status,
            CommodityMovement.FixedStatus.PARTIALLY_FIXED,
        )
        self.assertEqual(self.exposure.open_fine_weight, Decimal("41.600"))
        self.assertEqual(result.rate_fixing.valuation_amount, Decimal("310000.00"))

    def test_purchase_rate_fixing_rejects_overfix_and_rolls_back(self):
        with self.assertRaises(ValidationError):
            post_purchase_rate_fixing(
                self._fixing_payload(fine_weight=Decimal("100.000")),
                actor=self.user,
            )

        self.exposure.refresh_from_db()
        self.assertEqual(self.exposure.status, ExposureLine.Status.OPEN)
        self.assertEqual(self.exposure.open_fine_weight, Decimal("91.600"))
        self.assertEqual(RateFixing.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(Voucher.objects.filter(voucher_type__name=PURCHASE_RATE_FIXING_VOUCHER_TYPE).count(), 0)

    def test_purchase_rate_fixing_rejects_closed_period(self):
        self.period.status = AccountingPeriod.PeriodStatus.CLOSED
        self.period.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            post_purchase_rate_fixing(self._fixing_payload(), actor=self.user)

        self.assertEqual(RateFixing.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def _unfixed_payload(self):
        return UnfixedPurchasePostingPayload(
            source=self.supplier_customer,
            purchase_date=date(2026, 6, 24),
            party=self.party,
            commodity=self.gold,
            gross_weight=Decimal("100.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("91.600"),
            from_commodity_account=self.supplier_commodity_account,
            to_commodity_account=self.vault,
            rate_basis="Supplier call fixing",
            narration="Rate fixing test exposure",
        )

    def _fixing_payload(
        self,
        *,
        fine_weight=Decimal("91.600"),
        rate=Decimal("6200.0000"),
    ):
        return PurchaseRateFixingPayload(
            exposure=self.exposure,
            fixing_date=date(2026, 6, 24),
            fine_weight=fine_weight,
            rate=rate,
            supplier_account=self.supplier_account,
            inventory_ledger=self.ledgers["INVENTORY"],
            payable_ledger=self.ledgers["ACCOUNTS_PAYABLE"],
            narration="Purchase rate fixing test",
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
        EntityType.objects.get_or_create(name="Organisation")

    def _seed_ledgers(self):
        asset_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset", "code_prefix": "1"},
        )
        liability_type, _ = AccountType.objects.get_or_create(
            AccountType="Liability",
            defaults={"description": "Liability", "code_prefix": "2"},
        )
        inventory, _ = Ledger.objects.get_or_create(
            name="RATE_FIXING_INVENTORY",
            defaults={
                "AccountType": asset_type,
                "code": f"1.RATEFIX.INV.{uuid.uuid4().hex[:6]}",
            },
        )
        accounts_payable, _ = Ledger.objects.get_or_create(
            name="RATE_FIXING_AP",
            defaults={
                "AccountType": liability_type,
                "code": f"2.RATEFIX.AP.{uuid.uuid4().hex[:6]}",
            },
        )
        return {
            "INVENTORY": inventory,
            "ACCOUNTS_PAYABLE": accounts_payable,
        }


class SaleRateFixingServiceTests(TenantTestCase):
    test_schema_name = f"dea_sale_rate_fixing_{uuid.uuid4().hex[:8]}"
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
            username="dea-sale-rate-fixing-owner",
            defaults={"email": "dea-sale-rate-fixing-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-sale-rate-fixing-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-sale-rate-fixing-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-sale-rate-fixing-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        self.period = AccountingPeriod.objects.create(
            name="June 2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )
        self._seed_account_masters()
        self.ledgers = self._seed_ledgers()
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.party = Party.objects.create(display_name="Rate Fixing Customer")
        self.customer = Customer.objects.create(
            firstname="Rate",
            lastname="Buyer",
            customer_type=Customer.CustomerType.Retail,
        )
        self.customer_account = Account.objects.create(
            contact=self.customer,
            entity=EntityType.objects.get(name="Person"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Debtor"),
        )
        self.vault = CommodityAccount.objects.create(
            code="SALE_RATE_FIXING_GOLD_VAULT",
            name="Sale rate fixing gold vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        self.exposure = post_unfixed_sale(
            self._unfixed_sale_payload(),
            actor=self.user,
        ).exposure

    def test_sale_rate_fixing_posts_receivable_revenue_and_closes_exposure(self):
        result = post_sale_rate_fixing(self._sale_fixing_payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, SALE_RATE_FIXING_VOUCHER_TYPE)
        self.assertEqual(result.rate_fixing.status, RateFixing.Status.POSTED)
        self.assertEqual(result.rate_fixing.voucher, result.voucher)
        self.assertEqual(result.rate_fixing.side, ExposureLine.Side.SALE)
        self.assertEqual(result.rate_fixing.fine_weight, Decimal("91.600"))
        self.assertEqual(result.rate_fixing.rate, Decimal("6400.0000"))
        self.assertEqual(result.rate_fixing.valuation_amount, Decimal("586240.00"))

        self.exposure.refresh_from_db()
        self.assertEqual(self.exposure.status, ExposureLine.Status.FIXED)
        self.assertEqual(self.exposure.fixed_status, CommodityMovement.FixedStatus.FIXED)
        self.assertEqual(self.exposure.open_fine_weight, Decimal("0.000"))

        allocation = RateFixingAllocation.objects.get(rate_fixing=result.rate_fixing)
        self.assertEqual(allocation.exposure, self.exposure)
        self.assertEqual(allocation.fine_weight, Decimal("91.600"))
        self.assertEqual(allocation.amount, Decimal("586240.00"))

        ledger_txn = LedgerTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(ledger_txn.ledgerno_dr, self.ledgers["ACCOUNTS_RECEIVABLE"])
        self.assertEqual(ledger_txn.ledgerno, self.ledgers["SALES_REVENUE"])
        self.assertEqual(ledger_txn.amount.amount, Decimal("586240.000"))
        self.assertEqual(str(ledger_txn.amount.currency), "INR")

        account_txn = AccountTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(account_txn.Account, self.customer_account)
        self.assertEqual(account_txn.ledgerno, self.ledgers["ACCOUNTS_RECEIVABLE"])
        self.assertEqual(account_txn.XactTypeCode_id, "Dr")
        self.assertEqual(account_txn.amount.amount, Decimal("586240.00"))

        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.filter(voucher=result.voucher).count(), 2)
        self.assertEqual(RateFixing.objects.count(), 1)

    def test_sale_rate_fixing_is_idempotent_for_same_payload(self):
        first = post_sale_rate_fixing(self._sale_fixing_payload(), actor=self.user)
        second = post_sale_rate_fixing(self._sale_fixing_payload(), actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.rate_fixing.pk, second.rate_fixing.pk)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(RateFixing.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(RateFixingAllocation.objects.count(), 1)

    def test_sale_rate_fixing_can_partially_fix_exposure(self):
        result = post_sale_rate_fixing(
            self._sale_fixing_payload(fine_weight=Decimal("50.000")),
            actor=self.user,
        )

        self.exposure.refresh_from_db()
        self.assertEqual(self.exposure.status, ExposureLine.Status.PARTIALLY_FIXED)
        self.assertEqual(
            self.exposure.fixed_status,
            CommodityMovement.FixedStatus.PARTIALLY_FIXED,
        )
        self.assertEqual(self.exposure.open_fine_weight, Decimal("41.600"))
        self.assertEqual(result.rate_fixing.valuation_amount, Decimal("320000.00"))

    def test_sale_rate_fixing_rejects_overfix_and_rolls_back(self):
        with self.assertRaises(ValidationError):
            post_sale_rate_fixing(
                self._sale_fixing_payload(fine_weight=Decimal("100.000")),
                actor=self.user,
            )

        self.exposure.refresh_from_db()
        self.assertEqual(self.exposure.status, ExposureLine.Status.OPEN)
        self.assertEqual(self.exposure.open_fine_weight, Decimal("91.600"))
        self.assertEqual(RateFixing.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(
            Voucher.objects.filter(voucher_type__name=SALE_RATE_FIXING_VOUCHER_TYPE).count(),
            0,
        )

    def test_sale_rate_fixing_rejects_closed_period(self):
        self.period.status = AccountingPeriod.PeriodStatus.CLOSED
        self.period.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            post_sale_rate_fixing(self._sale_fixing_payload(), actor=self.user)

        self.assertEqual(RateFixing.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def _unfixed_sale_payload(self):
        return UnfixedSalePostingPayload(
            source=self.customer,
            sale_date=date(2026, 6, 24),
            party=self.party,
            commodity=self.gold,
            gross_weight=Decimal("100.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("91.600"),
            from_commodity_account=self.vault,
            rate_basis="Customer call fixing",
            narration="Sale rate fixing test exposure",
        )

    def _sale_fixing_payload(
        self,
        *,
        fine_weight=Decimal("91.600"),
        rate=Decimal("6400.0000"),
    ):
        return SaleRateFixingPayload(
            exposure=self.exposure,
            fixing_date=date(2026, 6, 24),
            fine_weight=fine_weight,
            rate=rate,
            customer_account=self.customer_account,
            receivable_ledger=self.ledgers["ACCOUNTS_RECEIVABLE"],
            revenue_ledger=self.ledgers["SALES_REVENUE"],
            narration="Sale rate fixing test",
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
        EntityType.objects.get_or_create(name="Organisation")

    def _seed_ledgers(self):
        asset_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset", "code_prefix": "1"},
        )
        revenue_type, _ = AccountType.objects.get_or_create(
            AccountType="Revenue",
            defaults={"description": "Revenue", "code_prefix": "4"},
        )
        accounts_receivable, _ = Ledger.objects.get_or_create(
            name="SALE_RATE_FIXING_AR",
            defaults={
                "AccountType": asset_type,
                "code": f"1.SALERATEFIX.AR.{uuid.uuid4().hex[:6]}",
            },
        )
        sales_revenue, _ = Ledger.objects.get_or_create(
            name="SALE_RATE_FIXING_REVENUE",
            defaults={
                "AccountType": revenue_type,
                "code": f"4.SALERATEFIX.REV.{uuid.uuid4().hex[:6]}",
            },
        )
        return {
            "ACCOUNTS_RECEIVABLE": accounts_receivable,
            "SALES_REVENUE": sales_revenue,
        }
