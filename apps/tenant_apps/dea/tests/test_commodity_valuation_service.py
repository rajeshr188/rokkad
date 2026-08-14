import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
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
from apps.tenant_apps.dea.selectors.commodity import get_commodity_position_for_account
from apps.tenant_apps.dea.services.valuation import (
    VALUATION_MISSING_RATE,
    VALUATION_UNSUPPORTED_COMMODITY,
    VALUATION_UNSUPPORTED_CURRENCY,
    VALUATION_VALUED,
    value_exposure_lines,
    value_position_rows,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.rates.models import Rate, RateSource


User = get_user_model()


class CommodityValuationServiceTests(TenantTestCase):
    test_schema_name = f"dea_commodity_value_{uuid.uuid4().hex[:8]}"
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
            username="dea-commodity-value-owner",
            defaults={"email": "dea-commodity-value-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-commodity-value-tenant-{uuid.uuid4().hex[:8]}"
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
            location_label="Main vault",
        )
        self.adjustment = CommodityAccount.objects.create(
            code="GOLD_ADJUSTMENT",
            name="Gold adjustment",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.ADJUSTMENT,
        )
        self.rate_source = RateSource.objects.create(
            name="Local Market",
            location="Mumbai",
        )

    def test_position_valuation_uses_buying_rate_on_fine_weight(self):
        self._rate(
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6200.00"),
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
        self._movement(fine_weight=Decimal("91.600"))

        positions = get_commodity_position_for_account(self.vault)
        valued = value_position_rows(positions, as_of=date(2026, 6, 2))

        self.assertEqual(len(valued), 1)
        self.assertEqual(valued[0].valuation_status, VALUATION_VALUED)
        self.assertEqual(valued[0].valuation_rate, Decimal("6000.00"))
        self.assertEqual(valued[0].valuation_amount, Decimal("549600.00"))
        self.assertEqual(valued[0].valuation_currency, "INR")
        self.assertEqual(valued[0].rate_source_name, "Local Market")
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def test_position_valuation_uses_latest_rate_at_or_before_as_of(self):
        self._rate(
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6200.00"),
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
        self._rate(
            buying_rate=Decimal("6500.00"),
            selling_rate=Decimal("6700.00"),
            timestamp=datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc),
        )
        self._movement(fine_weight=Decimal("10.000"))

        positions = get_commodity_position_for_account(self.vault)
        valued = value_position_rows(positions, as_of=date(2026, 6, 5))

        self.assertEqual(valued[0].valuation_rate, Decimal("6000.00"))
        self.assertEqual(valued[0].valuation_amount, Decimal("60000.00"))

    def test_position_valuation_reports_missing_rate_without_zero_value(self):
        self._movement(fine_weight=Decimal("10.000"))

        positions = get_commodity_position_for_account(self.vault)
        valued = value_position_rows(positions, as_of=date(2026, 6, 5))

        self.assertEqual(valued[0].valuation_status, VALUATION_MISSING_RATE)
        self.assertIsNone(valued[0].valuation_rate)
        self.assertIsNone(valued[0].valuation_amount)

    def test_position_valuation_reports_unsupported_commodity(self):
        platinum = Commodity.objects.create(code="PLATINUM", name="Platinum")
        platinum_vault = CommodityAccount.objects.create(
            code="PLATINUM_VAULT",
            name="Platinum vault",
            commodity=platinum,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        platinum_adjustment = CommodityAccount.objects.create(
            code="PLATINUM_ADJ",
            name="Platinum adjustment",
            commodity=platinum,
            purpose=CommodityAccount.Purpose.ADJUSTMENT,
        )
        self._movement(
            commodity=platinum,
            from_account=platinum_adjustment,
            to_account=platinum_vault,
            fine_weight=Decimal("5.000"),
            movement_no="cm-platinum",
        )

        positions = get_commodity_position_for_account(platinum_vault)
        valued = value_position_rows(positions, as_of=date(2026, 6, 5))

        self.assertEqual(valued[0].valuation_status, VALUATION_UNSUPPORTED_COMMODITY)
        self.assertIsNone(valued[0].valuation_amount)

    def test_position_valuation_reports_unsupported_currency(self):
        self._movement(fine_weight=Decimal("10.000"))

        positions = get_commodity_position_for_account(self.vault)
        valued = value_position_rows(
            positions,
            as_of=date(2026, 6, 5),
            currency="EUR",
        )

        self.assertEqual(valued[0].valuation_status, VALUATION_UNSUPPORTED_CURRENCY)
        self.assertIsNone(valued[0].valuation_amount)

    def test_sale_exposure_valuation_uses_selling_rate(self):
        self._rate(
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6200.00"),
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
        exposure = self._exposure(side=ExposureLine.Side.SALE)

        valued = value_exposure_lines([exposure], as_of=date(2026, 6, 2))

        self.assertEqual(valued[0].valuation_status, VALUATION_VALUED)
        self.assertEqual(valued[0].valuation_rate, Decimal("6200.00"))
        self.assertEqual(valued[0].valuation_amount, Decimal("310000.00"))

    def test_purchase_exposure_valuation_uses_buying_rate(self):
        self._rate(
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6200.00"),
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
        exposure = self._exposure(side=ExposureLine.Side.PURCHASE)

        valued = value_exposure_lines([exposure], as_of=date(2026, 6, 2))

        self.assertEqual(valued[0].valuation_rate, Decimal("6000.00"))
        self.assertEqual(valued[0].valuation_amount, Decimal("300000.00"))

    def _rate(self, *, buying_rate, selling_rate, timestamp):
        rate = Rate.objects.create(
            metal=Rate.Metal.GOLD,
            currency=Rate.Currency.INR,
            purity=Rate.Purity.K24,
            buying_rate=buying_rate,
            selling_rate=selling_rate,
            rate_source=self.rate_source,
        )
        Rate.objects.filter(pk=rate.pk).update(timestamp=timestamp)
        rate.refresh_from_db()
        return rate

    def _movement(
        self,
        *,
        fine_weight,
        commodity=None,
        from_account=None,
        to_account=None,
        movement_no="cm-value",
    ):
        commodity = commodity or self.gold
        return CommodityMovement.objects.create(
            movement_no=movement_no,
            movement_date=date(2026, 6, 1),
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=commodity.pk,
            commodity=commodity,
            gross_weight=(fine_weight / Decimal("0.916")).quantize(Decimal("0.001")),
            purity=Decimal("0.916000"),
            fine_weight=fine_weight,
            from_account=from_account or self.adjustment,
            to_account=to_account or self.vault,
            movement_type=CommodityMovement.MovementType.OPENING,
            fixed_status=CommodityMovement.FixedStatus.NOT_APPLICABLE,
            idempotency_key=f"commodity:test:valuation:{movement_no}",
        )

    def _exposure(self, *, side):
        return ExposureLine.objects.create(
            exposure_no=f"exp-{side.lower()}",
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=self.gold.pk,
            party=self.party,
            commodity=self.gold,
            side=side,
            status=ExposureLine.Status.OPEN,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
            original_fine_weight=Decimal("50.000"),
            open_fine_weight=Decimal("50.000"),
            valuation_currency="INR",
            idempotency_key=f"commodity:test:valuation:exposure:{side}",
        )
