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
    LedgerTransaction,
)
from apps.tenant_apps.dea.selectors.commodity import (
    get_commodity_position_for_account,
    get_commodity_position_for_party,
    get_commodity_position_rows,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class CommodityPositionSelectorTests(TenantTestCase):
    test_schema_name = f"dea_commodity_selectors_{uuid.uuid4().hex[:8]}"
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
            username="dea-commodity-selector-owner",
            defaults={"email": "dea-commodity-selector-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-commodity-selector-tenant-{uuid.uuid4().hex[:8]}"
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
        self.karigar = CommodityAccount.objects.create(
            code="GOLD_KARIGAR",
            name="Gold with karigar",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.KARIGAR_CUSTODY,
            party=self.party,
            location_label="Karigar",
        )
        self.adjustment = CommodityAccount.objects.create(
            code="GOLD_ADJUSTMENT",
            name="Gold adjustment",
            commodity=self.gold,
            purpose=CommodityAccount.Purpose.ADJUSTMENT,
        )

    def test_position_rows_show_incoming_and_outgoing_account_balances(self):
        self._movement(
            movement_no="cm-open",
            movement_date=date(2026, 6, 1),
            from_account=self.adjustment,
            to_account=self.vault,
            gross_weight=Decimal("100.000"),
            fine_weight=Decimal("91.600"),
            movement_type=CommodityMovement.MovementType.OPENING,
        )
        self._movement(
            movement_no="cm-issue",
            movement_date=date(2026, 6, 2),
            from_account=self.vault,
            to_account=self.karigar,
            gross_weight=Decimal("25.000"),
            fine_weight=Decimal("22.900"),
            movement_type=CommodityMovement.MovementType.KARIGAR_ISSUE,
        )

        positions = {
            row.account_code: row for row in get_commodity_position_rows()
        }

        self.assertEqual(positions["GOLD_MAIN_VAULT"].gross_weight, Decimal("75.000"))
        self.assertEqual(positions["GOLD_MAIN_VAULT"].fine_weight, Decimal("68.700"))
        self.assertEqual(positions["GOLD_KARIGAR"].gross_weight, Decimal("25.000"))
        self.assertEqual(positions["GOLD_KARIGAR"].fine_weight, Decimal("22.900"))
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def test_position_for_account_filters_to_single_account(self):
        self._movement(
            movement_no="cm-open-account",
            movement_date=date(2026, 6, 1),
            from_account=self.adjustment,
            to_account=self.vault,
        )

        rows = get_commodity_position_for_account(self.vault)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].account_code, "GOLD_MAIN_VAULT")
        self.assertEqual(rows[0].fine_weight, Decimal("91.600"))

    def test_position_for_party_filters_party_accounts(self):
        self._movement(
            movement_no="cm-party",
            movement_date=date(2026, 6, 2),
            from_account=self.vault,
            to_account=self.karigar,
            gross_weight=Decimal("10.000"),
            fine_weight=Decimal("9.160"),
            movement_type=CommodityMovement.MovementType.KARIGAR_ISSUE,
        )

        rows = get_commodity_position_for_party(self.party)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].account_code, "GOLD_KARIGAR")
        self.assertEqual(rows[0].party_name, "Bullion Supplier")
        self.assertEqual(rows[0].fine_weight, Decimal("9.160"))

    def test_position_can_filter_by_location_label(self):
        self._movement(
            movement_no="cm-location",
            movement_date=date(2026, 6, 1),
            from_account=self.adjustment,
            to_account=self.vault,
        )

        rows = get_commodity_position_rows(location_label="Main vault")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].location_label, "Main vault")
        self.assertEqual(rows[0].fine_weight, Decimal("91.600"))

    def test_position_respects_as_of_date(self):
        self._movement(
            movement_no="cm-before",
            movement_date=date(2026, 6, 1),
            from_account=self.adjustment,
            to_account=self.vault,
        )
        self._movement(
            movement_no="cm-after",
            movement_date=date(2026, 6, 10),
            from_account=self.vault,
            to_account=self.karigar,
            gross_weight=Decimal("50.000"),
            fine_weight=Decimal("45.800"),
            movement_type=CommodityMovement.MovementType.KARIGAR_ISSUE,
        )

        rows = get_commodity_position_for_account(
            self.vault,
            as_of=date(2026, 6, 5),
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].fine_weight, Decimal("91.600"))

    def test_reversal_movement_offsets_original_position(self):
        original = self._movement(
            movement_no="cm-original",
            movement_date=date(2026, 6, 1),
            from_account=self.adjustment,
            to_account=self.vault,
        )
        self._movement(
            movement_no="cm-reversal",
            movement_date=date(2026, 6, 2),
            from_account=self.vault,
            to_account=self.adjustment,
            movement_type=CommodityMovement.MovementType.REVERSAL,
            is_reversal_of=original,
        )

        rows = get_commodity_position_for_account(self.vault)

        self.assertEqual(rows, [])

    def test_position_rows_are_grouped_by_fixed_status(self):
        self._movement(
            movement_no="cm-fixed",
            movement_date=date(2026, 6, 1),
            from_account=self.adjustment,
            to_account=self.vault,
            fixed_status=CommodityMovement.FixedStatus.FIXED,
        )
        self._movement(
            movement_no="cm-unfixed",
            movement_date=date(2026, 6, 2),
            from_account=self.adjustment,
            to_account=self.vault,
            gross_weight=Decimal("50.000"),
            fine_weight=Decimal("45.800"),
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
        )

        rows = get_commodity_position_for_account(self.vault)

        self.assertEqual(len(rows), 2)
        by_status = {row.fixed_status: row for row in rows}
        self.assertEqual(
            by_status[CommodityMovement.FixedStatus.FIXED].fine_weight,
            Decimal("91.600"),
        )
        self.assertEqual(
            by_status[CommodityMovement.FixedStatus.UNFIXED].fine_weight,
            Decimal("45.800"),
        )

    def _movement(
        self,
        *,
        movement_no,
        movement_date,
        from_account,
        to_account,
        gross_weight=Decimal("100.000"),
        purity=Decimal("0.916000"),
        fine_weight=Decimal("91.600"),
        movement_type=CommodityMovement.MovementType.ADJUSTMENT_IN,
        fixed_status=CommodityMovement.FixedStatus.NOT_APPLICABLE,
        is_reversal_of=None,
    ):
        return CommodityMovement.objects.create(
            movement_no=movement_no,
            movement_date=movement_date,
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=self.gold.pk,
            commodity=self.gold,
            gross_weight=gross_weight,
            purity=purity,
            fine_weight=fine_weight,
            from_account=from_account,
            to_account=to_account,
            movement_type=movement_type,
            fixed_status=fixed_status,
            is_reversal_of=is_reversal_of,
            idempotency_key=f"commodity:test:selector:{movement_no}",
        )
