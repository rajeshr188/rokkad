import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    AccountTransaction,
    AccountingPeriod,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    ExposureLine,
    JournalEntry,
    LedgerTransaction,
    RateFixing,
    Voucher,
    VoucherLine,
    VoucherStatus,
)
from apps.tenant_apps.dea.services.karigar import (
    KARIGAR_ISSUE_VOUCHER_TYPE,
    KARIGAR_RECEIPT_VOUCHER_TYPE,
    KarigarIssuePayload,
    KarigarReceiptPayload,
    post_karigar_issue,
    post_karigar_receipt,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class KarigarServiceTests(TenantTestCase):
    test_schema_name = f"dea_karigar_{uuid.uuid4().hex[:8]}"
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
            username="dea-karigar-owner",
            defaults={"email": "dea-karigar-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-karigar-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-karigar-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-karigar-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        self.period = AccountingPeriod.objects.create(
            name="June 2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.source = Customer.objects.create(
            firstname="Karigar",
            lastname="Source",
            customer_type=Customer.CustomerType.Retail,
        )
        self.receipt_source = Customer.objects.create(
            firstname="Karigar",
            lastname="Receipt Source",
            customer_type=Customer.CustomerType.Retail,
        )
        self.karigar = Party.objects.create(display_name="Karigar One")
        self.other_karigar = Party.objects.create(display_name="Karigar Two")
        self.vault = CommodityAccount.objects.create(
            code="KARIGAR_GOLD_VAULT",
            name="Karigar gold vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        self.karigar_account = CommodityAccount.objects.create(
            code="KARIGAR_GOLD_CUSTODY",
            name="Karigar gold custody",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.KARIGAR_CUSTODY,
            party=self.karigar,
        )
        self.other_karigar_account = CommodityAccount.objects.create(
            code="KARIGAR_GOLD_OTHER_CUSTODY",
            name="Other karigar gold custody",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.KARIGAR_CUSTODY,
            party=self.other_karigar,
        )

    def test_karigar_issue_moves_metal_to_custody_only(self):
        result = post_karigar_issue(self._issue_payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, KARIGAR_ISSUE_VOUCHER_TYPE)
        self.assertTrue(result.voucher.fingerprint)

        movement = result.commodity_movement
        self.assertEqual(movement.voucher, result.voucher)
        self.assertEqual(movement.movement_type, CommodityMovement.MovementType.KARIGAR_ISSUE)
        self.assertEqual(movement.fixed_status, CommodityMovement.FixedStatus.NOT_APPLICABLE)
        self.assertEqual(movement.from_account, self.vault)
        self.assertEqual(movement.to_account, self.karigar_account)
        self.assertEqual(movement.fine_weight, Decimal("91.600"))
        self.assertEqual(movement.metadata["karigar_id"], self.karigar.pk)

        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assert_no_financial_or_exposure_rows()

    def test_karigar_receipt_moves_metal_back_from_custody_only(self):
        result = post_karigar_receipt(self._receipt_payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, KARIGAR_RECEIPT_VOUCHER_TYPE)
        self.assertTrue(result.voucher.fingerprint)

        movement = result.commodity_movement
        self.assertEqual(movement.voucher, result.voucher)
        self.assertEqual(movement.movement_type, CommodityMovement.MovementType.KARIGAR_RECEIPT)
        self.assertEqual(movement.fixed_status, CommodityMovement.FixedStatus.NOT_APPLICABLE)
        self.assertEqual(movement.from_account, self.karigar_account)
        self.assertEqual(movement.to_account, self.vault)
        self.assertEqual(movement.fine_weight, Decimal("90.000"))
        self.assertEqual(movement.metadata["karigar_id"], self.karigar.pk)

        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assert_no_financial_or_exposure_rows()

    def test_karigar_issue_is_idempotent_for_same_payload(self):
        first = post_karigar_issue(self._issue_payload(), actor=self.user)
        second = post_karigar_issue(self._issue_payload(), actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 1)

    def test_changed_karigar_issue_payload_for_same_source_is_rejected(self):
        post_karigar_issue(self._issue_payload(), actor=self.user)

        with self.assertRaises(ValidationError):
            post_karigar_issue(
                self._issue_payload(
                    gross_weight=Decimal("101.000"),
                    fine_weight=Decimal("92.516"),
                ),
                actor=self.user,
            )

        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 1)

    def test_karigar_receipt_rejects_mismatched_custody_party(self):
        with self.assertRaises(ValidationError):
            post_karigar_receipt(
                self._receipt_payload(from_karigar_account=self.other_karigar_account),
                actor=self.user,
            )

        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)

    def test_karigar_issue_rejects_closed_period(self):
        self.period.status = AccountingPeriod.PeriodStatus.CLOSED
        self.period.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            post_karigar_issue(self._issue_payload(), actor=self.user)

        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)

    def _issue_payload(
        self,
        *,
        gross_weight=Decimal("100.000"),
        purity=Decimal("0.916000"),
        fine_weight=Decimal("91.600"),
    ):
        return KarigarIssuePayload(
            source=self.source,
            issue_date=date(2026, 6, 24),
            karigar=self.karigar,
            commodity=self.gold,
            gross_weight=gross_weight,
            purity=purity,
            fine_weight=fine_weight,
            from_commodity_account=self.vault,
            to_karigar_account=self.karigar_account,
            narration="Karigar issue test",
        )

    def _receipt_payload(
        self,
        *,
        gross_weight=Decimal("100.000"),
        purity=Decimal("0.900000"),
        fine_weight=Decimal("90.000"),
        from_karigar_account=None,
    ):
        return KarigarReceiptPayload(
            source=self.receipt_source,
            receipt_date=date(2026, 6, 24),
            karigar=self.karigar,
            commodity=self.gold,
            gross_weight=gross_weight,
            purity=purity,
            fine_weight=fine_weight,
            from_karigar_account=from_karigar_account or self.karigar_account,
            to_commodity_account=self.vault,
            narration="Karigar receipt test",
        )

    def assert_no_financial_or_exposure_rows(self):
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)
