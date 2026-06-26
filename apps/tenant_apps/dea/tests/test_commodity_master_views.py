import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role
from apps.tenant_apps.dea.forms_business_events import FixedPurchasePreviewForm
from apps.tenant_apps.dea.models import Commodity, CommodityAccount


User = get_user_model()


@override_settings(ROOT_URLCONF="django_project.tenant_urls")
class CommodityMasterViewTests(TenantTestCase):
    test_schema_name = f"dea_commodity_master_{uuid.uuid4().hex[:8]}"
    test_domain = f"dea-commodity-master-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-commodity-master-owner",
            defaults={"email": "dea-commodity-master-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-commodity-master-tenant-{uuid.uuid4().hex[:8]}"
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
        self.client.raise_request_exception = False
        self.client.login(
            username="dea-commodity-master-owner",
            password="testpass123",
        )

    def _login_as_member(self):
        member = User.objects.create_user(
            username=f"dea-commodity-master-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-commodity-master-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.logout()
        self.client.login(username=member.username, password="testpass123")
        return member

    def test_member_role_cannot_access_commodity_master_routes(self):
        self._login_as_member()

        response = self.client.get(reverse("dea_commodity_list"))

        self.assertIn(response.status_code, (403, 500))

    def test_commodity_list_defaults_to_active_only(self):
        Commodity.objects.create(code="GOLD", name="Gold", is_active=True)
        Commodity.objects.create(code="SILVER", name="Silver", is_active=False)

        response = self.client.get(reverse("dea_commodity_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "GOLD")
        self.assertNotContains(response, "SILVER")

    def test_create_commodity_uppercases_code(self):
        response = self.client.post(
            reverse("dea_commodity_create"),
            data={
                "code": "copper",
                "name": "Copper",
                "commodity_type": Commodity.CommodityType.METAL,
                "default_uom": Commodity.UnitOfMeasure.GRAM,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        commodity = Commodity.objects.get(name="Copper")
        self.assertEqual(commodity.code, "COPPER")

    def test_create_duplicate_commodity_code_is_rejected(self):
        Commodity.objects.create(code="GOLD", name="Gold")

        response = self.client.post(
            reverse("dea_commodity_create"),
            data={
                "code": "gold",
                "name": "Gold Duplicate",
                "commodity_type": Commodity.CommodityType.METAL,
                "default_uom": Commodity.UnitOfMeasure.GRAM,
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Commodity.objects.filter(code="GOLD").count(), 1)

    def test_update_commodity_changes_attributes_but_not_code(self):
        commodity = Commodity.objects.create(code="PLATINUM", name="Platinum")

        response = self.client.post(
            reverse("dea_commodity_update", kwargs={"commodity_id": commodity.pk}),
            data={
                "name": "Platinum 999",
                "commodity_type": Commodity.CommodityType.METAL,
                "default_uom": Commodity.UnitOfMeasure.KG,
                "is_active": "on",
                "code": "PLAT-NEW",
            },
        )

        self.assertEqual(response.status_code, 302)
        commodity.refresh_from_db()
        self.assertEqual(commodity.code, "PLATINUM")
        self.assertEqual(commodity.name, "Platinum 999")
        self.assertEqual(commodity.default_uom, Commodity.UnitOfMeasure.KG)

    def test_cannot_deactivate_commodity_with_active_accounts(self):
        commodity = Commodity.objects.create(code="ZINC", name="Zinc")
        CommodityAccount.objects.create(
            code="ZINC_VAULT",
            name="Zinc Vault",
            commodity=commodity,
            purpose=CommodityAccount.Purpose.VAULT,
            is_active=True,
        )

        response = self.client.post(
            reverse("dea_commodity_deactivate", kwargs={"commodity_id": commodity.pk})
        )

        self.assertEqual(response.status_code, 302)
        commodity.refresh_from_db()
        self.assertTrue(commodity.is_active)

    def test_deactivated_commodity_is_hidden_from_business_event_forms(self):
        commodity = Commodity.objects.create(code="NICKEL", name="Nickel")

        response = self.client.post(
            reverse("dea_commodity_deactivate", kwargs={"commodity_id": commodity.pk})
        )
        self.assertEqual(response.status_code, 302)

        commodity.refresh_from_db()
        self.assertFalse(commodity.is_active)

        form = FixedPurchasePreviewForm()
        self.assertNotIn(commodity, form.fields["commodity"].queryset)
