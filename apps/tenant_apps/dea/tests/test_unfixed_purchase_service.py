import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.dea.models import (
    AccountTransaction,
    AccountingPeriod,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    ExposureLine,
    JournalEntry,
    LedgerTransaction,
    Voucher,
    VoucherLine,
    VoucherStatus,
)
from apps.tenant_apps.dea.services.unfixed_purchase import (
    UNFIXED_PURCHASE_VOUCHER_TYPE,
    UnfixedPurchasePostingPayload,
    post_unfixed_purchase,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class UnfixedPurchaseServiceTests(TenantTestCase):
    test_schema_name = f"dea_unfixed_purchase_{uuid.uuid4().hex[:8]}"
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
            username="dea-unfixed-purchase-owner",
            defaults={"email": "dea-unfixed-purchase-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-unfixed-purchase-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-unfixed-purchase-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-unfixed-purchase-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        self.period = AccountingPeriod.objects.create(
            name="June 2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.party = Party.objects.create(display_name="Unfixed Purchase Supplier")
        self.supplier_customer = self.party
        self.vault = CommodityAccount.objects.create(
            code="UNFIXED_PURCHASE_GOLD_VAULT",
            name="Unfixed purchase gold vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        self.supplier_commodity_account = CommodityAccount.objects.create(
            code="UNFIXED_PURCHASE_GOLD_SUPPLIER",
            name="Unfixed purchase supplier gold payable",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.PARTY_PAYABLE,
            party=self.party,
        )

    def test_unfixed_purchase_posts_commodity_movement_and_open_exposure_only(self):
        result = post_unfixed_purchase(self._payload(), actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.status, VoucherStatus.POSTED)
        self.assertEqual(result.voucher.voucher_type.name, UNFIXED_PURCHASE_VOUCHER_TYPE)
        self.assertTrue(result.voucher.fingerprint)

        movement = result.commodity_movement
        self.assertEqual(movement.voucher, result.voucher)
        self.assertEqual(movement.commodity, self.gold)
        self.assertEqual(movement.from_account, self.supplier_commodity_account)
        self.assertEqual(movement.to_account, self.vault)
        self.assertEqual(movement.fixed_status, CommodityMovement.FixedStatus.UNFIXED)
        self.assertEqual(movement.movement_type, CommodityMovement.MovementType.PURCHASE_RECEIPT)
        self.assertEqual(movement.fine_weight, Decimal("91.600"))
        self.assertEqual(movement.rate_currency, "")
        self.assertIsNone(movement.valuation_amount)

        exposure = result.exposure
        self.assertEqual(exposure.voucher, result.voucher)
        self.assertEqual(exposure.party, self.party)
        self.assertEqual(exposure.side, ExposureLine.Side.PURCHASE)
        self.assertEqual(exposure.status, ExposureLine.Status.OPEN)
        self.assertEqual(exposure.fixed_status, CommodityMovement.FixedStatus.UNFIXED)
        self.assertEqual(exposure.original_fine_weight, Decimal("91.600"))
        self.assertEqual(exposure.open_fine_weight, Decimal("91.600"))
        self.assertEqual(exposure.valuation_currency, "INR")
        self.assertEqual(exposure.rate_basis, "Supplier call fixing")

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def test_unfixed_purchase_is_idempotent_for_same_payload(self):
        first = post_unfixed_purchase(self._payload(), actor=self.user)
        second = post_unfixed_purchase(self._payload(), actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(first.exposure.pk, second.exposure.pk)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)

    def test_changed_payload_for_same_source_is_rejected_until_correction_exists(self):
        post_unfixed_purchase(self._payload(), actor=self.user)

        with self.assertRaises(ValidationError):
            post_unfixed_purchase(
                self._payload(
                    gross_weight=Decimal("101.000"),
                    fine_weight=Decimal("92.516"),
                ),
                actor=self.user,
            )

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)

    def test_unfixed_purchase_rolls_back_when_exposure_validation_fails(self):
        with self.assertRaises(ValidationError):
            post_unfixed_purchase(
                self._payload(valuation_currency="GLD"),
                actor=self.user,
            )

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_unfixed_purchase_rejects_closed_period(self):
        self.period.status = AccountingPeriod.PeriodStatus.CLOSED
        self.period.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            post_unfixed_purchase(self._payload(), actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)

    def _payload(
        self,
        *,
        gross_weight=Decimal("100.000"),
        purity=Decimal("0.916000"),
        fine_weight=Decimal("91.600"),
        valuation_currency="INR",
    ):
        return UnfixedPurchasePostingPayload(
            source=self.supplier_customer,
            purchase_date=date(2026, 6, 24),
            party=self.party,
            commodity=self.gold,
            gross_weight=gross_weight,
            purity=purity,
            fine_weight=fine_weight,
            from_commodity_account=self.supplier_commodity_account,
            to_commodity_account=self.vault,
            rate_basis="Supplier call fixing",
            valuation_currency=valuation_currency,
            narration="Unfixed purchase test",
        )
