import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role
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
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.rates.models import Rate, RateSource


User = get_user_model()


@override_settings(ROOT_URLCONF="django_project.tenant_urls")
class CommodityReportViewTests(TenantTestCase):
    test_schema_name = f"dea_comm_report_ui_{uuid.uuid4().hex[:8]}"
    test_domain = f"dea-comm-report-ui-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-commodity-report-ui-owner",
            defaults={"email": "dea-commodity-report-ui-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-commodity-report-ui-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=owner,
            company=tenant,
            defaults={"role": owner_role},
        )

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.user = User.objects.get(username="dea-commodity-report-ui-owner")
        self.client.login(username="dea-commodity-report-ui-owner", password="testpass123")
        self.gold = Commodity.objects.create(code="GOLD", name="Gold")
        self.party = Party.objects.create(display_name="Bullion Supplier")
        self.vault = CommodityAccount.objects.create(
            code="GOLD_UI_VAULT",
            name="Gold UI vault",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.VAULT,
            location_label="Main vault",
        )
        self.adjustment = CommodityAccount.objects.create(
            code="GOLD_UI_ADJUSTMENT",
            name="Gold UI adjustment",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.ADJUSTMENT,
        )

    def test_reports_hub_links_to_commodity_reports(self):
        response = self.client.get(reverse("dea_reports_hub"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commodity Reports")
        self.assertContains(response, reverse("dea_metal_balance_report"))
        self.assertContains(response, reverse("dea_exposure_report"))
        self.assertContains(response, reverse("dea_valuation_report"))

    def test_accounting_dashboard_links_to_commodity_reports(self):
        response = self.client.get(reverse("dea_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commodity Reports")
        self.assertContains(response, reverse("dea_metal_balance_report"))
        self.assertContains(response, reverse("dea_exposure_report"))
        self.assertContains(response, reverse("dea_valuation_report"))

    def test_enhanced_dashboard_links_to_commodity_reports(self):
        response = self.client.get(reverse("dea_dashboard_enhanced"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commodity Reports")
        self.assertContains(response, reverse("dea_metal_balance_report"))
        self.assertContains(response, reverse("dea_exposure_report"))
        self.assertContains(response, reverse("dea_valuation_report"))

    def test_metal_balance_report_page_renders_rows(self):
        self._movement(fine_weight=Decimal("91.600"))

        response = self.client.get(reverse("dea_metal_balance_report"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Metal Balance")
        self.assertContains(response, "Commodity Reports")
        self.assertContains(response, "GOLD_UI_VAULT")
        self.assertContains(response, "91.600")

    def test_exposure_report_page_renders_open_exposure_with_valuation_option(self):
        self._rate()
        exposure = self._exposure(open_fine_weight=Decimal("50.000"))
        ExposureLine.objects.filter(pk=exposure.pk).update(
            created_at=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
        )

        response = self.client.get(
            reverse("dea_exposure_report"),
            {
                "commodity": str(self.gold.pk),
                "party": str(self.party.pk),
                "as_of": "2026-06-02",
                "include_valuation": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commodity Exposure")
        self.assertContains(response, "EXP-UI-PURCHASE")
        self.assertContains(response, "300000.00")

    def test_valuation_report_page_is_read_only(self):
        self._rate()
        self._movement(fine_weight=Decimal("10.000"))
        exposure = self._exposure(open_fine_weight=Decimal("5.000"))
        ExposureLine.objects.filter(pk=exposure.pk).update(
            created_at=datetime(2026, 6, 2, 9, 0, tzinfo=timezone.utc)
        )
        before = self._side_effect_counts()

        response = self.client.get(
            reverse("dea_valuation_report"),
            {"as_of": "2026-06-02", "currency": "INR", "purity": "24k"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Commodity Valuation")
        self.assertContains(response, "VALUED")
        self.assertContains(response, "60000.00")
        self.assertEqual(self._side_effect_counts(), before)

    def _rate(self):
        rate_source = RateSource.objects.create(name="UI Market", location="Mumbai")
        rate = Rate.objects.create(
            metal=Rate.Metal.GOLD,
            currency=Rate.Currency.INR,
            purity=Rate.Purity.K24,
            buying_rate=Decimal("6000.00"),
            selling_rate=Decimal("6200.00"),
            rate_source=rate_source,
        )
        Rate.objects.filter(pk=rate.pk).update(
            timestamp=datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        )
        return rate

    def _movement(self, *, fine_weight):
        return CommodityMovement.objects.create(
            movement_no=f"CM-UI-{uuid.uuid4().hex[:8]}",
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
            idempotency_key=f"commodity:test:report-ui:movement:{uuid.uuid4().hex}",
        )

    def _exposure(self, *, open_fine_weight):
        return ExposureLine.objects.create(
            exposure_no="EXP-UI-PURCHASE",
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=self.gold.pk,
            party=self.party,
            commodity=self.gold,
            side=ExposureLine.Side.PURCHASE,
            status=ExposureLine.Status.OPEN,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
            original_fine_weight=open_fine_weight,
            open_fine_weight=open_fine_weight,
            rate_basis="UI test exposure",
            valuation_currency="INR",
            idempotency_key=f"commodity:test:report-ui:exposure:{uuid.uuid4().hex}",
        )

    def _side_effect_counts(self):
        return {
            "journal_entries": JournalEntry.objects.count(),
            "voucher_lines": VoucherLine.objects.count(),
            "ledger_transactions": LedgerTransaction.objects.count(),
            "account_transactions": AccountTransaction.objects.count(),
            "rate_fixings": RateFixing.objects.count(),
            "movements": CommodityMovement.objects.count(),
            "exposures": ExposureLine.objects.count(),
        }
