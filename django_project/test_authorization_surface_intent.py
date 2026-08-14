from pathlib import Path

from django.test import SimpleTestCase

from apps.orgs.middleware_v2 import SecureWorkspaceMiddleware
from django_project import tenant_urls, urls
from django_project.shared_urlpatterns import (
    CANONICAL_CONTROL_PLANE_URLPATTERNS,
    GLOBAL_AUTHENTICATED_URLPATTERNS,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _route_prefixes(patterns):
    return {str(pattern.pattern) for pattern in patterns}


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class AuthorizationSurfaceIntentTests(SimpleTestCase):
    def test_phase5_authorization_inventory_exists(self):
        inventory = DOCS_UI_ROOT / "authorization_cleanup_inventory.md"
        closeout = DOCS_UI_ROOT / "phase5_authorization_closeout_review.md"

        self.assertTrue(inventory.exists())
        self.assertTrue(closeout.exists())
        content = inventory.read_text(encoding="utf-8-sig")
        for expected in (
            "Public / Platform",
            "Global Authenticated",
            "Workspace Settings / Admin",
            "Tenant / Workspace ERP",
            "Customer / Member Portal",
            "Recommended Cleanup Order",
        ):
            self.assertIn(expected, content)

        closeout_content = closeout.read_text(encoding="utf-8-sig")
        self.assertIn("Phase 5 Authorization Closeout Review", closeout_content)
        self.assertIn("Commit the Phase 5 set, then begin Phase 6 onboarding", closeout_content)

    def test_public_urlconf_excludes_tenant_erp_prefixes(self):
        public_prefixes = _route_prefixes(urls.urlpatterns)
        tenant_only_prefixes = _route_prefixes(tenant_urls.TENANT_ERP_URLPATTERNS)

        self.assertTrue(tenant_only_prefixes.isdisjoint(public_prefixes))

    def test_tenant_erp_prefixes_are_workspace_required_by_middleware(self):
        tenant_prefixes = {
            prefix.rstrip("/")
            for prefix in _route_prefixes(tenant_urls.TENANT_ERP_URLPATTERNS)
        }
        tenant_prefixes.remove("portal")
        workspace_required = {
            prefix.strip("/")
            for prefix in SecureWorkspaceMiddleware.WORKSPACE_REQUIRED_URLS
        }

        self.assertTrue(tenant_prefixes.issubset(workspace_required))

    def test_canonical_control_plane_aliases_are_not_tenant_erp_prefixes(self):
        tenant_prefixes = _route_prefixes(tenant_urls.TENANT_ERP_URLPATTERNS)
        canonical_prefixes = _route_prefixes(CANONICAL_CONTROL_PLANE_URLPATTERNS)

        self.assertTrue(tenant_prefixes.isdisjoint(canonical_prefixes))
        self.assertEqual(
            GLOBAL_AUTHENTICATED_URLPATTERNS[: len(CANONICAL_CONTROL_PLANE_URLPATTERNS)],
            CANONICAL_CONTROL_PLANE_URLPATTERNS,
        )

    def test_secure_workspace_middleware_keeps_membership_before_tenant_context_contract(self):
        middleware_content = _read("apps/orgs/middleware_v2.py")

        self.assertIn("def _validate_workspace_access", middleware_content)
        self.assertIn("Membership.objects.select_related(\"role\").get", middleware_content)
        self.assertIn("self._set_tenant_context(request, workspace)", middleware_content)
        validation_index = middleware_content.index(
            "validation = self._validate_workspace_access"
        )
        tenant_context_index = middleware_content.index(
            "self._set_tenant_context(request, workspace)",
            validation_index,
        )
        self.assertLess(validation_index, tenant_context_index)

    def test_secure_workspace_middleware_extracts_legacy_and_canonical_workspace_ids(self):
        middleware = SecureWorkspaceMiddleware(get_response=lambda request: None)

        path_cases = {
            "/orgs/workspace/42/": 42,
            "/orgs/workspace/42/detail/": 42,
            "/orgs/company/43/preferences/": 43,
            "/workspace/44/settings/": 44,
            "/workspace/44/settings/team/": 44,
            "/workspace/44/settings/invitations/new/": 44,
        }

        for path, expected_workspace_id in path_cases.items():
            with self.subTest(path=path):
                self.assertEqual(
                    middleware._extract_workspace_id_from_path(path),
                    expected_workspace_id,
                )

        for public_path in ("/app/workspaces/", "/accounts/login/", "/workspace/44/"):
            with self.subTest(path=public_path):
                self.assertIsNone(middleware._extract_workspace_id_from_path(public_path))

    def test_secure_workspace_middleware_extracts_future_workspace_slugs(self):
        middleware = SecureWorkspaceMiddleware(get_response=lambda request: None)

        path_cases = {
            "/w/acme/": "acme",
            "/w/acme_workspace/settings/": "acme_workspace",
            "/w/acme-legacy/parties/": "acme-legacy",
        }

        for path, expected_workspace_slug in path_cases.items():
            with self.subTest(path=path):
                self.assertEqual(
                    middleware._extract_workspace_slug_from_path(path),
                    expected_workspace_slug,
                )

        for public_path in ("/app/workspaces/", "/workspace/44/settings/", "/party/"):
            with self.subTest(path=public_path):
                self.assertIsNone(
                    middleware._extract_workspace_slug_from_path(public_path)
                )

    def test_workspace_resolution_helper_does_not_use_profile_fallback_by_default(self):
        tenant_context = _read("apps/orgs/tenant_context.py")

        self.assertIn("allow_profile_fallback=False", tenant_context)
        self.assertIn("if not allow_profile_fallback:", tenant_context)
        self.assertIn("return None", tenant_context)

    def test_girvi_and_dea_shared_access_helpers_remain_available(self):
        girvi_access = _read("apps/tenant_apps/girvi/views/access.py")
        dea_access = _read("apps/tenant_apps/dea/views/access.py")
        party_access = _read("apps/tenant_apps/party/access.py")
        product_access = _read("apps/tenant_apps/product/access.py")
        rate_access = _read("apps/tenant_apps/rates/access.py")
        notify_access = _read("apps/tenant_apps/notify/access.py")

        for expected in (
            "def assert_girvi_workspace_access",
            "def girvi_workspace_required",
            "def assert_girvi_workspace_permission",
            "def girvi_permission_required",
            "class GirviPermissionRequiredMixin",
        ):
            self.assertIn(expected, girvi_access)

        for expected in (
            "def assert_dea_accountant_access",
            "def dea_accountant_required",
            "class DeaAccountantRequiredMixin",
            "ACCOUNTANT_ROLES",
        ):
            self.assertIn(expected, dea_access)

        for expected in (
            "def assert_party_workspace_access",
            "def assert_party_permission",
            "def assert_party_action_permission",
            "def party_action_required",
            "class PartyPermissionRequiredMixin",
        ):
            self.assertIn(expected, party_access)

        for expected in (
            "def assert_product_workspace_access",
            "def assert_product_permission",
            "def assert_product_action_permission",
            "def product_action_required",
            "class ProductPermissionRequiredMixin",
            "class ProductActionRequiredMixin",
        ):
            self.assertIn(expected, product_access)

        for expected in (
            "def assert_rate_workspace_access",
            "def assert_rate_permission",
            "def assert_rate_action_permission",
            "def rate_action_required",
            "class RateActionRequiredMixin",
        ):
            self.assertIn(expected, rate_access)

        for expected in (
            "def assert_notify_workspace_access",
            "def assert_notify_permission",
            "def assert_notify_action_permission",
            "def notify_action_required",
            "class NotifyActionRequiredMixin",
        ):
            self.assertIn(expected, notify_access)

    def test_known_tenant_authorization_gaps_are_documented_before_behavior_changes(self):
        inventory = (DOCS_UI_ROOT / "authorization_cleanup_inventory.md").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("Party list/detail read paths use the Party view action guard", inventory)
        self.assertIn(
            "Party role add/end and duplicate merge mutation paths use the Party edit action guard",
            inventory,
        )
        self.assertIn("Phase 5 tenant authorization cleanup is complete for current Product, Rates, Notify, and utility data-tool route groups", inventory)
        self.assertIn("Contact remains a legacy compatibility surface", inventory)
        self.assertIn("Middleware workspace-required prefixes cover current tenant ERP prefixes", inventory)
        self.assertIn("every current tenant ERP prefix", inventory)
        self.assertIn("canonical `/workspace/<id>/settings/...`", inventory)

    def test_login_only_tenant_app_gaps_remain_visible_for_phase5_cleanup(self):
        party_views = _read("apps/tenant_apps/party/views.py")
        contact_customer_views = _read("apps/tenant_apps/contact/views/customer.py")
        product_views = _read("apps/tenant_apps/product/views/product.py")
        producttype_views = _read("apps/tenant_apps/product/views/producttype.py")
        productvariant_views = _read("apps/tenant_apps/product/views/productvariant.py")
        product_stock_views = _read("apps/tenant_apps/product/views/stock.py")
        product_price_views = _read("apps/tenant_apps/product/views/price.py")
        product_image_views = _read("apps/tenant_apps/product/views/image.py")
        rate_views = _read("apps/tenant_apps/rates/views.py")
        notify_views = _read("apps/tenant_apps/notify/views.py")
        notify_v2_views = _read("apps/tenant_apps/notify_v2/views.py")

        self.assertNotIn("@login_required", party_views)
        self.assertIn("party_action_required", party_views)
        self.assertNotIn("@login_required", product_views)
        self.assertIn("product_action_required", product_views)
        self.assertIn("ProductActionRequiredMixin", product_views)
        self.assertNotIn("@login_required", producttype_views)
        self.assertIn("product_action_required", producttype_views)
        self.assertNotIn("@login_required", productvariant_views)
        self.assertIn("product_action_required", productvariant_views)
        self.assertIn("ProductActionRequiredMixin", productvariant_views)
        self.assertNotIn("@login_required", product_stock_views)
        self.assertIn("product_action_required", product_stock_views)
        self.assertIn("ProductActionRequiredMixin", product_stock_views)
        self.assertIn("def stock_select(request, q=None)", product_stock_views)
        self.assertNotIn("@login_required", product_price_views)
        self.assertIn("product_action_required", product_price_views)
        self.assertNotIn("LoginRequiredMixin", product_image_views)
        self.assertIn("ProductActionRequiredMixin", product_image_views)
        self.assertIn("rate_action_required", rate_views)
        self.assertIn("notify_action_required", notify_views)
        self.assertIn("notify_action_required", notify_v2_views)
        self.assertIn("def whatsapp_cloud_webhook", notify_v2_views)

        self.assertIn("@login_required", contact_customer_views)

        self.assertNotIn("girvi_permission_required", party_views)
        self.assertNotIn("dea_accountant_required", party_views)

    def test_phase87_current_tenant_utility_surfaces_keep_action_guards(self):
        guard_cases = {
            "party": {
                "content": _read("apps/tenant_apps/party/views.py"),
                "guard": "@party_action_required(",
                "minimum": 18,
            },
            "product_catalog": {
                "content": _read("apps/tenant_apps/product/views/product.py")
                + _read("apps/tenant_apps/product/views/producttype.py")
                + _read("apps/tenant_apps/product/views/productvariant.py"),
                "guard": "@product_action_required(",
                "minimum": 12,
            },
            "product_stock_price": {
                "content": _read("apps/tenant_apps/product/views/stock.py")
                + _read("apps/tenant_apps/product/views/price.py"),
                "guard": "@product_action_required(",
                "minimum": 20,
            },
            "product_image_attribute": {
                "content": _read("apps/tenant_apps/product/views/image.py"),
                "guard": "ProductActionRequiredMixin",
                "minimum": 12,
            },
            "rates": {
                "content": _read("apps/tenant_apps/rates/views.py"),
                "guard": "@rate_action_required(",
                "minimum": 10,
            },
            "notify_legacy": {
                "content": _read("apps/tenant_apps/notify/views.py"),
                "guard": "@notify_action_required(",
                "minimum": 9,
            },
            "notify_v2": {
                "content": _read("apps/tenant_apps/notify_v2/views.py"),
                "guard": "@notify_action_required(",
                "minimum": 8,
            },
            "utility_data_tools": {
                "content": _read("apps/tenant_apps/utils/importing/views.py"),
                "guard": "@owner_or_admin_required",
                "minimum": 5,
            },
        }

        for surface, case in guard_cases.items():
            with self.subTest(surface=surface):
                self.assertGreaterEqual(
                    case["content"].count(case["guard"]),
                    case["minimum"],
                )

    def test_phase87_tenant_prefix_and_middleware_authorization_sets_match(self):
        tenant_prefixes = {
            prefix.strip("/")
            for prefix in _route_prefixes(tenant_urls.TENANT_ERP_URLPATTERNS)
        }
        self.assertIn("portal", tenant_prefixes)
        tenant_prefixes.remove("portal")
        workspace_required = {
            prefix.strip("/")
            for prefix in SecureWorkspaceMiddleware.WORKSPACE_REQUIRED_URLS
        }

        self.assertEqual(
            tenant_prefixes,
            {
                "party",
                "contact",
                "data-tools",
                "girvi",
                "loans",
                "rates",
                "product",
                "notify",
                "notify-v2",
                "dea",
            },
        )
        self.assertTrue(tenant_prefixes.issubset(workspace_required))

    def test_phase87_deferred_authorization_boundaries_remain_documented(self):
        inventory = _read("docs/ui/authorization_cleanup_inventory.md")
        closeout = _read("docs/ui/phase5_authorization_closeout_review.md")
        phase8_plan = _read("docs/ui/phase8_regression_consolidation_plan.md")

        for content in (inventory, closeout, phase8_plan):
            with self.subTest():
                self.assertIn("Contact", content)
                self.assertIn("DEA", content)
                self.assertIn("Girvi", content)

        self.assertIn(
            "Contact remains a legacy compatibility surface while Party replaces it",
            inventory,
        )
        self.assertIn(
            "DEA and Girvi still have broader domain-specific permission-hardening tracks",
            inventory,
        )
        self.assertIn(
            "Notify v2 WhatsApp Cloud webhook remains intentionally unauthenticated",
            inventory,
        )
        self.assertIn(
            "not fully closed by this SaaS UI phase",
            closeout,
        )
        self.assertIn(
            "Contact compatibility gap remaining documented until Party cutover",
            phase8_plan,
        )
        self.assertIn(
            "DEA and Girvi remaining separate domain-specific permission tracks",
            phase8_plan,
        )
