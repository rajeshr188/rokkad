import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.dea.models import (
    AccountTransaction,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    ExposureLine,
    LedgerTransaction,
)
from apps.tenant_apps.dea.services.commodity_posting import (
    CommodityMovementPayload,
    ExposurePayload,
    open_exposure,
    post_commodity_movement,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class CommodityPostingServiceTests(TenantTestCase):
    test_schema_name = f"dea_commodity_posting_{uuid.uuid4().hex[:8]}"
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
            username="dea-commodity-posting-owner",
            defaults={"email": "dea-commodity-posting-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-commodity-posting-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.party = Party.objects.create(display_name="Bullion Supplier")
        self.vault = CommodityAccount.objects.create(
            code="GOLD_MAIN_VAULT",
            name="Gold main vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        self.supplier = CommodityAccount.objects.create(
            code="GOLD_SUPPLIER_PAYABLE",
            name="Gold supplier payable",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.PARTY_PAYABLE,
            party=self.party,
        )

    def test_post_commodity_movement_creates_immutable_movement(self):
        result = post_commodity_movement(self._movement_payload())

        self.assertTrue(result.created)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(result.record.commodity, self.gold)
        self.assertEqual(result.record.to_account, self.vault)
        self.assertTrue(result.record.idempotency_key.startswith("commodity:movement:"))
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def test_post_commodity_movement_is_idempotent_for_same_payload(self):
        first = post_commodity_movement(self._movement_payload())
        second = post_commodity_movement(self._movement_payload())

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.record.pk, second.record.pk)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_changed_movement_payload_creates_distinct_idempotency_key(self):
        first = post_commodity_movement(self._movement_payload())
        changed = post_commodity_movement(
            self._movement_payload(
                gross_weight=Decimal("101.000"),
                fine_weight=Decimal("92.516"),
            )
        )

        self.assertTrue(first.created)
        self.assertTrue(changed.created)
        self.assertNotEqual(first.record.idempotency_key, changed.record.idempotency_key)
        self.assertEqual(CommodityMovement.objects.count(), 2)

    def test_open_exposure_creates_exposure_line(self):
        result = open_exposure(self._exposure_payload())

        self.assertTrue(result.created)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(result.record.party, self.party)
        self.assertEqual(result.record.commodity, self.gold)
        self.assertEqual(result.record.open_fine_weight, Decimal("91.600"))
        self.assertTrue(result.record.idempotency_key.startswith("commodity:exposure:"))

    def test_open_exposure_is_idempotent_for_same_payload(self):
        first = open_exposure(self._exposure_payload())
        second = open_exposure(self._exposure_payload())

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.record.pk, second.record.pk)
        self.assertEqual(ExposureLine.objects.count(), 1)

    def test_changed_exposure_payload_creates_distinct_record(self):
        first = open_exposure(self._exposure_payload())
        changed = open_exposure(
            self._exposure_payload(
                original_fine_weight=Decimal("50.000"),
                open_fine_weight=Decimal("50.000"),
            )
        )

        self.assertTrue(first.created)
        self.assertTrue(changed.created)
        self.assertNotEqual(first.record.idempotency_key, changed.record.idempotency_key)
        self.assertEqual(ExposureLine.objects.count(), 2)

    def _movement_payload(
        self,
        *,
        gross_weight=Decimal("100.000"),
        purity=Decimal("0.916000"),
        fine_weight=Decimal("91.600"),
    ):
        return CommodityMovementPayload(
            source=self.gold,
            event_type="purchase-receipt",
            movement_date=date(2026, 6, 24),
            commodity=self.gold,
            gross_weight=gross_weight,
            purity=purity,
            fine_weight=fine_weight,
            from_account=self.supplier,
            to_account=self.vault,
            movement_type=CommodityMovement.MovementType.PURCHASE_RECEIPT,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
            rate=Decimal("6200.0000"),
            rate_currency="INR",
            valuation_currency="INR",
            valuation_amount=Decimal("567920.00"),
            narration="Unfixed purchase receipt",
        )

    def _exposure_payload(
        self,
        *,
        original_fine_weight=Decimal("91.600"),
        open_fine_weight=Decimal("91.600"),
    ):
        return ExposurePayload(
            source=self.gold,
            event_type="purchase-exposure",
            party=self.party,
            commodity=self.gold,
            side=ExposureLine.Side.PURCHASE,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
            original_fine_weight=original_fine_weight,
            open_fine_weight=open_fine_weight,
            rate_basis="Manual unfixed purchase",
            valuation_currency="INR",
        )
