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
    JournalEntry,
    Ledger,
    LedgerTransaction,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherStatus,
)
from apps.tenant_apps.dea.services.fixed_purchase import (
    FIXED_PURCHASE_VOUCHER_TYPE,
    FixedPurchasePostingPayload,
    post_fixed_purchase,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class FixedPurchaseServiceTests(TenantTestCase):
    test_schema_name = f"dea_fixed_purchase_{uuid.uuid4().hex[:8]}"
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
            username="dea-fixed-purchase-owner",
            defaults={"email": "dea-fixed-purchase-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-fixed-purchase-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-fixed-purchase-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-fixed-purchase-user-{uuid.uuid4().hex[:8]}@example.com",
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
        self.party = Party.objects.create(display_name="Fixed Purchase Supplier")
        self.supplier_customer = Customer.objects.create(
            firstname="Fixed",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
        )
        self.supplier_account = Account.objects.create(
            contact=self.supplier_customer,
            entity=EntityType.objects.get(name="Organisation"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Creditor"),
        )
        self.vault = CommodityAccount.objects.create(
            code="FIXED_PURCHASE_GOLD_VAULT",
            name="Fixed purchase gold vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        self.supplier_commodity_account = CommodityAccount.objects.create(
            code="FIXED_PURCHASE_GOLD_SUPPLIER",
            name="Fixed purchase supplier gold payable",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.PARTY_PAYABLE,
            party=self.party,
        )

    def test_fixed_purchase_posts_financial_and_commodity_effects(self):
        result = post_fixed_purchase(self._payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, FIXED_PURCHASE_VOUCHER_TYPE)
        self.assertEqual(result.journal_entry.voucher, result.voucher)

        ledger_txn = LedgerTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(ledger_txn.ledgerno_dr, self.ledgers["INVENTORY"])
        self.assertEqual(ledger_txn.ledgerno, self.ledgers["ACCOUNTS_PAYABLE"])
        self.assertEqual(ledger_txn.amount.amount, Decimal("620000.000"))
        self.assertEqual(str(ledger_txn.amount.currency), "INR")

        account_txn = AccountTransaction.objects.get(
            journal_entry=result.journal_entry
        )
        self.assertEqual(account_txn.Account, self.supplier_account)
        self.assertEqual(account_txn.ledgerno, self.ledgers["ACCOUNTS_PAYABLE"])
        self.assertEqual(account_txn.XactTypeCode_id, "Cr")
        self.assertEqual(str(account_txn.amount.currency), "INR")

        movement = result.commodity_movement
        self.assertEqual(movement.voucher, result.voucher)
        self.assertEqual(movement.commodity, self.gold)
        self.assertEqual(movement.from_account, self.supplier_commodity_account)
        self.assertEqual(movement.to_account, self.vault)
        self.assertEqual(movement.fixed_status, CommodityMovement.FixedStatus.FIXED)
        self.assertEqual(movement.movement_type, CommodityMovement.MovementType.PURCHASE_RECEIPT)
        self.assertEqual(movement.fine_weight, Decimal("100.000"))
        self.assertEqual(movement.rate_currency, "INR")
        self.assertEqual(movement.valuation_currency, "INR")

        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.filter(voucher=result.voucher).count(), 2)

    def test_fixed_purchase_is_idempotent_for_same_payload(self):
        first = post_fixed_purchase(self._payload(), actor=self.user)
        second = post_fixed_purchase(self._payload(), actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_changed_payload_for_same_source_is_rejected_until_correction_exists(self):
        post_fixed_purchase(self._payload(), actor=self.user)

        with self.assertRaises(ValidationError):
            post_fixed_purchase(
                self._payload(
                    gross_weight=Decimal("101.000"),
                    fine_weight=Decimal("101.000"),
                    money_amount=Decimal("626200.00"),
                ),
                actor=self.user,
            )

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_fixed_purchase_rolls_back_financial_posting_when_commodity_fails(self):
        with self.assertRaises(ValidationError):
            post_fixed_purchase(
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

    def test_fixed_purchase_rejects_non_inr_currency_for_mvp(self):
        with self.assertRaises(ValidationError):
            post_fixed_purchase(self._payload(currency="USD"), actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def _payload(
        self,
        *,
        gross_weight=Decimal("100.000"),
        purity=Decimal("1.000000"),
        fine_weight=Decimal("100.000"),
        money_amount=Decimal("620000.00"),
        currency="INR",
    ):
        return FixedPurchasePostingPayload(
            source=self.supplier_customer,
            purchase_date=date(2026, 6, 24),
            supplier_account=self.supplier_account,
            inventory_ledger=self.ledgers["INVENTORY"],
            payable_ledger=self.ledgers["ACCOUNTS_PAYABLE"],
            commodity=self.gold,
            gross_weight=gross_weight,
            purity=purity,
            fine_weight=fine_weight,
            from_commodity_account=self.supplier_commodity_account,
            to_commodity_account=self.vault,
            money_amount=money_amount,
            currency=currency,
            narration="Fixed purchase test",
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
            name="FIXED_PURCHASE_INVENTORY",
            defaults={
                "AccountType": asset_type,
                "code": f"1.FIXPUR.INV.{uuid.uuid4().hex[:6]}",
            },
        )
        accounts_payable, _ = Ledger.objects.get_or_create(
            name="FIXED_PURCHASE_AP",
            defaults={
                "AccountType": liability_type,
                "code": f"2.FIXPUR.AP.{uuid.uuid4().hex[:6]}",
            },
        )
        return {
            "INVENTORY": inventory,
            "ACCOUNTS_PAYABLE": accounts_payable,
        }
