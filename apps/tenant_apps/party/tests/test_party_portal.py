import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import connection
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.party.models import Party, PartyDocument, PartyPortalAccess
from apps.tenant_apps.party.portal_access import (
    PortalIdentityDenied,
    resolve_portal_identity,
)
from apps.tenant_apps.party.portal_selectors import (
    get_portal_documents_summary,
    get_portal_invoices_summary,
    get_portal_loans_summary,
    get_portal_payments_summary,
    get_portal_statements_summary,
)
from apps.tenant_apps.party.portal_views import (
    portal_dashboard,
    portal_invoices,
    portal_loans,
    portal_payments,
    portal_statements,
)
from apps.tenant_apps.party.services.portal_access import (
    PortalAccessLifecycleError,
    activate_portal_access,
    revoke_portal_access,
    suspend_portal_access,
)
from django_project import tenant_urls, urls


User = get_user_model()

TEST_STORAGES = {
    **settings.STORAGES,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


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
        self.factory = RequestFactory()

    def _request(self):
        request = type("Request", (), {})()
        request.user = self.user
        request.tenant = self.tenant
        return request

    def _view_request(self, path="/portal/"):
        request = self.factory.get(path, HTTP_HOST=self.test_domain)
        request.user = self.user
        request.tenant = self.tenant
        request.LANGUAGE_CODE = settings.LANGUAGE_CODE
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

    def test_portal_access_lifecycle_activate_logs_and_enables_identity(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.INVITED,
        )

        with patch(
            "apps.tenant_apps.party.services.portal_access.AuditLog.log"
        ) as audit_log:
            result = activate_portal_access(
                grant,
                actor=self.user,
                request=self._request(),
            )

        grant.refresh_from_db()
        identity = resolve_portal_identity(self._request())
        self.assertTrue(result.changed)
        self.assertEqual(grant.status, PartyPortalAccess.Status.ACTIVE)
        self.assertIsNotNone(grant.activated_at)
        self.assertEqual(identity.access_grant, grant)
        audit_log.assert_called_once()
        self.assertEqual(audit_log.call_args.args[0], "PARTY_PORTAL_ACCESS_ACTIVATE")
        self.assertEqual(audit_log.call_args.kwargs["company"], self.tenant)
        self.assertEqual(
            audit_log.call_args.kwargs["data"]["previous_status"],
            PartyPortalAccess.Status.INVITED,
        )

    def test_portal_access_lifecycle_suspend_logs_and_disables_identity(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )

        with patch(
            "apps.tenant_apps.party.services.portal_access.AuditLog.log"
        ) as audit_log:
            result = suspend_portal_access(
                grant,
                actor=self.user,
                request=self._request(),
            )

        grant.refresh_from_db()
        self.assertTrue(result.changed)
        self.assertEqual(grant.status, PartyPortalAccess.Status.SUSPENDED)
        with self.assertRaises(PortalIdentityDenied):
            resolve_portal_identity(self._request())
        audit_log.assert_called_once()
        self.assertEqual(audit_log.call_args.args[0], "PARTY_PORTAL_ACCESS_SUSPEND")

    def test_portal_access_lifecycle_revoke_logs_and_blocks_reactivation(self):
        grant = PartyPortalAccess.objects.create(
            party=self.party,
            user=self.user,
            status=PartyPortalAccess.Status.ACTIVE,
        )

        with patch(
            "apps.tenant_apps.party.services.portal_access.AuditLog.log"
        ) as audit_log:
            result = revoke_portal_access(
                grant,
                actor=self.user,
                request=self._request(),
            )

        grant.refresh_from_db()
        self.assertTrue(result.changed)
        self.assertEqual(grant.status, PartyPortalAccess.Status.REVOKED)
        self.assertIsNotNone(grant.revoked_at)
        with self.assertRaises(PortalIdentityDenied):
            resolve_portal_identity(self._request())
        with self.assertRaises(PortalAccessLifecycleError):
            activate_portal_access(grant, actor=self.user, request=self._request())
        audit_log.assert_called_once()
        self.assertEqual(audit_log.call_args.args[0], "PARTY_PORTAL_ACCESS_REVOKE")

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
