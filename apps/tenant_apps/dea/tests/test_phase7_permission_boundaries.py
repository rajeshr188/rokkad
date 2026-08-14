import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import RequestFactory, override_settings
from django.urls import resolve, reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role


User = get_user_model()


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class Phase7PermissionBoundaryTests(TenantTestCase):
    """Guard accountant-only DEA legacy surfaces before navigation cleanup."""

    test_schema_name = f"dea_phase7_perm_{uuid.uuid4().hex[:8]}"
    test_domain = f"dea-phase7-perm-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-phase7-owner",
            defaults={"email": "dea-phase7-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-phase7-perm-tenant-{uuid.uuid4().hex[:8]}"
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
        self.request_factory = RequestFactory()
        self.owner = User.objects.get(username="dea-phase7-owner")
        self.member = User.objects.create_user(
            username=f"dea-phase7-member-{uuid.uuid4().hex[:8]}",
            email=f"dea-phase7-member-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(
            user=self.member,
            company=self.tenant,
            role=member_role,
        )

    def test_owner_can_reach_accountant_legacy_surfaces(self):
        self.client.login(username="dea-phase7-owner", password="testpass123")

        for route_name in self._accountant_get_routes():
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)

    def test_member_is_denied_accountant_legacy_surfaces(self):
        for route_name in self._accountant_get_routes():
            with self.subTest(route=route_name):
                path = reverse(route_name)
                request = self._member_request("get", path)
                match = resolve(path)
                with self.assertRaises(PermissionDenied):
                    match.func(request, *match.args, **match.kwargs)

    def test_member_is_denied_accountant_post_actions_before_object_lookup(self):
        route_kwargs = {"pk": 999999}

        for route_name in ("dea_voucher_post", "dea_voucher_reverse", "dea_expense_post"):
            with self.subTest(route=route_name):
                path = reverse(route_name, kwargs=route_kwargs)
                request = self._member_request("post", path)
                match = resolve(path)
                with self.assertRaises(PermissionDenied):
                    match.func(request, *match.args, **match.kwargs)

    def test_member_is_denied_period_surfaces(self):
        """Period CRUD requires accountant access; members must be denied."""
        for route_name in ("dea_period_list", "dea_period_create"):
            with self.subTest(route=route_name):
                path = reverse(route_name)
                request = self._member_request("get", path)
                match = resolve(path)
                with self.assertRaises(PermissionDenied):
                    match.func(request, *match.args, **match.kwargs)

    def test_owner_can_reach_period_list(self):
        """Owner (accountant-capable) must be able to reach period list."""
        self.client.login(username="dea-phase7-owner", password="testpass123")
        response = self.client.get(reverse("dea_period_list"))
        self.assertEqual(response.status_code, 200)

    def test_member_is_denied_bank_reconciliation_list(self):
        """Bank reconciliation list requires accountant access; members must be denied."""
        path = reverse("bank-accounts-list")
        request = self._member_request("get", path)
        match = resolve(path)
        with self.assertRaises(PermissionDenied):
            match.func(request, *match.args, **match.kwargs)

    def _member_request(self, method, path):
        request = getattr(self.request_factory, method)(path)
        request.user = self.member
        request.tenant = self.tenant
        return request

    def _accountant_get_routes(self):
        return (
            "dea_voucher_hub",
            "dea_voucher_list",
            "dea_payment_list",
            "dea_expense_list",
            "dea_journal_entry_voucher_list",
            "dea_opening_balance_wizard",
        )
