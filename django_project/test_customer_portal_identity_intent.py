from pathlib import Path
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

from apps.tenant_apps.party.portal_access import (
    PortalIdentity,
    PortalIdentityDenied,
    PortalIdentityNotConfigured,
    resolve_portal_identity,
)
from django_project import tenant_urls, urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class CustomerPortalIdentityIntentTests(SimpleTestCase):
    def test_phase122_identity_plan_exists(self):
        plan_path = DOCS_UI_ROOT / "customer_portal_identity_phase12.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Customer Portal Identity Phase 12",
            "Phase 12.2 chooses the portal identity model",
            "PartyPortalAccess",
            "PORTAL_CUSTOMER",
            "Why Not Email Inference",
            "resolve_portal_identity()",
            "PortalIdentityNotConfigured",
            "Phase 12.3",
        ):
            self.assertIn(expected, content)

    def test_phase122_role_seed_uses_portal_customer_not_portal_user(self):
        role_seed = _read("apps/tenant_apps/party/services/role_seed.py")
        portal_plan = _read("docs/ui/customer_portal_phase12_plan.md")
        identity_plan = _read("docs/ui/customer_portal_identity_phase12.md")

        self.assertIn('"PORTAL_CUSTOMER"', role_seed)
        self.assertIn("PORTAL_CUSTOMER", portal_plan)
        self.assertIn("PORTAL_CUSTOMER", identity_plan)
        self.assertNotIn("PORTAL_USER", portal_plan)
        self.assertNotIn("PORTAL_USER", identity_plan)

    def test_phase122_portal_access_helper_fails_closed_without_binding_lookup(self):
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))

        with self.assertRaises(PortalIdentityNotConfigured):
            resolve_portal_identity(request)

    def test_phase122_portal_access_helper_requires_authentication(self):
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))

        with self.assertRaises(PortalIdentityDenied):
            resolve_portal_identity(request, binding_lookup=lambda user, req: None)

    def test_phase122_portal_access_helper_accepts_explicit_complete_identity(self):
        user = SimpleNamespace(is_authenticated=True)
        request = SimpleNamespace(user=user)
        identity = PortalIdentity(
            user=user,
            workspace=SimpleNamespace(schema_name="acme"),
            party=SimpleNamespace(status="ACTIVE"),
            access_grant=SimpleNamespace(status="ACTIVE"),
        )

        resolved = resolve_portal_identity(
            request,
            binding_lookup=lambda bound_user, req: identity,
        )

        self.assertEqual(resolved, identity)

    def test_phase122_portal_access_helper_rejects_incomplete_or_inactive_identity(self):
        user = SimpleNamespace(is_authenticated=True)
        request = SimpleNamespace(user=user)

        with self.assertRaisesMessage(PermissionDenied, "party"):
            resolve_portal_identity(
                request,
                binding_lookup=lambda bound_user, req: PortalIdentity(
                    user=user,
                    workspace=SimpleNamespace(schema_name="acme"),
                    party=None,
                    access_grant=SimpleNamespace(status="ACTIVE"),
                ),
            )

        with self.assertRaisesMessage(PermissionDenied, "not active"):
            resolve_portal_identity(
                request,
                binding_lookup=lambda bound_user, req: PortalIdentity(
                    user=user,
                    workspace=SimpleNamespace(schema_name="acme"),
                    party=SimpleNamespace(status="BLOCKED"),
                    access_grant=SimpleNamespace(status="ACTIVE"),
                ),
            )

    def test_phase122_target_portal_routes_still_remain_absent(self):
        for route_name in (
            "customer_portal_dashboard",
            "customer_portal_loans",
            "customer_portal_invoices",
            "customer_portal_payments",
            "customer_portal_documents",
            "customer_portal_statements",
        ):
            with self.subTest(route_name=route_name):
                with self.assertRaises(NoReverseMatch):
                    reverse(route_name)

        for path in (
            "/portal/",
            "/portal/loans/",
            "/portal/invoices/",
            "/portal/payments/",
            "/portal/documents/",
            "/portal/statements/",
        ):
            with self.subTest(path=path, urlconf="public"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)
            with self.subTest(path=path, urlconf="tenant"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=tenant_urls)

    def test_phase122_project_docs_point_to_identity_phase(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")

        for content in (status, memory, audit):
            with self.subTest():
                self.assertIn("Phase 12.2", content)
                self.assertIn("customer_portal_identity_phase12.md", content)
                self.assertIn("Phase 12.3", content)
