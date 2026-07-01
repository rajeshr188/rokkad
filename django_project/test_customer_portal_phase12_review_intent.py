from pathlib import Path

from django.test import SimpleTestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

from django_project import tenant_urls, urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class CustomerPortalPhase12ReviewIntentTests(SimpleTestCase):
    def test_phase12_review_closes_portal_without_live_routes(self):
        review_path = DOCS_UI_ROOT / "customer_portal_phase12_review.md"

        self.assertTrue(review_path.exists())
        content = review_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Customer Portal Phase 12 Review",
            "Phase 12 is complete",
            "Do not add live `/portal/...` routes with placeholder views",
            "PartyPortalAccess",
            "cross-party denial tests",
            "Proceed with Phase 13.2",
        ):
            self.assertIn(expected, content)

    def test_phase125_live_portal_routes_remain_absent_by_decision(self):
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

    def test_phase12_project_docs_point_to_closeout_and_phase13(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")
        portal_plan = _read("docs/ui/customer_portal_phase12_plan.md")

        for content in (status, memory, audit, portal_plan):
            with self.subTest():
                self.assertIn("customer_portal_phase12_review.md", content)
                self.assertIn("PartyPortalAccess", content)
                self.assertIn("Phase 13.2", content)
