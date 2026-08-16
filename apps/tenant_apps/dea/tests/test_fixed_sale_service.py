import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

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
    JournalEntry,
    Ledger,
    LedgerTransaction,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherStatus,
)
from apps.tenant_apps.dea.services.fixed_sale import (
    FIXED_SALE_VOUCHER_TYPE,
    FixedSalePostingPayload,
    post_fixed_sale,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class FixedSaleServiceTests(TenantTestCase):
    test_schema_name = f"dea_fixed_sale_{uuid.uuid4().hex[:8]}"
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
            username="dea-fixed-sale-owner",
            defaults={"email": "dea-fixed-sale-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-fixed-sale-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-fixed-sale-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-fixed-sale-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        AccountingPeriod.objects.create(
            name="June 2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )
        self._seed_account_masters()
        self.ledgers = self._seed_ledgers()
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.customer = Party.objects.create(display_name="Fixed Buyer")
        self.customer_account = Account.objects.create(
            party=self.customer,
            entity=EntityType.objects.get(name="Person"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Debtor"),
        )
        self.vault = CommodityAccount.objects.create(
            code="FIXED_SALE_GOLD_VAULT",
            name="Fixed sale gold vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )

    def test_fixed_sale_posts_financial_and_commodity_effects(self):
        result = post_fixed_sale(self._payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, FIXED_SALE_VOUCHER_TYPE)
        self.assertEqual(result.journal_entry.voucher, result.voucher)

        ledger_txn = LedgerTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(ledger_txn.ledgerno_dr, self.ledgers["ACCOUNTS_RECEIVABLE"])
        self.assertEqual(ledger_txn.ledgerno, self.ledgers["SALES_REVENUE"])
        self.assertEqual(ledger_txn.amount.amount, Decimal("700000.000"))
        self.assertEqual(str(ledger_txn.amount.currency), "INR")

        account_txn = AccountTransaction.objects.get(
            journal_entry=result.journal_entry
        )
        self.assertEqual(account_txn.Account, self.customer_account)
        self.assertEqual(account_txn.ledgerno, self.ledgers["ACCOUNTS_RECEIVABLE"])
        self.assertEqual(account_txn.XactTypeCode_id, "Dr")
        self.assertEqual(str(account_txn.amount.currency), "INR")

        movement = result.commodity_movement
        self.assertEqual(movement.voucher, result.voucher)
        self.assertEqual(movement.commodity, self.gold)
        self.assertEqual(movement.from_account, self.vault)
        self.assertIsNone(movement.to_account)
        self.assertEqual(movement.fixed_status, CommodityMovement.FixedStatus.FIXED)
        self.assertEqual(movement.movement_type, CommodityMovement.MovementType.SALE_ISSUE)
        self.assertEqual(movement.fine_weight, Decimal("100.000"))
        self.assertEqual(movement.rate_currency, "INR")
        self.assertEqual(movement.valuation_currency, "INR")

        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.filter(voucher=result.voucher).count(), 2)

    def test_fixed_sale_is_idempotent_for_same_payload(self):
        first = post_fixed_sale(self._payload(), actor=self.user)
        second = post_fixed_sale(self._payload(), actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_changed_payload_for_same_source_is_rejected_until_correction_exists(self):
        post_fixed_sale(self._payload(), actor=self.user)

        with self.assertRaises(ValidationError):
            post_fixed_sale(
                self._payload(
                    gross_weight=Decimal("101.000"),
                    fine_weight=Decimal("101.000"),
                    money_amount=Decimal("707000.00"),
                ),
                actor=self.user,
            )

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_fixed_sale_rolls_back_financial_posting_when_commodity_fails(self):
        with self.assertRaises(ValidationError):
            post_fixed_sale(
                self._payload(
                    gross_weight=Decimal("100.000"),
                    purity=Decimal("0.900000"),
                    fine_weight=Decimal("100.000"),
                ),
                actor=self.user,
            )

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def test_fixed_sale_rejects_non_inr_currency_for_mvp(self):
        with self.assertRaises(ValidationError):
            post_fixed_sale(self._payload(currency="USD"), actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def _payload(
        self,
        *,
        gross_weight=Decimal("100.000"),
        purity=Decimal("1.000000"),
        fine_weight=Decimal("100.000"),
        money_amount=Decimal("700000.00"),
        currency="INR",
    ):
        return FixedSalePostingPayload(
            source=self.customer,
            sale_date=date(2026, 6, 24),
            customer_account=self.customer_account,
            receivable_ledger=self.ledgers["ACCOUNTS_RECEIVABLE"],
            revenue_ledger=self.ledgers["SALES_REVENUE"],
            commodity=self.gold,
            gross_weight=gross_weight,
            purity=purity,
            fine_weight=fine_weight,
            from_commodity_account=self.vault,
            money_amount=money_amount,
            currency=currency,
            narration="Fixed sale test",
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
            name="FIXED_SALE_AR",
            defaults={
                "AccountType": asset_type,
                "code": f"1.FIXSAL.AR.{uuid.uuid4().hex[:6]}",
            },
        )
        sales_revenue, _ = Ledger.objects.get_or_create(
            name="FIXED_SALE_REVENUE",
            defaults={
                "AccountType": revenue_type,
                "code": f"4.FIXSAL.REV.{uuid.uuid4().hex[:6]}",
            },
        )
        return {
            "ACCOUNTS_RECEIVABLE": accounts_receivable,
            "SALES_REVENUE": sales_revenue,
        }
