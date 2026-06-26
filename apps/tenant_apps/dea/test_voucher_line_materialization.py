from datetime import date
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.contact.models import Customer

from .models import (
    Account,
    AccountType,
    AccountType_Ext,
    AccountingPeriod,
    EntityType,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherType,
    Ledger,
)
from .services.materialize_journal import (
    materialize_journal_from_voucher_lines,
    sync_voucher_lines_from_bundle,
)
from apps.tenant_apps.dea.posting.types import AccountLine, DualLedgerLine, PostingBundle


User = get_user_model()


class VoucherLineMaterializationTests(TenantTestCase):
    test_schema_name = f"test_dea_voucher_lines_{uuid.uuid4().hex[:8]}"
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
            username="dea-vl-owner",
            defaults={"email": "dea-vl-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"dea-vl-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-vl-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-vl-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )

        self.period = AccountingPeriod.objects.create(
            name="May 2026",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
        )

        asset_type = AccountType.objects.create(
            AccountType="Asset", description="Asset", code_prefix="1"
        )
        equity_type = AccountType.objects.create(
            AccountType="Equity", description="Equity", code_prefix="3"
        )

        self.cash = Ledger.objects.create(
            AccountType=asset_type,
            name="Cash-VL-Test",
            code="1.TEST.VL.CASH",
        )
        self.capital = Ledger.objects.create(
            AccountType=equity_type,
            name="Capital-VL-Test",
            code="3.TEST.VL.CAPITAL",
        )

        dr_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        TransactionType_DE.objects.get_or_create(
            XactTypeCode="Cr",
            defaults={"name": "Credit"},
        )
        ext, _ = AccountType_Ext.objects.get_or_create(
            XactTypeCode=dr_code,
            description="Sundry Debtor - VL Test",
        )
        entity, _ = EntityType.objects.get_or_create(name="Person")

        customer = Customer.objects.create(
            firstname="Voucher",
            lastname="Line",
            customer_type=Customer.CustomerType.Retail,
        )
        self.account, _ = Account.objects.get_or_create(
            contact=customer,
            defaults={
                "entity": entity,
                "AccountType_Ext": ext,
            },
        )

        voucher_type = VoucherType.objects.create(name="MANUAL_VL", description="Manual")
        self.voucher = Voucher.objects.create(
            voucher_no="VL-TEST-001",
            voucher_type=voucher_type,
            voucher_date=self.period.end_date,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(AccountingPeriod),
            doc_object_id=self.period.pk,
            fingerprint="vl-materialization",
        )

    def test_materialize_creates_ledger_and_account_transactions(self):
        VoucherLine.objects.create(
            voucher=self.voucher,
            line_no=1,
            side=VoucherLine.LineSide.DR,
            ledger=self.cash,
            account=self.account,
            amount=Money(500, "INR"),
            amount_base=Money(500, "INR"),
            xact_type_ext="TXN",
            narration="Cash introduced",
        )
        VoucherLine.objects.create(
            voucher=self.voucher,
            line_no=2,
            side=VoucherLine.LineSide.CR,
            ledger=self.capital,
            amount=Money(500, "INR"),
            amount_base=Money(500, "INR"),
            xact_type_ext="TXN",
            narration="Capital credit",
        )

        je = materialize_journal_from_voucher_lines(
            voucher=self.voucher,
            posted_by_id=self.user.id,
            period=self.period,
        )

        self.assertEqual(je.ltxns.count(), 1)
        ledger_txn = je.ltxns.get()
        self.assertEqual(ledger_txn.ledgerno_dr_id, self.cash.id)
        self.assertEqual(ledger_txn.ledgerno_id, self.capital.id)
        self.assertEqual(ledger_txn.amount, Money(500, "INR"))

        self.assertEqual(je.atxns.count(), 1)
        account_txn = je.atxns.get()
        self.assertEqual(account_txn.Account_id, self.account.id)
        self.assertEqual(account_txn.ledgerno_id, self.cash.id)
        self.assertEqual(account_txn.XactTypeCode_id, "Dr")
        self.assertEqual(account_txn.amount, Money(500, "INR"))

    def test_sync_voucher_lines_from_bundle_preserves_unmatched_account_lines(self):
        bundle = PostingBundle(
            ledger_lines=[
                DualLedgerLine(
                    debit_ledger_id=self.cash.id,
                    credit_ledger_id=self.capital.id,
                    currency="INR",
                    amount=Decimal("500"),
                    amount_base=Decimal("500"),
                )
            ],
            account_lines=[
                AccountLine(
                    ledger_id=self.capital.id,
                    account_id=self.account.id,
                    side="Dr",
                    currency="INR",
                    amount=Decimal("500"),
                    amount_base=Decimal("500"),
                    xact_type_ext="TXN",
                )
            ],
        )

        # Use a voucher that is still draft-like for line sync
        sync_voucher_lines_from_bundle(self.voucher, bundle)

        lines = list(VoucherLine.objects.filter(voucher=self.voucher).order_by("line_no"))
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0].ledger_id, self.cash.id)
        self.assertEqual(lines[0].side, VoucherLine.LineSide.DR)
        self.assertIsNone(lines[0].account_id)
        self.assertEqual(lines[1].ledger_id, self.capital.id)
        self.assertEqual(lines[1].side, VoucherLine.LineSide.CR)
        self.assertIsNone(lines[1].account_id)
        self.assertEqual(lines[2].ledger_id, self.capital.id)
        self.assertEqual(lines[2].side, VoucherLine.LineSide.DR)
        self.assertEqual(lines[2].account_id, self.account.id)
