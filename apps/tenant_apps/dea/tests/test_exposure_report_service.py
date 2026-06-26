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
    CommodityMovement,
    ExposureLine,
    JournalEntry,
    LedgerTransaction,
    VoucherLine,
)
from apps.tenant_apps.dea.services.exposure_report import build_exposure_report
from apps.tenant_apps.dea.services.valuation import VALUATION_VALUED
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.rates.models import Rate, RateSource


User = get_user_model()


class ExposureReportServiceTests(TenantTestCase):
    test_schema_name = f"dea_exposure_report_{uuid.uuid4().hex[:8]}"
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
            username="dea-exposure-report-owner",
            defaults={"email": "dea-exposure-report-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-exposure-report-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.silver = Commodity.objects.create(code="SILVER", name="Silver")
        self.supplier = Party.objects.create(display_name="Bullion Supplier")
        self.customer = Party.objects.create(display_name="Retail Customer")
        self.rate_source = RateSource.objects.create(
            name="Local Market",
            location="Mumbai",
        )

    def test_report_defaults_to_active_exposures_and_totals_by_commodity_side_status(self):
        self._exposure(
            exposure_no="exp-purchase-open",
            party=self.supplier,
            commodity=self.gold,
            side=ExposureLine.Side.PURCHASE,
            status=ExposureLine.Status.OPEN,
            original_fine_weight=Decimal("100.000"),
            open_fine_weight=Decimal("100.000"),
        )
        self._exposure(
            exposure_no="exp-sale-partial",
            party=self.customer,
            commodity=self.gold,
            side=ExposureLine.Side.SALE,
            status=ExposureLine.Status.PARTIALLY_FIXED,
            fixed_status=CommodityMovement.FixedStatus.PARTIALLY_FIXED,
            original_fine_weight=Decimal("75.000"),
            open_fine_weight=Decimal("25.000"),
        )
        self._exposure(
            exposure_no="exp-fixed-excluded",
            party=self.supplier,
            commodity=self.gold,
            side=ExposureLine.Side.PURCHASE,
            status=ExposureLine.Status.FIXED,
            fixed_status=CommodityMovement.FixedStatus.FIXED,
            original_fine_weight=Decimal("40.000"),
            open_fine_weight=Decimal("0.000"),
        )

        report = build_exposure_report()

        self.assertEqual([row.exposure_no for row in report.rows], ["EXP-PURCHASE-OPEN", "EXP-SALE-PARTIAL"])
        totals = {(total.side, total.status): total for total in report.totals}
        self.assertEqual(
            totals[(ExposureLine.Side.PURCHASE, ExposureLine.Status.OPEN)].open_fine_weight,
            Decimal("100.000"),
        )
        self.assertEqual(
            totals[(ExposureLine.Side.SALE, ExposureLine.Status.PARTIALLY_FIXED)].open_fine_weight,
            Decimal("25.000"),
        )

    def test_report_filters_by_party_commodity_side_status_and_as_of(self):
        before = self._exposure(
            exposure_no="exp-before",
            party=self.supplier,
            commodity=self.gold,
            side=ExposureLine.Side.PURCHASE,
            status=ExposureLine.Status.OPEN,
        )
        after = self._exposure(
            exposure_no="exp-after",
            party=self.customer,
            commodity=self.silver,
            side=ExposureLine.Side.SALE,
            status=ExposureLine.Status.OPEN,
        )
        ExposureLine.objects.filter(pk=before.pk).update(
            created_at=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        )
        ExposureLine.objects.filter(pk=after.pk).update(
            created_at=datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)
        )

        report = build_exposure_report(
            as_of=date(2026, 6, 5),
            party=self.supplier,
            commodity=self.gold,
            side=ExposureLine.Side.PURCHASE,
            statuses=(ExposureLine.Status.OPEN,),
        )

        self.assertEqual(len(report.rows), 1)
        self.assertEqual(report.rows[0].exposure_no, "EXP-BEFORE")
        self.assertEqual(report.party_id, self.supplier.pk)
        self.assertEqual(report.commodity_id, self.gold.pk)
        self.assertEqual(report.side, ExposureLine.Side.PURCHASE)
        self.assertEqual(report.statuses, (ExposureLine.Status.OPEN,))

    def test_report_can_include_valuation_without_financial_side_effects(self):
        self._rate(
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6200.00"),
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
        purchase_exposure = self._exposure(
            exposure_no="exp-valued-purchase",
            party=self.supplier,
            commodity=self.gold,
            side=ExposureLine.Side.PURCHASE,
            status=ExposureLine.Status.OPEN,
            original_fine_weight=Decimal("50.000"),
            open_fine_weight=Decimal("50.000"),
        )
        sale_exposure = self._exposure(
            exposure_no="exp-valued-sale",
            party=self.customer,
            commodity=self.gold,
            side=ExposureLine.Side.SALE,
            status=ExposureLine.Status.OPEN,
            original_fine_weight=Decimal("25.000"),
            open_fine_weight=Decimal("25.000"),
        )
        ExposureLine.objects.filter(pk__in=[purchase_exposure.pk, sale_exposure.pk]).update(
            created_at=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
        )

        report = build_exposure_report(
            as_of=date(2026, 6, 2),
            include_valuation=True,
        )

        rows = {row.exposure_no: row for row in report.rows}
        self.assertEqual(rows["EXP-VALUED-PURCHASE"].valuation_status, VALUATION_VALUED)
        self.assertEqual(rows["EXP-VALUED-PURCHASE"].valuation_rate, Decimal("6000.00"))
        self.assertEqual(rows["EXP-VALUED-PURCHASE"].valuation_amount, Decimal("300000.00"))
        self.assertEqual(rows["EXP-VALUED-SALE"].valuation_rate, Decimal("6200.00"))
        self.assertEqual(rows["EXP-VALUED-SALE"].valuation_amount, Decimal("155000.00"))
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def test_report_without_valuation_does_not_lookup_or_fill_valuation_fields(self):
        self._exposure(
            exposure_no="exp-no-value",
            party=self.supplier,
            commodity=self.gold,
            side=ExposureLine.Side.PURCHASE,
            status=ExposureLine.Status.OPEN,
        )

        report = build_exposure_report(include_valuation=False)

        self.assertFalse(report.include_valuation)
        self.assertEqual(report.rows[0].valuation_status, "")
        self.assertIsNone(report.rows[0].valuation_rate)
        self.assertIsNone(report.rows[0].valuation_amount)

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

    def _exposure(
        self,
        *,
        exposure_no,
        party,
        commodity,
        side,
        status,
        fixed_status=CommodityMovement.FixedStatus.UNFIXED,
        original_fine_weight=Decimal("50.000"),
        open_fine_weight=Decimal("50.000"),
    ):
        return ExposureLine.objects.create(
            exposure_no=exposure_no,
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=commodity.pk,
            party=party,
            commodity=commodity,
            side=side,
            status=status,
            fixed_status=fixed_status,
            original_fine_weight=original_fine_weight,
            open_fine_weight=open_fine_weight,
            rate_basis="Exposure report test",
            valuation_currency="INR",
            idempotency_key=f"commodity:test:exposure-report:{exposure_no}",
        )
