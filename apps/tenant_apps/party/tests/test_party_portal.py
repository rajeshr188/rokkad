import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve, reverse
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.party.models import Party, PartyDocument, PartyPortalAccess
from apps.tenant_apps.party.portal_access import (
    PortalIdentityDenied,
    resolve_portal_identity,
)
from apps.tenant_apps.party.portal_selectors import get_portal_documents_summary
from django_project import tenant_urls, urls


User = get_user_model()


class PartyPortalAccessTests(TenantTestCase):
    test_schema_name = f"party_portal_{uuid.uuid4().hex[:8]}"
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
            username="party-portal-owner",
            defaults={"email": "party-portal-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"party-portal-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"portal-user-{uuid.uuid4().hex[:8]}",
            email="portal-user@example.com",
            password="testpass123",
        )
        self.party = Party.objects.create(display_name="Portal Customer")
        self.other_party = Party.objects.create(display_name="Other Customer")

    def _request(self):
        request = type("Request", (), {})()
        request.user = self.user
        request.tenant = self.tenant
        return request

    def test_active_party_portal_access_resolves_identity(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )

        identity = resolve_portal_identity(self._request())

        self.assertEqual(identity.party, self.party)
        self.assertEqual(identity.access_grant, grant)
        self.assertEqual(identity.workspace, self.tenant)

    def test_inactive_party_portal_access_fails_closed(self):
        PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.INVITED,
        )

        with self.assertRaises(PortalIdentityDenied):
            resolve_portal_identity(self._request())

    def test_document_selector_only_returns_granted_party_documents(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )
        own_document = PartyDocument.objects.create(
            party=self.party,
            document_type=PartyDocument.DocumentType.KYC,
            title="Own KYC",
        )
        PartyDocument.objects.create(
            party=self.other_party,
            document_type=PartyDocument.DocumentType.KYC,
            title="Other KYC",
        )
        identity = resolve_portal_identity(self._request())

        summary = get_portal_documents_summary(identity)

        self.assertEqual(identity.access_grant, grant)
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.items, (own_document,))


class PartyPortalRouteIntentTests(SimpleTestCase):
    def test_portal_routes_are_tenant_only(self):
        expected_routes = {
            "customer_portal_dashboard": "/portal/",
            "customer_portal_loans": "/portal/loans/",
            "customer_portal_invoices": "/portal/invoices/",
            "customer_portal_payments": "/portal/payments/",
            "customer_portal_documents": "/portal/documents/",
            "customer_portal_statements": "/portal/statements/",
        }
        for route_name, path in expected_routes.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, urlconf=tenant_urls), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)
