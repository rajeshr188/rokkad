from pathlib import Path

from django.test import SimpleTestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

from django_project import tenant_urls, urls
from django_project.shared_urlpatterns import CANONICAL_WORKSPACE_SLUG_URLPATTERNS


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class WorkspaceSlugRouteMapIntentTests(SimpleTestCase):
    def test_phase101_plan_exists_and_keeps_runtime_baseline_explicit(self):
        plan_path = DOCS_UI_ROOT / "workspace_slug_route_map_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Workspace Slug Route Map Plan",
            "Phase 10.1: Plan And Guard Baseline",
            "Status: complete",
            "Do not add slug routes",
            "Company` has `schema_name`, but no explicit user-facing slug field",
            "Membership check order",
            "Phase 10.2: Slug Source Decision",
            "Use `Company.schema_name` as the initial compatibility slug",
            "Skip Contact because Party is the canonical replacement",
        ):
            self.assertIn(expected, content)

    def test_phase101_unsafe_workspace_slug_routes_remain_intentionally_absent(self):
        absent_route_names = (
            "workspace_slug_contact",
        )

        for route_name in absent_route_names:
            with self.subTest(route_name=route_name):
                with self.assertRaises(NoReverseMatch):
                    reverse(route_name, kwargs={"workspace_slug": "acme"})

        absent_paths = (
            "/w/acme/contact/",
        )

        for path in absent_paths:
            with self.subTest(path=path, urlconf="public"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)
            with self.subTest(path=path, urlconf="tenant"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=tenant_urls)

    def test_phase101_current_workspace_identity_sources_are_documented(self):
        plan = _read("docs/ui/workspace_slug_route_map_plan.md")
        middleware = _read("apps/orgs/middleware_v2.py")
        models = _read("apps/orgs/models.py")

        self.assertIn("Domain mapping through `django-tenants` `Domain`", plan)
        self.assertIn("/workspace/<id>/settings/...", plan)
        self.assertIn("User profile fallback", plan)
        self.assertIn("WORKSPACE_ID_PATTERNS", middleware)
        self.assertIn("WORKSPACE_SLUG_PATTERNS", middleware)
        self.assertIn("def _extract_workspace_slug_from_path", middleware)
        self.assertIn("schema_name=workspace_slug", middleware)
        self.assertIn("schema_name", models)
        self.assertNotIn("slug = models.SlugField", models)

    def test_phase102_slug_source_decision_uses_schema_name_without_migration(self):
        plan = _read("docs/ui/workspace_slug_route_map_plan.md")
        models = _read("apps/orgs/models.py")

        for expected in (
            "Status: complete",
            "Use `Company.schema_name` as the initial compatibility slug",
            "no migration is needed",
            "Do not expose schema names as editable marketing slugs",
            "Adding `Company.slug` immediately",
        ):
            self.assertIn(expected, plan)

        self.assertIn("class Company(TenantMixin):", models)
        self.assertIn("schema_name", plan)
        self.assertNotIn("slug = models.SlugField", models)

    def test_phase101_slug_rollout_is_reflected_in_project_docs(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")

        for content in (status, memory, audit):
            with self.subTest():
                self.assertIn("Phase 10.1", content)
                self.assertIn("workspace_slug_route_map_plan.md", content)
                self.assertIn("Phase 10.2", content)
                self.assertIn("Company.schema_name", content)

    def test_phase103_middleware_slug_extraction_is_documented(self):
        plan = _read("docs/ui/workspace_slug_route_map_plan.md")

        for expected in (
            "Phase 10.3: Middleware Slug Extraction",
            "Status: complete",
            "WORKSPACE_SLUG_PATTERNS",
            "_extract_workspace_slug_from_path()",
            "resolves slug paths by `Company.schema_name`",
            "No URL patterns have been added yet",
            "Phase 10.4: Add Minimal Slug Aliases",
        ):
            self.assertIn(expected, plan)

    def test_phase104_minimal_slug_aliases_are_live(self):
        route_cases = {
            "workspace_slug_dashboard": ({"workspace_slug": "acme"}, "/w/acme/"),
            "workspace_slug_settings": ({"workspace_slug": "acme"}, "/w/acme/settings/"),
            "workspace_slug_settings_preferences": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/preferences/",
            ),
            "workspace_slug_settings_team": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/team/",
            ),
            "workspace_slug_settings_invitations": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/invitations/",
            ),
            "workspace_slug_settings_profile": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/profile/",
            ),
            "workspace_slug_settings_billing": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/billing/",
            ),
            "workspace_slug_settings_roles": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/roles/",
            ),
            "workspace_slug_settings_numbering": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/numbering/",
            ),
            "workspace_slug_settings_modules": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/modules/",
            ),
            "workspace_slug_settings_security": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/security/",
            ),
            "workspace_slug_settings_accounting": (
                {"workspace_slug": "acme"},
                "/w/acme/settings/accounting/",
            ),
            "workspace_slug_operations": (
                {"workspace_slug": "acme"},
                "/w/acme/operations/",
            ),
            "workspace_slug_parties": ({"workspace_slug": "acme"}, "/w/acme/parties/"),
            "workspace_slug_party_create": (
                {"workspace_slug": "acme"},
                "/w/acme/parties/new/",
            ),
            "workspace_slug_party_detail": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/parties/7/",
            ),
            "workspace_slug_party_update": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/parties/7/edit/",
            ),
            "workspace_slug_party_merge": (
                {"workspace_slug": "acme", "pk": 7},
                "/w/acme/parties/7/merge/",
            ),
            "workspace_slug_sales": ({"workspace_slug": "acme"}, "/w/acme/sales/"),
            "workspace_slug_purchase": ({"workspace_slug": "acme"}, "/w/acme/purchase/"),
            "workspace_slug_loans": ({"workspace_slug": "acme"}, "/w/acme/loans/"),
            "workspace_slug_inventory": ({"workspace_slug": "acme"}, "/w/acme/inventory/"),
            "workspace_slug_accounting": ({"workspace_slug": "acme"}, "/w/acme/accounting/"),
            "workspace_slug_commodity": ({"workspace_slug": "acme"}, "/w/acme/commodity/"),
            "workspace_slug_reports": ({"workspace_slug": "acme"}, "/w/acme/reports/"),
        }

        self.assertEqual(
            len(CANONICAL_WORKSPACE_SLUG_URLPATTERNS),
            len(route_cases),
        )

        for route_name, (kwargs, expected_path) in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, kwargs=kwargs), expected_path)
                self.assertEqual(resolve(expected_path).url_name, route_name)

    def test_phase11_target_tenant_route_map_is_complete_except_portal(self):
        ia_audit = _read("docs/ui/saas_information_architecture_audit.md")
        phase11_review = _read("docs/ui/workspace_slug_phase11_review.md")
        route_map_source = _read("django_project/shared_urlpatterns.py")

        expected_target_routes = (
            "/w/<workspace_slug>/",
            "/w/<workspace_slug>/operations/",
            "/w/<workspace_slug>/parties/",
            "/w/<workspace_slug>/sales/",
            "/w/<workspace_slug>/purchase/",
            "/w/<workspace_slug>/loans/",
            "/w/<workspace_slug>/inventory/",
            "/w/<workspace_slug>/commodity/",
            "/w/<workspace_slug>/accounting/",
            "/w/<workspace_slug>/reports/",
            "/w/<workspace_slug>/settings/",
            "/w/<workspace_slug>/settings/profile/",
            "/w/<workspace_slug>/settings/team/",
            "/w/<workspace_slug>/settings/invitations/",
            "/w/<workspace_slug>/settings/roles/",
            "/w/<workspace_slug>/settings/billing/",
            "/w/<workspace_slug>/settings/modules/",
            "/w/<workspace_slug>/settings/numbering/",
            "/w/<workspace_slug>/settings/accounting/",
            "/w/<workspace_slug>/settings/security/",
        )
        expected_route_names = (
            "workspace_slug_dashboard",
            "workspace_slug_operations",
            "workspace_slug_parties",
            "workspace_slug_sales",
            "workspace_slug_purchase",
            "workspace_slug_loans",
            "workspace_slug_inventory",
            "workspace_slug_commodity",
            "workspace_slug_accounting",
            "workspace_slug_reports",
            "workspace_slug_settings",
            "workspace_slug_settings_profile",
            "workspace_slug_settings_team",
            "workspace_slug_settings_invitations",
            "workspace_slug_settings_roles",
            "workspace_slug_settings_billing",
            "workspace_slug_settings_modules",
            "workspace_slug_settings_numbering",
            "workspace_slug_settings_accounting",
            "workspace_slug_settings_security",
        )

        for route in expected_target_routes:
            with self.subTest(route=route):
                self.assertIn(route, ia_audit)
                self.assertIn(route, phase11_review)

        for route_name in expected_route_names:
            with self.subTest(route_name=route_name):
                self.assertIn(route_name, route_map_source)

        self.assertIn("customer/member portal", phase11_review)
        self.assertIn("/portal/loans/", phase11_review)

    def test_phase105_tenant_erp_section_aliases_are_live_without_contact(self):
        route_cases = {
            "workspace_slug_parties": "/w/acme/parties/",
            "workspace_slug_loans": "/w/acme/loans/",
            "workspace_slug_inventory": "/w/acme/inventory/",
            "workspace_slug_accounting": "/w/acme/accounting/",
        }

        for route_name, expected_path in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(
                    reverse(route_name, kwargs={"workspace_slug": "acme"}),
                    expected_path,
                )
                self.assertEqual(resolve(expected_path).url_name, route_name)

        with self.assertRaises(NoReverseMatch):
            reverse("workspace_slug_contact", kwargs={"workspace_slug": "acme"})

        for urlconf in (urls, tenant_urls):
            with self.subTest(urlconf=urlconf):
                with self.assertRaises(Resolver404):
                    resolve("/w/acme/contact/", urlconf=urlconf)

    def test_phase112_safe_deferred_slug_aliases_are_live(self):
        route_cases = {
            "workspace_slug_operations": "/w/acme/operations/",
            "workspace_slug_sales": "/w/acme/sales/",
            "workspace_slug_purchase": "/w/acme/purchase/",
            "workspace_slug_commodity": "/w/acme/commodity/",
            "workspace_slug_reports": "/w/acme/reports/",
            "workspace_slug_settings_profile": "/w/acme/settings/profile/",
            "workspace_slug_settings_billing": "/w/acme/settings/billing/",
            "workspace_slug_settings_accounting": "/w/acme/settings/accounting/",
        }

        for route_name, expected_path in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(
                    reverse(route_name, kwargs={"workspace_slug": "acme"}),
                    expected_path,
                )
                self.assertEqual(resolve(expected_path).url_name, route_name)

    def test_phase113_interim_settings_aliases_are_live(self):
        route_cases = {
            "workspace_slug_settings_roles": "/w/acme/settings/roles/",
            "workspace_slug_settings_numbering": "/w/acme/settings/numbering/",
        }

        for route_name, expected_path in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(
                    reverse(route_name, kwargs={"workspace_slug": "acme"}),
                    expected_path,
                )
                self.assertEqual(resolve(expected_path).url_name, route_name)

    def test_phase114_new_screen_settings_aliases_are_live(self):
        route_cases = {
            "workspace_slug_settings_modules": "/w/acme/settings/modules/",
            "workspace_slug_settings_security": "/w/acme/settings/security/",
        }

        for route_name, expected_path in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(
                    reverse(route_name, kwargs={"workspace_slug": "acme"}),
                    expected_path,
                )
                self.assertEqual(resolve(expected_path).url_name, route_name)

    def test_phase107_review_closes_workspace_slug_route_map_phase(self):
        review_path = DOCS_UI_ROOT / "workspace_slug_route_map_review.md"

        self.assertTrue(review_path.exists())
        content = review_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Workspace Slug Route Map Review",
            "Chose `Company.schema_name` as the initial compatibility slug",
            "Added middleware slug extraction",
            "/w/<workspace_slug>/settings/preferences/",
            "/w/<workspace_slug>/parties/",
            "Contact is intentionally not exposed",
            "65 tests passed",
            "Commit Boundary",
        ):
            self.assertIn(expected, content)
