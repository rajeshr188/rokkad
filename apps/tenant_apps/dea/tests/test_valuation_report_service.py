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
    JournalEntry,
    LedgerTransaction,
    RateFixing,
    VoucherLine,
)
from apps.tenant_apps.dea.services.valuation import (
    VALUATION_MISSING_RATE,
    VALUATION_UNSUPPORTED_CURRENCY,
    VALUATION_UNSUPPORTED_PURITY,
    VALUATION_VALUED,
)
from apps.tenant_apps.dea.services.valuation_report import build_valuation_report
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.rates.models import Rate, RateSource


User = get_user_model()


class ValuationReportServiceTests(TenantTestCase):
    test_schema_name = f"dea_value_report_{uuid.uuid4().hex[:8]}"
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
            username="dea-value-report-owner",
            defaults={"email": "dea-value-report-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-value-report-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.party = Party.objects.create(display_name="Bullion Counterparty")
        self.vault = CommodityAccount.objects.create(
            code="GOLD_VAULT",
            name="Gold vault",
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
            name="Local Bullion",
            location="Mumbai",
        )

    def test_report_values_positions_and_exposures_with_side_rates(self):
        self._rate(
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6200.00"),
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
        self._movement(fine_weight=Decimal("10.000"))
        self._exposure(
            exposure_no="exp-purchase",
            side=ExposureLine.Side.PURCHASE,
            open_fine_weight=Decimal("5.000"),
        )
        self._exposure(
            exposure_no="exp-sale",
            side=ExposureLine.Side.SALE,
            open_fine_weight=Decimal("4.000"),
        )

        report = build_valuation_report(as_of=date(2026, 6, 24))

        self.assertEqual(len(report.position_rows), 1)
        self.assertEqual(len(report.exposure_rows), 2)
        self.assertEqual(report.position_rows[0].valuation_status, VALUATION_VALUED)
        self.assertEqual(report.position_rows[0].valuation_rate, Decimal("6000.00"))
        self.assertEqual(report.position_rows[0].valuation_amount, Decimal("60000.00"))

        exposures_by_no = {row.exposure_no: row for row in report.exposure_rows}
        self.assertEqual(exposures_by_no["EXP-PURCHASE"].valuation_rate, Decimal("6000.00"))
        self.assertEqual(exposures_by_no["EXP-PURCHASE"].valuation_amount, Decimal("30000.00"))
        self.assertEqual(exposures_by_no["EXP-SALE"].valuation_rate, Decimal("6200.00"))
        self.assertEqual(exposures_by_no["EXP-SALE"].valuation_amount, Decimal("24800.00"))

        self.assertEqual(len(report.totals_by_status), 1)
        self.assertEqual(report.totals_by_status[0].valuation_status, VALUATION_VALUED)
        self.assertEqual(report.totals_by_status[0].row_count, 3)
        self.assertEqual(report.totals_by_status[0].valuation_amount, Decimal("114800.00"))

    def test_report_marks_missing_rate_without_silent_zero_value(self):
        self._movement(fine_weight=Decimal("10.000"))
        self._exposure(
            exposure_no="exp-missing-rate",
            side=ExposureLine.Side.PURCHASE,
            open_fine_weight=Decimal("5.000"),
        )

        report = build_valuation_report(as_of=date(2026, 6, 24))

        self.assertEqual(report.position_rows[0].valuation_status, VALUATION_MISSING_RATE)
        self.assertIsNone(report.position_rows[0].valuation_amount)
        self.assertEqual(report.exposure_rows[0].valuation_status, VALUATION_MISSING_RATE)
        self.assertIsNone(report.exposure_rows[0].valuation_amount)
        self.assertEqual(report.totals_by_status[0].valuation_status, VALUATION_MISSING_RATE)
        self.assertEqual(report.totals_by_status[0].row_count, 2)
        self.assertIsNone(report.totals_by_status[0].valuation_amount)

    def test_report_surfaces_unsupported_currency_and_purity_statuses(self):
        self._movement(fine_weight=Decimal("10.000"))

        unsupported_currency = build_valuation_report(
            as_of=date(2026, 6, 24),
            valuation_currency="EUR",
        )
        unsupported_purity = build_valuation_report(
            as_of=date(2026, 6, 24),
            valuation_purity="21k",
        )

        self.assertEqual(
            unsupported_currency.position_rows[0].valuation_status,
            VALUATION_UNSUPPORTED_CURRENCY,
        )
        self.assertEqual(
            unsupported_purity.position_rows[0].valuation_status,
            VALUATION_UNSUPPORTED_PURITY,
        )
        self.assertIsNone(unsupported_currency.position_rows[0].valuation_amount)
        self.assertIsNone(unsupported_purity.position_rows[0].valuation_amount)

    def test_report_is_read_only_and_creates_no_financial_or_fixing_rows(self):
        self._rate(
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6200.00"),
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        )
        self._movement(fine_weight=Decimal("10.000"))
        self._exposure(
            exposure_no="exp-read-only",
            side=ExposureLine.Side.SALE,
            open_fine_weight=Decimal("5.000"),
        )

        before = {
            "journal_entries": JournalEntry.objects.count(),
            "voucher_lines": VoucherLine.objects.count(),
            "ledger_transactions": LedgerTransaction.objects.count(),
            "account_transactions": AccountTransaction.objects.count(),
            "rate_fixings": RateFixing.objects.count(),
            "rates": Rate.objects.count(),
            "movements": CommodityMovement.objects.count(),
            "exposures": ExposureLine.objects.count(),
        }

        report = build_valuation_report(as_of=date(2026, 6, 24))

        self.assertEqual(len(report.position_rows), 1)
        self.assertEqual(len(report.exposure_rows), 1)
        self.assertEqual(
            {
                "journal_entries": JournalEntry.objects.count(),
                "voucher_lines": VoucherLine.objects.count(),
                "ledger_transactions": LedgerTransaction.objects.count(),
                "account_transactions": AccountTransaction.objects.count(),
                "rate_fixings": RateFixing.objects.count(),
                "rates": Rate.objects.count(),
                "movements": CommodityMovement.objects.count(),
                "exposures": ExposureLine.objects.count(),
            },
            before,
        )

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

    def _movement(self, *, fine_weight):
        return CommodityMovement.objects.create(
            movement_no=f"cm-{uuid.uuid4().hex[:8]}",
            movement_date=date(2026, 6, 1),
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=self.gold.pk,
            commodity=self.gold,
            gross_weight=(fine_weight / Decimal("0.916")).quantize(Decimal("0.001")),
            purity=Decimal("0.916000"),
            fine_weight=fine_weight,
            from_account=self.adjustment,
            to_account=self.vault,
            movement_type=CommodityMovement.MovementType.OPENING,
            fixed_status=CommodityMovement.FixedStatus.NOT_APPLICABLE,
            idempotency_key=f"commodity:test:valuation-report:movement:{uuid.uuid4().hex}",
        )

    def _exposure(self, *, exposure_no, side, open_fine_weight):
        return ExposureLine.objects.create(
            exposure_no=exposure_no,
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=self.gold.pk,
            party=self.party,
            commodity=self.gold,
            side=side,
            status=ExposureLine.Status.OPEN,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
            original_fine_weight=open_fine_weight,
            open_fine_weight=open_fine_weight,
            valuation_currency="INR",
            idempotency_key=f"commodity:test:valuation-report:exposure:{exposure_no}",
        )
