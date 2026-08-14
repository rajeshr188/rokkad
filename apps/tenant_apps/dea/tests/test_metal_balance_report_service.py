import uuid
from datetime import date
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
    JournalEntry,
    LedgerTransaction,
    VoucherLine,
)
from apps.tenant_apps.dea.services.metal_balance_report import (
    build_metal_balance_report,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class MetalBalanceReportServiceTests(TenantTestCase):
    test_schema_name = f"dea_metal_report_{uuid.uuid4().hex[:8]}"
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
            username="dea-metal-report-owner",
            defaults={"email": "dea-metal-report-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-metal-report-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.silver = Commodity.objects.create(code="SILVER", name="Silver")
        self.karigar_party = Party.objects.create(display_name="Karigar A")
        self.gold_vault = CommodityAccount.objects.create(
            code="GOLD_MAIN_VAULT",
            name="Gold main vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
            location_label="Main vault",
        )
        self.gold_karigar = CommodityAccount.objects.create(
            code="GOLD_KARIGAR_A",
            name="Gold with Karigar A",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.KARIGAR_CUSTODY,
            party=self.karigar_party,
            location_label="Karigar A",
        )
        self.gold_adjustment = CommodityAccount.objects.create(
            code="GOLD_ADJUSTMENT",
            name="Gold adjustment",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.ADJUSTMENT,
        )
        self.silver_vault = CommodityAccount.objects.create(
            code="SILVER_MAIN_VAULT",
            name="Silver main vault",
            commodity=self.silver,
            purpose=CommodityAccount.Purpose.VAULT,
            location_label="Main vault",
        )
        self.silver_adjustment = CommodityAccount.objects.create(
            code="SILVER_ADJUSTMENT",
            name="Silver adjustment",
            commodity=self.silver,
            purpose=CommodityAccount.Purpose.ADJUSTMENT,
        )

    def test_report_returns_account_rows_and_commodity_totals(self):
        self._movement(
            movement_no="gold-opening",
            movement_date=date(2026, 6, 1),
            commodity=self.gold,
            from_account=self.gold_adjustment,
            to_account=self.gold_vault,
            gross_weight=Decimal("100.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("91.600"),
            movement_type=CommodityMovement.MovementType.OPENING,
        )
        self._movement(
            movement_no="gold-karigar-issue",
            movement_date=date(2026, 6, 2),
            commodity=self.gold,
            from_account=self.gold_vault,
            to_account=self.gold_karigar,
            gross_weight=Decimal("25.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("22.900"),
            movement_type=CommodityMovement.MovementType.KARIGAR_ISSUE,
        )
        self._movement(
            movement_no="silver-opening",
            movement_date=date(2026, 6, 1),
            commodity=self.silver,
            from_account=self.silver_adjustment,
            to_account=self.silver_vault,
            gross_weight=Decimal("200.000"),
            purity=Decimal("0.999000"),
            fine_weight=Decimal("199.800"),
            movement_type=CommodityMovement.MovementType.OPENING,
        )

        report = build_metal_balance_report()

        rows = {row.account_code: row for row in report.rows}
        self.assertEqual(rows["GOLD_MAIN_VAULT"].fine_weight, Decimal("68.700"))
        self.assertEqual(rows["GOLD_KARIGAR_A"].fine_weight, Decimal("22.900"))
        self.assertEqual(rows["SILVER_MAIN_VAULT"].fine_weight, Decimal("199.800"))
        totals = {total.commodity_code: total for total in report.totals_by_commodity}
        self.assertEqual(totals["GOLD"].fine_weight, Decimal("91.600"))
        self.assertEqual(totals["SILVER"].fine_weight, Decimal("199.800"))

    def test_report_filters_by_party_location_and_as_of_date(self):
        self._movement(
            movement_no="party-before",
            movement_date=date(2026, 6, 1),
            commodity=self.gold,
            from_account=self.gold_vault,
            to_account=self.gold_karigar,
            gross_weight=Decimal("30.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("27.480"),
            movement_type=CommodityMovement.MovementType.KARIGAR_ISSUE,
        )
        self._movement(
            movement_no="party-after",
            movement_date=date(2026, 6, 10),
            commodity=self.gold,
            from_account=self.gold_karigar,
            to_account=self.gold_vault,
            gross_weight=Decimal("10.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("9.160"),
            movement_type=CommodityMovement.MovementType.KARIGAR_RECEIPT,
        )

        report = build_metal_balance_report(
            as_of=date(2026, 6, 5),
            party=self.karigar_party,
            location_label="Karigar A",
        )

        self.assertEqual(len(report.rows), 1)
        self.assertEqual(report.rows[0].account_code, "GOLD_KARIGAR_A")
        self.assertEqual(report.rows[0].fine_weight, Decimal("27.480"))
        self.assertEqual(report.totals_by_commodity[0].fine_weight, Decimal("27.480"))

    def test_report_can_filter_by_fixed_status(self):
        self._movement(
            movement_no="fixed-gold",
            movement_date=date(2026, 6, 1),
            commodity=self.gold,
            from_account=self.gold_adjustment,
            to_account=self.gold_vault,
            fixed_status=CommodityMovement.FixedStatus.FIXED,
        )
        self._movement(
            movement_no="unfixed-gold",
            movement_date=date(2026, 6, 2),
            commodity=self.gold,
            from_account=self.gold_adjustment,
            to_account=self.gold_vault,
            gross_weight=Decimal("50.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("45.800"),
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
        )

        report = build_metal_balance_report(
            commodity=self.gold,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
        )

        self.assertEqual(len(report.rows), 1)
        self.assertEqual(report.rows[0].fixed_status, CommodityMovement.FixedStatus.UNFIXED)
        self.assertEqual(report.totals_by_commodity[0].fine_weight, Decimal("45.800"))
        self.assertEqual(report.totals_by_status[0].fine_weight, Decimal("45.800"))

    def test_report_is_commodity_only_and_does_not_create_financial_rows(self):
        self._movement(
            movement_no="commodity-only",
            movement_date=date(2026, 6, 1),
            commodity=self.gold,
            from_account=self.gold_adjustment,
            to_account=self.gold_vault,
        )

        report = build_metal_balance_report(account=self.gold_vault)

        self.assertEqual(len(report.rows), 1)
        self.assertEqual(report.rows[0].fine_weight, Decimal("91.600"))
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def _movement(
        self,
        *,
        movement_no,
        movement_date,
        commodity,
        from_account,
        to_account,
        gross_weight=Decimal("100.000"),
        purity=Decimal("0.916000"),
        fine_weight=Decimal("91.600"),
        movement_type=CommodityMovement.MovementType.ADJUSTMENT_IN,
        fixed_status=CommodityMovement.FixedStatus.NOT_APPLICABLE,
    ):
        return CommodityMovement.objects.create(
            movement_no=movement_no,
            movement_date=movement_date,
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=commodity.pk,
            commodity=commodity,
            gross_weight=gross_weight,
            purity=purity,
            fine_weight=fine_weight,
            from_account=from_account,
            to_account=to_account,
            movement_type=movement_type,
            fixed_status=fixed_status,
            idempotency_key=f"commodity:test:metal-report:{movement_no}",
        )
