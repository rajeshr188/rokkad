from pathlib import Path

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from django_project import tenant_urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class TenantRouteCanonicalizationIntentTests(SimpleTestCase):
    def test_phase131_plan_records_alias_not_replacement_reality(self):
        plan_path = DOCS_UI_ROOT / "tenant_route_canonicalization_phase13_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Tenant Route Canonicalization Phase 13 Plan",
            "aliases, not as full canonical replacements",
            "/dea/",
            "/party/",
            "/girvi/",
            "Phase 11 completed route availability",
            "did not remove legacy tenant roots",
            "Phase 13.2",
        ):
            self.assertIn(expected, content)

    def test_phase131_legacy_tenant_roots_are_still_active_compatibility_routes(self):
        path_cases = {
            "/party/": "party_list",
            "/girvi/deletemultiple/": "girvi_loan_deletemultiple",
            "/product/": "product_product_home",
            "/dea/": "dea_home",
        }

        for path, route_name in path_cases.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)

    def test_phase131_slug_routes_are_entry_aliases_not_full_app_remounts_yet(self):
        route_cases = {
            "workspace_slug_parties": "/w/acme/parties/",
            "workspace_slug_loans": "/w/acme/loans/",
            "workspace_slug_inventory": "/w/acme/inventory/",
            "workspace_slug_accounting": "/w/acme/accounting/",
            "workspace_slug_operations": "/w/acme/operations/",
            "workspace_slug_reports": "/w/acme/reports/",
        }

        for route_name, path in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, kwargs={"workspace_slug": "acme"}), path)
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)

        shared_urlpatterns = _read("django_project/shared_urlpatterns.py")
        org_views = _read("apps/orgs/views.py")
        self.assertIn("CANONICAL_WORKSPACE_SLUG_URLPATTERNS", shared_urlpatterns)
        self.assertIn('return redirect("dea_home")', org_views)
        self.assertIn('return redirect("party:party_list")', org_views)
        self.assertIn('return redirect("girvi:girvi_dashboard")', org_views)

    def test_phase131_project_docs_no_longer_overclaim_full_canonicalization(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")
        phase11_review = _read("docs/ui/workspace_slug_phase11_review.md")

        for content in (status, memory, audit, phase11_review):
            with self.subTest():
                self.assertIn("Phase 13", content)
                self.assertIn("tenant_route_canonicalization_phase13_plan.md", content)
                self.assertIn("tenant roots", content)
