from pathlib import Path

from django.test import SimpleTestCase
from django.urls import Resolver404, resolve, reverse

from django_project import tenant_urls, urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class CustomerPortalPhase12ReviewIntentTests(SimpleTestCase):
    def test_phase12_review_records_superseded_live_route_decision(self):
        review_path = DOCS_UI_ROOT / "customer_portal_phase12_review.md"

        self.assertTrue(review_path.exists())
        content = review_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Customer Portal Phase 12 Review",
            "read-only portal MVP",
            "Superseded Route Decision",
            "do not add live `/portal/...` routes",
            "placeholder views",
            "PartyPortalAccess",
            "Public URLConf still does not expose `/portal/...`",
            "Customer-facing portal mutation routes remain out of scope",
        ):
            self.assertIn(expected, content)

    def test_live_portal_routes_are_tenant_only_after_party_rollout(self):
        route_map = {
            "customer_portal_dashboard": "/portal/",
            "customer_portal_loans": "/portal/loans/",
            "customer_portal_invoices": "/portal/invoices/",
            "customer_portal_payments": "/portal/payments/",
            "customer_portal_documents": "/portal/documents/",
            "customer_portal_statements": "/portal/statements/",
        }

        for route_name, path in route_map.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, urlconf=tenant_urls), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)
            with self.subTest(path=path, urlconf="public"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)

    def test_phase12_project_docs_point_to_closeout_and_phase13(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")
        portal_plan = _read("docs/ui/customer_portal_phase12_plan.md")

        for content in (status, memory, audit, portal_plan):
            with self.subTest():
                self.assertIn("customer_portal_phase12_review.md", content)
                self.assertIn("PartyPortalAccess", content)
                self.assertIn("/portal/...", content)
