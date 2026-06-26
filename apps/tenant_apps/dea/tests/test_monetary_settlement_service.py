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
    CommodityMovement,
    EntityType,
    ExposureLine,
    JournalEntry,
    Ledger,
    LedgerTransaction,
    PaymentVoucher,
    RateFixing,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherStatus,
)
from apps.tenant_apps.dea.services.monetary_settlement import (
    CUSTOMER_RECEIPT_VOUCHER_TYPE,
    SUPPLIER_PAYMENT_VOUCHER_TYPE,
    CustomerReceiptPayload,
    SupplierPaymentPayload,
    post_customer_receipt,
    post_supplier_payment,
)


User = get_user_model()


class MonetarySettlementServiceTests(TenantTestCase):
    test_schema_name = f"dea_monetary_settlement_{uuid.uuid4().hex[:8]}"
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
            username="dea-monetary-settlement-owner",
            defaults={"email": "dea-monetary-settlement-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-monetary-settlement-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-monetary-settlement-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-monetary-settlement-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        self.period = AccountingPeriod.objects.create(
            name="June 2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )
        self._seed_account_masters()
        self.ledgers = self._seed_ledgers()
        self.customer = Customer.objects.create(
            firstname="Settlement",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
        )
        self.supplier = Customer.objects.create(
            firstname="Settlement",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
        )
        self.customer_account = Account.objects.create(
            contact=self.customer,
            entity=EntityType.objects.get(name="Person"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Debtor"),
        )
        self.supplier_account = Account.objects.create(
            contact=self.supplier,
            entity=EntityType.objects.get(name="Organisation"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Creditor"),
        )

    def test_customer_receipt_posts_cash_debit_and_customer_credit_only(self):
        result = post_customer_receipt(self._receipt_payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertTrue(result.payment_voucher.posted)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, CUSTOMER_RECEIPT_VOUCHER_TYPE)

        ledger_txn = LedgerTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(ledger_txn.ledgerno_dr, self.ledgers["CASH"])
        self.assertEqual(ledger_txn.ledgerno, self.ledgers["ACCOUNTS_RECEIVABLE"])
        self.assertEqual(ledger_txn.amount.amount, Decimal("125000.000"))
        self.assertEqual(str(ledger_txn.amount.currency), "INR")

        account_txn = AccountTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(account_txn.Account, self.customer_account)
        self.assertEqual(account_txn.ledgerno, self.ledgers["ACCOUNTS_RECEIVABLE"])
        self.assertEqual(account_txn.XactTypeCode_id, "Cr")
        self.assertEqual(account_txn.amount.amount, Decimal("125000.00"))

        self.assertEqual(PaymentVoucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.filter(voucher=result.voucher).count(), 2)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_supplier_payment_posts_payable_debit_and_cash_credit_only(self):
        result = post_supplier_payment(self._payment_payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertTrue(result.payment_voucher.posted)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, SUPPLIER_PAYMENT_VOUCHER_TYPE)

        ledger_txn = LedgerTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(ledger_txn.ledgerno_dr, self.ledgers["ACCOUNTS_PAYABLE"])
        self.assertEqual(ledger_txn.ledgerno, self.ledgers["CASH"])
        self.assertEqual(ledger_txn.amount.amount, Decimal("87500.000"))
        self.assertEqual(str(ledger_txn.amount.currency), "INR")

        account_txn = AccountTransaction.objects.get(journal_entry=result.journal_entry)
        self.assertEqual(account_txn.Account, self.supplier_account)
        self.assertEqual(account_txn.ledgerno, self.ledgers["ACCOUNTS_PAYABLE"])
        self.assertEqual(account_txn.XactTypeCode_id, "Dr")
        self.assertEqual(account_txn.amount.amount, Decimal("87500.00"))

        self.assertEqual(PaymentVoucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.filter(voucher=result.voucher).count(), 2)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_customer_receipt_is_idempotent_for_same_source_reference(self):
        first = post_customer_receipt(self._receipt_payload(), actor=self.user)
        second = post_customer_receipt(self._receipt_payload(), actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.payment_voucher.pk, second.payment_voucher.pk)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(PaymentVoucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_changed_receipt_payload_for_same_reference_is_rejected(self):
        post_customer_receipt(self._receipt_payload(), actor=self.user)

        with self.assertRaises(ValidationError):
            post_customer_receipt(
                self._receipt_payload(money_amount=Decimal("126000.00")),
                actor=self.user,
            )

        self.assertEqual(PaymentVoucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_supplier_payment_rejects_closed_period(self):
        self.period.status = AccountingPeriod.PeriodStatus.CLOSED
        self.period.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            post_supplier_payment(self._payment_payload(), actor=self.user)

        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_monetary_settlement_rejects_non_inr_currency_for_mvp(self):
        with self.assertRaises(ValidationError):
            post_customer_receipt(
                self._receipt_payload(currency="USD"),
                actor=self.user,
            )

        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)

    def _receipt_payload(
        self,
        *,
        money_amount=Decimal("125000.00"),
        currency="INR",
        reference_number="RCP-SETTLE-001",
    ):
        return CustomerReceiptPayload(
            source=self.customer,
            receipt_date=date(2026, 6, 24),
            customer_account=self.customer_account,
            cash_or_bank_ledger=self.ledgers["CASH"],
            receivable_ledger=self.ledgers["ACCOUNTS_RECEIVABLE"],
            money_amount=money_amount,
            currency=currency,
            reference_number=reference_number,
            narration="Customer receipt settlement test",
        )

    def _payment_payload(
        self,
        *,
        money_amount=Decimal("87500.00"),
        currency="INR",
        reference_number="PAY-SETTLE-001",
    ):
        return SupplierPaymentPayload(
            source=self.supplier,
            payment_date=date(2026, 6, 24),
            supplier_account=self.supplier_account,
            payable_ledger=self.ledgers["ACCOUNTS_PAYABLE"],
            cash_or_bank_ledger=self.ledgers["CASH"],
            money_amount=money_amount,
            currency=currency,
            reference_number=reference_number,
            narration="Supplier payment settlement test",
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
        revenue_type, _ = AccountType.objects.get_or_create(
            AccountType="Revenue",
            defaults={"description": "Revenue", "code_prefix": "4"},
        )
        cash, _ = Ledger.objects.get_or_create(
            name="MONETARY_SETTLEMENT_CASH",
            defaults={
                "AccountType": asset_type,
                "code": f"1.MONSET.CASH.{uuid.uuid4().hex[:6]}",
            },
        )
        accounts_receivable, _ = Ledger.objects.get_or_create(
            name="MONETARY_SETTLEMENT_AR",
            defaults={
                "AccountType": asset_type,
                "code": f"1.MONSET.AR.{uuid.uuid4().hex[:6]}",
            },
        )
        accounts_payable, _ = Ledger.objects.get_or_create(
            name="MONETARY_SETTLEMENT_AP",
            defaults={
                "AccountType": liability_type,
                "code": f"2.MONSET.AP.{uuid.uuid4().hex[:6]}",
            },
        )
        Ledger.objects.get_or_create(
            name="MONETARY_SETTLEMENT_REVENUE",
            defaults={
                "AccountType": revenue_type,
                "code": f"4.MONSET.REV.{uuid.uuid4().hex[:6]}",
            },
        )
        return {
            "CASH": cash,
            "ACCOUNTS_RECEIVABLE": accounts_receivable,
            "ACCOUNTS_PAYABLE": accounts_payable,
        }
