from io import StringIO
import uuid

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.dea.models import Commodity
from apps.tenant_apps.dea.services.commodity_seed import (
    CANONICAL_COMMODITIES,
    seed_default_commodities,
)


User = get_user_model()


class CommoditySeedCommandTests(TenantTestCase):
    test_schema_name = f"dea_commodity_seed_{uuid.uuid4().hex[:8]}"
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
            username="dea-commodity-seed-owner",
            defaults={"email": "dea-commodity-seed-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-commodity-seed-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

    def test_seed_default_commodities_is_idempotent(self):
        first = seed_default_commodities()
        second = seed_default_commodities()

        self.assertEqual(first["created"], len(CANONICAL_COMMODITIES))
        self.assertEqual(first["updated"], 0)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["updated"], len(CANONICAL_COMMODITIES))
        self.assertEqual(Commodity.objects.count(), len(CANONICAL_COMMODITIES))

    def test_seed_creates_gold_and_silver_as_active_metal_gram_commodities(self):
        seed_default_commodities()

        for commodity_seed in CANONICAL_COMMODITIES:
            commodity = Commodity.objects.get(code=commodity_seed.code)
            self.assertEqual(commodity.name, commodity_seed.name)
            self.assertEqual(commodity.commodity_type, Commodity.CommodityType.METAL)
            self.assertEqual(commodity.default_uom, Commodity.UnitOfMeasure.GRAM)
            self.assertTrue(commodity.is_active)

    def test_seed_repairs_existing_default_commodity_metadata(self):
        Commodity.objects.create(
            code="GOLD",
            name="Legacy Gold",
            commodity_type=Commodity.CommodityType.OTHER,
            default_uom=Commodity.UnitOfMeasure.TOLA,
            is_active=False,
        )

        result = seed_default_commodities()
        gold = Commodity.objects.get(code="GOLD")

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(gold.name, "Gold")
        self.assertEqual(gold.commodity_type, Commodity.CommodityType.METAL)
        self.assertEqual(gold.default_uom, Commodity.UnitOfMeasure.GRAM)
        self.assertTrue(gold.is_active)

    def test_management_command_seeds_default_commodities(self):
        out = StringIO()

        call_command("seed_dea_commodities", stdout=out, verbosity=0)

        self.assertIn("DEA commodities ready", out.getvalue())
        self.assertEqual(Commodity.objects.count(), len(CANONICAL_COMMODITIES))

    def test_management_command_dry_run_does_not_create_rows(self):
        out = StringIO()

        call_command("seed_dea_commodities", "--dry-run", stdout=out, verbosity=0)

        self.assertIn("Would seed DEA commodities: GOLD, SILVER", out.getvalue())
        self.assertEqual(Commodity.objects.count(), 0)

    def test_management_command_can_target_schema(self):
        connection.set_schema_to_public()
        try:
            call_command(
                "seed_dea_commodities",
                "--schema",
                self.tenant.schema_name,
                verbosity=0,
            )
        finally:
            connection.set_tenant(self.tenant)

        self.assertEqual(Commodity.objects.count(), len(CANONICAL_COMMODITIES))
