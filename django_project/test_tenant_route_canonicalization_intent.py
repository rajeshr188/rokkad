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

        parties_section = org_views.split("def workspace_slug_parties", 1)[1].split(
            "def workspace_slug_loans", 1
        )[0]
        loans_section = org_views.split("def workspace_slug_loans", 1)[1].split(
            "def workspace_slug_inventory", 1
        )[0]
        inventory_section = org_views.split("def workspace_slug_inventory", 1)[1].split(
            "def workspace_slug_accounting", 1
        )[0]
        accounting_section = org_views.split("def workspace_slug_accounting", 1)[1].split(
            "def workspace_slug_operations", 1
        )[0]
        self.assertIn("party_list(request)", parties_section)
        self.assertNotIn('redirect("party:party_list")', parties_section)
        self.assertIn("girvi_dashboard(request)", loans_section)
        self.assertNotIn('redirect("girvi:girvi_dashboard")', loans_section)
        self.assertIn("product_home(request)", inventory_section)
        self.assertNotIn('redirect("product_product_home")', inventory_section)
        self.assertIn("dea_home(request)", accounting_section)
        self.assertNotIn('redirect("dea_home")', accounting_section)

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

    def test_phase132_visible_tenant_entry_links_use_slug_aliases(self):
        sidebar = _read("templates/components/navigation/sidebar.html")
        dashboard = _read("templates/company/workspace_dashboard.html")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        for expected in (
            "Status: complete",
            "workspace_slug_operations",
            "workspace_slug_reports",
            "workspace_slug_commodity",
            "workspace_slug_accounting",
            "Legacy tenant roots remain active",
            "Phase 13.3",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, plan + sidebar + dashboard)

        for legacy_entry in (
            "{% url 'dea_business_events_dashboard' %}",
            "{% url 'dea_reports_hub' %}",
            "{% url 'dea_commodity_list' %}",
            "{% url 'dea_dashboard' %}",
        ):
            with self.subTest(legacy_entry=legacy_entry):
                self.assertNotIn(legacy_entry, sidebar + dashboard)

    def test_phase133_parties_slug_entry_direct_renders_existing_party_list(self):
        org_views = _read("apps/orgs/views.py")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        parties_section = org_views.split("def workspace_slug_parties", 1)[1].split(
            "def workspace_slug_loans", 1
        )[0]

        self.assertIn("Phase 13.3", plan)
        self.assertIn("Status: complete for the low-risk entrypoint set", plan)
        self.assertIn("/w/<workspace_slug>/parties/", plan)
        self.assertIn("from apps.tenant_apps.party.views import party_list", parties_section)
        self.assertIn("return party_list(request)", parties_section)
        self.assertNotIn('return redirect("party:party_list")', parties_section)

    def test_phase133_inventory_slug_entry_direct_renders_existing_product_home(self):
        org_views = _read("apps/orgs/views.py")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        inventory_section = org_views.split("def workspace_slug_inventory", 1)[1].split(
            "def workspace_slug_accounting", 1
        )[0]

        self.assertIn("Phase 13.3", plan)
        self.assertIn("/w/<workspace_slug>/inventory/", plan)
        self.assertIn("Product entrypoint policy", plan)
        self.assertIn(
            "from apps.tenant_apps.product.views.home import home as product_home",
            inventory_section,
        )
        self.assertIn("return product_home(request)", inventory_section)
        self.assertNotIn('return redirect("product_product_home")', inventory_section)

    def test_phase133_loans_slug_entry_direct_renders_existing_girvi_dashboard(self):
        org_views = _read("apps/orgs/views.py")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        loans_section = org_views.split("def workspace_slug_loans", 1)[1].split(
            "def workspace_slug_inventory", 1
        )[0]

        self.assertIn("Phase 13.3", plan)
        self.assertIn("/w/<workspace_slug>/loans/", plan)
        self.assertIn("Girvi workspace access guard", plan)
        self.assertIn(
            "from apps.tenant_apps.girvi.views.dashboard import girvi_dashboard",
            loans_section,
        )
        self.assertIn("return girvi_dashboard(request)", loans_section)
        self.assertNotIn('return redirect("girvi:girvi_dashboard")', loans_section)

    def test_phase133_accounting_slug_entry_direct_renders_existing_dea_home(self):
        org_views = _read("apps/orgs/views.py")
        plan = _read("docs/ui/tenant_route_canonicalization_phase13_plan.md")

        accounting_section = org_views.split("def workspace_slug_accounting", 1)[1].split(
            "def workspace_slug_operations", 1
        )[0]

        self.assertIn("Phase 13.3", plan)
        self.assertIn("/w/<workspace_slug>/accounting/", plan)
        self.assertIn("DEA home view", plan)
        self.assertIn(
            "from apps.tenant_apps.dea.views.common import home as dea_home",
            accounting_section,
        )
        self.assertIn("return dea_home(request)", accounting_section)
        self.assertNotIn('return redirect("dea_home")', accounting_section)

    def test_phase134_deep_link_plan_exists_before_nested_remounts(self):
        plan = _read("docs/ui/tenant_deep_link_canonicalization_phase13_4_plan.md")
        shared_urlpatterns = _read("django_project/shared_urlpatterns.py")

        for expected in (
            "Tenant Deep-Link Canonicalization Phase 13.4 Plan",
            "planning and guard phase",
            "Do not include full app URLConfs under `/w/<workspace_slug>/...` yet",
            "Do not remove legacy tenant roots",
            "Party",
            "Product And Inventory",
            "Rates",
            "Notify And Notify V2",
            "Data Tools",
            "Girvi",
            "DEA",
            "Phase 13.5a",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, plan)

        self.assertIn("Recommended first deep-link module", plan)
        self.assertIn("/w/<workspace_slug>/parties/<pk>/", plan)
        self.assertIn("Customer portal `/portal/...` remains out of scope", plan)

        forbidden_remounts = (
            'include("apps.tenant_apps.party.urls")',
            'include("apps.tenant_apps.product.urls")',
            'include("apps.tenant_apps.girvi.urls")',
            'include("apps.tenant_apps.dea.urls")',
        )
        slug_urlpatterns = shared_urlpatterns.split(
            "CANONICAL_WORKSPACE_SLUG_URLPATTERNS", 1
        )[1]
        for forbidden in forbidden_remounts:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, slug_urlpatterns)
