from pathlib import Path

from django.test import SimpleTestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

from django_project import tenant_urls, urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"
TEMPLATES_ROOT = PROJECT_ROOT / "templates"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class CustomerPortalPhase12IntentTests(SimpleTestCase):
    def test_phase121_portal_plan_exists_and_keeps_routes_absent(self):
        plan_path = DOCS_UI_ROOT / "customer_portal_phase12_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Customer Portal Phase 12 Plan",
            "Phase 12.1: Plan And Guard Baseline",
            "Status: complete",
            "not add live `/portal/...` routes yet",
            "No first-party `portal` app or URL group is currently installed",
            "identity binding",
            "PORTAL_CUSTOMER",
            "get_party_loan_history_summary",
            "Phase 12.2: Portal Identity Design",
        ):
            self.assertIn(expected, content)

    def test_phase121_target_portal_routes_remain_intentionally_absent(self):
        absent_route_names = (
            "customer_portal_dashboard",
            "customer_portal_loans",
            "customer_portal_invoices",
            "customer_portal_payments",
            "customer_portal_documents",
            "customer_portal_statements",
        )

        for route_name in absent_route_names:
            with self.subTest(route_name=route_name):
                with self.assertRaises(NoReverseMatch):
                    reverse(route_name)

        absent_paths = (
            "/portal/",
            "/portal/loans/",
            "/portal/invoices/",
            "/portal/payments/",
            "/portal/documents/",
            "/portal/statements/",
        )

        for path in absent_paths:
            with self.subTest(path=path, urlconf="public"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)
            with self.subTest(path=path, urlconf="tenant"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=tenant_urls)

    def test_phase124_portal_shell_alias_is_now_real_shell_without_routes(self):
        portal_alias = (
            TEMPLATES_ROOT / "base_customer_portal.html"
        ).read_text(encoding="utf-8-sig")
        portal_nav = (
            TEMPLATES_ROOT / "components" / "navigation" / "customer_portal_nav.html"
        ).read_text(encoding="utf-8-sig")
        plan = _read("docs/ui/customer_portal_phase12_plan.md")

        self.assertIn('extends "layouts/base.html"', portal_alias)
        self.assertIn("base_customer_portal.html", plan)
        self.assertIn("portal_content", portal_alias)
        self.assertIn("customer_portal_nav.html", portal_alias)
        self.assertIn("data-route-pending", portal_nav)
        self.assertIn("Phase 12.4", plan)
        self.assertIn("customer_portal_shell_phase12.md", plan)

    def test_phase121_project_docs_point_to_portal_phase(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")

        for content in (status, memory, audit):
            with self.subTest():
                self.assertIn("Phase 12.1", content)
                self.assertIn("customer_portal_phase12_plan.md", content)
                self.assertIn("Phase 12.2", content)
